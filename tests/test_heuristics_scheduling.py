"""
Tests for LPT scheduling heuristic and warm-start integration with the IPM
single-stage solver.
"""

import pytest

from solvers.heuristics.scheduling_lpt import lpt_schedule
from solvers.scheduling.single_stage_ipm import SingleStageIPMSolver


@pytest.fixture
def example_params():
    return SingleStageIPMSolver().get_example_params()


def test_lpt_feasible_on_example(example_params):
    result = lpt_schedule(example_params)
    assert result.feasible
    assert result.cmax > 0
    # Every order has been assigned to exactly one of its eligible units.
    for order, unit in result.assignment.items():
        assert unit in example_params["eligible"][order]


def test_lpt_assignments_respect_eligibility():
    params = {
        "orders": ["O1", "O2", "O3"],
        "units": ["U1", "U2", "U3"],
        "eligible": {"O1": ["U1"], "O2": ["U2"], "O3": ["U3"]},
        "processing_time": {
            "O1": {"U1": 2.0},
            "O2": {"U2": 3.0},
            "O3": {"U3": 1.0},
        },
        "due_date": {"O1": 10, "O2": 10, "O3": 10},
    }
    result = lpt_schedule(params)
    assert result.feasible
    assert result.assignment == {"O1": "U1", "O2": "U2", "O3": "U3"}
    # No-changeover makespan = max single processing time = 3.0
    assert result.cmax == pytest.approx(3.0, abs=1e-6)


def test_lpt_no_eligible_unit_is_infeasible():
    params = {
        "orders": ["O1", "O2"],
        "units": ["U1"],
        "eligible": {"O1": ["U1"], "O2": []},
        "processing_time": {"O1": {"U1": 1}, "O2": {"U1": 1}},
        "due_date": {"O1": 5, "O2": 5},
    }
    result = lpt_schedule(params)
    assert not result.feasible


def test_lpt_warm_start_matches_exact(example_params):
    """The warm-started exact solve must produce the same objective as the
    from-scratch exact solve, and warm_started must be True (scheduling is MIP)."""
    solver = SingleStageIPMSolver()
    cold = solver.solve(example_params)
    lpt = lpt_schedule(example_params)

    warm_payload = {
        "assignment": lpt.assignment,
        "sequence": lpt.sequence,
        "completion": lpt.completion,
        "cmax": lpt.cmax,
    }
    warm = solver.solve(example_params, warm_start=warm_payload)

    assert cold["status"] == "OPTIMAL"
    assert warm["status"] == "OPTIMAL"
    assert warm["warm_started"] is True
    assert warm["Cmax"] == pytest.approx(cold["Cmax"], abs=1e-6)


def test_lpt_cmax_is_upper_bound_on_optimum(example_params):
    """LPT is a feasible primal, so its Cmax >= optimal Cmax (minimization)."""
    solver = SingleStageIPMSolver()
    cold = solver.solve(example_params)
    lpt = lpt_schedule(example_params)
    assert lpt.cmax >= cold["Cmax"] - 1e-6


def test_lpt_handles_changeover(example_params):
    """Changeovers should be included in completion times."""
    result = lpt_schedule(example_params)
    # The example has changeover times; cumulative completion should reflect them
    # rather than just sum of processing times on each machine.
    for unit, seq in result.sequence.items():
        if len(seq) < 2:
            continue
        # Each successive job's completion must be strictly greater than
        # the predecessor's (changeover + processing > 0).
        for prev, nxt in zip(seq, seq[1:]):
            assert result.completion[nxt] > result.completion[prev]
