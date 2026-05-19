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
    from .problem_specific import resolve_plugin
    from .solver_based import solver_feasibility_check, generate_solver_suggestions

    reasons = []

    # Layer 0: Structural checks (domain-agnostic).
    ok0, msg0 = structural_checks(instance)
    if not ok0:
        return FeasibilityReport(
            status=FeasStatus.INFEASIBLE,
            reasons=msg0,
            layer_passed=0,
            suggestions=generate_structural_suggestions(instance, msg0),
        )
    reasons.extend(msg0)

    # Layer 1: Problem-specific necessary conditions.
    #
    # Checker AND suggester now come from the SAME resolved plugin — no
    # more `if "SCHEDUL" else transport` dispatch that handed transport's
    # "increase supply" advice to an infeasible schedule. `plugin is None`
    # means this domain has NO Layer-1 check: that is "not validated", NOT
    # "validated feasible", and is remembered for the Layer-2 verdict.
    ptype = (
        getattr(instance, 'problem_type', None)
        or (instance.get('problem_type', '') if isinstance(instance, dict) else '')
    )
    plugin = resolve_plugin(ptype)

    if plugin is not None:
        ok1, msg1 = plugin.checker(instance)
        if not ok1:
            return FeasibilityReport(
                status=FeasStatus.INFEASIBLE,
                reasons=reasons + msg1,
                layer_passed=1,
                suggestions=plugin.suggester(instance, msg1),
            )
        reasons.extend(msg1)
    else:
        reasons.append(
            f"No Layer 1 plugin for problem type '{ptype}' — necessary "
            f"conditions NOT validated for this domain"
        )

    # Layer 2: Solver-based feasibility (LP relaxation).
    status2, details2 = solver_feasibility_check(instance)

    if status2 == "INFEASIBLE":
        return FeasibilityReport(
            status=FeasStatus.INFEASIBLE,
            reasons=reasons + [
                f"Solver-based check failed: "
                f"{details2.get('reason', 'LP relaxation infeasible')}"
            ],
            layer_passed=2,
            suggestions=generate_solver_suggestions(instance, details2),
        )

    if status2 == "FEASIBLE":
        reasons.append("Solver-based check passed (LP relaxation found a feasible solution)")
        return FeasibilityReport(
            status=FeasStatus.FEASIBLE,
            reasons=reasons,
            layer_passed=2,
        )

    # status2 == "UNKNOWN" — the solver was inconclusive (no solver for
    # this domain, build/convert error, presolver "other", …).
    #
    # FAIL CLOSED. The old code asserted FEASIBLE here "if Layer 0+1 pass"
    # — a latent false-feasible for every domain without a Layer-1 plugin
    # (the scheduling bug class). We never assert feasibility from
    # ignorance: surface UNKNOWN honestly and let the real solver — now
    # hardened to fail soft with a clean INFEASIBLE — be the backstop
    # downstream. Callers gate on INFEASIBLE (block) and treat UNKNOWN as
    # "proceed, the solver decides".
    reasons.append(f"Layer 2 inconclusive: {details2.get('reason', 'unknown')}")
    return FeasibilityReport(
        status=FeasStatus.UNKNOWN,
        reasons=reasons,
        layer_passed=(1 if plugin is not None else 0),
    )
