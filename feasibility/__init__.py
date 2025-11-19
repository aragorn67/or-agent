"""
Feasibility Checking Module

Provides three-layer validation for OR problem instances:
- Layer 0: Structural/sanity checks (fast, deterministic)
- Layer 1: Problem-specific necessary conditions (domain knowledge)
- Layer 2: Solver-based feasibility (LP relaxation)

Main entry point:
    from feasibility import check_feasibility, FeasStatus

    report = check_feasibility(instance)
    if report.status == FeasStatus.INFEASIBLE:
        print(report.reasons)
"""

from .core import check_feasibility, FeasibilityReport, FeasStatus

__all__ = [
    'check_feasibility',
    'FeasibilityReport',
    'FeasStatus'
]
