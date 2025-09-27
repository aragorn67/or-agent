# llm/enhanced_client.py
from typing import Dict, Any, List
from .client import LLMClient
from .ollama_client import OllamaClient
from .transportation_specialist import TransportationSpecialist

class EnhancedLLMClient(LLMClient):
    """Enhanced LLM client with problem-specific specialists"""

    def __init__(self, host: str = "http://localhost:11434", model: str = "qwen2:7b"):
        self.base_client = OllamaClient(host, model)

        # Initialize specialists
        self.transportation = TransportationSpecialist(self.base_client)

        # Future specialists can be added here:
        # self.scheduling = SchedulingSpecialist(self.base_client)
        # self.assignment = AssignmentSpecialist(self.base_client)
        # self.knapsack = KnapsackSpecialist(self.base_client)

    def classify_problem(self, description: str, problem_types: List[str]) -> Dict[str, Any]:
        """Classify problem type using base client"""
        return self.base_client.classify_problem(description, problem_types)

    def extract_parameters(self, description: str, problem_type: str, example: Dict) -> Dict[str, Any]:
        """Route to appropriate specialist based on problem type"""

        problem_type = (problem_type or "").upper()

        if problem_type == "TRANSPORTATION":
            return self.transportation.extract_parameters(description)

        # Future problem types:
        # elif problem_type == "SCHEDULING":
        #     return self.scheduling.extract_parameters(description)
        # elif problem_type == "ASSIGNMENT":
        #     return self.assignment.extract_parameters(description)

        else:
            # Fallback to base client for unsupported types
            return {"error": f"Problem type '{problem_type}' not yet supported by specialist handlers"}

    def explain_solution(self, solution: Dict, problem_type: str, original_description: str = "") -> str:
        """Generate clean, factual explanation with proper units"""

        from .solution_formatter import SolutionFormatter

        # Use generic solution formatter for all problem types
        formatter = SolutionFormatter(self.base_client)
        result = formatter.format_solution(solution, problem_type, original_description)

        return result['explanation']

    def detect_follow_up_intent(self, new_message: str, conversation_context: Dict) -> Dict[str, Any]:
        """Detect follow-up intent using base client"""
        return self.base_client.detect_follow_up_intent(new_message, conversation_context)

    def _chat(self, system: str, user: str, json_mode: bool = False) -> str:
        """Delegate core chat functionality to base client"""
        return self.base_client._chat(system, user, json_mode)

    def extract_modification_parameters(self, user_request: str, original_params: Dict) -> Dict[str, Any]:
        """Route modification detection to appropriate specialist"""

        # Try to detect problem type from params structure
        if self._is_transportation_params(original_params):
            return self.transportation.detect_transportation_modifications(user_request, original_params)

        # Future problem types:
        # elif self._is_scheduling_params(original_params):
        #     return self.scheduling.detect_scheduling_modifications(user_request, original_params)

        else:
            # Fallback to base client
            return self.base_client.extract_modification_parameters(user_request, original_params)

    def suggest_analysis(self, solution: Dict, params: Dict, problem_type: str) -> List[str]:
        """Get problem-specific analysis suggestions"""

        problem_type = (problem_type or "").upper()

        if problem_type == "TRANSPORTATION":
            return self.transportation.suggest_transportation_analysis(solution, params)

        # Future problem types will have their own suggestions

        else:
            return ["Basic solution analysis", "Parameter sensitivity analysis"]

    def _is_transportation_params(self, params: Dict) -> bool:
        """Check if parameters match transportation problem structure"""
        required_keys = {"plants", "markets", "capacity", "demand"}
        return required_keys.issubset(set(params.keys()))

    # Future helper methods for other problem types:
    # def _is_scheduling_params(self, params: Dict) -> bool:
    #     required_keys = {"jobs", "machines", "processing_times"}
    #     return required_keys.issubset(set(params.keys()))

    # def _is_assignment_params(self, params: Dict) -> bool:
    #     required_keys = {"agents", "tasks", "costs"}
    #     return required_keys.issubset(set(params.keys()))