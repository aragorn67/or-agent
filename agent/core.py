# agent/core.py
"""
Main Optimization Agent - Entry Point for All Requests

DATA FLOW:
    Text Input → detect_intent() → classify_problem() → extract_parameters() → solve() → explain() → Output

EXECUTION PATH:
    1. detect_intent(): Is this smalltalk, help, follow-up, or new optimization problem?
    2. classify_problem(): What type? (transportation, scheduling, etc.)
    3. extract_parameters(): Pull out numbers, names, constraints from text
    4. solve(): Run mathematical optimization (calls solvers/)
    5. explain(): Generate human-readable explanation
    6. Return: solution + explanation + optional charts

KEY FUNCTIONS TO READ:
    - solve_natural_language(): Main entry point (line ~26)
    - _handle_follow_up(): Handles analysis/modification requests (line ~200)
    - _map_to_solver(): Routes problem types to solvers (line ~370)
"""
from typing import Dict, Any, List, Optional
from llm.client import LLMClient
from llm.intent_router import IntentRouter
from llm.follow_up_handler import FollowUpHandler
from solvers import get_default_solver_for_category, get_solver, list_problem_types
from analysis.detector import AnalysisDetector
from analysis.engine import AnalysisEngine
from analysis import detect_analysis_type, execute_analysis, format_analysis_output
from .heuristic_handler import (
    heuristic_mode_supported,
    is_scheduling,
    run_heuristic_for_scheduling,
    run_heuristic_for_transport,
)
from .job_store import default_store as default_job_store, JobStore

