# llm/client.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class LLMClient(ABC):
    """Abstract interface for LLM providers"""

    @abstractmethod
    def classify_problem(self, description: str, problem_types: List[str]) -> Dict[str, Any]:
        """Returns: {"type": "TRANSPORTATION", "confidence": 0.95}"""
        pass

    @abstractmethod
    def extract_parameters(self, description: str, problem_type: str, example: Dict) -> Dict[str, Any]:
        """Extract structured parameters from natural language"""
        pass

    @abstractmethod
    def explain_solution(self, solution: Dict, problem_type: str) -> str:
        """Generate natural language explanation of solution"""
        pass