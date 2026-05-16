"""
Phase 2 — first-message analysis-intent dead-end fix.

A what-if / sensitivity / resolve / pareto request as the *first* message has
no solved baseline to analyse. Previously it was misrouted into the solver
pipeline and dead-ended with a cryptic "not supported by our solvers" /
"Parameter extraction failed". It now short-circuits to a conversational
guide that asks for the base problem first.

Deterministic: the guard uses keyword-only analysis detection (no LLM); the
integration test stubs intent detection so no LLM call is made.
"""

import pytest

from agent.core import OptimizationAgent


class _DummyLLM:
    """Sub-handlers only store the client at init; never called here."""


@pytest.fixture
def agent():
    return OptimizationAgent(_DummyLLM())


# ---- the helper in isolation ----

def test_bare_whatif_first_message_returns_guide(agent):
    out = agent._analysis_needs_baseline(
        "what if demand increases by 20%?", {}, allow_data_rich=False
    )
    assert out is not None
    assert out["success"] is True
    assert out["type"] == "analysis_no_baseline"
    assert out["analysis_type"] == "what_if"
    assert "needs a solved problem" in out["response"]


def test_sensitivity_and_pareto_first_message(agent):
    assert agent._analysis_needs_baseline(
        "do a sensitivity analysis on shipping cost", {}, allow_data_rich=False
    )["analysis_type"] == "sensitivity"
    assert agent._analysis_needs_baseline(
        "show me the pareto front of cost vs distance", {}, allow_data_rich=False
    )["analysis_type"] == "pareto"


def test_non_analysis_message_passes_through(agent):
    # A plain problem statement is not an analysis intent -> let pipeline run.
    assert agent._analysis_needs_baseline(
        "ship from 2 plants to 3 customers, minimize cost",
        {}, allow_data_rich=False,
    ) is None


def test_existing_baseline_passes_through(agent):
    # With a prior solution this IS a real follow-up — don't intercept.
    ctx = {"last_solution": {"problem_type": "TRANSPORTATION"}}
    assert agent._analysis_needs_baseline(
        "what if demand increases by 20%?", ctx, allow_data_rich=False
    ) is None


def test_data_rich_whatif_not_short_circuited_early(agent):
    # A full problem stated as a what-if is number-heavy; the early gate must
    # let it reach the solver instead of returning the guide.
    msg = ("what if, with plants P1 cap 100 and P2 cap 80 shipping to "
           "customers demand 50 60 40 at costs 4 6 8 5 3 7, P1 drops to 50?")
    assert agent._analysis_needs_baseline(msg, {}, allow_data_rich=False) is None
    # But the post-failure net (allow_data_rich=True) still rescues it.
    assert agent._analysis_needs_baseline(msg, {}, allow_data_rich=True) is not None


# ---- integration: early guard inside solve_natural_language ----

def test_solve_natural_language_short_circuits_bare_whatif(agent, monkeypatch):
    monkeypatch.setattr(
        agent.intent_router, "detect_intent",
        lambda msg, ctx=None: {"intent": "optimization", "confidence": 0.9},
    )
    out = agent.solve_natural_language("what if I increase capacity by 20%?")
    assert out["success"] is True
    assert out["type"] == "analysis_no_baseline"