class OptimizationAgent:
    """
    Main agent orchestrating problem solving with intelligent intent routing.

    This is the brain of the system. It decides what to do with user input and
    coordinates all the other components (LLM, solvers, analysis engines).
    """

    def __init__(self, llm_client: LLMClient, job_store: Optional[JobStore] = None):
        self.llm = llm_client
        self.intent_router = IntentRouter(llm_client)
        self.follow_up_handler = FollowUpHandler(llm_client)
        self.analysis_detector = AnalysisDetector(llm_client)
        self.analysis_engine = AnalysisEngine()
        self.job_store = job_store if job_store is not None else default_job_store

        # Conversation state
        self.conversation_context = {
            "last_solution": None,
            "messages": [],
            "analysis_history": []
        }

    def solve_natural_language(
        self,
        description: str,
        progress_callback=None,
        conversation_context: Optional[Dict] = None,
        mode: str = "exact",
    ) -> Dict[str, Any]:
        """
        Main entry point for natural language problem solving with intent routing.

        This is the refactored version that:
        1. Routes smalltalk/help to quick handlers
        2. Detects follow-ups and handles deterministically when possible
        3. Only processes optimization problems through the full pipeline
        """

        def update_progress(step: str, progress: int):
            if progress_callback:
                progress_callback(step, progress)

        # Use provided context or instance context
        if conversation_context is None:
            conversation_context = self.conversation_context

        # Add message to context
        conversation_context.setdefault("messages", []).append({
            "role": "user",
            "content": description
        })

        try:
            # STAGE 1: Intent Detection (NEW - fixes Issue #1)
            update_progress("Detecting intent...", 5)
            intent_result = self.intent_router.detect_intent(description, conversation_context)
            intent_type = intent_result.get("intent", "optimization")

            # Handle smalltalk
            if intent_type == "smalltalk":
                response = self.intent_router.handle_smalltalk(description)
                return {
                    "success": True,
                    "type": "smalltalk",
                    "response": response["response"]
                }

            # Handle help requests
            if intent_type == "help":
                response = self.intent_router.handle_help_request(description)
                return {
                    "success": True,
                    "type": "help",
                    "response": response["response"]
                }

            # Handle follow-ups (NEW - fixes Issue #3)
            if intent_type == "follow_up":
                update_progress("Handling follow-up question...", 10)
                return self._handle_follow_up(description, conversation_context, update_progress)

            # Otherwise, process as optimization problem
            update_progress("Analyzing problem type...", 15)

            # Step 1: Classify problem type
            available_types = list_problem_types()
            classification = self.llm.classify_problem(description, available_types)
            problem_type = classification.get('type', 'TRANSPORTATION')
            solver_id = classification.get('solver_id', 'none')  # NEW: get specific solver
            confidence = classification.get('confidence', 0.5)

            update_progress(f"Identified as {problem_type} problem", 25)

            # Check if problem type is unknown or confidence too low
            if problem_type == "UNKNOWN" or confidence < 0.3:
                return {
                    "success": False,
                    "error": "Could not understand the problem description. Please provide a clear optimization problem with specific details about sources, destinations, capacities, demands, costs, etc.",
                    "suggestion": "Try describing a problem like: 'I need to ship goods from 2 factories to 3 customers with these capacities and demands...'",
                    "problem_type": problem_type,
                    "confidence": confidence
                }

            # Check if we have a solver for this problem
            if solver_id == "none":
                return {
                    "success": False,
                    "error": f"Problem type '{problem_type}' is recognized but not yet supported by our solvers.",
                    "suggestion": "Currently supported: bipartite transportation (plants→markets), single-stage scheduling.",
                    "problem_type": problem_type,
                    "confidence": confidence
                }

            # Step 2: Get solver by solver_id (NEW ARCHITECTURE)
            solver = get_solver(solver_id)

            update_progress("Extracting parameters from description...", 40)

            # Step 3: Extract parameters using LLM
            example_params = solver.get_example_params()
            params = self.llm.extract_parameters(description, problem_type, example_params)

            # Check if LLM extraction failed
            if "error" in params:
                return {
                    "success": False,
                    "status": "infeasible",  # Extraction failure = structural infeasibility
                    "error": "Parameter extraction failed",
                    "details": [params["error"]],
                    "problem_type": problem_type,
                    "confidence": confidence,
                    "extracted_params": params,  # Include partial params (may only contain 'error')
                    "suggestion": "Please provide complete information including all factory names, capacities, customer names, demands, and distances between all factories and customers."
                }

            update_progress("Validating parameters...", 55)

            # Step 4: Validate parameters
            validation_errors = solver.validate_params(params)
            if validation_errors:
                return {
                    "success": False,
                    "error": "Parameter validation failed",
                    "details": validation_errors,
                    "problem_type": problem_type,
                    "confidence": confidence
                }

            update_progress("Checking feasibility...", 60)

            # Step 4.5: Check feasibility (NEW - 3-layer validation)
            from feasibility.core import check_feasibility, FeasStatus
            from feasibility.schemas import ParsedInstance

            # Convert params to instance format for feasibility checking
            instance = ParsedInstance(
                problem_type=problem_type,
                solver_id=solver_id,
                sets=self._extract_sets_from_params(params),
                params=self._convert_params_for_feasibility(params)
            )

            feas_report = check_feasibility(instance)

            if feas_report.status == FeasStatus.INFEASIBLE:
                # Store infeasibility info in conversation context
                conversation_context["last_infeasibility"] = {
                    "params": params,
                    "original_params": params.copy(),  # Store original
                    "report": feas_report,
                    "retry_count": 0,
                    "problem_type": problem_type,
                    "solver_id": solver_id,
                    "description": description
                }

                # Return infeasibility to user with suggestions
                return {
                    "success": False,
                    "status": "infeasible",
                    "layer_failed": feas_report.layer_passed,
                    "reasons": feas_report.reasons,
                    "suggestions": feas_report.suggestions or [],
                    "problem_type": problem_type,
                    "extracted_params": params,  # Include params so modifications can be applied
                    "retry_count": 0,
                    "max_retries": 3,
                    "message": "The problem is infeasible. Please provide modifications to fix it, or provide a complete new problem description."
                }

            # Step 4.6: Mode routing — heuristic modes short-circuit the exact
            # solve and persist the job so /continue can warm-start later.
            if mode in ("heuristic", "heuristic_then_ask"):
                if heuristic_mode_supported(problem_type):
                    update_progress("Running heuristic...", 70)
                    handler = (
                        run_heuristic_for_scheduling
                        if is_scheduling(problem_type)
                        else run_heuristic_for_transport
                    )
                    return handler(
                        params=params,
                        description=description,
                        problem_type=problem_type,
                        solver_id=solver_id,
                        classification=classification,
                        job_store=self.job_store,
                        ask_to_continue=(mode == "heuristic_then_ask"),
                    )
                # Heuristic unsupported for this domain — fall through to exact.

            update_progress("Solving optimization problem...", 70)

            # Step 5: Solve the problem
            solution = solver.solve(params)

            update_progress("Generating explanation...", 85)

            # Step 6: Generate explanation with original description for unit context
            # New: explain_solution returns a dict with summary, explanation, units_info
            explanation_result = self.llm.explain_solution(solution, problem_type, description)
            explanation = explanation_result.get('explanation', '')
            summary = explanation_result.get('summary', '')

            update_progress("Checking for analysis requests...", 90)

            # Step 7: Check if user wants additional analysis/plots
            analysis_requests = self.analysis_detector.detect_analysis_requests(description)

            analysis_results = []
            if analysis_requests.get("wants_analysis", False):
                update_progress("Performing additional analysis...", 95)
                analysis_results = self._perform_requested_analyses(analysis_requests, params)

            update_progress("Complete!", 100)

            result = {
                "success": True,
                "problem_type": problem_type,
                "confidence": confidence,
                "extracted_params": params,
                "solution": solution,
                "explanation": explanation,
                "summary": summary,
                "units_info": explanation_result.get('units_info', {}),
                "grounding_check": explanation_result.get('grounding_check', 'unknown')
            }

            # Add analysis results if any
            if analysis_results:
                result["analysis"] = analysis_results

            # Store in conversation context for follow-ups
            conversation_context["last_solution"] = result

            return result

        except Exception as e:
            error_msg = str(e)

            # Provide user-friendly explanations for common technical errors
            if "float() argument must be a string or a real number, not 'NoneType'" in error_msg:
                return {
                    "success": False,
                    "error": "🤔 I found some missing or invalid numbers in your problem description.",
                    "details": [
                        "Some capacities, demands, distances, or costs couldn't be understood",
                        "Please make sure all numbers are clearly specified",
                        "Example: 'Factory Seattle can produce 350 units' (not just 'Factory Seattle')"
                    ],
                    "suggestion": "Try rephrasing with complete information for all factories, customers, capacities, demands, distances, and shipping costs.",
                    "problem_type": "UNKNOWN",
                    "confidence": 0.0
                }
            elif "No module named" in error_msg:
                return {
                    "success": False,
                    "error": "⚙️ System configuration issue - missing required software component.",
                    "details": [error_msg],
                    "problem_type": "UNKNOWN",
                    "confidence": 0.0
                }
            elif "Solver" in error_msg and "not found" in error_msg:
                return {
                    "success": False,
                    "error": "⚙️ Optimization solver not available.",
                    "details": ["The mathematical solver (GLPK) might not be properly installed"],
                    "suggestion": "Please ensure GLPK is installed: sudo apt install glpk-utils",
                    "problem_type": "UNKNOWN",
                    "confidence": 0.0
                }
            else:
                return {
                    "success": False,
                    "error": f"🔧 Unexpected error: {error_msg}",
                    "details": ["This might be a system issue or an unusual problem format"],
                    "suggestion": "Please try rephrasing your problem or contact support if this persists.",
                    "problem_type": "UNKNOWN",
                    "confidence": 0.0
                }

    def continue_job(self, job_id: str, action: str) -> Dict[str, Any]:
        """
        Resume a job that was started in heuristic mode.

        Args:
            job_id: UUID returned by a prior heuristic-mode /solve call.
            action: one of "optimize" | "accept" | "use_heuristic".
                - optimize: run the exact solver, warm-started from the
                  stored heuristic flows. Returns the proven-optimal answer.
                - accept / use_heuristic: terminal acknowledgement; we return
                  the stored heuristic answer and drop the job.

        Returns:
            Dict shaped like the API solve responses. On unknown / expired
            job_id, returns {"success": False, "error": "..."}.
        """
        record = self.job_store.get(job_id)
        if record is None:
            return {
                "success": False,
                "error": f"Job {job_id} not found or expired (10-minute TTL).",
            }

        action = (action or "").lower()
        if action not in {"optimize", "accept", "use_heuristic"}:
            return {
                "success": False,
                "error": f"Unknown action '{action}'. Expected one of: "
                         "optimize, accept, use_heuristic.",
            }

        if action in ("accept", "use_heuristic"):
            self.job_store.drop(job_id)
            solution: Dict[str, Any] = {
                "status": "ACCEPTED_HEURISTIC",
                "objective_value": record.heuristic_cost,
                "objective": record.heuristic_cost,
                "best_bound": record.lp_bound,
                "gap": (
                    (record.heuristic_cost - record.lp_bound) / record.heuristic_cost
                    if record.lp_bound is not None and record.heuristic_cost > 0
                    else None
                ),
                "is_heuristic": True,
            }
            # Domain-specific payload: scheduling stores a dict, transport
            # stores (i,j) flows.
            if isinstance(record.heuristic_flows, dict) and "assignment" in record.heuristic_flows:
                w = record.heuristic_flows
                solution["assignments"] = [
                    {"order": o, "unit": u} for o, u in w["assignment"].items()
                ]
                solution["sequence"] = w["sequence"]
                solution["completion"] = w["completion"]
                solution["Cmax"] = w["cmax"]
            else:
                solution["flows"] = [
                    {"plant": str(i), "market": str(j), "value": float(v)}
                    for (i, j), v in record.heuristic_flows.items()
                ]
            return {
                "success": True,
                "type": "heuristic_accepted",
                "job_id": job_id,
                "problem_type": record.problem_type,
                "solution": solution,
                "message": f"Heuristic answer accepted: cost {record.heuristic_cost:.2f}.",
            }

        # action == "optimize": warm-started exact solve.
        solver = get_solver(record.solver_id)
        solution = solver.solve(record.params, warm_start=record.heuristic_flows)
        self.job_store.drop(job_id)

        explanation_result = self.llm.explain_solution(
            solution, record.problem_type, record.description
        )

        return {
            "success": True,
            "type": "exact_after_heuristic",
            "job_id": job_id,
            "problem_type": record.problem_type,
            "confidence": record.classification.get("confidence"),
            "extracted_params": record.params,
            "solution": solution,
            "heuristic_baseline": {
                "cost": record.heuristic_cost,
                "lp_bound": record.lp_bound,
            },
            "explanation": explanation_result.get("explanation", ""),
            "summary": explanation_result.get("summary", ""),
            "units_info": explanation_result.get("units_info", {}),
        }

    def follow_up_on_job(self, job_id: str, message: str) -> Dict[str, Any]:
        """
        Answer a free-text follow-up / what-if against a still-pending
        heuristic_then_ask job, WITHOUT consuming it.

        The chat UI funnels every message for a pending job to /chat/continue.
        When the message is not an optimize/accept/use_heuristic action it used
        to dead-end. Instead we synthesise a baseline solution from the job's
        parameters (an exact solve — fast for these sizes) and route the
        message through the normal follow-up path so "what if X changes"
        actually re-solves and answers. The job is left intact so the user can
        still 'optimize' or 'accept' afterwards.
        """
        record = self.job_store.get(job_id)
        if record is None:
            return {
                "success": False,
                "error": f"Job {job_id} not found or expired (10-minute TTL).",
            }

        solver = get_solver(record.solver_id)
        baseline = solver.solve(record.params)

        conversation_context: Dict[str, Any] = {
            "messages": [],
            "last_solution": {
                "success": True,
                "problem_type": record.problem_type,
                "solver_id": record.solver_id,
                "extracted_params": record.params,
                "solution": baseline,
            },
        }

        def _noop(_step: str, _progress: int) -> None:
            pass

        result = self._handle_follow_up(message, conversation_context, _noop)
        # Job is still pending: the user can keep deciding optimize/accept.
        result["job_id"] = job_id
        result["job_pending"] = True
        return result

    def _handle_follow_up(self, message: str, conversation_context: Dict, update_progress) -> Dict[str, Any]:
        """
        Handle follow-up questions about previous solutions.
        Uses deterministic responses when possible (NEW - fixes Issue #3).
        Also handles infeasibility fixes (NEW).
        """

        last_solution = conversation_context.get("last_solution")
        last_infeasibility = conversation_context.get("last_infeasibility")

        # Check if this is a response to an infeasibility report
        if last_infeasibility and not last_solution:
            return self._handle_infeasibility_fix(message, conversation_context, update_progress)

        if not last_solution:
            return {
                "success": False,
                "error": "No previous optimization solution found. Please solve a problem first.",
                "type": "follow_up_error"
            }

        # Detect follow-up type
        follow_up_result = self.follow_up_handler.detect_follow_up_intent(message, conversation_context)
        follow_up_type = follow_up_result.get("follow_up_type", "question")

        # Handle questions deterministically when possible
        if follow_up_type == "question":
            question_category = follow_up_result.get("question_category", "general")
            deterministic_answer = self.follow_up_handler.answer_deterministic_question(
                message, last_solution, question_category
            )

            if deterministic_answer:
                return {
                    "success": True,
                    "type": "follow_up_question",
                    "response": deterministic_answer,
                    "deterministic": True
                }

        # Keyword-only analysis-type detection here (no LLM) — this is just a
        # routing gate; the heavy LLM parse happens once inside the engine.
        # Reuse the detected type downstream so we don't classify twice.
        kw_analysis_type = detect_analysis_type(message)  # no llm_client

        # Modifications and analysis both route to the analysis engine, which
        # actually re-solves and returns a concrete answer. Previously the
        # "modification" branch dead-ended with a canned "please re-describe"
        # message — that was the #8 follow-up bug.
        if follow_up_type in ("modification", "analysis"):
            return self._handle_follow_up_analysis(
                message, conversation_context, update_progress,
                analysis_type=(kw_analysis_type if kw_analysis_type != "unknown" else None),
            )

        # The lightweight keyword classifier frequently mislabels phrasings
        # like "what if P2 capacity drops to 50?" as a plain question (it
        # starts with "what"). If keyword detection finds a concrete
        # what-if / sensitivity / resolve / pareto intent, run it rather than
        # falling through to the generic response.
        if kw_analysis_type != "unknown":
            return self._handle_follow_up_analysis(
                message, conversation_context, update_progress,
                analysis_type=kw_analysis_type,
            )

        # Generic follow-up response (fallback)
        return {
            "success": True,
            "type": "follow_up_general",
            "response": f"I can help with questions about your previous {last_solution.get('problem_type', 'optimization')} solution. What would you like to know?",
            "deterministic": False
        }

    def _handle_infeasibility_fix(self, message: str, conversation_context: Dict, update_progress) -> Dict[str, Any]:
        """
        Handle user's response to an infeasibility report.

        This method:
        1. Parses the user's modification or new description
        2. Applies modifications or re-extracts parameters
        3. Re-checks feasibility
        4. Returns to solve if feasible, or reports infeasibility again
        """
        MAX_RETRIES = 3

        infeas_info = conversation_context["last_infeasibility"]
        retry_count = infeas_info.get("retry_count", 0)

        # Check if max retries exceeded
        if retry_count >= MAX_RETRIES:
            # Clear infeasibility context
            conversation_context.pop("last_infeasibility", None)
            return {
                "success": False,
                "error": "Maximum retry limit reached (3 attempts). Please start with a new problem description.",
                "type": "max_retries_exceeded"
            }

        update_progress("Parsing your modifications...", 10)

        # Parse user's fix
        parse_result = self.llm.parse_infeasibility_fix(
            message,
            infeas_info["params"],
            {
                "layer_failed": infeas_info["report"].layer_passed,
                "reasons": infeas_info["report"].reasons,
                "suggestions": infeas_info["report"].suggestions
            }
        )

        # If complete redescription, treat as new problem
        if parse_result.get("is_complete_redescription", False):
            # Clear infeasibility context and treat as new problem
            conversation_context.pop("last_infeasibility", None)
            return self.solve_natural_language(message, update_progress, conversation_context)

        # Apply modifications
        modified_params = parse_result.get("applied_params", infeas_info["params"])

        # Generate diff
        update_progress("Checking modifications...", 30)
        diff = self._generate_param_diff(infeas_info["original_params"], modified_params)

        # Re-check feasibility
        update_progress("Re-checking feasibility...", 50)
        from feasibility.core import check_feasibility, FeasStatus
        from feasibility.schemas import ParsedInstance

        instance = ParsedInstance(
            problem_type=infeas_info["problem_type"],
            solver_id=infeas_info["solver_id"],
            sets=self._extract_sets_from_params(modified_params),
            params=self._convert_params_for_feasibility(modified_params)
        )

        feas_report = check_feasibility(instance)

        if feas_report.status == FeasStatus.INFEASIBLE:
            # Still infeasible, increment retry count
            infeas_info["retry_count"] = retry_count + 1
            infeas_info["params"] = modified_params
            infeas_info["report"] = feas_report

            # Add to modification history
            if "modification_history" not in infeas_info:
                infeas_info["modification_history"] = []
            infeas_info["modification_history"].append({
                "attempt": retry_count + 1,
                "modifications": parse_result.get("modifications", []),
                "diff": diff
            })

            return {
                "success": False,
                "status": "still_infeasible",
                "layer_failed": feas_report.layer_passed,
                "reasons": feas_report.reasons,
                "suggestions": feas_report.suggestions or [],
                "retry_count": retry_count + 1,
                "max_retries": MAX_RETRIES,
                "diff": diff,
                "message": f"The problem is still infeasible (attempt {retry_count + 1}/{MAX_RETRIES}). Please provide additional modifications."
            }

        # Feasible! Now solve it
        update_progress("Problem is now feasible! Solving...", 70)

        # Clear infeasibility context
        conversation_context.pop("last_infeasibility", None)

        # Solve with modified params
        solver = get_solver(infeas_info["solver_id"])
        solution = solver.solve(modified_params)

        update_progress("Generating explanation...", 85)

        explanation_result = self.llm.explain_solution(
            solution,
            infeas_info["problem_type"],
            infeas_info["description"]
        )

        update_progress("Complete!", 100)

        result = {
            "success": True,
            "problem_type": infeas_info["problem_type"],
            "extracted_params": modified_params,
            "solution": solution,
            "explanation": explanation_result.get('explanation', ''),
            "summary": explanation_result.get('summary', ''),
            "units_info": explanation_result.get('units_info', {}),
            "grounding_check": explanation_result.get('grounding_check', 'unknown'),
            "modifications_applied": parse_result.get("modifications", []),
            "diff": diff,
            "message": f"Problem fixed! Applied {len(parse_result.get('modifications', []))} modification(s)."
        }

        # Store in conversation context
        conversation_context["last_solution"] = result

        return result

    def _handle_follow_up_analysis(self, message: str, conversation_context: Dict, update_progress, analysis_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Handle follow-up analysis requests (sensitivity, what-if, resolve, pareto).

        This method:
        1. Detects the type of analysis requested (skipped if the caller
           already classified it — avoids a redundant LLM round-trip)
        2. Routes to appropriate analysis engine
        3. Stores results in analysis history
        4. Returns formatted results
        """
        last_solution = conversation_context.get("last_solution")

        if not last_solution:
            return {
                "success": False,
                "error": "No previous solution found. Please solve a problem first before requesting analysis.",
                "type": "analysis_error"
            }

        # Extract params and solution from last_solution
        params = last_solution.get("extracted_params")
        solution = last_solution.get("solution")

        if not params or not solution:
            return {
                "success": False,
                "error": "Cannot perform analysis - previous solution is incomplete.",
                "type": "analysis_error"
            }

        update_progress("Detecting analysis type...", 10)

        # Use the caller-supplied classification when available; otherwise
        # fall back to LLM detection (robust to typos / loose phrasing).
        if analysis_type is None:
            analysis_type = detect_analysis_type(message, self.llm)

        if analysis_type == 'unknown':
            return {
                "success": False,
                "error": "Could not understand analysis request.",
                "suggestion": "Try: 'sensitivity on Plant North capacity', 'what if demand increases by 20', or 'resolve with capacity = 100'",
                "type": "analysis_error"
            }

        update_progress(f"Performing {analysis_type} analysis...", 40)

        # Resolve the solver by its real solver_id. The solution carries the
        # solver_id it was produced with; fall back to the category default
        # (problem_type is a category like "TRANSPORTATION", NOT a solver_id).
        solver_id = (
            solution.get("solver_id")
            or last_solution.get("solver_id")
            or get_default_solver_for_category(
                last_solution.get("problem_type", "TRANSPORTATION").lower()
            )
        )

        try:
            # Execute analysis
            results = execute_analysis(
                analysis_type=analysis_type,
                solver=get_solver(solver_id),
                params=params,
                solution=solution,
                query=message,
                llm_client=self.llm
            )

            if not results.get('success', False):
                # A "validly infeasible" what-if is a useful answer, not an
                # error: the user asked "what if X" and the honest answer is
                # "that can't work, because…". Surface the plain-language
                # reasons/suggestions the feasibility engine produced instead
                # of the cryptic internal "failed at layer N" message.
                if results.get('feasible') is False:
                    conversation_context.setdefault("analysis_history", []).append({
                        "query": message,
                        "analysis_type": analysis_type,
                        "results": results,
                        "timestamp": message,
                    })
                    return {
                        "success": True,
                        "type": "follow_up_analysis",
                        "analysis_type": analysis_type,
                        "response": format_analysis_output(analysis_type, results),
                        "raw_results": results,
                    }
                return {
                    "success": False,
                    "error": results.get('message', 'Analysis failed'),
                    "type": "analysis_error"
                }

            update_progress("Formatting results...", 80)

            # Format output
            formatted_output = format_analysis_output(analysis_type, results)

            # Store in analysis history
            conversation_context.setdefault("analysis_history", []).append({
                "query": message,
                "analysis_type": analysis_type,
                "results": results,
                "timestamp": message  # In production, use actual timestamp
            })

            update_progress("Analysis complete!", 100)

            # For resolve operations, update the last_solution with new params and solution
            if analysis_type == 'resolve' and results.get('success'):
                last_solution["extracted_params"] = results["new_params"]
                last_solution["solution"] = results["new_solution"]
                conversation_context["last_solution"] = last_solution

            return {
                "success": True,
                "type": "follow_up_analysis",
                "analysis_type": analysis_type,
                "response": formatted_output,
                "raw_results": results
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Analysis failed: {str(e)}",
                "type": "analysis_error"
            }

    def _perform_requested_analyses(self, analysis_requests: Dict, params: Dict) -> List[Dict]:
        """Perform the analyses requested by the user"""
        results = []

        try:
            requests = analysis_requests.get("requests", [])

            for request in requests:
                analysis_type = request.get("type", "")

                if analysis_type == "sensitivity":
                    # Perform sensitivity analysis
                    variable = request.get("x_variable", "")
                    if variable:
                        # Determine reasonable range for the variable
                        original_value = self.analysis_engine._get_variable_value(params, variable)
                        if original_value:
                            # Create range from 50% to 150% of original value
                            range_min = original_value * 0.5
                            range_max = original_value * 1.5

                            analysis_result = self.analysis_engine.run_sensitivity_analysis(
                                params, variable, (range_min, range_max), steps=15
                            )

                            # Generate plot
                            plot_b64 = self.analysis_engine.create_sensitivity_plot(analysis_result)

                            results.append({
                                "type": "sensitivity_analysis",
                                "description": request.get("description", "Sensitivity Analysis"),
                                "variable": variable,
                                "data": analysis_result,
                                "plot_base64": plot_b64
                            })

                elif analysis_type == "visualization":
                    # Generate basic plots for the solution
                    try:
                        from api import _plot_shipments_by_plant, _plot_shipments_matrix, _b64

                        # Get the last solution from memory
                        solver = self._get_solver_for_params(params)
                        if solver:
                            solution = solver.solve(params)

                            # Generate plots
                            img1 = _plot_shipments_by_plant(solution)
                            img2 = _plot_shipments_matrix(solution)

                            results.append({
                                "type": "shipments_by_plant",
                                "description": "Shipments by Plant",
                                "plot_base64": _b64(img1)
                            })

                            results.append({
                                "type": "shipments_matrix",
                                "description": "Shipments Matrix (Stacked)",
                                "plot_base64": _b64(img2)
                            })
                    except Exception as e:
                        results.append({
                            "type": "error",
                            "description": f"Failed to generate plots: {str(e)}"
                        })

                elif analysis_type == "scenario":
                    # Perform scenario comparison (simplified)
                    scenarios = []  # Would need to extract from user request
                    analysis_result = self.analysis_engine.run_scenario_comparison(params, scenarios)

                    plot_b64 = self.analysis_engine.create_scenario_plot(analysis_result)

                    results.append({
                        "type": "scenario_comparison",
                        "description": request.get("description", "Scenario Comparison"),
                        "data": analysis_result,
                        "plot_base64": plot_b64
                    })

        except Exception as e:
            results.append({
                "type": "error",
                "description": f"Analysis failed: {str(e)}"
            })

        return results

    def _map_to_solver(self, problem_type: str) -> str:
        """
        Map problem type/subcategory to actual solver name

        Scheduling subcategories all map to "scheduling" solver
        """
        # Scheduling subcategories
        scheduling_types = [
            "job_shop", "flow_shop", "single_stage_scheduling",
            "shift_rostering", "project_scheduling"
        ]

        if problem_type.lower() in scheduling_types:
            return "scheduling"

        # Default: use the problem type as-is
        return problem_type

    def get_capabilities(self) -> Dict[str, Any]:
        """Return agent capabilities, keyed by registered solver_id."""
        from solvers import list_solvers
        registered = list_solvers()
        capabilities = {}
        for entry in registered:
            sid = entry["solver_id"]
            try:
                solver = get_solver(sid)
                capabilities[sid] = {
                    "problem_type": entry["problem_type"],
                    "description": solver.description,
                    "example_params": solver.get_example_params(),
                }
            except Exception as e:
                capabilities[sid] = {"error": str(e)}

        return {
            "supported_solvers": [e["solver_id"] for e in registered],
            "capabilities": capabilities,
        }

    def _extract_sets_from_params(self, params: Dict) -> Dict:
        """Extract sets from solver params for feasibility checking"""
        sets = {}

        # Transportation problem
        if "plants" in params:
            sets["I_plants"] = params["plants"]
        if "markets" in params:
            sets["J_markets"] = params["markets"]

        # Scheduling problem
        if "orders" in params:
            sets["J_orders"] = params["orders"]
        if "units" in params:
            sets["I_units"] = params["units"]

        return sets

    def _convert_params_for_feasibility(self, params: Dict) -> Dict:
        """Convert solver params to feasibility checker format"""
        feas_params = {}

        # Copy relevant parameters
        if "capacity" in params:
            feas_params["supply"] = params["capacity"]  # Feasibility uses 'supply'
        if "demand" in params:
            feas_params["demand"] = params["demand"]
        if "cost" in params:
            # Flatten nested cost dict {i: {j: c}} to {(i,j): c} for feasibility checker
            cost = params["cost"]
            if cost and isinstance(cost, dict):
                first_val = next(iter(cost.values()), None)
                if isinstance(first_val, dict):
                    # Nested format - flatten it
                    feas_params["cost"] = {
                        (i, j): c
                        for i, markets in cost.items()
                        for j, c in markets.items()
                    }
                else:
                    # Already flat format
                    feas_params["cost"] = cost
        if "distance" in params:
            feas_params["distance"] = params["distance"]
        if "freight" in params:
            feas_params["freight"] = params["freight"]
        if "arc_capacity" in params:
            feas_params["arc_capacity"] = params["arc_capacity"]

        # Scheduling params
        if "processing_time" in params:
            feas_params["processing_time"] = params["processing_time"]
        if "due_date" in params:
            feas_params["due_date"] = params["due_date"]

        return feas_params

    def _generate_param_diff(self, original: Dict, modified: Dict) -> List[str]:
        """
        Generate human-readable diff of parameter changes.

        Args:
            original: Original parameters
            modified: Modified parameters

        Returns:
            List of change descriptions
        """
        diff = []

        # Check capacity/supply changes
        if "capacity" in original and "capacity" in modified:
            for entity in original["capacity"]:
                old_val = original["capacity"].get(entity, 0)
                new_val = modified["capacity"].get(entity, 0)
                if abs(old_val - new_val) > 1e-6:
                    diff.append(f"Capacity[{entity}]: {old_val} → {new_val} (change: {new_val - old_val:+.2f})")

        # Check demand changes
        if "demand" in original and "demand" in modified:
            for entity in original["demand"]:
                old_val = original["demand"].get(entity, 0)
                new_val = modified["demand"].get(entity, 0)
                if abs(old_val - new_val) > 1e-6:
                    diff.append(f"Demand[{entity}]: {old_val} → {new_val} (change: {new_val - old_val:+.2f})")

        # Check cost changes
        if "cost" in original and "cost" in modified:
            for route in original["cost"]:
                old_val = original["cost"].get(route, 0)
                new_val = modified["cost"].get(route, 0)
                if abs(old_val - new_val) > 1e-6:
                    diff.append(f"Cost[{route}]: {old_val} → {new_val} (change: {new_val - old_val:+.2f})")

        # Check arc_capacity changes
        if "arc_capacity" in modified:
            original_arc = original.get("arc_capacity", {})
            for route in modified["arc_capacity"]:
                old_val = original_arc.get(route, 0)
                new_val = modified["arc_capacity"].get(route, 0)
                if abs(old_val - new_val) > 1e-6:
                    if old_val == 0:
                        diff.append(f"Arc_capacity[{route}]: ADDED with value {new_val}")
                    else:
                        diff.append(f"Arc_capacity[{route}]: {old_val} → {new_val} (change: {new_val - old_val:+.2f})")

        if not diff:
            diff.append("No parameter changes detected")

        return diff