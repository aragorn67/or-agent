"""Regression: extractor must not short-circuit the feasibility gate.

Historically the transportation extractor was prompted to flag "anything
that looks wrong", so qwen3 would self-attach an `error` field for cases
like supply<demand. The agent then short-circuited with "Parameter
extraction failed" — useless to the user — and the real 3-layer
feasibility gate never executed.

The fix routes any *complete* params dict through the gate regardless of
whether the LLM also attached an advisory note. These tests pin that.
"""

import os

import pytest

os.environ.setdefault("LLM_BACKEND", "ollama")

from agent.core import OptimizationAgent
from llm.enhanced_client import EnhancedLLMClient


@pytest.fixture(scope="module")
def agent():
    return OptimizationAgent(EnhancedLLMClient())


def test_supply_less_demand_reaches_feasibility_gate(agent):
    text = (
        "Ship from one plant with capacity 100 to two customers needing "
        "80 and 70 respectively. Per-unit costs: 1 and 2. Minimize cost."
    )
    result = agent.solve_natural_language(text)

    assert result.get("success") is False
    assert result.get("status") == "infeasible"
    assert result.get("error") != "Parameter extraction failed"
    assert result.get("layer_failed") == 1, (
        "Layer-1 (problem-specific aggregate check) must catch supply<demand, "
        f"got layer_failed={result.get('layer_failed')!r}"
    )
    reasons = result.get("reasons") or []
    assert any("supply" in r.lower() and "demand" in r.lower() for r in reasons), (
        f"Expected a supply/demand reason from the gate, got: {reasons!r}"
    )
