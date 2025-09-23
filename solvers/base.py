# solvers/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class OptimizationSolver(ABC):
    """Base class for all optimization solvers"""

    @property
    @abstractmethod
    def problem_type(self) -> str:
        """Unique identifier for this problem type"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of problem type"""
        pass

    @abstractmethod
    def solve(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Solve the optimization problem"""
        pass

    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        """Return list of validation errors (empty = valid)"""
        pass

    @abstractmethod
    def get_example_params(self) -> Dict[str, Any]:
        """Return example parameters for this problem type"""
        pass