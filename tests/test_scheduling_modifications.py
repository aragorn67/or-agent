"""
Regression tests for scheduling what-if / modification support.

Before this fix the modification pipeline was transport-only:
  * parse_infeasibility_fix's schema had no due_date/processing_time, so
    scheduling what-ifs returned zero modifications ("Could not parse").
  * _apply_modifications had no scheduling branch, so a *parsed* deadline
    change was silently dropped — the engine then solved the UNCHANGED
    problem and reported it FEASIBLE (a false-feasible verdict).

These tests exercise the pure apply logic and the zero-applied guard
without touching the LLM or a real solver.
"""

import pytest

from llm.enhanced_client import EnhancedLLMClient
from analysis.scenarios.engine import perform_what_if_scenario


SCHED_PARAMS = {
    "orders": ["OrderA", "OrderB", "OrderC", "OrderD"],
    "units": ["Unit1", "Unit2"],
    "eligible": {o: ["Unit1", "Unit2"] for o in ["OrderA", "OrderB", "OrderC", "OrderD"]},
    "processing_time": {
        "OrderA": {"Unit1": 4.0, "Unit2": 5.0},
        "OrderB": {"Unit1": 3.0, "Unit2": 3.0},
        "OrderC": {"Unit1": 6.0, "Unit2": 5.0},
        "OrderD": {"Unit1": 2.0, "Unit2": 4.0},
    },
    "due_date": {"OrderA": 20.0, "OrderB": 20.0, "OrderC": 20.0, "OrderD": 20.0},
    "objective": "makespan",
}


@pytest.fixture
def client():
    # Bypass __init__ (no Ollama connection); _apply_modifications is pure
    # except for self._parse_route, unused on the scheduling branches.
    return object.__new__(EnhancedLLMClient)


def test_due_date_set_single_order(client):
    mods = [{"type": "set", "entity": "OrderC", "parameter": "due_date", "value": 9}]
    out, applied = client._apply_modifications(SCHED_PARAMS, mods)
    assert applied == 1
    assert out["due_date"]["OrderC"] == 9
    assert out["due_date"]["OrderA"] == 20.0          # others untouched
    assert SCHED_PARAMS["due_date"]["OrderC"] == 20.0  # original not mutated


def test_due_date_set_all_orders(client):
    mods = [{"type": "set", "entity": "ALL", "parameter": "due_date", "value": 4}]
    out, applied = client._apply_modifications(SCHED_PARAMS, mods)
    assert applied == 1
    assert all(v == 4 for v in out["due_date"].values())


def test_due_date_decrease(client):
    mods = [{"type": "decrease", "entity": "OrderB", "parameter": "due_date", "value": 5}]
    out, applied = client._apply_modifications(SCHED_PARAMS, mods)
    assert applied == 1
    assert out["due_date"]["OrderB"] == 15.0


def test_processing_time_set(client):
    mods = [{"type": "set", "entity": "OrderA on Unit1",
             "parameter": "processing_time", "value": 7}]
    out, applied = client._apply_modifications(SCHED_PARAMS, mods)
    assert applied == 1
    assert out["processing_time"]["OrderA"]["Unit1"] == 7
    assert out["processing_time"]["OrderA"]["Unit2"] == 5.0


def test_unmappable_modification_counts_zero(client):
    """A parsed modification that maps to nothing must NOT count as applied
    (this is what previously caused the false-feasible verdict)."""
    mods = [{"type": "set", "entity": "NoSuchOrder",
             "parameter": "due_date", "value": 3}]
    out, applied = client._apply_modifications(SCHED_PARAMS, mods)
    assert applied == 0
    assert out["due_date"] == SCHED_PARAMS["due_date"]


class _StubLLM:
    """Returns a parsed-but-unapplied modification (applied_count=0)."""

    def parse_infeasibility_fix(self, query, params, ctx):
        return {
            "is_complete_redescription": False,
            "modifications": [{"type": "set", "entity": "NoSuchOrder",
                               "parameter": "due_date", "value": 3}],
            "applied_count": 0,
            "applied_params": params,  # unchanged
        }


def test_zero_applied_does_not_report_feasible():
    """The scenario engine must reject a zero-applied modification instead of
    solving the unchanged problem and calling it FEASIBLE."""
    sentinel_solver = object()  # must never be touched

    res = perform_what_if_scenario(
        llm_client=_StubLLM(),
        solver=sentinel_solver,
        params=SCHED_PARAMS,
        solution={"objective_value": 8.0, "status": "OPTIMAL"},
        query="what if every order must finish within 4 hours?",
        problem_type="SINGLE_STAGE_SCHEDULING",
    )

    assert res["success"] is False
    assert "could not apply" in res["message"].lower()
    assert "OrderC" in res["message"]  # scheduling-flavoured hint, not "Plant North"
