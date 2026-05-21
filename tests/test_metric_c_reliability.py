"""Phase-C named-reliability-metric aggregation + noise-injection invariants.

Two surfaces:
1. ``_reliability_metrics`` — pure aggregation over a list of RoundTripResults.
   Tested with synthetic results so the math is verifiable without an LLM.
2. ``_inject_noise`` — text mutation. Two invariants matter for the eval:
   (a) determinism given the seed, (b) all numbers and Capitalised entity
   tokens are preserved verbatim (otherwise we measure verbalizer fidelity,
   not agent robustness).
"""

from __future__ import annotations

import re
from collections import Counter

import pytest

from evals.round_trip import RoundTripResult
from evals.run_eval import _reliability_metrics
from evals.verbalizer import _inject_noise


def _result(bucket: str | None) -> RoundTripResult:
    return RoundTripResult(seed=0, failure_bucket=bucket)


def _metrics(buckets: list[str | None]) -> dict:
    results = [_result(b) for b in buckets]
    counts = Counter(b for b in buckets if b)
    return _reliability_metrics(results, counts)


# ---------------------------------------------------------------------------
# Reliability aggregation
# ---------------------------------------------------------------------------

def test_all_pass_yields_perfect_rates():
    m = _metrics([None, None, None, None])
    assert m["structured_output_validity_rate"] == pytest.approx(1.0)
    assert m["classification_validity_rate"] == pytest.approx(1.0)
    assert m["feasibility_preservation_rate"] == pytest.approx(1.0)
    assert m["solver_error_rate"] == pytest.approx(0.0)


def test_classification_miss_only_affects_classification_validity():
    # 2 classification misses out of 4 -> classification rate 0.5
    m = _metrics(["classification_miss", "classification_miss", None, None])
    assert m["classification_validity_rate"] == pytest.approx(0.5)
    # The misses never reached extraction, so extraction denominator drops.
    # 0 extraction failures / 2 reached extraction -> 1.0.
    assert m["structured_output_validity_rate"] == pytest.approx(1.0)


def test_extraction_fail_and_agent_exception_both_count_as_structured_output_failure():
    m = _metrics(["extraction_fail", "agent_exception", None, None])
    # Both reached extraction (denominator 4), both failed (numerator 2).
    assert m["structured_output_validity_rate"] == pytest.approx(0.5)


def test_agent_infeasible_only_affects_feasibility_preservation():
    m = _metrics(["agent_infeasible", "agent_infeasible", None, None])
    # 2 agent_infeasible / 4 with feasible truth -> rate 0.5
    assert m["feasibility_preservation_rate"] == pytest.approx(0.5)
    # All 4 reached classification and extraction successfully (infeasibility
    # is detected at solve time, after extraction returned valid params).
    assert m["structured_output_validity_rate"] == pytest.approx(1.0)
    assert m["classification_validity_rate"] == pytest.approx(1.0)


def test_generator_infeasible_does_not_charge_downstream_stages():
    # The seed couldn't be solved as ground truth — it never went through the
    # agent at all. Downstream rates should ignore it (or report None) rather
    # than blaming the LLM for an empty input.
    m = _metrics(["generator_infeasible", None, None])
    assert m["denominators"]["runs_with_feasible_truth"] == 2
    assert m["denominators"]["runs_reaching_classification"] == 2
    assert m["feasibility_preservation_rate"] == pytest.approx(1.0)


def test_solver_error_rate_isolated_from_feasibility():
    # solver_error is the solver raising; agent_infeasible is the solver
    # returning infeasible. Both real outcomes, different signals.
    m = _metrics(["solver_error", None, None, None])
    # 1 solver_error / 4 reached solver -> 0.25
    assert m["solver_error_rate"] == pytest.approx(0.25)
    assert m["feasibility_preservation_rate"] == pytest.approx(1.0)


def test_empty_batch_returns_none_rates_not_crash():
    m = _metrics([])
    assert m["structured_output_validity_rate"] is None
    assert m["classification_validity_rate"] is None
    assert m["feasibility_preservation_rate"] is None
    assert m["solver_error_rate"] is None


# ---------------------------------------------------------------------------
# Noise injection invariants
# ---------------------------------------------------------------------------

_SAMPLE = (
    "Boston can supply up to 350 units. Tokyo demands 120 units. "
    "Shipping from Boston to Tokyo costs $2.67 per unit. The objective "
    "is to minimize total cost while meeting all demand."
)


def test_noise_is_deterministic_per_seed():
    a = _inject_noise(_SAMPLE, rng_seed=42)
    b = _inject_noise(_SAMPLE, rng_seed=42)
    assert a == b


def test_noise_actually_perturbs_text():
    # With any reasonable seed and a long-enough input, at least one of the
    # low-probability transforms should fire. Zero perturbation would mean
    # the eval is silently measuring nothing.
    perturbed = _inject_noise(_SAMPLE * 3, rng_seed=7)
    assert perturbed != _SAMPLE * 3


def test_noise_preserves_every_number():
    """The robustness-to-noise metric is meaningless if the numbers change —
    extraction would fail on the noise, not on the agent's parsing."""
    perturbed = _inject_noise(_SAMPLE, rng_seed=1)
    for num in ("350", "120", "2.67"):
        assert num in perturbed, f"noise dropped number {num!r}"


def test_noise_preserves_capitalised_entities():
    perturbed = _inject_noise(_SAMPLE, rng_seed=1)
    for name in ("Boston", "Tokyo"):
        assert name in perturbed, f"noise dropped entity {name!r}"


def test_noise_does_not_touch_dollar_amounts():
    perturbed = _inject_noise(_SAMPLE, rng_seed=99)
    # Dollar amount should pass through intact via the $\d+ numeric guard
    assert "$2.67" in perturbed
