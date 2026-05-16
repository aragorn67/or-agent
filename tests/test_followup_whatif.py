"""
Regression tests for the #8 follow-up / what-if fix.

Two real defects were fixed:

1. A pending heuristic_then_ask job dead-ended on any non-action message
   (the chat UI funnels everything to /chat/continue). `follow_up_on_job`
   now answers it without consuming the job.
2. `_handle_follow_up` routed "modification" follow-ups to canned text, and
   `_handle_follow_up_analysis` resolved the solver from the problem-type
   *category* ("transportation") instead of the real solver_id
   ("transport_basic_bipartite"), so the analysis engine always raised
   "Unsupported solver_id".

These tests are deterministic — the LLM-backed analysis engine is stubbed;
the real end-to-end path is verified manually (see ANALYSIS.md).
"""

import pytest

from agent.core import OptimizationAgent


FIXED_CHARGE_PARAMS = {
    "plants": ["P1", "P2"],
    "markets": ["M1", "M2", "M3"],
    "capacity": {"P1": 100, "P2": 100},
    "demand": {"M1": 40, "M2": 40, "M3": 40},
    "cost": {"P1": {"M1": 1, "M2": 2, "M3": 3},
             "P2": {"M1": 3, "M2": 2, "M3": 1}},
    "fixed_cost": {"P1": {"M1": 500, "M2": 500, "M3": 500},
                   "P2": {"M1": 500, "M2": 500, "M3": 500}},
}


class _DummyLLM:
    """Agent sub-handlers only store the client at init; never called here."""


@pytest.fixture
def agent():
    return OptimizationAgent(_DummyLLM())


def _make_job(agent):
    return agent.job_store.create(
        problem_type="TRANSPORTATION",
        solver_id="transport_basic_bipartite",
        params=FIXED_CHARGE_PARAMS,
        heuristic_flows={("P1", "M1"): 40.0},
        heuristic_cost=1660.0,
        lp_bound=160.0,
        description="fixed-charge demo",
    )


def test_follow_up_on_job_routes_and_keeps_job(agent, monkeypatch):
    rec = _make_job(agent)
    seen = {}

    def fake_handle_follow_up(message, ctx, _progress):
        seen["message"] = message
        seen["ctx"] = ctx
        return {"success": True, "type": "follow_up_analysis", "response": "ok"}

    monkeypatch.setattr(agent, "_handle_follow_up", fake_handle_follow_up)

    out = agent.follow_up_on_job(rec.job_id, "what if P2 capacity drops to 50?")

    assert out["success"] is True
    assert out["job_pending"] is True
    assert out["job_id"] == rec.job_id
    # Job must survive so the user can still optimize/accept.
    assert agent.job_store.get(rec.job_id) is not None

    # A real baseline was solved and handed to the follow-up handler with the
    # correct solver_id (the old bug used the category instead).
    ls = seen["ctx"]["last_solution"]
    assert ls["solver_id"] == "transport_basic_bipartite"
    assert ls["extracted_params"] is FIXED_CHARGE_PARAMS
    assert ls["solution"]["status"] == "OPTIMAL"
    assert ls["solution"]["objective"] == pytest.approx(1660.0)


def test_follow_up_on_unknown_job(agent):
    out = agent.follow_up_on_job("does-not-exist", "what if capacity drops?")
    assert out["success"] is False
    assert "not found" in out["error"].lower()


def test_modification_follow_up_routes_to_analysis(agent, monkeypatch):
    """A 'change X' follow-up must reach the analysis engine, not canned text."""
    sentinel = {"success": True, "type": "follow_up_analysis", "response": "re-solved"}
    monkeypatch.setattr(
        agent, "_handle_follow_up_analysis",
        lambda *a, **k: sentinel,
    )
    ctx = {"last_solution": {"problem_type": "TRANSPORTATION",
                             "solver_id": "transport_basic_bipartite",
                             "extracted_params": FIXED_CHARGE_PARAMS,
                             "solution": {"status": "OPTIMAL"}}}

    out = agent._handle_follow_up("change P2 capacity to 50", ctx, lambda *a: None)
    assert out is sentinel
    assert out["type"] != "follow_up_modification"  # no longer the dead-end


