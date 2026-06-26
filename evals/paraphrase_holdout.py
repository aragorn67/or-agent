"""Phase 4 of the eval-hardening plan: paraphrase-stability / synthetic-vs-real gap.

For each seed:
  - generator → params (known optimum)
  - canonical verbalization (the seed's single neutral statement)
  - K paraphrases of the canonical text (varying tone, style, ordering)
  - run the full pipeline on canonical + each paraphrase
  - per-seed agreement metric: do all K+1 phrasings recover the same answer?

Aggregates across seeds:
  - canonical pass rate        — the baseline number `run_eval.py` already reports
  - paraphrase pass rate       — same threshold, applied across paraphrase runs
  - paraphrase agreement rate  — fraction of paraphrases whose recovered objective
                                  matches the canonical run's recovered objective
                                  (NOT the ground truth — agreement-with-canonical
                                  isolates phrasing sensitivity from correctness)
  - param-recall std per seed  — how much the recovered params drift under rephrase

"Synthetic-vs-real gap" is the canonical-vs-paraphrase pass-rate delta. It's a
lower-bound proxy until the curated real-data benchmark lands (backlog #2).

Usage:
    python -m evals.paraphrase_holdout --domain transport --seeds 1,2,3 --k 5
    python -m evals.paraphrase_holdout --domain scheduling --seeds 1,2,3 --k 3
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
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


_RESULTS_DIR = Path(__file__).parent / "results"


@dataclass
class _Run:
    """One pipeline run on one piece of prose (canonical OR paraphrase)."""
    label: str                                  # "canonical" or "paraphrase_<idx>"
    text: str = ""
    recovered_classification: Optional[str] = None
    recovered_params: Optional[Dict[str, Any]] = None
    recovered_objective: Optional[float] = None
    param_recall_overall: Optional[float] = None
    objective_gap: Optional[float] = None
    failure_bucket: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SeedResult:
    seed: int
    domain: str
    true_objective: Optional[float] = None
    canonical: Optional[_Run] = None
    paraphrases: List[_Run] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "domain": self.domain,
            "true_objective": self.true_objective,
            "canonical": self.canonical.to_dict() if self.canonical else None,
            "paraphrases": [p.to_dict() for p in self.paraphrases],
        }


def _one_pipeline_run(
    label: str, text: str, agent, domain: str,
    expected_classification: set, true_obj: Optional[float],
    generated_params: Dict[str, Any], gap_threshold: float,
) -> _Run:
    """Run text through the agent and bucket the outcome the same way round_trip does."""
    from .comparators import objective_gap as _obj_gap, param_recall as _param_recall

    run = _Run(label=label, text=text)
    fresh_context = {"last_solution": None, "messages": [], "analysis_history": []}
    try:
        result = agent.solve_natural_language(text, None, fresh_context)
    except Exception as e:
        run.failure_bucket = "agent_exception"
        run.error = f"agent: {e}"
        return run

    classification = result.get("problem_type")
    rec_params = result.get("extracted_params")
    rec_solution = result.get("solution") or {}
    rec_obj = rec_solution.get("objective_value")
    if rec_obj is None:
        rec_obj = rec_solution.get("objective")
    try:
        rec_obj = float(rec_obj) if rec_obj is not None else None
    except (TypeError, ValueError):
        rec_obj = None

    run.recovered_classification = classification
    run.recovered_params = rec_params
    run.recovered_objective = rec_obj

    classified_ok = bool(classification) and str(classification).upper() in expected_classification

    if not result.get("success", False):
        if classification and not classified_ok:
            run.failure_bucket = "classification_miss"
        elif result.get("status") == "infeasible":
            run.failure_bucket = "agent_infeasible"
        elif "extracted_params" not in result or rec_params is None:
            run.failure_bucket = "extraction_fail"
        else:
            run.failure_bucket = "solver_error"
        run.error = result.get("error")
        return run

    if not classified_ok:
        run.failure_bucket = "classification_miss"
        run.error = f"got {classification!r}, expected one of {sorted(expected_classification)}"
        return run

    recall = _param_recall(generated_params, rec_params or {}, domain=domain)
    run.param_recall_overall = recall["overall"]
    run.objective_gap = _obj_gap(true_obj, rec_obj)
    if run.objective_gap > gap_threshold:
        run.failure_bucket = "objective_mismatch"
    return run


def _run_seed(
    seed: int, domain: str, k: int, agent, llm, gap_threshold: float,
) -> SeedResult:
    from solvers.scheduling.single_stage_ipm import SingleStageIPMSolver
    from solvers.transport.bipartite import BipartiteTransportSolver
    from .generators.scheduling_generator import generate as gen_sched
    from .generators.transport_generator import generate as gen_tran
    from .verbalizer import paraphrase, verbalize

    spec = {
        "transport": (gen_tran, BipartiteTransportSolver,
                      {"TRANSPORTATION"}),
        "scheduling": (gen_sched, SingleStageIPMSolver,
                       {"SINGLE_STAGE_SCHEDULING", "SINGLE_MACHINE_MAKESPAN",
                        "PARALLEL_MACHINE_SCHEDULING"}),
    }[domain]
    generator, solver_cls, expected = spec

    params = generator(seed)
    out = SeedResult(seed=seed, domain=domain)

    true_sol = solver_cls().solve(params)
    if true_sol.get("status") != "OPTIMAL":
        return out
    obj_val = true_sol.get("objective_value", true_sol.get("objective"))
    out.true_objective = float(obj_val) if obj_val is not None else None

    canonical_text = verbalize(
        params, llm, cache_key=f"seed:{seed}:style:neutral", domain=domain,
    )
    out.canonical = _one_pipeline_run(
        "canonical", canonical_text, agent, domain, expected,
        out.true_objective, params, gap_threshold,
    )

    paraphrases = paraphrase(
        canonical_text, llm, params, domain=domain, k=k,
        cache_key=f"seed:{seed}:style:neutral",
    )
    for idx, ptext in enumerate(paraphrases):
        run = _one_pipeline_run(
            f"paraphrase_{idx}", ptext, agent, domain, expected,
            out.true_objective, params, gap_threshold,
        )
        out.paraphrases.append(run)

    return out


def _summarize(seed_results: List[SeedResult], gap_threshold: float) -> Dict[str, Any]:
    """Aggregate paraphrase agreement + canonical-vs-paraphrase pass-rate gap."""
    canonical_pass = 0
    canonical_total = 0
    paraphrase_pass = 0
    paraphrase_total = 0
    canonical_buckets: Counter = Counter()
    paraphrase_buckets: Counter = Counter()
    agreement_with_canonical_pass = 0
    agreement_with_canonical_total = 0
    per_seed_recall_std = []

    for r in seed_results:
        if r.canonical is None:
            continue
        canonical_total += 1
        if r.canonical.objective_gap is not None and r.canonical.objective_gap < gap_threshold:
            canonical_pass += 1
        if r.canonical.failure_bucket:
            canonical_buckets[r.canonical.failure_bucket] += 1

        recalls = []
        if r.canonical.param_recall_overall is not None:
            recalls.append(r.canonical.param_recall_overall)

        canonical_obj = r.canonical.recovered_objective
        for p in r.paraphrases:
            paraphrase_total += 1
            if p.objective_gap is not None and p.objective_gap < gap_threshold:
                paraphrase_pass += 1
            if p.failure_bucket:
                paraphrase_buckets[p.failure_bucket] += 1
            if p.param_recall_overall is not None:
                recalls.append(p.param_recall_overall)
            if canonical_obj is not None and p.recovered_objective is not None:
                agreement_with_canonical_total += 1
                rel = abs(canonical_obj - p.recovered_objective) / max(abs(canonical_obj), 1e-9)
                if rel < gap_threshold:
                    agreement_with_canonical_pass += 1

        if len(recalls) >= 2:
            per_seed_recall_std.append(_st.pstdev(recalls))

    def _safe_rate(num, denom):
        return num / denom if denom else 0.0

    return {
        "seeds": len(seed_results),
        "canonical_pass_rate": _safe_rate(canonical_pass, canonical_total),
        "paraphrase_pass_rate": _safe_rate(paraphrase_pass, paraphrase_total),
        "synthetic_vs_real_gap": (
            _safe_rate(canonical_pass, canonical_total)
            - _safe_rate(paraphrase_pass, paraphrase_total)
        ),
        "paraphrase_agreement_with_canonical": _safe_rate(
            agreement_with_canonical_pass, agreement_with_canonical_total,
        ),
        "canonical_failure_histogram": dict(canonical_buckets),
        "paraphrase_failure_histogram": dict(paraphrase_buckets),
        "per_seed_recall_std_mean": (
            _st.mean(per_seed_recall_std) if per_seed_recall_std else None
        ),
        "gap_threshold": gap_threshold,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Paraphrase-holdout robustness eval")
    p.add_argument("--domain", choices=["transport", "scheduling"], default="transport")
    p.add_argument("--seeds", default="1,2,3", help="Comma-separated seeds")
    p.add_argument("--k", type=int, default=3, help="Paraphrases per seed (max 10)")
    p.add_argument("--gap-threshold", type=float, default=0.01)
    p.add_argument("--output", default="")
    args = p.parse_args(argv)

    from agent.core import OptimizationAgent
    from llm.enhanced_client import EnhancedLLMClient

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    print(f"[paraphrase_holdout] domain={args.domain} seeds={seeds} k={args.k} "
          f"backend={args.backend}", flush=True)

    llm = EnhancedLLMClient()
    agent = OptimizationAgent(llm)

    t0 = time.perf_counter()
    seed_results: List[SeedResult] = []
    for i, seed in enumerate(seeds, 1):
        print(f"  [{i}/{len(seeds)}] seed={seed} starting...", flush=True)
        r = _run_seed(seed, args.domain, args.k, agent, llm, args.gap_threshold)
        seed_results.append(r)
        canon_bucket = r.canonical.failure_bucket if r.canonical else "(no-canonical)"
        para_buckets = [p.failure_bucket or "ok" for p in r.paraphrases]
        print(f"     canonical={canon_bucket or 'ok'} paraphrases={para_buckets}",
              flush=True)

    elapsed = time.perf_counter() - t0
    report = {
        "domain": args.domain,
        "k": args.k,
        "started_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "wall_seconds": elapsed,
        "metrics": _summarize(seed_results, args.gap_threshold),
        "seed_results": [r.to_dict() for r in seed_results],
    }

    if args.output:
        out_path = Path(args.output)
    else:
        _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = _RESULTS_DIR / f"paraphrase_{args.domain}_{ts}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n[paraphrase_holdout] wrote {out_path}", flush=True)
    print(json.dumps(report["metrics"], indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
