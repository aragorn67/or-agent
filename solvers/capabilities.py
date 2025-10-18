"""
Solver Capabilities Mapping

This file defines which solvers can handle which problem subcategories.
Each solver has a list of subcategories it supports.
"""

# Solver capabilities: maps solver name to list of supported subcategories
SOLVER_CAPABILITIES = {
    "transportation": {
        "description": "Standard transportation/distribution problems",
        "subcategories": [
            "standard_transportation",      # Classic supply-demand matching
            "distribution",                 # Multi-source to multi-destination
            "balanced_transportation",      # Supply = Demand
            "unbalanced_transportation",    # Supply != Demand (with dummy)
        ],
        "cannot_solve": [
            "transshipment",               # Intermediate nodes with storage
            "multi_commodity",             # Multiple product types
            "time_varying",                # Time-indexed transportation
        ]
    },

    "scheduling": {
        "description": "Single-stage continuous process scheduling (IPM model)",
        "subcategories": [
            "single_stage_scheduling",     # Orders on units, single processing step
            "batch_scheduling",            # Chemical batch processing
            "parallel_machine_simple",     # Parallel machines with eligibility
        ],
        "cannot_solve": [
            "job_shop",                    # Multi-stage with precedence between jobs
            "flow_shop",                   # Fixed sequence through machines
            "project_scheduling",          # Activities with complex precedence (PERT/CPM)
            "shift_rostering",             # Employee shift scheduling
            "resource_constrained",        # Multiple resource types
            "sequence_dependent_complex",  # Complex sequencing with multiple constraints
            "preemptive_scheduling",       # Jobs that can be interrupted
        ]
    },
}

# Problem type to subcategory mapping
# Maps broad problem types to their subcategories
PROBLEM_SUBCATEGORIES = {
    "scheduling": {
        # Solvable by current solver
        "single_stage_scheduling": "Single-stage orders on processing units",
        "batch_scheduling": "Chemical/pharmaceutical batch processing",
        "parallel_machine_simple": "Parallel machines with simple eligibility",

        # Not solvable by current solver
        "job_shop": "Multi-stage job shop with operation sequences",
        "flow_shop": "Jobs follow fixed machine sequence",
        "project_scheduling": "Project activities with precedence (PERT/CPM)",
        "shift_rostering": "Employee/nurse shift scheduling",
        "resource_constrained": "Tasks with multiple resource requirements",
        "single_machine_sequencing": "Single machine with sequence-dependent setups",
    },

    "transportation": {
        # Solvable by current solver
        "standard_transportation": "Classic factory-to-warehouse distribution",
        "distribution": "Multi-source multi-destination shipping",

        # Not solvable by current solver
        "transshipment": "With intermediate storage/transfer nodes",
        "multi_commodity": "Multiple product types with different costs",
    }
}


def get_solver_capabilities(solver_name: str) -> dict:
    """
    Get capabilities for a specific solver

    Returns:
        dict with 'subcategories' (list of solvable types) and 'cannot_solve' (list of unsolvable types)
    """
    return SOLVER_CAPABILITIES.get(solver_name, {
        "description": "Unknown solver",
        "subcategories": [],
        "cannot_solve": []
    })


def can_solver_handle(solver_name: str, subcategory: str) -> bool:
    """
    Check if a solver can handle a specific problem subcategory

    Args:
        solver_name: Name of the solver (e.g., "scheduling", "transportation")
        subcategory: Problem subcategory (e.g., "job_shop", "single_stage_scheduling")

    Returns:
        True if solver can handle this subcategory, False otherwise
    """
    capabilities = get_solver_capabilities(solver_name)
    return subcategory in capabilities.get("subcategories", [])


def get_subcategory_description(problem_type: str, subcategory: str) -> str:
    """
    Get human-readable description of a problem subcategory

    Args:
        problem_type: Broad problem type (e.g., "scheduling")
        subcategory: Specific subcategory (e.g., "job_shop")

    Returns:
        Description string
    """
    return PROBLEM_SUBCATEGORIES.get(problem_type, {}).get(
        subcategory,
        "Unknown subcategory"
    )


def get_available_subcategories(problem_type: str) -> dict:
    """
    Get all known subcategories for a problem type

    Returns:
        Dict mapping subcategory name to description
    """
    return PROBLEM_SUBCATEGORIES.get(problem_type, {})
