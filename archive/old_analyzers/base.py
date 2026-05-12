# analysis/analyzers/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional

class BaseAnalyzer(ABC):
    """Abstract base class for problem-specific sensitivity analyzers"""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    @abstractmethod
    def get_problem_type(self) -> str:
        """Return the problem type this analyzer handles"""
        pass

    @abstractmethod
    def extract_variable_from_message(self, user_message: str, available_params: Dict) -> Tuple[Optional[str], Optional[float]]:
        """
        Extract which specific variable to analyze from natural language

        Args:
            user_message: User's request like "units produced at diego affects cost"
            available_params: Available parameters from the solved problem

        Returns:
            Tuple of (variable_name, original_value) or (None, None) if not found
        """
        pass

    @abstractmethod
    def get_supported_variable_types(self) -> Dict[str, Dict[str, Any]]:
        """
        Return supported variable types and their metadata

        Returns:
            Dict mapping variable types to their configuration:
            {
                "capacity": {
                    "synonyms": ["units produced", "production", "output"],
                    "entity_type": "plant",
                    "description": "Production capacity at plants"
                }
            }
        """
        pass

    @abstractmethod
    def format_variable_for_analysis(self, variable_type: str, entity_name: str) -> str:
        """
        Format a variable name for the analysis engine

        Args:
            variable_type: Type like "capacity", "demand", etc.
            entity_name: Specific entity like "seattle", "chicago"

        Returns:
            Formatted variable name like "capacity_seattle"
        """
        pass

    def get_variable_description(self, variable_name: str, original_value: float) -> str:
        """Generate human-readable description of the variable being analyzed"""
        return f"Variable: {variable_name} (original value: {original_value})"