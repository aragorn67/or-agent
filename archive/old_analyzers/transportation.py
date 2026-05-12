# analysis/analyzers/transportation.py
from typing import Dict, Any, Tuple, Optional
from .base import BaseAnalyzer
import json

class TransportationAnalyzer(BaseAnalyzer):
    """LLM-driven analyzer for transportation optimization problems"""

    def get_problem_type(self) -> str:
        return "TRANSPORTATION"

    def get_supported_variable_types(self) -> Dict[str, Dict[str, Any]]:
        return {
            "capacity": {"description": "Production capacity at plants"},
            "demand": {"description": "Demand requirements at markets"},
            "distance": {"description": "Distance between plants and markets"},
            "freight": {"description": "Freight cost per unit per distance"}
        }

    def extract_variable_from_message(self, user_message: str, available_params: Dict) -> Tuple[Optional[str], Optional[float]]:
        """Let the LLM extract transportation variables from natural language"""

        if not self.llm:
            # Fallback to simple pattern matching if no LLM
            return self._simple_fallback(user_message, available_params)

        prompt = f"""
User wants to analyze: "{user_message}"

Available data: {json.dumps(available_params, indent=2)}

Return the exact parameter path to vary. Examples:
- For capacity at san-diego: "capacity_san-diego"
- For demand at chicago: "demand_chicago"
- For freight cost: "freight"

Return JSON: {{"variable_name": "exact_parameter_path"}}
"""

        try:
            response = self.llm._generate(prompt)
            print(f"LLM Response: {response}")  # Debug log

            # Extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx == -1 or end_idx == 0:
                print("No valid JSON found in LLM response")
                return self._simple_fallback(user_message, available_params)

            json_str = response[start_idx:end_idx]
            print(f"Extracted JSON: {json_str}")  # Debug log
            result = json.loads(json_str)

            variable_name = result.get("variable_name")
            if not variable_name:
                print("No variable_name in LLM result")
                return self._simple_fallback(user_message, available_params)

            # Get the original value
            original_value = self._get_original_value(variable_name, available_params)
            print(f"Final result: {variable_name}, {original_value}")  # Debug log

            return variable_name, original_value

        except Exception as e:
            print(f"LLM extraction failed: {e}")
            return self._simple_fallback(user_message, available_params)

    def format_variable_for_analysis(self, variable_type: str, entity_name: str) -> str:
        """Format variable name for analysis engine"""
        if variable_type == "freight":
            return "freight"
        elif variable_type == "distance":
            return entity_name  # Already formatted as "distance_plant_market"
        else:
            return f"{variable_type}_{entity_name}"

    def _get_original_value(self, variable_name: str, params: Dict) -> Optional[float]:
        """Get the original value of a variable"""
        try:
            if variable_name == "freight":
                return float(params.get("freight", 0))
            elif variable_name.startswith("capacity_"):
                plant = variable_name.replace("capacity_", "")
                return float(params.get("capacity", {}).get(plant, 0))
            elif variable_name.startswith("demand_"):
                market = variable_name.replace("demand_", "")
                return float(params.get("demand", {}).get(market, 0))
            elif variable_name.startswith("distance_"):
                parts = variable_name.split("_")
                if len(parts) >= 3:
                    plant = parts[1]
                    market = "_".join(parts[2:])
                    return float(params.get("distance", {}).get(plant, {}).get(market, 0))
        except:
            pass
        return None

    def _simple_fallback(self, user_message: str, available_params: Dict) -> Tuple[Optional[str], Optional[float]]:
        """Simple fallback if LLM is unavailable"""
        message_lower = user_message.lower()

        # Simple pattern matching as fallback
        if "capacity" in message_lower or "production" in message_lower or "units" in message_lower:
            capacities = available_params.get("capacity", {})
            for plant, value in capacities.items():
                if value > 0:
                    return f"capacity_{plant}", float(value)

        elif "demand" in message_lower:
            demands = available_params.get("demand", {})
            for market, value in demands.items():
                if value > 0:
                    return f"demand_{market}", float(value)

        elif "distance" in message_lower:
            distances = available_params.get("distance", {})
            for plant, plant_distances in distances.items():
                for market, value in plant_distances.items():
                    if value > 0:
                        return f"distance_{plant}_{market}", float(value)

        # Default to freight
        freight = available_params.get("freight")
        if freight:
            return "freight", float(freight)

        return None, None