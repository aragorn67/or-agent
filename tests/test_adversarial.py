"""Offline checks for the adversarial transformations and the outcome classifier.

The live runner needs an LLM and an agent; these tests verify the *pure-Python
plumbing* — that each transform actually mutates the prose in the intended way
and that the outcome classifier maps buckets to the right reported category.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from evals.adversarial import transforms_for
from evals.adversarial_eval import _AdvRun, _outcome, _summarize


_TRANSPORT_PARAMS: Dict[str, Any] = {
    "plants": ["Boston", "Atlanta"],
    "markets": ["Tokyo", "Paris"],
    "capacity": {"Boston": 350, "Atlanta": 400},
    "demand": {"Tokyo": 200, "Paris": 150},
    "cost": {
        "Boston": {"Tokyo": 2.50, "Paris": 3.00},
        "Atlanta": {"Tokyo": 4.00, "Paris": 1.50},
    },
}
_TRANSPORT_CANONICAL = (
    "Boston can supply up to 350 units. Atlanta can supply up to 400 units. "
    "Tokyo demands 200 units. Paris demands 150 units. Shipping from Boston "
    "to Tokyo costs $2.50 per unit. Shipping from Boston to Paris costs "
    "$3.00 per unit. Shipping from Atlanta to Tokyo costs $4.00 per unit. "
    "Shipping from Atlanta to Paris costs $1.50 per unit. Minimize total "
    "transportation cost while meeting all demand."
)


_SCHED_PARAMS: Dict[str, Any] = {
    "orders": ["OrderA", "OrderB"],
    "units": ["Unit1", "Unit2"],
    "eligible": {"OrderA": ["Unit1", "Unit2"], "OrderB": ["Unit1", "Unit2"]},
    "processing_time": {
        "OrderA": {"Unit1": 3.0, "Unit2": 4.0},
        "OrderB": {"Unit1": 2.0, "Unit2": 5.0},
    },
    "due_date": {"OrderA": 20.0, "OrderB": 20.0},
    "objective": "makespan",
}
_SCHED_CANONICAL = (
    "Schedule 2 orders on 2 processing units. OrderA takes 3 hours on Unit1 "
    "and 4 hours on Unit2. OrderB takes 2 hours on Unit1 and 5 hours on "
    "Unit2. OrderA is due by hour 20. OrderB is due by hour 20. Minimize "
    "the makespan."
)


def _by_name(domain: str):
    return {t.name: t for t in transforms_for(domain)}


# ---------------------------------------------------------------------------
# Transport transform invariants
# ---------------------------------------------------------------------------

def test_drop_one_plant_removes_target_plant_mentions():
    t = _by_name("transport")["drop_one_plant"]
    out = t.apply(_TRANSPORT_CANONICAL, _TRANSPORT_PARAMS, seed=1)
    # Alphabetically first plant is Atlanta — it should be gone.
    assert "Atlanta" not in out
    # Boston remains.
    assert "Boston" in out


def test_contradict_one_capacity_appends_a_different_number():
    t = _by_name("transport")["contradict_one_capacity"]
    out = t.apply(_TRANSPORT_CANONICAL, _TRANSPORT_PARAMS, seed=1)
    # Original text is preserved.
    assert _TRANSPORT_CANONICAL.rstrip() in out
    # And a fake capacity appears (50% of 350 or 400 = 175 or 200).
    assert "175" in out or "200" in out


def test_drop_units_suffix_removes_units_globally():
    t = _by_name("transport")["drop_units_suffix"]
    out = t.apply(_TRANSPORT_CANONICAL, _TRANSPORT_PARAMS, seed=1)
    assert " units" not in out.lower()
    # All numeric capacities still present.
    assert "350" in out and "400" in out


def test_inject_irrelevant_fact_adds_truck_noise():
    t = _by_name("transport")["inject_irrelevant_fact"]
    out = t.apply(_TRANSPORT_CANONICAL, _TRANSPORT_PARAMS, seed=1)
    assert "trucks" in out
    # Original numbers untouched.
    for n in ("350", "400", "200", "150", "2.50", "3.00", "4.00", "1.50"):
        assert n in out


def test_transport_transforms_are_deterministic_per_seed():
    for tname in ("contradict_one_capacity", "inject_irrelevant_fact"):
        t = _by_name("transport")[tname]
        a = t.apply(_TRANSPORT_CANONICAL, _TRANSPORT_PARAMS, seed=42)
        b = t.apply(_TRANSPORT_CANONICAL, _TRANSPORT_PARAMS, seed=42)
        assert a == b


# ---------------------------------------------------------------------------
# Scheduling transform invariants
# ---------------------------------------------------------------------------

def test_drop_one_order_removes_target_order():
    t = _by_name("scheduling")["drop_one_order"]
    out = t.apply(_SCHED_CANONICAL, _SCHED_PARAMS, seed=1)
    assert "OrderA" not in out
    assert "OrderB" in out


def test_contradict_one_due_date_appends_correction():
    t = _by_name("scheduling")["contradict_one_due_date"]
    out = t.apply(_SCHED_CANONICAL, _SCHED_PARAMS, seed=1)
    assert _SCHED_CANONICAL.rstrip() in out
    # The fake due date is original-5 = 15
    assert "15" in out


def test_drop_hours_suffix_strips_hour_word():
    t = _by_name("scheduling")["drop_hours_suffix"]
    out = t.apply(_SCHED_CANONICAL, _SCHED_PARAMS, seed=1)
    assert "hour" not in out.lower()
    assert "3" in out and "4" in out and "20" in out


# ---------------------------------------------------------------------------
# Outcome classification
# ---------------------------------------------------------------------------

def _run(bucket: str | None = None, gap: float | None = None) -> _AdvRun:
    return _AdvRun(transform="t", expected_category="should_solve", seed=0,
                   failure_bucket=bucket, objective_gap=gap)


def test_outcome_end_to_end_pass_when_gap_under_threshold():
    assert _outcome(_run(None, 0.001), gap_threshold=0.01) == "end_to_end_pass"


def test_outcome_recovered_with_drift_for_high_gap():
    assert _outcome(_run("objective_mismatch", 0.5), 0.01) == "recovered_with_drift"


def test_outcome_graceful_failure_for_extraction_fail():
    assert _outcome(_run("extraction_fail"), 0.01) == "graceful_failure"
    assert _outcome(_run("classification_miss"), 0.01) == "graceful_failure"
    assert _outcome(_run("agent_infeasible"), 0.01) == "graceful_failure"


def test_outcome_hard_failure_for_agent_exception():
    assert _outcome(_run("agent_exception"), 0.01) == "hard_failure"
    assert _outcome(_run("solver_error"), 0.01) == "hard_failure"


def test_summarize_groups_runs_per_transform():
    runs = [
        _AdvRun(transform="a", expected_category="should_solve", seed=1,
                objective_gap=0.0),
        _AdvRun(transform="a", expected_category="should_solve", seed=2,
                failure_bucket="extraction_fail"),
        _AdvRun(transform="b", expected_category="graceful_degrade", seed=1,
                objective_gap=0.0),
    ]
    s = _summarize(runs, gap_threshold=0.01)
    assert s["a"]["n"] == 2
    assert s["a"]["end_to_end_pass"] == 1
    assert s["a"]["graceful_failure"] == 1
    assert s["b"]["n"] == 1
    assert s["b"]["end_to_end_pass"] == 1
    assert s["b"]["expected_category"] == "graceful_degrade"
