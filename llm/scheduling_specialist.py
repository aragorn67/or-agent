# llm/scheduling_specialist.py
import json
from typing import Dict, Any, List
from .ollama_client import OllamaClient

class SchedulingSpecialist:
    """Specialized LLM handler for scheduling optimization problems"""

    def __init__(self, ollama_client: OllamaClient, knowledge_base=None):
        """
        Initialize scheduling specialist.

        Args:
            ollama_client: LLM client for parameter extraction
            knowledge_base: Optional KnowledgeBase for RAG context
        """
        self.client = ollama_client
        self.kb = knowledge_base

    def extract_parameters(self, description: str) -> Dict[str, Any]:
        """Extract scheduling-specific parameters with deep validation"""

        # Get relevant context from knowledge base if available
        rag_context = ""
        if self.kb is not None:
            try:
                rag_context = self.kb.get_context(
                    "scheduling problem makespan processing time changeover",
                    max_tokens=500
                )
                if rag_context:
                    rag_context = f"\n\nRelevant OR knowledge:\n{rag_context}\n"
            except:
                pass  # KB not available, continue without RAG

        system = """
Extract parameters for a Scheduling problem. Output STRICT JSON with keys:
- orders: string[] (jobs, tasks, orders to be scheduled)
- units: string[] (machines, resources, processing units)
- eligible: {order: string[]} (which units can process each order)
- processing_time: {order: {unit: number}} (time to process order on unit)
- due_date: {order: number} (deadline for each order)
- changeover: {unit: {order1: {order2: number}}} (optional - setup/changeover time between orders on same unit)
- window: {order: 0 or 1} (optional - if 1, order has strict time window)
- lower: {order: number} (optional - earliest start time for orders with time window)
- objective: string (optional - "makespan" or "changeover", default "makespan")

EXTRACTION RULES:
1. Use ONLY entities & numbers explicitly mentioned in the text
2. Look for various phrasings: "jobs/orders/tasks" = orders, "machines/units/resources" = units
3. Extract ALL processing times mentioned (e.g., "Order A takes 2 hours on Unit 1")
4. Extract ALL due dates/deadlines mentioned (e.g., "Order A due by hour 10")
5. Extract eligibility constraints (e.g., "Order B can only use Unit 1")
6. Extract changeover/setup times if mentioned (e.g., "switching from A to B takes 0.5 hours")
7. If time windows mentioned, set window=1 and extract lower bound
8. If ANY required piece is missing, return: {"error": "<specific missing information>"}
9. All numbers must be numeric types, not strings
10. Time units should be consistent (convert to hours if needed)

NESTED STRUCTURE EXAMPLES:
- processing_time: {"O1": {"U1": 2.0, "U2": 3.0}, "O2": {"U1": 1.5}}
- changeover: {"U1": {"O1": {"O2": 0.5, "O3": 0.3}, "O2": {"O1": 0.4}}}
- eligible: {"O1": ["U1", "U2"], "O2": ["U1"], "O3": ["U1", "U2"]}

═══════════════════════════════════════════════════════════════════════════════
SPECIAL CASE — PURE SEQUENCE-DEPENDENT SETUP (single machine, minimize total setup)
═══════════════════════════════════════════════════════════════════════════════
Some problems give ONLY a sequence-dependent setup-time matrix on ONE machine,
with NO processing times and NO due dates — the goal is to order the jobs to
minimize total setup time. The matrix has one row per "immediately preceding"
job PLUS a special "None" row for the setup of whichever job runs FIRST (from
the machine's idle state). A "—" / dash means not-applicable (the diagonal).

For this case, output ONLY these keys (do NOT invent processing_time/due_date):
- orders: list of the job labels exactly as named (e.g. ["1","2","3","4","5"])
- setup_matrix: {preceding_job: {following_job: time}} INCLUDING a "None" key
  for the initial-setup row. Skip every "—"/dash cell.
- objective: "changeover"

setup_matrix EXAMPLE for a 3-job table (rows None/1/2/3, dash on diagonal):
  {"None": {"1": 4, "2": 5, "3": 8},
   "1": {"2": 7, "3": 12},
   "2": {"1": 6, "3": 10},
   "3": {"1": 10, "2": 11}}
Transcribe EVERY off-diagonal number and the whole None row — accuracy matters.
"""

        user = f"SCHEDULING PROBLEM:\n{description}\n\nReturn ONLY the JSON."

        try:
            content = self.client._chat(system, user, json_mode=True)
            result = json.loads(content)

            if "error" in result:
                return result

            # Pure sequence-dependent setup problems (single machine, minimize
            # total setup) carry a `setup_matrix` instead of processing times /
            # due dates. The LLM transcribes the visible table; we deterministically
            # assemble the solver's canonical changeover params (LLM reads, code
            # builds the math).
            if "setup_matrix" in result:
                seq_error = self._validate_sequencing(result)
                if seq_error:
                    return {"error": seq_error}
                return self._build_sequencing_params(
                    result["orders"], result["setup_matrix"]
                )

            # Deep validation for scheduling
            validation_error = self._validate_scheduling_deep(description, result)
            if validation_error:
                return {"error": validation_error}

            return result

        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON response from LLM: {str(e)}"}
        except Exception as e:
            return {"error": f"Scheduling extraction error: {e}"}

    def _validate_scheduling_deep(self, description: str, params: Dict) -> str:
        """Deep validation specifically for scheduling problems"""

        # Core structure validation
        required = ["orders", "units", "eligible", "processing_time", "due_date"]
        missing = [k for k in required if k not in params or not params[k]]
        if missing:
            return f"Missing required scheduling data: {', '.join(missing)}. Please specify all orders, units, eligibility, processing times, and due dates."

        orders = params["orders"]
        units = params["units"]
        eligible = params["eligible"]
        processing_time = params["processing_time"]
        due_date = params["due_date"]

        # Type validation
        if not isinstance(orders, list):
            return "orders must be a list"
        if not isinstance(units, list):
            return "units must be a list"
        if not isinstance(eligible, dict):
            return "eligible must be a dictionary"
        if not isinstance(processing_time, dict):
            return "processing_time must be a dictionary"
        if not isinstance(due_date, dict):
            return "due_date must be a dictionary"

        # Check all orders have eligibility
        if set(eligible.keys()) != set(orders):
            missing_elig = set(orders) - set(eligible.keys())
            extra_elig = set(eligible.keys()) - set(orders)
            if missing_elig:
                return f"Missing eligibility data for orders: {', '.join(missing_elig)}"
            if extra_elig:
                return f"Extra eligibility data for unknown orders: {', '.join(extra_elig)}"

        # Check all orders have processing times
        if set(processing_time.keys()) != set(orders):
            missing_pt = set(orders) - set(processing_time.keys())
            if missing_pt:
                return f"Missing processing time data for orders: {', '.join(missing_pt)}"

        # Check all orders have due dates
        if set(due_date.keys()) != set(orders):
            missing_dd = set(orders) - set(due_date.keys())
            if missing_dd:
                return f"Missing due date data for orders: {', '.join(missing_dd)}"

        # Validate eligibility structure
        for order, eligible_units in eligible.items():
            if not isinstance(eligible_units, list):
                return f"Eligibility for order '{order}' must be a list of units"
            if not eligible_units:
                return f"Order '{order}' has no eligible units"

            # Check all eligible units exist
            invalid_units = [u for u in eligible_units if u not in units]
            if invalid_units:
                return f"Order '{order}' lists non-existent units: {', '.join(invalid_units)}"

        # Validate processing time structure and completeness
        for order in orders:
            if order not in processing_time:
                return f"Missing processing times for order '{order}'"

            order_times = processing_time[order]
            if not isinstance(order_times, dict):
                return f"Processing times for order '{order}' must be a dictionary"

            # Check that processing times are provided for all eligible units
            eligible_units = eligible[order]
            for unit in eligible_units:
                if unit not in order_times:
                    return f"Missing processing time for order '{order}' on eligible unit '{unit}'"

                time_val = order_times[unit]
                if not isinstance(time_val, (int, float)) or time_val <= 0:
                    return f"Processing time for order '{order}' on unit '{unit}' must be a positive number, got: {time_val}"

        # Validate due dates
        for order, dd in due_date.items():
            if not isinstance(dd, (int, float)) or dd <= 0:
                return f"Due date for order '{order}' must be a positive number, got: {dd}"

        # Validate optional changeover if present
        if "changeover" in params:
            changeover = params["changeover"]
            if not isinstance(changeover, dict):
                return "changeover must be a dictionary"

            # Validate nested structure: {unit: {order1: {order2: time}}}
            for unit, unit_changeovers in changeover.items():
                if unit not in units:
                    return f"Changeover specified for non-existent unit '{unit}'"
                if not isinstance(unit_changeovers, dict):
                    return f"Changeover data for unit '{unit}' must be a dictionary"

                for from_order, to_orders in unit_changeovers.items():
                    if from_order not in orders:
                        return f"Changeover specified for non-existent order '{from_order}' on unit '{unit}'"
                    if not isinstance(to_orders, dict):
                        return f"Changeover from order '{from_order}' on unit '{unit}' must be a dictionary"

                    for to_order, time in to_orders.items():
                        if to_order not in orders:
                            return f"Changeover to non-existent order '{to_order}' on unit '{unit}'"
                        if not isinstance(time, (int, float)) or time < 0:
                            return f"Changeover time from '{from_order}' to '{to_order}' on unit '{unit}' must be non-negative, got: {time}"

        # Validate optional window and lower if present
        if "window" in params:
            window = params["window"]
            if not isinstance(window, dict):
                return "window must be a dictionary"
            for order, val in window.items():
                if order not in orders:
                    return f"Time window specified for non-existent order '{order}'"
                if val not in [0, 1]:
                    return f"Time window for order '{order}' must be 0 or 1, got: {val}"

        if "lower" in params:
            lower = params["lower"]
            if not isinstance(lower, dict):
                return "lower must be a dictionary"
            for order, val in lower.items():
                if order not in orders:
                    return f"Lower bound specified for non-existent order '{order}'"
                if not isinstance(val, (int, float)) or val < 0:
                    return f"Lower bound for order '{order}' must be non-negative, got: {val}"

        # Validate objective if present
        if "objective" in params:
            obj = params["objective"]
            if obj not in ["makespan", "changeover"]:
                return f"objective must be 'makespan' or 'changeover', got: '{obj}'"

        # Business logic checks
        # Check if any order has impossible due date (less than minimum processing time)
        for order in orders:
            min_time = min(processing_time[order].values())
            if due_date[order] < min_time:
                return f"Order '{order}' has due date {due_date[order]} but minimum processing time is {min_time} - impossible to meet deadline"

        # Prose vs extracted validation
        import re
        text = description.lower()

        # Check mentioned counts vs extracted counts
        # Use word boundary to avoid matching "due by hour 10" as "10 orders"
        order_match = re.search(r'\b(\d+)\s+(?:production\s+)?(?:orders?|jobs?|tasks?)\b', text)
        if order_match and int(order_match.group(1)) != len(orders):
            return f"You mentioned {order_match.group(1)} orders/jobs but I found {len(orders)} order names. Please list all order names clearly."

        unit_match = re.search(r'\b(\d+)\s+(?:processing\s+)?(?:units?|machines?|resources?)\b', text)
        if unit_match and int(unit_match.group(1)) != len(units):
            return f"You mentioned {unit_match.group(1)} units/machines but I found {len(units)} unit names. Please list all unit names clearly."

        return None  # All validations passed

    @staticmethod
    def _is_none_key(k) -> bool:
        return str(k).strip().lower() in ("none", "idle", "start", "initial")

    def _validate_sequencing(self, result: Dict) -> str:
        """Validate a pure sequence-dependent setup extraction. Completeness is
        enforced on purpose: a silently-missing setup entry would default to 0
        and understate the objective, so we flag gaps as a clear error rather
        than letting a wrong optimum slip through."""
        orders = result.get("orders")
        matrix = result.get("setup_matrix")
        if not isinstance(orders, list) or not orders:
            return "Sequencing problem needs a non-empty 'orders' list."
        if not isinstance(matrix, dict) or not matrix:
            return "Sequencing problem needs a 'setup_matrix' dict."

        oset = {str(o) for o in orders}
        if len(oset) != len(orders):
            return "Duplicate job labels in 'orders'."

        # Initial-setup ("None") row: one entry per job.
        none_rows = [k for k in matrix if self._is_none_key(k)]
        if not none_rows:
            return ("Missing the initial-setup row (label 'None') giving the "
                    "setup of whichever job runs first.")
        init_row = matrix[none_rows[0]]
        if not isinstance(init_row, dict):
            return "The 'None' initial-setup row must map each job to a number."
        missing_init = oset - {str(k) for k in init_row}
        if missing_init:
            return f"Initial-setup ('None') row missing jobs: {sorted(missing_init)}"

        # Each job's outgoing row must cover every OTHER job (off-diagonal).
        for o in orders:
            row = matrix.get(str(o), matrix.get(o))
            if not isinstance(row, dict):
                return f"Missing the setup row for job '{o}' (after running it)."
            have = {str(k) for k in row}
            need = oset - {str(o)}
            missing = need - have
            if missing:
                return (f"Setup row for job '{o}' missing transitions to "
                        f"jobs: {sorted(missing)}")

        # Every number must be a non-negative numeric.
        for frm, tos in matrix.items():
            for to, val in tos.items():
                if not isinstance(val, (int, float)) or val < 0:
                    return (f"Setup time from '{frm}' to '{to}' must be a "
                            f"non-negative number, got: {val}")
        return None

    def _build_sequencing_params(self, orders: List, setup_matrix: Dict) -> Dict[str, Any]:
        """Assemble the single-stage IPM's canonical changeover params from a
        transcribed setup matrix. Single machine U1, zero processing time, and a
        large sentinel due date — the model minimizes total (initial + inter-job)
        setup. Mirrors the proven ground_truth_params shape exactly."""
        UNIT = "U1"
        orders = [str(o) for o in orders]

        none_key = next(k for k in setup_matrix if self._is_none_key(k))
        init_row = setup_matrix[none_key]
        initial_changeover = {
            o: {UNIT: float(init_row[o] if o in init_row else init_row[str(o)])}
            for o in orders
        }

        changeover = {UNIT: {}}
        for frm, tos in setup_matrix.items():
            if self._is_none_key(frm):
                continue
            changeover[UNIT][str(frm)] = {str(to): float(v) for to, v in tos.items()}

        return {
            "orders": orders,
            "units": [UNIT],
            "eligible": {o: [UNIT] for o in orders},
            "processing_time": {o: {UNIT: 0.0} for o in orders},
            "due_date": {o: 1000.0 for o in orders},
            "changeover": changeover,
            "initial_changeover": initial_changeover,
            "objective": "changeover",
        }

    def explain_solution(self, solution: Dict) -> str:
        """Generate scheduling-specific solution explanation"""

        system = """
You are explaining a Scheduling Optimization solution. Focus on:
1. Total makespan (completion time) or objective achieved
2. Assignment of orders to units
3. Sequence of orders on each unit
4. Whether all due dates are met
5. Key insights about the schedule (e.g., parallel processing, bottlenecks)

Be clear and business-focused. Use 2-3 sentences.
"""

        user = f"Scheduling Solution: {json.dumps(solution, indent=2)}"

        try:
            return self.client._chat(system, user, json_mode=False)
        except Exception:
            # Fallback explanation
            cmax = solution.get("Cmax", "N/A")
            num_assignments = len(solution.get("assignments", []))
            return f"Optimal schedule found with makespan of {cmax} time units. {num_assignments} orders assigned to processing units, all meeting their due date constraints."

    def suggest_scheduling_analysis(self, solution: Dict, params: Dict) -> List[str]:
        """Suggest scheduling-specific analyses based on the solution"""

        suggestions = []

        # Analyze solution characteristics
        assignments = solution.get("assignments", [])
        if not assignments:
            return ["Basic schedule visualization"]

        orders = params.get("orders", [])
        units = params.get("units", [])

        # Check unit utilization
        unit_usage = {}
        for assignment in assignments:
            unit = assignment.get("unit")
            unit_usage[unit] = unit_usage.get(unit, 0) + 1

        if len(unit_usage) < len(units):
            suggestions.append("Unit utilization analysis - some units are not being used")

        # Check for bottlenecks
        max_usage = max(unit_usage.values()) if unit_usage else 0
        min_usage = min(unit_usage.values()) if unit_usage else 0
        if max_usage > min_usage * 2:
            suggestions.append("Bottleneck analysis - workload is unevenly distributed")

        # Check due date slack
        completion = solution.get("completion", {})
        due_dates = params.get("due_date", {})
        tight_schedules = []
        for order, comp_time in completion.items():
            if order in due_dates:
                slack = due_dates[order] - comp_time
                if slack < 1.0:  # Less than 1 time unit slack
                    tight_schedules.append(order)

        if tight_schedules:
            suggestions.append(f"Due date sensitivity analysis - {len(tight_schedules)} orders have tight margins")

        # Changeover analysis
        if "changeover" in params and params["changeover"]:
            suggestions.append("Changeover time optimization analysis")

        # Makespan sensitivity
        suggestions.append("Processing time sensitivity - how changes affect makespan")

        return suggestions[:4]  # Top 4 suggestions
