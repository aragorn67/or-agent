"""
Core feasibility checking orchestration.

This module provides the main check_feasibility() function that coordinates
all three layers of validation:
- Layer 0: Structural/sanity checks
- Layer 1: Problem-specific necessary conditions
- Layer 2: Solver-based feasibility (LP relaxation)
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class FeasStatus(str, Enum):
    """Feasibility status enumeration."""
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"


@dataclass
class FeasibilityReport:
    """
    Result of feasibility checking.

    Attributes:
        status: Overall feasibility status
        reasons: Human-readable explanations of checks performed/failed
        layer_passed: Highest validation layer passed (0, 1, or 2)
        suggestions: Optional fix suggestions for infeasible instances
    """
    status: FeasStatus
    reasons: list[str]
    layer_passed: int  # 0, 1, or 2 (debugging aid)
    suggestions: Optional[list[str]] = None


def check_feasibility(instance) -> FeasibilityReport:
    """
    Main orchestration function for feasibility checking.

    Runs three layers of validation:
    1. Structural checks (pure Python, fast)
    2. Problem-specific necessary conditions (domain knowledge)
    3. Solver-based feasibility (LP relaxation) - Phase 2

    Args:
        instance: ParsedInstance or dict with problem data

    Returns:
        FeasibilityReport with status and diagnostic information

    Example:
        >>> report = check_feasibility(instance)
        >>> if report.status == FeasStatus.INFEASIBLE:
        ...     print("Problem is infeasible:", report.reasons)
    """
    from .structural import structural_checks, generate_structural_suggestions
    from .problem_specific import problem_specific_checks
    from .solver_based import solver_feasibility_check, generate_solver_suggestions

    reasons = []

    # Layer 0: Structural checks
    ok0, msg0 = structural_checks(instance)
    if not ok0:
        suggestions = generate_structural_suggestions(instance, msg0)
        return FeasibilityReport(
            status=FeasStatus.INFEASIBLE,
            reasons=msg0,
            layer_passed=0,
            suggestions=suggestions
        )
    reasons.extend(msg0)

    # Layer 1: Problem-specific necessary conditions
    ok1, msg1 = problem_specific_checks(instance)
    if not ok1:
        # Generate problem-specific suggestions
        from .problem_specific.transport import generate_transport_suggestions
        suggestions = generate_transport_suggestions(instance, msg1)
        return FeasibilityReport(
            status=FeasStatus.INFEASIBLE,
            reasons=reasons + msg1,
            layer_passed=1,
            suggestions=suggestions
        )
    reasons.extend(msg1)

    # Layer 2: Solver-based feasibility (LP relaxation + slacks)
    status2, details2 = solver_feasibility_check(instance)

    if status2 == "INFEASIBLE":
        suggestions = generate_solver_suggestions(instance, details2)
        return FeasibilityReport(
            status=FeasStatus.INFEASIBLE,
            reasons=reasons + [f"Solver-based check failed: {details2.get('reason', 'LP relaxation infeasible')}"],
            layer_passed=2,
            suggestions=suggestions
        )
    elif status2 == "UNKNOWN":
        # Layer 2 inconclusive, but Layers 0 and 1 passed
        reasons.append(f"Layer 2 check inconclusive: {details2.get('reason', 'Unknown')}")
        return FeasibilityReport(
            status=FeasStatus.FEASIBLE,  # Assume feasible if Layer 0+1 pass
            reasons=reasons,
            layer_passed=1
        )

    # All layers passed!
    reasons.append(f"Solver-based check passed (LP relaxation found feasible solution)")
    return FeasibilityReport(
        status=FeasStatus.FEASIBLE,
        reasons=reasons,
        layer_passed=2
    )
