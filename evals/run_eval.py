"""CLI entry: round-trip the agent against N synthetic instances.

Usage:
    python -m evals.run_eval --n 100 --domain transport
    python -m evals.run_eval --n 5 --seeds 1,2,3,4,5 --domain scheduling
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import statistics as _st
import sys
import time
from collections import Counter
from pathlib import Path
from typing import List, Optional

from .round_trip import RoundTripResult, run_one


_RESULTS_DIR = Path(__file__).parent / "results"

_EXPECTED_CLASSIFICATION = {
    "transport": {"TRANSPORTATION"},
    "scheduling": {
        "SINGLE_STAGE_SCHEDULING",
        "SINGLE_MACHINE_MAKESPAN",
        "PARALLEL_MACHINE_SCHEDULING",
    },
}

_PARAM_KEYS = {
    "transport": ("plants", "markets", "capacity", "demand", "cost"),
    "scheduling": ("orders", "units", "processing_time", "due_date"),
}


def _parse_seeds(arg: str, n: int) -> List[int]:
    if arg:
        return [int(s.strip()) for s in arg.split(",") if s.strip()]
    return list(range(1, n + 1))


def _aggregate(results: List[RoundTripResult], gap_threshold: float, domain: str) -> dict:
    n = len(results)
    expected = _EXPECTED_CLASSIFICATION[domain]
    classification_hits = sum(
        1 for r in results
        if r.recovered_classification and str(r.recovered_classification).upper() in expected
    )

    scored = [r for r in results if r.param_recall is not None]
    if scored:
        overall_recalls = [r.param_recall["overall"] for r in scored]
        per_key = {}
        for key in _PARAM_KEYS[domain]:
            vals = [r.param_recall["by_key"][key] for r in scored if key in r.param_recall["by_key"]]
            if vals:
                per_key[key] = {"mean": _st.mean(vals), "min": min(vals), "max": max(vals)}
        recall_stats = {
            "mean_overall": _st.mean(overall_recalls),
            "median_overall": _st.median(overall_recalls),
            "by_key": per_key,
        }
    else:
        recall_stats = None

    gaps = [r.objective_gap for r in results if r.objective_gap is not None and r.objective_gap != float("inf")]
    if gaps:
        gaps_sorted = sorted(gaps)
        p95_idx = max(0, int(0.95 * (len(gaps_sorted) - 1)))
        gap_stats = {
            "median": _st.median(gaps),
            "mean": _st.mean(gaps),
            "p95": gaps_sorted[p95_idx],
            "max": max(gaps),
        }
    else:
        gap_stats = None

    pass_rate = sum(
        1 for r in results
        if r.objective_gap is not None and r.objective_gap < gap_threshold
    ) / n if n else 0.0

    latency_keys = {k for r in results for k in r.stage_latencies_ms}
    latency_stats = {}
    for k in latency_keys:
        vals = [r.stage_latencies_ms[k] for r in results if k in r.stage_latencies_ms]
        if vals:
            latency_stats[k] = {"mean_ms": _st.mean(vals), "median_ms": _st.median(vals)}

    bucket_counts = Counter(r.failure_bucket for r in results if r.failure_bucket)

    reliability = _reliability_metrics(results, bucket_counts)

    return {
        "n": n,
        "classification_accuracy": classification_hits / n if n else 0.0,
        "param_recall": recall_stats,
        "objective_gap": gap_stats,
        "end_to_end_pass_rate": pass_rate,
        "gap_threshold": gap_threshold,
        "stage_latency": latency_stats,
        "failure_histogram": dict(bucket_counts),
        "reliability": reliability,
    }


def _reliability_metrics(results: List[RoundTripResult],
                         bucket_counts: Counter) -> dict:
    """Phase-C named reliability rates, derived from the failure histogram.

    All rates are denominated in **runs that reached their stage** — so the
    structured-output rate is over runs that got past the generator, the
    feasibility-preservation rate is over runs whose problem was feasible by
    construction (i.e., not generator_infeasible).

    Definitions:
      structured_output_validity_rate
          1 − (extraction_fail + agent_exception) / runs_reaching_extraction
          Captures "did the LLM produce a parseable, usable JSON envelope?"
          (agent_exception is included because the most common exception
          path through the agent is a JSON-shape mismatch at extraction.)

      classification_validity_rate
          1 − classification_miss / runs_reaching_classification
          "Did the classifier return one of the expected labels?"

      feasibility_preservation_rate
          1 − agent_infeasible / runs_with_feasible_truth
          "When the ground truth was feasible, did the agent's recovered
          params also solve as feasible?" A failure here means the agent's
          extraction drift produced a problem the solver rejected.

      solver_error_rate
          solver_error / runs_reaching_solver
          Distinct from feasibility loss — the solver itself raised, not the
          model being infeasible.
    """
    n = len(results)
    generator_infeasible = bucket_counts.get("generator_infeasible", 0)
    verbalizer_error = bucket_counts.get("verbalizer_error", 0)
    classification_miss = bucket_counts.get("classification_miss", 0)
    extraction_fail = bucket_counts.get("extraction_fail", 0)
    agent_infeasible = bucket_counts.get("agent_infeasible", 0)
    solver_error = bucket_counts.get("solver_error", 0)
    agent_exception = bucket_counts.get("agent_exception", 0)

    runs_reaching_classification = max(0, n - generator_infeasible - verbalizer_error)
    runs_reaching_extraction = max(0, runs_reaching_classification - classification_miss)
    runs_reaching_solver = max(0, runs_reaching_extraction - extraction_fail - agent_exception)
    runs_with_feasible_truth = max(0, n - generator_infeasible)

    def _rate(denom: int, fails: int) -> Optional[float]:
        if denom <= 0:
            return None
        return 1.0 - fails / denom

    return {
        "structured_output_validity_rate": _rate(
            runs_reaching_extraction, extraction_fail + agent_exception,
        ),
        "classification_validity_rate": _rate(
            runs_reaching_classification, classification_miss,
        ),
        "feasibility_preservation_rate": _rate(
            runs_with_feasible_truth, agent_infeasible,
        ),
        "solver_error_rate": (
            solver_error / runs_reaching_solver if runs_reaching_solver else None
        ),
        "denominators": {
            "runs_reaching_classification": runs_reaching_classification,
            "runs_reaching_extraction": runs_reaching_extraction,
            "runs_reaching_solver": runs_reaching_solver,
            "runs_with_feasible_truth": runs_with_feasible_truth,
        },
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Round-trip eval for transportation agent")
    p.add_argument("--n", type=int, default=100, help="Number of round-trips")
    p.add_argument("--seeds", type=str, default="", help="Comma-separated seeds (overrides --n)")
    p.add_argument("--domain", type=str, default="transport", choices=["transport", "scheduling"])
    p.add_argument("--gap-threshold", type=float, default=0.01, help="Objective gap to count as pass")
    p.add_argument("--output", type=str, default="", help="Output JSON path (default auto-named)")
    p.add_argument("--style", type=str, default="neutral", choices=["neutral", "noisy"],
                   help="Verbalizer style. 'noisy' applies deterministic typo/"
                        "article-drop/punctuation noise post-hoc (Phase-C "
                        "robustness-to-noise metric).")
    args = p.parse_args(argv)

    from agent.core import OptimizationAgent
    from llm.enhanced_client import EnhancedLLMClient

    seeds = _parse_seeds(args.seeds, args.n)

    print(f"[run_eval] domain={args.domain} backend=ollama n={len(seeds)} "
          f"gap_threshold={args.gap_threshold} style={args.style}", flush=True)

    llm = EnhancedLLMClient()
    agent = OptimizationAgent(llm)

    results: List[RoundTripResult] = []
    t0 = time.perf_counter()
    for i, seed in enumerate(seeds, 1):
        try:
            r = run_one(seed, agent, llm, gap_threshold=args.gap_threshold,
                        domain=args.domain, style=args.style)
        except Exception as e:
            r = RoundTripResult(
                seed=seed, domain=args.domain, generated_params={},
                failure_bucket="agent_exception", error=f"unhandled: {e}",
            )
        results.append(r)
        gap_str = f"{r.objective_gap:.3f}" if isinstance(r.objective_gap, float) else "—"
        bucket = r.failure_bucket or "ok"
        print(f"  [{i}/{len(seeds)}] seed={seed} bucket={bucket} gap={gap_str}", flush=True)

    elapsed = time.perf_counter() - t0
    report = {
        "domain": args.domain,
        "style": args.style,
        "started_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "wall_seconds": elapsed,
        "metrics": _aggregate(results, args.gap_threshold, args.domain),
        "results": [r.to_dict() for r in results],
    }

    if args.output:
        out_path = Path(args.output)
    else:
        _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = _RESULTS_DIR / f"{args.domain}_{ts}.json"

    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n[run_eval] wrote {out_path}", flush=True)
    print(json.dumps(report["metrics"], indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
