# llm/client.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class LLMClient(ABC):
    """Abstract interface for LLM providers with standardized methods"""

    @abstractmethod
    def classify_problem(self, description: str, problem_types: List[str]) -> Dict[str, Any]:
        """Returns: {"type": "TRANSPORTATION", "confidence": 0.95}"""
        pass

    @abstractmethod
    def extract_parameters(self, description: str, problem_type: str, example: Dict) -> Dict[str, Any]:
        """Extract structured parameters from natural language"""
        pass

    @abstractmethod
    def explain_solution(self, solution: Dict, problem_type: str, original_description: str = "") -> str:
        """Generate natural language explanation of solution"""
        pass

    @abstractmethod
    def detect_follow_up_intent(self, new_message: str, conversation_context: Dict) -> Dict[str, Any]:
        """Detect if message is follow-up and what type of analysis is requested"""
        pass

    @abstractmethod
    def extract_modification_parameters(self, user_request: str, original_params: Dict) -> Dict[str, Any]:
        """Extract parameter modifications from user request"""
        pass

    @abstractmethod
    def _chat(self, system: str, user: str, json_mode: bool = False) -> str:
        """Core chat functionality - all implementations must provide this"""
        pass