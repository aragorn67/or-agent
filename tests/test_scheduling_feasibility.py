"""
Layer-1 scheduling feasibility checks.

Before this, the feasibility registry was transport-only: an infeasible
schedule (deadline shorter than the order's fastest processing time)
passed the gate and the solver raised a raw HiGHS exception surfaced as
"Analysis failed: <pyomo internals>" — no explanation. These tests pin
the necessary-condition check via the real instance-builder path.
"""

import copy

from analysis.instance_builder import build_instance_from_params
from feasibility.core import check_feasibility, FeasStatus
from feasibility.problem_specific import problem_specific_checks


BASE = {
    "orders": ["OrderA", "OrderB", "OrderC", "OrderD"],
    "units": ["Unit1", "Unit2"],
    "eligible": {o: ["Unit1", "Unit2"] for o in ["OrderA", "OrderB", "OrderC", "OrderD"]},
    "processing_time": {
        "OrderA": {"Unit1": 4.0, "Unit2": 5.0},
        "OrderB": {"Unit1": 3.0, "Unit2": 3.0},
        "OrderC": {"Unit1": 6.0, "Unit2": 5.0},  # fastest = 5 h
        "OrderD": {"Unit1": 2.0, "Unit2": 4.0},
    },
    "due_date": {"OrderA": 20.0, "OrderB": 20.0, "OrderC": 20.0, "OrderD": 20.0},
    "objective": "makespan",
}


def _instance(params):
    return build_instance_from_params(
        params, "SINGLE_STAGE_SCHEDULING", "single_stage_ipm_scheduling"
    )


def test_loose_deadlines_pass_layer1():
    ok, _ = problem_specific_checks(_instance(BASE))
    assert ok is True


def test_tight_deadline_is_infeasible_with_explanation():
    p = copy.deepcopy(BASE)
    p["due_date"] = {o: 4.0 for o in p["orders"]}  # OrderC needs >= 5 h

    report = check_feasibility(_instance(p))

    assert report.status == FeasStatus.INFEASIBLE
    assert report.layer_passed <= 1
    blob = " ".join(report.reasons)
    assert "OrderC" in blob
    assert "5" in blob and "4" in blob          # the actual numbers
    assert report.suggestions                    # plain-language fix offered
    assert any("deadline" in s.lower() or "faster" in s.lower()
               for s in report.suggestions)


def test_order_with_no_eligible_unit_is_infeasible():
    p = copy.deepcopy(BASE)
    p["eligible"]["OrderC"] = []
    report = check_feasibility(_instance(p))
    assert report.status == FeasStatus.INFEASIBLE
    assert "OrderC" in " ".join(report.reasons)


def test_scheduling_routes_by_substring_problem_type():
    """Variant problem-type strings must still hit the scheduling checker."""
    inst = build_instance_from_params(
        {**BASE, "due_date": {o: 4.0 for o in BASE["orders"]}},
        "single_stage_scheduling",  # lowercase variant
        "single_stage_ipm_scheduling",
    )
    ok, msgs = problem_specific_checks(inst)
    assert ok is False
    assert "OrderC" in " ".join(msgs)
