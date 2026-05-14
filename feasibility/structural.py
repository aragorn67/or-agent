"""
Layer 0: Structural and sanity checks.

Fast, deterministic validation that catches extraction bugs:
- Empty sets
- Index consistency
- Dimension mismatches
- Domain validity (finite numbers, non-negative where required)

These checks are problem-agnostic and run before any domain-specific logic.
"""

import math
from typing import Any


def check_no_empty_sets(instance) -> tuple[bool, list[str]]:
    """
    Ensure all sets have at least one element.

    Empty sets usually indicate extraction errors or malformed problems.
    """
    messages = []
    sets = instance.sets if hasattr(instance, 'sets') else instance.get('sets', {})

    for set_name, set_values in sets.items():
        if not set_values or len(set_values) == 0:
            return False, [f"Set '{set_name}' is empty. Cannot build model with zero elements."]

    return True, messages


def check_index_consistency(instance) -> tuple[bool, list[str]]:
    """
    Verify all param indices reference valid set elements.

    For example, if cost[(i,j)] is defined, both i and j must exist
    in their respective sets.
    """
    messages = []
    sets = instance.sets if hasattr(instance, 'sets') else instance.get('sets', {})
    params = instance.params if hasattr(instance, 'params') else instance.get('params', {})

    # Get set names and values
    # Common patterns: I/J for bipartite, N for nodes, etc.
    set_values = {name: set(values) for name, values in sets.items()}

    # Check each param
    for param_name, param_data in params.items():
        if isinstance(param_data, dict):
            for key in param_data.keys():
                # Handle both single indices and tuples
                if isinstance(key, tuple):
                    indices = key
                else:
                    indices = (key,)

                # For now, we can't strictly validate without knowing which set
                # each index belongs to. We'll do basic checks:
                # - All indices should be strings or numbers
                # - None should be None or empty
                for idx in indices:
                    if idx is None or idx == '':
                        return False, [
                            f"Parameter '{param_name}' has invalid index: {key}. "
                            f"Found None or empty string."
                        ]

    return True, messages


def check_dimensions(instance) -> tuple[bool, list[str]]:
    """
    Verify matrix/array dimensions match set sizes.

    For transportation: cost matrix should have shape (|sources|, |sinks|)
    For scheduling: processing_time array length should match number of jobs
    """
    messages = []
    sets = instance.sets if hasattr(instance, 'sets') else instance.get('sets', {})
    params = instance.params if hasattr(instance, 'params') else instance.get('params', {})

    # Transportation-specific check
    if 'cost' in params and isinstance(params['cost'], dict):
        # Infer source and sink set names
        source_set_name = None
        sink_set_name = None

        for name in ['I', 'I_sources', 'I_plants', 'I_factories', 'I_mills', 'I_warehouses']:
            if name in sets:
                source_set_name = name
                break

        for name in ['J', 'J_sinks', 'J_markets', 'J_warehouses', 'J_stores', 'J_projects', 'J_centres']:
            if name in sets:
                sink_set_name = name
                break

        if source_set_name and sink_set_name:
            sources = sets[source_set_name]
            sinks = sets[sink_set_name]
            cost_matrix = params['cost']

            # Expected dimensions
            expected_size = len(sources) * len(sinks)

            # Check if we have costs for all (i,j) pairs
            cost_keys = set(cost_matrix.keys())
            expected_keys = {(i, j) for i in sources for j in sinks}

            missing_keys = expected_keys - cost_keys
            if missing_keys:
                # Get a sample of missing keys for error message
                sample = list(missing_keys)[:3]
                return False, [
                    f"Cost matrix dimension mismatch: "
                    f"Expected {len(sources)} sources × {len(sinks)} sinks = {expected_size} entries, "
                    f"but found {len(cost_matrix)} entries. "
                    f"Missing cost entries for: {sample}{'...' if len(missing_keys) > 3 else ''}"
                ]

    return True, messages


def check_domain_validity(instance) -> tuple[bool, list[str]]:
    """
    Check for finite numbers, non-negative values where required.

    Catches:
    - Infinite or NaN values
    - Negative processing times, capacities, demands
    - Other domain violations
    """
    messages = []
    params = instance.params if hasattr(instance, 'params') else instance.get('params', {})

    # Parameters that must be non-negative
    non_negative_params = [
        'supply', 'demand', 'capacity', 'cost',
        'processing_time', 'proc_time', 'due_date', 'release_date'
    ]

    for param_name in non_negative_params:
        if param_name not in params:
            continue

        param_data = params[param_name]

        # Handle dict parameters (flat or nested, e.g. processing_time[order][unit])
        if isinstance(param_data, dict):
            stack = [([str(k)], v) for k, v in param_data.items()]
            while stack:
                path, value = stack.pop()
                if isinstance(value, dict):
                    stack.extend(([*path, str(k)], v) for k, v in value.items())
                    continue
                key_str = "][".join(path)
                if not _is_valid_number(value):
                    return False, [
                        f"Parameter '{param_name}[{key_str}]' has invalid value: {value}. "
                        f"Must be a finite number."
                    ]
                if value < 0:
                    return False, [
                        f"Parameter '{param_name}[{key_str}]' is negative: {value}. "
                        f"This parameter must be non-negative."
                    ]

        # Handle list/array parameters
        elif isinstance(param_data, (list, tuple)):
            for i, value in enumerate(param_data):
                if not _is_valid_number(value):
                    return False, [
                        f"Parameter '{param_name}[{i}]' has invalid value: {value}. "
                        f"Must be a finite number."
                    ]
                if value < 0:
                    return False, [
                        f"Parameter '{param_name}[{i}]' is negative: {value}. "
                        f"This parameter must be non-negative."
                    ]

        # Handle scalar parameters
        elif isinstance(param_data, (int, float)):
            if not _is_valid_number(param_data):
                return False, [
                    f"Parameter '{param_name}' has invalid value: {param_data}. "
                    f"Must be a finite number."
                ]
            if param_data < 0:
                return False, [
                    f"Parameter '{param_name}' is negative: {param_data}. "
                    f"This parameter must be non-negative."
                ]

    return True, messages


