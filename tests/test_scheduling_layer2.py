"""
Genuine Layer-2 (solver-based) feasibility for scheduling.

Before this work scheduling had no real Layer 2 — `solver_based.py`
bailed to UNKNOWN ("solver does not expose build_model") and the
verdict rested on Layers 0+1 + the solver backstop. Factoring
`build_model` out of the scheduling solver + a domain-aware Layer-2
converter makes Layer 2 conclusive for scheduling, the same as
transport. These tests pin that and guard the build_model extraction.
"""

import copy
import pytest

from analysis.instance_builder import build_instance_from_params
from feasibility import check_feasibility, FeasStatus
from feasibility.solver_based import solver_feasibility_check
from feasibility.schemas import ParsedInstance
from solvers.scheduling.single_stage_ipm import SingleStageIPMSolver


SID = "single_stage_ipm_scheduling"

FEASIBLE = {
    "orders": ["A", "B"], "units": ["U1"],
    "processing_time": {"A": {"U1": 2.0}, "B": {"U1": 3.0}},
    "due_date": {"A": 10.0, "B": 10.0},
    "eligible": {"A": ["U1"], "B": ["U1"]},
}


# ---- Part A: build_model extraction is behaviour-preserving ---------------

def test_build_model_returns_a_model_with_objective():
    m = SingleStageIPMSolver().build_model(FEASIBLE)
    assert hasattr(m, "OBJ") and hasattr(m, "Y") and hasattr(m, "Cmax")


def test_solve_unchanged_after_extraction():
    """A→2h then B→3h on the one unit ⇒ makespan 5."""
    r = SingleStageIPMSolver().solve(copy.deepcopy(FEASIBLE))
    assert r["status"] == "OPTIMAL"
    assert r["Cmax"] == 5.0


def test_build_model_raises_on_invalid_params():
    with pytest.raises(ValueError):
        SingleStageIPMSolver().build_model({"orders": ["A"]})  # missing keys


# ---- LP relaxation un-stubbed (was NOT_IMPLEMENTED) ----------------------

def test_lp_relaxation_is_a_valid_lower_bound():
    out = SingleStageIPMSolver().solve_lp_relaxation(copy.deepcopy(FEASIBLE))
    assert out["status"] == "OPTIMAL"
    assert out["bound"] is not None
    # Relaxed optimum must not exceed the exact makespan (5.0).
    assert 0.0 <= out["bound"] <= 5.0 + 1e-6


# ---- Part B: Layer 2 is now conclusive for scheduling --------------------

def test_feasible_schedule_is_conclusive_at_layer2():
    inst = build_instance_from_params(FEASIBLE, "SINGLE_STAGE_SCHEDULING", SID)
    status, _ = solver_feasibility_check(inst)
    assert status == "FEASIBLE"          # was "UNKNOWN"

    report = check_feasibility(inst)
    assert report.status == FeasStatus.FEASIBLE
    assert report.layer_passed == 2      # genuinely reached Layer 2


def test_layer2_catches_what_layer1_cannot():
    """Each order alone meets its 4 h deadline (Layer 1 passes: 3 <= 4),
    but two 3 h orders on the single unit cannot both finish by hour 4 —
    only the solver-based layer can see that."""
    hard = copy.deepcopy(FEASIBLE)
    hard["processing_time"] = {"A": {"U1": 3.0}, "B": {"U1": 3.0}}
    hard["due_date"] = {"A": 4.0, "B": 4.0}
    inst = build_instance_from_params(hard, "SINGLE_STAGE_SCHEDULING", SID)
    report = check_feasibility(inst)
    assert report.status == FeasStatus.INFEASIBLE
    assert report.layer_passed == 2


# ---- Regressions: transport unchanged, fail-closed intact ----------------

def test_transport_layer2_still_conclusive():
    inst = ParsedInstance(
        problem_type="TRANSPORTATION", solver_id="transport_basic_bipartite",
        sets={"I": ["P1"], "J": ["M1"]},
        params={"supply": {"P1": 50}, "demand": {"M1": 50},
                "cost": {("P1", "M1"): 1.0}},
    )
    assert check_feasibility(inst).status == FeasStatus.FEASIBLE


def test_domain_without_a_solver_still_fails_closed():
    """Part B must not reopen the fail-open seam: a domain with no
    solver/build_model is still honestly UNKNOWN, never FEASIBLE."""
    inst = ParsedInstance(
        problem_type="KNAPSACK", solver_id="none",
        sets={"items": ["a"]}, params={"value": {"a": 1}},
    )
    assert check_feasibility(inst).status == FeasStatus.UNKNOWN
