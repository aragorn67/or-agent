# solvers/base.py
"""
Base classes and interfaces for optimization solvers.

Each solver variant should:
1. Inherit from OptimizationSolver
2. Implement solve() method
3. Define solver_id, problem_type, and description
4. Provide validate_params() and get_example_params()
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class OptimizationSolver(ABC):
    """
    Abstract base class for all optimization solvers.

    Each concrete solver represents a specific mathematical formulation
    for a particular problem structure (e.g., bipartite transportation,
    single-stage scheduling with immediate precedence, etc.)
    """

    @property
    @abstractmethod
    def solver_id(self) -> str:
        """
        Unique identifier for this solver variant.

        Examples:
            - "transport_basic_bipartite"
            - "single_stage_ipm_scheduling"
            - "min_cost_flow_network"

        This is what the LLM classifier should predict.
        """
        pass

    @property
    @abstractmethod
    def problem_type(self) -> str:
        """
        OR problem category this solver handles.

        Examples: "transportation", "scheduling", "assignment"
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this solver handles."""
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