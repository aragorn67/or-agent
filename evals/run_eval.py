"""CLI entry: round-trip the agent against N synthetic transportation instances.

Usage:
    python -m evals.run_eval --n 100 --domain transport
    python -m evals.run_eval --n 5 --seeds 1,2,3,4,5
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import statistics as _st
import sys
import time
from collections import Counter
from pathlib import Path
from typing import List

from agent.core import OptimizationAgent
from llm.enhanced_client import EnhancedLLMClient

from .round_trip import RoundTripResult, run_one


_RESULTS_DIR = Path(__file__).parent / "results"


def _parse_seeds(arg: str, n: int) -> List[int]:
    if arg:
        return [int(s.strip()) for s in arg.split(",") if s.strip()]
    return list(range(1, n + 1))


def _aggregate(results: List[RoundTripResult], gap_threshold: float) -> dict:
    n = len(results)
    classification_hits = sum(
        1 for r in results
        if r.recovered_classification and str(r.recovered_classification).upper() == "TRANSPORTATION"
    )

    scored = [r for r in results if r.param_recall is not None]
    if scored:
        overall_recalls = [r.param_recall["overall"] for r in scored]
        per_key = {}
        for key in ("plants", "markets", "capacity", "demand", "cost"):
            vals = [r.param_recall["by_key"][key] for r in scored]
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

    return {
        "n": n,
        "classification_accuracy": classification_hits / n if n else 0.0,
        "param_recall": recall_stats,
        "objective_gap": gap_stats,
        "end_to_end_pass_rate": pass_rate,
        "gap_threshold": gap_threshold,
        "stage_latency": latency_stats,
        "failure_histogram": dict(bucket_counts),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Round-trip eval for transportation agent")
    p.add_argument("--n", type=int, default=100, help="Number of round-trips")
    p.add_argument("--seeds", type=str, default="", help="Comma-separated seeds (overrides --n)")
    p.add_argument("--domain", type=str, default="transport", choices=["transport"])
    p.add_argument("--gap-threshold", type=float, default=0.01, help="Objective gap to count as pass")
    p.add_argument("--output", type=str, default="", help="Output JSON path (default auto-named)")
    args = p.parse_args(argv)

    seeds = _parse_seeds(args.seeds, args.n)

    print(f"[run_eval] domain={args.domain} n={len(seeds)} gap_threshold={args.gap_threshold}", flush=True)

    llm = EnhancedLLMClient()
    agent = OptimizationAgent(llm)

    results: List[RoundTripResult] = []
    t0 = time.perf_counter()
    for i, seed in enumerate(seeds, 1):
        try:
            r = run_one(seed, agent, llm, gap_threshold=args.gap_threshold)
        except Exception as e:
            r = RoundTripResult(
                seed=seed, generated_params={}, true_objective=None,
                verbalized_text=None, recovered_classification=None,
                recovered_params=None, recovered_objective=None,
                failure_bucket="agent_exception", error=f"unhandled: {e}",
            )
        results.append(r)
        gap_str = f"{r.objective_gap:.3f}" if isinstance(r.objective_gap, float) else "—"
        bucket = r.failure_bucket or "ok"
        print(f"  [{i}/{len(seeds)}] seed={seed} bucket={bucket} gap={gap_str}", flush=True)

    elapsed = time.perf_counter() - t0
    report = {
        "domain": args.domain,
        "started_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "wall_seconds": elapsed,
        "metrics": _aggregate(results, args.gap_threshold),
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