def test_whatif_question_phrasing_routes_to_analysis(agent, monkeypatch):
    """'what if ...' is keyword-classified as a question; the analysis-type
    detector must still pull it into the re-solving path."""
    sentinel = {"success": True, "type": "follow_up_analysis"}
    monkeypatch.setattr(agent, "_handle_follow_up_analysis", lambda *a, **k: sentinel)
    monkeypatch.setattr("agent.core.detect_analysis_type", lambda *a, **k: "what_if")

    ctx = {"last_solution": {"problem_type": "TRANSPORTATION",
                             "solver_id": "transport_basic_bipartite",
                             "extracted_params": FIXED_CHARGE_PARAMS,
                             "solution": {"status": "OPTIMAL"}}}

    out = agent._handle_follow_up("what if P2 capacity drops to 50?", ctx, lambda *a: None)
    assert out is sentinel


def test_infeasible_whatif_is_a_plain_answer_not_an_error(agent, monkeypatch):
    """A validly-infeasible what-if must surface as a success-type answer with
    plain-language reasons — not a cryptic 'failed at layer N' error."""
    infeasible = {
        "success": False,
        "feasible": False,
        "modifications": [{"type": "set", "parameter": "capacity",
                           "entity": "P1", "value": 5}],
        "layer_failed": 1,
        "reasons": ["Total supply (105.00) is less than total demand (120.00)."],
        "suggestions": ["Increase capacity of 'P2' from 100.00 to 115.00"],
        "message": "Scenario is infeasible (failed at layer 1)",
    }
    monkeypatch.setattr("agent.core.detect_analysis_type", lambda *a, **k: "what_if")
    monkeypatch.setattr("agent.core.execute_analysis", lambda **k: infeasible)

    ctx = {"last_solution": {
        "problem_type": "TRANSPORTATION",
        "extracted_params": FIXED_CHARGE_PARAMS,
        "solution": {"status": "OPTIMAL", "solver_id": "transport_basic_bipartite",
                     "objective_value": 1660.0, "flows": []},
    }}

    out = agent._handle_follow_up_analysis("what if P1 cap = 5?", ctx, lambda *a: None)

    assert out["success"] is True            # an answer, not a dead-end error
    assert out["type"] == "follow_up_analysis"
    resp = out["response"].lower()
    assert "layer" not in resp               # no internal jargon
    assert "can't work" in resp
    assert "less than total demand" in resp  # the plain reason is surfaced


def test_analysis_resolves_real_solver_id_not_category(agent, monkeypatch):
    """Regression: the solver must be built from the solution's solver_id,
    not from problem_type.lower() ('transportation' is not a solver_id)."""
    captured = {}

    def fake_execute(analysis_type, solver, params, solution, query, llm_client=None):
        captured["solver_id"] = solver.solver_id
        return {"success": True}

    monkeypatch.setattr("agent.core.detect_analysis_type", lambda *a, **k: "what_if")
    monkeypatch.setattr("agent.core.execute_analysis", fake_execute)
    monkeypatch.setattr("agent.core.format_analysis_output", lambda *a, **k: "ok")

    ctx = {"last_solution": {
        "problem_type": "TRANSPORTATION",
        "extracted_params": FIXED_CHARGE_PARAMS,
        "solution": {"status": "OPTIMAL", "solver_id": "transport_basic_bipartite",
                     "objective_value": 1660.0, "flows": []},
    }}

    out = agent._handle_follow_up_analysis("what if P2 cap = 50?", ctx, lambda *a: None)
    assert out["success"] is True
    assert captured["solver_id"] == "transport_basic_bipartite"
