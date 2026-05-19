"""
FeasibilityPlugin contract + the fail-closed Layer-2 guarantee.

Regression net for the scheduling bug class: a domain must not be
half-wired, and the stack must NEVER assert FEASIBLE from Layer-2
ignorance (the old `UNKNOWN -> FEASIBLE` default).
"""

import copy
import pytest

from feasibility import check_feasibility, FeasStatus
from feasibility.plugins import (
    FeasibilityPlugin,
    resolve_plugin,
    registered_plugins,
)
from feasibility.problem_specific import problem_specific_checks
from feasibility.schemas import ParsedInstance


# ---- plugin contract -------------------------------------------------------

def test_half_wired_plugin_is_a_construction_error():
    """Forgetting the suggester (or checker) must fail at construction,
    not silently fall back to another domain's advice at runtime."""
    with pytest.raises(TypeError):
        FeasibilityPlugin(
            name="broken", match_tokens=("X",),
            checker=lambda i: (True, []), suggester=None,  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        FeasibilityPlugin(
            name="broken", match_tokens=(),  # no tokens
            checker=lambda i: (True, []), suggester=lambda i, m: [],
        )


def test_builtin_domains_registered_with_both_halves():
    by_name = {p.name: p for p in registered_plugins()}
    assert {"transportation", "single_stage_scheduling"} <= set(by_name)
    for p in by_name.values():
        assert callable(p.checker) and callable(p.suggester)


@pytest.mark.parametrize("ptype,expected", [
    ("TRANSPORTATION", "transportation"),
    ("transportation", "transportation"),
    ("SINGLE_STAGE_SCHEDULING", "single_stage_scheduling"),
    ("single_stage_scheduling", "single_stage_scheduling"),
    ("SINGLE_MACHINE_MAKESPAN", "single_stage_scheduling"),
    ("KNAPSACK", None),
    ("", None),
])
def test_resolution_exact_substring_and_miss(ptype, expected):
    plugin = resolve_plugin(ptype)
    assert (plugin.name if plugin else None) == expected


# ---- fail-closed Layer 2 ---------------------------------------------------

def test_unknown_domain_does_not_assert_feasible():
    """No Layer-1 plugin + no solver for the domain => Layer 2 is
    inconclusive. The verdict must be UNKNOWN, never FEASIBLE."""
    inst = ParsedInstance(
        problem_type="KNAPSACK",            # no plugin, no solver
        solver_id="none",
        sets={"items": ["a", "b"]},
        params={"value": {"a": 1}, "weight": {"a": 1}, "capacity": 1},
    )
    report = check_feasibility(inst)
    assert report.status == FeasStatus.UNKNOWN
    assert report.status != FeasStatus.FEASIBLE
    assert any("not validated" in r.lower() or "inconclusive" in r.lower()
               for r in report.reasons)


def test_transport_still_feasible_end_to_end():
    """The Layer-2-conclusive happy path is untouched by the refactor."""
    inst = ParsedInstance(
        problem_type="TRANSPORTATION",
        solver_id="transport_basic_bipartite",
        sets={"I": ["P1", "P2"], "J": ["M1", "M2"]},
        params={
            "supply": {"P1": 100, "P2": 100},
            "demand": {"M1": 80, "M2": 80},
            "cost": {("P1", "M1"): 2, ("P1", "M2"): 3,
                     ("P2", "M1"): 4, ("P2", "M2"): 1},
        },
    )
    assert check_feasibility(inst).status == FeasStatus.FEASIBLE


def test_infeasible_scheduling_uses_its_own_suggester_not_transports():
    """Plugin bundling: an infeasible schedule gets scheduling advice
    (deadline/eligible-unit), never transport's 'increase supply'."""
    base = {
        "orders": ["OrderA", "OrderC"],
        "units": ["U1"],
        "processing_time": {"OrderA": {"U1": 2.0}, "OrderC": {"U1": 5.0}},
        "due_date": {"OrderA": 10.0, "OrderC": 4.0},   # OrderC needs >= 5 h
        "eligible": {"OrderA": ["U1"], "OrderC": ["U1"]},
    }
    inst = ParsedInstance(
        problem_type="SINGLE_STAGE_SCHEDULING",
        solver_id="single_stage_ipm_scheduling",
        sets={}, params=copy.deepcopy(base),
    )
    report = check_feasibility(inst)
    assert report.status == FeasStatus.INFEASIBLE
    assert report.layer_passed <= 1
    blob = " ".join(report.suggestions or []).lower()
    assert "supply" not in blob and "demand" not in blob
    assert "deadline" in blob or "faster" in blob or "eligible" in blob


def test_unknown_problem_type_layer1_shim_is_not_a_pass_claim():
    ok, msgs = problem_specific_checks(
        ParsedInstance(problem_type="VRP", solver_id="none",
                       sets={}, params={})
    )
    assert ok is True  # Layer 0 alone must not block
    assert any("no layer 1 plugin" in m.lower() for m in msgs)
