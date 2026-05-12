"""
Generic Instance Builder for Analysis Framework

Dynamically builds ParsedInstance objects from parameter dicts,
making the analysis framework work with ANY problem type.
"""

from typing import Dict, Any, List


# Mapping from common parameter names to solver-expected names
# This handles cases where user params have different names than solver expects
PARAM_NAME_MAPPINGS = {
    # Transportation
    "capacity": "supply",  # User says "capacity", solver expects "supply"
    "plants": "I_plants",
    "factories": "I_plants",
    "sources": "I_plants",
    "markets": "J_markets",
    "warehouses": "J_markets",
    "customers": "J_markets",
    "destinations": "J_markets",

    # Scheduling
    "jobs": "I_jobs",
    "tasks": "I_jobs",
    "machines": "J_machines",
    "processors": "J_machines",
    "resources": "J_machines",

    # Knapsack
    "items": "I_items",
    "objects": "I_items",

    # Assignment
    "workers": "I_workers",
    "agents": "I_workers",
    "employees": "I_workers",
    "projects": "J_projects",

    # Facility Location
    "facilities": "I_facilities",
    "sites": "I_facilities",
    "demand_points": "J_customers",

    # Network Flow
    "nodes": "I_nodes",
    "vertices": "I_nodes",
    "arcs": "arcs",
    "edges": "arcs",
}


def build_instance_from_params(
    params: Dict[str, Any],
    problem_type: str,
    solver_id: str
) -> Dict[str, Any]:
    """
    Dynamically build a ParsedInstance from ANY params dict.

    Works by:
    1. Auto-detecting sets (lists in params)
    2. Auto-detecting parameters (dicts/numbers in params)
    3. Mapping param names based on problem_type conventions
    4. Flattening nested dicts for solver compatibility

    Args:
        params: Problem parameters (e.g., {'plants': [...], 'capacity': {...}, 'cost': {...}})
        problem_type: Problem type string (e.g., 'TRANSPORTATION', 'SCHEDULING')
        solver_id: Solver identifier (e.g., 'transport_basic_bipartite')

    Returns:
        Instance dict with:
        - problem_type: str
        - solver_id: str
        - sets: Dict[str, List]
        - params: Dict[str, Any]

    Examples:
        Transportation:
        >>> params = {'plants': ['P1', 'P2'], 'markets': ['M1', 'M2'],
        ...           'capacity': {'P1': 100}, 'demand': {'M1': 50}}
        >>> build_instance_from_params(params, 'TRANSPORTATION', 'transport_basic_bipartite')
        {
            'problem_type': 'TRANSPORTATION',
            'solver_id': 'transport_basic_bipartite',
            'sets': {'I_plants': ['P1', 'P2'], 'J_markets': ['M1', 'M2']},
            'params': {'supply': {'P1': 100}, 'demand': {'M1': 50}, ...}
        }

        Scheduling:
        >>> params = {'jobs': ['J1', 'J2'], 'machines': ['M1', 'M2'],
        ...           'processing_time': {'J1': 10}, 'due_date': {'J1': 50}}
        >>> build_instance_from_params(params, 'SCHEDULING', 'single_stage_ipm_scheduling')
        {
            'problem_type': 'SCHEDULING',
            'solver_id': 'single_stage_ipm_scheduling',
            'sets': {'I_jobs': ['J1', 'J2'], 'J_machines': ['M1', 'M2']},
            'params': {'processing_time': {'J1': 10}, 'due_date': {'J1': 50}}
        }
    """

    sets = {}
    instance_params = {}

    # Step 1: Auto-detect sets (lists of entities)
    for key, value in params.items():
        if isinstance(value, list) and value:
            # This is a set (plants, jobs, items, machines, etc.)
            mapped_name = _map_set_name(key, problem_type)
            sets[mapped_name] = value

    # Step 2: Auto-detect parameters (dicts/numbers)
    for key, value in params.items():
        if isinstance(value, dict):
            # Check if this is a nested dict (like cost matrix)
            if _is_nested_dict(value):
                # Flatten nested dict: {i: {j: val}} → {(i,j): val}
                instance_params[key] = _flatten_nested_dict(value)
            else:
                # Simple dict: {entity: value}
                # Map parameter name if needed
                mapped_name = PARAM_NAME_MAPPINGS.get(key, key)
                instance_params[mapped_name] = value
        elif isinstance(value, (int, float)):
            # Scalar parameter
            instance_params[key] = value
        # Skip lists (those are sets, already handled)

    return {
        'problem_type': problem_type,
        'solver_id': solver_id,
        'sets': sets,
        'params': instance_params
    }


def _map_set_name(set_name: str, problem_type: str) -> str:
    """
    Map a set name to solver-expected format.

    Follows OR naming conventions:
    - Source sets: I_* (I_plants, I_jobs, I_workers, etc.)
    - Sink/resource sets: J_* (J_markets, J_machines, J_tasks, etc.)

    Args:
        set_name: Original set name (e.g., 'plants', 'jobs')
        problem_type: Problem type for context

    Returns:
        Mapped set name (e.g., 'I_plants', 'I_jobs')
    """
    # Check if there's an explicit mapping
    if set_name in PARAM_NAME_MAPPINGS:
        return PARAM_NAME_MAPPINGS[set_name]

    # Otherwise, infer from problem type and set name
    # Source entities typically get I_* prefix
    # Sink/resource entities get J_* prefix

    # Common source entities
    if set_name in ['plants', 'factories', 'sources', 'jobs', 'tasks', 'items',
                     'workers', 'agents', 'facilities', 'vehicles', 'assets']:
        return f"I_{set_name}"

    # Common sink/resource entities
    if set_name in ['markets', 'warehouses', 'customers', 'destinations',
                     'machines', 'processors', 'resources', 'projects', 'locations']:
        return f"J_{set_name}"

    # Default: prefix with I_
    return f"I_{set_name}"


def _is_nested_dict(d: dict) -> bool:
    """
    Check if a dictionary is nested (contains dicts as values).

    Args:
        d: Dictionary to check

    Returns:
        True if nested, False otherwise
    """
    if not d:
        return False

    # Check first value
    first_value = next(iter(d.values()))
    return isinstance(first_value, dict)


def _flatten_nested_dict(nested: dict) -> dict:
    """
    Flatten a nested dictionary.

    Converts {i: {j: val}} to {(i, j): val}

    Args:
        nested: Nested dictionary

    Returns:
        Flattened dictionary with tuple keys
    """
    flat = {}
    for outer_key, inner_dict in nested.items():
        if isinstance(inner_dict, dict):
            for inner_key, value in inner_dict.items():
                flat[(outer_key, inner_key)] = value
    return flat


# EXTENSION GUIDE:
# ================
# To support a new problem type:
#
# 1. Add set name mappings to PARAM_NAME_MAPPINGS if needed
#    Example for bin packing:
#    "bins": "I_bins",
#    "containers": "I_bins",
#
# 2. Add parameter name mappings if your solver expects different names
#    Example:
#    "bin_size": "capacity",
#
# 3. That's it! The builder will automatically handle the new problem type.
#
# 4. Test with:
#    params = {'bins': ['B1', 'B2'], 'items': ['I1', 'I2'], 'bin_capacity': {...}}
#    instance = build_instance_from_params(params, 'BIN_PACKING', 'bin_packing_solver')
