"""
Layer 1: Problem-specific necessary condition checks.

Dispatches to the appropriate checker based on problem_type.
Uses a registry pattern for easy expansion.
"""

from .transport import transport_checks


# Registry mapping problem_type to checker function
PROBLEM_TYPE_CHECKERS = {
    "TRANSPORTATION": transport_checks,
    "transportation": transport_checks,  # Support both cases
    # Future additions:
    # "SINGLE_MACHINE_SCHEDULING": scheduling_checks,
    # "ASSIGNMENT": assignment_checks,
}


def problem_specific_checks(instance) -> tuple[bool, list[str]]:
    """
    Run problem-specific Layer 1 checks based on problem_type.

    Args:
        instance: Problem instance with problem_type field

    Returns:
        (ok, messages) tuple where ok=True if checks pass

    Example:
        >>> ok, msgs = problem_specific_checks(transport_instance)
        >>> if not ok:
        ...     print("Infeasible:", msgs)
    """
    # Get problem type
    problem_type = None
    if hasattr(instance, 'problem_type'):
        problem_type = instance.problem_type
    elif isinstance(instance, dict):
        problem_type = instance.get('problem_type', '')

    if not problem_type:
        return True, ["No problem_type specified, skipping problem-specific checks"]

    # Look up checker
    checker = PROBLEM_TYPE_CHECKERS.get(problem_type)

    if checker:
        return checker(instance)
    else:
        # No specific checker for this problem type
        return True, [f"No specific Layer 1 checks implemented for problem type '{problem_type}'"]
