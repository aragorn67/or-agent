"""Offline harness checks for the paraphrase-holdout runner.

The live runner takes minutes (LLM calls × seeds × paraphrases); these tests
exercise the *plumbing* — aggregation math, paraphrase coverage guards, run
labelling — with stubbed prose so a wiring regression fails in CI rather than
mid-overnight-run.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from evals.paraphrase_holdout import SeedResult, _Run, _summarize
from evals.verbalizer import _PARAPHRASE_STYLES, paraphrase


def _seed_result(seed: int, canonical_gap: float, paraphrase_gaps: List[float],
                 canonical_obj: float = 100.0,
                 paraphrase_objs: List[float] | None = None) -> SeedResult:
    """Helper: build a synthetic SeedResult with given per-run objective gaps."""
    canon = _Run(label="canonical", recovered_objective=canonical_obj,
                 param_recall_overall=1.0, objective_gap=canonical_gap)
    paras = []
    objs = paraphrase_objs or [canonical_obj] * len(paraphrase_gaps)
    for i, (gap, obj) in enumerate(zip(paraphrase_gaps, objs)):
        paras.append(_Run(label=f"paraphrase_{i}", recovered_objective=obj,
                          param_recall_overall=1.0, objective_gap=gap))
    return SeedResult(seed=seed, domain="transport", true_objective=100.0,
                      canonical=canon, paraphrases=paras)


def test_summarize_canonical_and_paraphrase_pass_rates():
    """Pass-rate split: canonical 2/2 pass, paraphrases 3/4 pass."""
    results = [
        _seed_result(1, canonical_gap=0.001, paraphrase_gaps=[0.001, 0.5]),
        _seed_result(2, canonical_gap=0.005, paraphrase_gaps=[0.0, 0.002]),
    ]
    m = _summarize(results, gap_threshold=0.01)
    assert m["canonical_pass_rate"] == pytest.approx(1.0)
    assert m["paraphrase_pass_rate"] == pytest.approx(0.75)
    assert m["synthetic_vs_real_gap"] == pytest.approx(0.25)


def test_summarize_agreement_with_canonical_uses_canonical_objective():
    """Agreement is paraphrase-vs-canonical, not paraphrase-vs-truth — so a
    paraphrase that drifts AWAY from the true value but matches canonical is
    still 'agreement', and a paraphrase that drifts FROM canonical even when
    it accidentally lands near truth is 'disagreement'.
    """
    # canonical recovers 200 (drifted 100% from truth=100), paraphrase
    # recovers 200 too -> they agree even though both are wrong.
    r = _seed_result(
        1, canonical_gap=1.0, paraphrase_gaps=[1.0],
        canonical_obj=200.0, paraphrase_objs=[200.0],
    )
    m = _summarize([r], gap_threshold=0.01)
    assert m["paraphrase_agreement_with_canonical"] == pytest.approx(1.0)

    # canonical=200, paraphrase=100 (matches truth) -> disagreement.
    r2 = _seed_result(
        2, canonical_gap=1.0, paraphrase_gaps=[0.0],
        canonical_obj=200.0, paraphrase_objs=[100.0],
    )
    m2 = _summarize([r2], gap_threshold=0.01)
    assert m2["paraphrase_agreement_with_canonical"] == pytest.approx(0.0)


def test_summarize_handles_canonical_failures():
    """A seed whose canonical run failed extraction has no recovered_objective;
    paraphrase agreement should fall back to "no comparable pairs" not crash."""
    r = SeedResult(seed=1, domain="transport", true_objective=100.0,
                   canonical=_Run(label="canonical",
                                  failure_bucket="extraction_fail"),
                   paraphrases=[_Run(label="paraphrase_0",
                                     recovered_objective=100.0,
                                     objective_gap=0.0)])
    m = _summarize([r], gap_threshold=0.01)
    # canonical_pass_rate counts canonical_total=1, pass=0 (gap is None)
    assert m["canonical_pass_rate"] == pytest.approx(0.0)
    assert m["paraphrase_pass_rate"] == pytest.approx(1.0)
    # No canonical recovered_objective → no agreement pairs → 0 by safe_rate
    assert m["paraphrase_agreement_with_canonical"] == pytest.approx(0.0)


def test_paraphrase_styles_are_distinct_and_nonempty():
    """The styles drive the prompt diversity — duplicates would silently shrink k."""
    assert len(_PARAPHRASE_STYLES) == len(set(_PARAPHRASE_STYLES))
    assert all(s.strip() for s in _PARAPHRASE_STYLES)


def test_paraphrase_rejects_k_above_style_count():
    """The runner caps k at the style-pool size to keep paraphrases distinct."""
    class _DummyLLM:
        class _R:
            def _chat(self, *a, **k): return "irrelevant"
        reasoning_client = _R()

    params = {"plants": ["A"], "markets": ["X"], "capacity": {"A": 1},
              "demand": {"X": 1}, "cost": {"A": {"X": 1.0}}}
    with pytest.raises(ValueError, match="distinct styles"):
        paraphrase("canon text", _DummyLLM(), params, domain="transport",
                   k=999)


def test_paraphrase_returns_canned_text_per_style(monkeypatch, tmp_path):
    """With a deterministic stub LLM, paraphrase() should produce one output
    per requested style and run all coverage guards on each."""
    # Real text the stub returns must contain every entity + number to pass
    # the coverage check — otherwise we exercise the failure path instead.
    canonical = (
        "PlantA can supply up to 10 units. MarketX needs 5 units. "
        "Shipping from PlantA to MarketX costs $1.00 per unit. "
        "Minimize total transportation cost while meeting all demand "
        "without exceeding any plant's capacity."
    )
    params = {
        "plants": ["PlantA"], "markets": ["MarketX"],
        "capacity": {"PlantA": 10}, "demand": {"MarketX": 5},
        "cost": {"PlantA": {"MarketX": 1.00}},
    }

    class _StubLLM:
        class _R:
            def _chat(self, system, user, json_mode=False):
                # Echo the canonical text; passes coverage by construction.
                return canonical
        reasoning_client = _R()

    # Point cache dir at tmp so we don't pollute the real .verbalizer_cache.
    import evals.verbalizer as v
    monkeypatch.setattr(v, "_CACHE_DIR", tmp_path / "cache")

    out = paraphrase(canonical, _StubLLM(), params, domain="transport", k=3)
    assert len(out) == 3
    assert all(o == canonical for o in out)
