"""
Tests for the two-call protocol: heuristic mode + /continue handler.

These tests bypass the LLM (classification + extraction) and exercise the
handler/job-store/agent.continue_job paths directly with known params. The
round-trip eval framework covers the LLM pipeline; this file isolates the
new heuristic plumbing.
"""

import pytest

from agent.heuristic_handler import (
    heuristic_mode_supported,
    run_heuristic_for_transport,
)
from agent.job_store import JobStore
from solvers.transport.bipartite import BipartiteTransportSolver


@pytest.fixture
def seattle_params():
    return BipartiteTransportSolver().get_example_params()


@pytest.fixture
def store():
    return JobStore(ttl_seconds=600)


def test_heuristic_mode_supported():
    assert heuristic_mode_supported("TRANSPORTATION")
    assert heuristic_mode_supported("transportation")
    assert heuristic_mode_supported("SCHEDULING")
    assert heuristic_mode_supported("single_stage_scheduling")
    assert not heuristic_mode_supported("UNKNOWN")


def test_heuristic_handler_returns_job_id_and_bound(seattle_params, store):
    result = run_heuristic_for_transport(
        params=seattle_params,
        description="Seattle to NY/Chicago/Topeka",
        problem_type="TRANSPORTATION",
        solver_id="transport_basic_bipartite",
        classification={"confidence": 0.95, "type": "TRANSPORTATION"},
        job_store=store,
        ask_to_continue=False,
    )
    assert result["success"]
    assert result["mode"] == "heuristic"
    assert "job_id" in result and len(result["job_id"]) == 32  # uuid4 hex
    assert result["solution"]["is_heuristic"]
    assert result["solution"]["best_bound"] is not None
    assert result["solution"]["objective_value"] > 0


def test_heuristic_handler_with_ask_to_continue(seattle_params, store):
    result = run_heuristic_for_transport(
        params=seattle_params,
        description="Seattle demo",
        problem_type="TRANSPORTATION",
        solver_id="transport_basic_bipartite",
        classification={"confidence": 0.9},
        job_store=store,
        ask_to_continue=True,
    )
    assert "follow_up_prompt" in result
    assert "available_actions" in result
    assert set(result["available_actions"]) == {"optimize", "accept", "use_heuristic"}


def test_heuristic_handler_persists_in_store(seattle_params, store):
    result = run_heuristic_for_transport(
        params=seattle_params,
        description="Seattle demo",
        problem_type="TRANSPORTATION",
        solver_id="transport_basic_bipartite",
        classification={},
        job_store=store,
        ask_to_continue=False,
    )
    record = store.get(result["job_id"])
    assert record is not None
    assert record.problem_type == "TRANSPORTATION"
    assert record.heuristic_cost == result["solution"]["objective_value"]


def test_job_store_returns_none_for_unknown_id(store):
    assert store.get("nonexistent") is None


def test_job_store_ttl_eviction(seattle_params):
    short_store = JobStore(ttl_seconds=0.0)  # instantly stale
    record = short_store.create(
        problem_type="TRANSPORTATION",
        solver_id="transport_basic_bipartite",
        params=seattle_params,
        heuristic_flows={},
        heuristic_cost=0.0,
        lp_bound=0.0,
        description="x",
    )
    import time as _t
    _t.sleep(0.01)
    assert short_store.get(record.job_id) is None


def test_job_store_drop(seattle_params, store):
    record = store.create(
        problem_type="TRANSPORTATION",
        solver_id="transport_basic_bipartite",
        params=seattle_params,
        heuristic_flows={},
        heuristic_cost=0.0,
        lp_bound=0.0,
        description="x",
    )
    store.drop(record.job_id)
    assert store.get(record.job_id) is None


def test_continue_optimize_after_heuristic_matches_exact(seattle_params, store):
    """The full two-call round-trip: heuristic → optimize. The exact solve
    after warm-start must match a from-scratch exact solve."""
    handler_result = run_heuristic_for_transport(
        params=seattle_params,
        description="Seattle demo",
        problem_type="TRANSPORTATION",
        solver_id="transport_basic_bipartite",
        classification={},
        job_store=store,
        ask_to_continue=False,
    )
    job_id = handler_result["job_id"]
    record = store.get(job_id)

    solver = BipartiteTransportSolver()
    cold = solver.solve(seattle_params)
    warm = solver.solve(record.params, warm_start=record.heuristic_flows)

    assert warm["status"] == "OPTIMAL"
    assert warm["objective_value"] == pytest.approx(cold["objective_value"], abs=1e-6)


def test_heuristic_infeasible_returns_failure(store):
    """Supply < demand should bubble back as an infeasibility response."""
    infeasible = {
        "plants": ["P1"],
        "markets": ["M1", "M2"],
        "capacity": {"P1": 10},
        "demand": {"M1": 40, "M2": 40},
        "cost": {("P1", "M1"): 1, ("P1", "M2"): 1},
    }
    result = run_heuristic_for_transport(
        params=infeasible,
        description="infeasible",
        problem_type="TRANSPORTATION",
        solver_id="transport_basic_bipartite",
        classification={},
        job_store=store,
        ask_to_continue=False,
    )
    assert not result["success"]
    assert result["status"] == "infeasible"
