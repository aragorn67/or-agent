# solvers/__init__.py
"""
Solvers package - provides access to all optimization solvers via registry.

NEW ARCHITECTURE:
    - Use solver_id (specific variant) instead of problem_type (category)
    - Registry maps solver_id -> solver instance
    - Old get_solver(problem_type) still works for backward compatibility

USAGE:
    from solvers.registry import get_solver

    solver = get_solver("transport_basic_bipartite")
    result = solver.solve(params)
"""

from .base import OptimizationSolver
from .registry import (
    get_solver,
    list_solvers,
    get_solver_by_category,
    solver_exists,
    get_solver_family,
    get_default_solver_for_category
)

# Re-export key components
__all__ = [
    'OptimizationSolver',
    'get_solver',
    'list_solvers',
    'get_solver_by_category',
    'solver_exists',
    'get_solver_family',
    'get_default_solver_for_category',
]


# Backward compatibility: old get_solver(problem_type)
# Maps problem_type (category) to default solver_id
def _get_solver_by_category_compat(problem_type: str) -> OptimizationSolver:
    """
    DEPRECATED: Backward compatibility for get_solver(problem_type).

    Use get_solver(solver_id) instead.
    """
    # Map old problem_type (category) to default solver_id
    solver_id = get_default_solver_for_category(problem_type)
    if solver_id is None:
        raise ValueError(f"Unknown problem type: {problem_type}")
    return get_solver(solver_id)


def list_problem_types() -> list:
    """
    DEPRECATED: List problem categories (for backward compatibility).

    Use list_solvers() instead.
    """
    return ["transportation", "scheduling"]