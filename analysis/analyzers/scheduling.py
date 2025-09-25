# analysis/analyzers/scheduling.py
from typing import Dict, Any, Tuple, Optional
from .base import BaseAnalyzer
import json

class SchedulingAnalyzer(BaseAnalyzer):
    """LLM-driven analyzer for scheduling optimization problems"""

    def get_problem_type(self) -> str:
        return "SCHEDULING"

    def get_supported_variable_types(self) -> Dict[str, Dict[str, Any]]:
        return {
            "processing_time": {"description": "Time to process jobs"},
            "setup_time": {"description": "Setup time between jobs"},
            "machine_capacity": {"description": "Machine processing capacity"},
            "deadline_penalty": {"description": "Penalty for missing deadlines"}
        }

    def extract_variable_from_message(self, user_message: str, available_params: Dict) -> Tuple[Optional[str], Optional[float]]:
        """LLM-driven extraction for scheduling variables"""

        if not self.llm:
            return self._simple_fallback(user_message, available_params)

        prompt = f"""
Analyze this scheduling optimization sensitivity request:

User request: "{user_message}"
Available parameters: {json.dumps(available_params, indent=2)}

Return ONLY valid JSON:
{{
  "variable_name": "formatted_parameter_name",
  "confidence": 0.9
}}

Focus on scheduling concepts like processing times, setup times, machine capacity, deadlines.
"""

        try:
            response = self.llm._generate(prompt)
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx == -1 or end_idx == 0:
                return self._simple_fallback(user_message, available_params)

            result = json.loads(response[start_idx:end_idx])
            variable_name = result.get("variable_name")

            if variable_name:
                original_value = self._extract_value(variable_name, available_params)
                return variable_name, original_value

        except Exception as e:
            print(f"Scheduling LLM extraction failed: {e}")

        return self._simple_fallback(user_message, available_params)

    def format_variable_for_analysis(self, variable_type: str, entity_name: str) -> str:
        return f"{variable_type}_{entity_name}" if entity_name else variable_type

    def _extract_value(self, variable_name: str, params: Dict) -> Optional[float]:
        """Extract value from parameters - implement based on scheduling parameter structure"""
        # TODO: Implement based on actual scheduling parameter structure
        return 60.0  # Placeholder (minutes)

    def _simple_fallback(self, user_message: str, available_params: Dict) -> Tuple[Optional[str], Optional[float]]:
        """Simple fallback for scheduling problems"""
        # TODO: Implement basic pattern matching for scheduling
        return None, None