def _is_valid_number(value: Any) -> bool:
    """Check if value is a finite number."""
    if not isinstance(value, (int, float)):
        return False
    if math.isnan(value) or math.isinf(value):
        return False
    return True


def structural_checks(instance) -> tuple[bool, list[str]]:
    """
    Run all Layer 0 structural checks.

    Returns:
        (ok, messages) where ok=True if all checks pass, messages contains
        diagnostic information (errors if ok=False, warnings if ok=True)
    """
    all_checks = [
        check_no_empty_sets,
        check_index_consistency,
        check_dimensions,
        check_domain_validity
    ]

    reasons = []
    for check in all_checks:
        ok, msgs = check(instance)
        if not ok:
            return False, msgs
        reasons.extend(msgs)

    return True, reasons


def generate_structural_suggestions(instance, error_messages: list[str]) -> list[str]:
    """
    Generate actionable suggestions based on structural errors.

    Args:
        instance: The problem instance
        error_messages: Error messages from structural_checks

    Returns:
        List of actionable suggestions for the user
    """
    suggestions = []

    for error_msg in error_messages:
        # Empty set errors
        if "is empty" in error_msg:
            set_name = error_msg.split("'")[1] if "'" in error_msg else "unknown"
            suggestions.append(
                f"Add at least one element to set '{set_name}'. "
                f"For example, if this is a source/factory set, provide at least one factory name."
            )

        # Dimension mismatch errors (missing cost entries)
        elif "Cost matrix dimension mismatch" in error_msg and "Missing cost entries" in error_msg:
            # Extract missing keys from error message
            sets = instance.sets if hasattr(instance, 'sets') else instance.get('sets', {})
            params = instance.params if hasattr(instance, 'params') else instance.get('params', {})

            # Find source and sink sets
            source_set_name = None
            sink_set_name = None
            for name in ['I', 'I_sources', 'I_plants', 'I_factories']:
                if name in sets:
                    source_set_name = name
                    break
            for name in ['J', 'J_sinks', 'J_markets', 'J_warehouses']:
                if name in sets:
                    sink_set_name = name
                    break

            if source_set_name and sink_set_name:
                sources = sets[source_set_name]
                sinks = sets[sink_set_name]
                cost_matrix = params.get('cost', {})

                missing_keys = {(i, j) for i in sources for j in sinks} - set(cost_matrix.keys())

                if missing_keys:
                    sample = list(missing_keys)[:3]
                    suggestions.append(
                        f"Add missing cost entries for all source-sink pairs. "
                        f"For example, add costs for: {', '.join([f'{i}→{j}' for i, j in sample])}"
                    )

                    # Be more specific about what to add
                    for src, snk in sample:
                        suggestions.append(
                            f"Specify the cost from '{src}' to '{snk}' "
                            f"(e.g., 'the shipping cost from {src} to {snk} is 10 dollars')"
                        )

        # Invalid index errors
        elif "has invalid index" in error_msg:
            param_name = error_msg.split("'")[1] if "'" in error_msg else "unknown"
            suggestions.append(
                f"Fix the indices for parameter '{param_name}'. "
                f"Ensure all indices are valid strings or numbers (not None or empty)."
            )

        # Invalid number errors (NaN, Inf)
        elif "has invalid value" in error_msg and "Must be a finite number" in error_msg:
            # Extract parameter name
            if "[" in error_msg:
                param_part = error_msg.split("'")[1]
                suggestions.append(
                    f"Replace the invalid value in '{param_part}' with a valid finite number. "
                    f"Check that all costs, capacities, and demands are properly specified."
                )
            else:
                suggestions.append(
                    f"Ensure all numeric values are finite numbers (not NaN or infinity)."
                )

        # Negative value errors
        elif "is negative" in error_msg and "must be non-negative" in error_msg:
            # Extract parameter name and value
            if "[" in error_msg:
                param_part = error_msg.split("'")[1]
                suggestions.append(
                    f"Change the negative value in '{param_part}' to a non-negative number. "
                    f"Capacities, demands, costs, and processing times cannot be negative."
                )
            else:
                suggestions.append(
                    f"Replace negative values with non-negative numbers (0 or positive)."
                )

    # If no specific suggestions were generated, provide a general one
    if not suggestions:
        suggestions.append(
            "Fix the structural issues mentioned above. "
            "Ensure all sets are non-empty, all parameters have valid indices and values."
        )

    return suggestions
