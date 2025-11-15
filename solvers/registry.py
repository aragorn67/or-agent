# solvers/registry.py
"""
Solver Registry - Maps solver_id to concrete solver implementations.

The LLM classifier predicts a solver_id (e.g., "transport_basic_bipartite"),
and this registry returns the appropriate solver instance.

Usage:
    from solvers.registry import get_solver

    solver_id = "transport_basic_bipartite"
    solver = get_solver(solver_id)
    result = solver.solve(params)
"""

from typing import Dict, List, Optional
from .base import OptimizationSolver
from .transport.bipartite import BipartiteTransportSolver
from .scheduling.single_stage_ipm import SingleStageIPMSolver


# ============================================================================
# SOLVER REGISTRY
# ============================================================================

_SOLVER_REGISTRY: Dict[str, OptimizationSolver] = {}


def _initialize_registry():
    """Initialize the solver registry with all available solvers."""
    global _SOLVER_REGISTRY

    # Register transportation solvers
    bipartite_transport = BipartiteTransportSolver()
    _SOLVER_REGISTRY[bipartite_transport.solver_id] = bipartite_transport

    # Register scheduling solvers
    single_stage_ipm = SingleStageIPMSolver()
    _SOLVER_REGISTRY[single_stage_ipm.solver_id] = single_stage_ipm

    # Future solvers can be registered here:
    # min_cost_flow = MinCostFlowSolver()
    # _SOLVER_REGISTRY[min_cost_flow.solver_id] = min_cost_flow


# Initialize on module import
_initialize_registry()


# ============================================================================
# PUBLIC API
# ============================================================================

def get_solver(solver_id: str) -> OptimizationSolver:
    """
    Get solver instance by solver_id.

    Args:
        solver_id: Unique solver identifier (e.g., "transport_basic_bipartite")

    Returns:
        OptimizationSolver instance

    Raises:
        ValueError: If solver_id is not registered
    """
    if solver_id not in _SOLVER_REGISTRY:
        available = list(_SOLVER_REGISTRY.keys())
        raise ValueError(
            f"Unsupported solver_id: '{solver_id}'\n"
            f"Available solvers: {available}"
        )
    return _SOLVER_REGISTRY[solver_id]


def list_solvers() -> List[Dict[str, str]]:
    """
    List all registered solvers with their metadata.

    Returns:
        List of dicts with solver_id, problem_type, and description
    """
    return [
        {
            "solver_id": solver.solver_id,
            "problem_type": solver.problem_type,
            "description": solver.description
        }
        for solver in _SOLVER_REGISTRY.values()
    ]


def get_solver_by_category(category: str) -> List[OptimizationSolver]:
    """
    Get all solvers that handle a given problem category.

    Args:
        category: Problem category (e.g., "transportation", "scheduling")

    Returns:
        List of OptimizationSolver instances for that category
    """
    return [
        solver for solver in _SOLVER_REGISTRY.values()
        if solver.problem_type.lower() == category.lower()
    ]


def solver_exists(solver_id: str) -> bool:
    """Check if a solver_id is registered."""
    return solver_id in _SOLVER_REGISTRY


# ============================================================================
# SOLVER FAMILY MAPPING (for backward compatibility & classification)
# ============================================================================

def get_solver_family(expected_type: str) -> Optional[str]:
    """
    Map fine-grained OR problem types to solver families.

    This bridges the gap between OR taxonomy (expected_type)
    and what our solvers can actually handle (solver_id).

    Args:
        expected_type: Fine-grained OR problem type
                      (e.g., "transportation", "min_cost_flow",
                       "single_stage_scheduling", "job_shop")

    Returns:
        solver_id if we have a solver for it, None otherwise

    Examples:
        get_solver_family("transportation") -> "transport_basic_bipartite"
        get_solver_family("min_cost_flow") -> "transport_basic_bipartite" (if bipartite)
        get_solver_family("job_shop") -> None (not yet implemented)
    """
    # Normalize to lowercase
    t = expected_type.lower().strip()

    # Transportation family
    if t in ["transportation", "transport_basic", "bipartite_transport"]:
        return "transport_basic_bipartite"

    # Min-cost flow: ONLY map to bipartite if it's truly plant->market
    # For now, we DON'T auto-map min_cost_flow -> bipartite
    # (classification should explicitly choose bipartite if appropriate)
    # if t == "min_cost_flow":
    #     return "transport_basic_bipartite"  # only if problem fits!

    # Scheduling family
    if t in ["single_stage_scheduling", "single_machine_tardiness", "single_stage"]:
        return "single_stage_ipm_scheduling"

    # Job shop: not yet implemented
    if t == "job_shop":
        return None

    # Unknown
    return None


def get_default_solver_for_category(category: str) -> Optional[str]:
    """
    Get the default solver_id for a given category.

    Args:
        category: Problem category (e.g., "transportation")

    Returns:
        solver_id of the default solver for that category, or None
    """
    defaults = {
        "transportation": "transport_basic_bipartite",
        "scheduling": "single_stage_ipm_scheduling",
    }
    return defaults.get(category.lower())


# ============================================================================
# DEBUGGING / INTROSPECTION
# ============================================================================

def print_registry():
    """Print all registered solvers (for debugging)."""
    print("\n" + "="*80)
    print("REGISTERED SOLVERS")
    print("="*80)
    for solver_id, solver in _SOLVER_REGISTRY.items():
        print(f"\n  solver_id: {solver_id}")
        print(f"  category:  {solver.problem_type}")
        print(f"  desc:      {solver.description}")
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    # Quick test
    print_registry()
    print("\nSolver family mappings:")
    print(f"  transportation -> {get_solver_family('transportation')}")
    print(f"  single_stage_scheduling -> {get_solver_family('single_stage_scheduling')}")
    print(f"  min_cost_flow -> {get_solver_family('min_cost_flow')}")
    print(f"  job_shop -> {get_solver_family('job_shop')}")
