# agent/core.py
from typing import Dict, Any, List
from llm.client import LLMClient
from solvers import get_solver, list_problem_types
from analysis.detector import AnalysisDetector
from analysis.engine import AnalysisEngine

class OptimizationAgent:
    """Main agent orchestrating problem solving"""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.analysis_detector = AnalysisDetector(llm_client)
        self.analysis_engine = AnalysisEngine()

    def solve_natural_language(self, description: str, progress_callback=None) -> Dict[str, Any]:
        """Main entry point for natural language problem solving"""

        def update_progress(step: str, progress: int):
            if progress_callback:
                progress_callback(step, progress)

        try:
            update_progress("Analyzing problem type...", 10)

            # Step 1: Classify problem type
            available_types = list_problem_types()
            classification = self.llm.classify_problem(description, available_types)
            problem_type = classification.get('type', 'TRANSPORTATION')
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

            # Step 2: Get appropriate solver
            solver = get_solver(problem_type)

            update_progress("Extracting parameters from description...", 40)

            # Step 3: Extract parameters using LLM
            example_params = solver.get_example_params()
            params = self.llm.extract_parameters(description, problem_type, example_params)

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

            update_progress("Solving optimization problem...", 70)

            # Step 5: Solve the problem
            solution = solver.solve(params)

            update_progress("Generating explanation...", 85)

            # Step 6: Generate explanation
            explanation = self.llm.explain_solution(solution, problem_type)

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
                "explanation": explanation
            }

            # Add analysis results if any
            if analysis_results:
                result["analysis"] = analysis_results

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

    def get_capabilities(self) -> Dict[str, Any]:
        """Return agent capabilities and supported problem types"""
        problem_types = list_problem_types()
        capabilities = {}

        for ptype in problem_types:
            try:
                solver = get_solver(ptype)
                capabilities[ptype] = {
                    "description": solver.description,
                    "example_params": solver.get_example_params()
                }
            except Exception as e:
                capabilities[ptype] = {"error": str(e)}

        return {
            "supported_types": problem_types,
            "capabilities": capabilities
        }