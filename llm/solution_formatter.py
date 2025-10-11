# llm/solution_formatter.py
from typing import Dict, Any
from .units_handler import UnitsHandler
from .explanation_guard import ExplanationGuard

class SolutionFormatter:
    """Generic solution formatting system for all optimization problem types"""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.units_handler = UnitsHandler()
        self.explanation_guard = ExplanationGuard()

    def format_solution(self,
                       solution: Dict[str, Any],
                       problem_type: str,
                       original_description: str) -> Dict[str, Any]:
        """Format solution with proper units, concise explanation, and no speculation"""

        # Step 1: Detect units from original problem
        units_info = self.units_handler.detect_units(original_description)

        # Step 2: Create deterministic summary (always works)
        deterministic_summary = self.explanation_guard.create_deterministic_summary(solution)

        # Step 3: Try to get LLM explanation (optional enhancement)
        llm_explanation = None
        if self.llm_client:
            try:
                # Use concise prompt with _chat method (not _generate which doesn't exist)
                system = "You are a concise optimization solution explainer. Only state facts from the data."
                user = self.explanation_guard.create_concise_prompt(problem_type) + f"\n\nSolution data: {solution}"
                raw_explanation = self.llm_client._chat(system, user, json_mode=False)

                # Filter for groundedness
                llm_explanation = self.explanation_guard.filter_explanation(raw_explanation, solution)
            except Exception:
                pass  # Fall back to deterministic

        # Step 4: Choose best explanation
        final_explanation = llm_explanation if llm_explanation else deterministic_summary

        # Step 5: Format with proper units
        formatted_summary = self.units_handler.format_solution_summary(solution, units_info)

        return {
            'formatted_summary': formatted_summary,
            'explanation': final_explanation,
            'units_info': units_info,
            'grounding_check': 'passed' if llm_explanation else 'deterministic_fallback'
        }