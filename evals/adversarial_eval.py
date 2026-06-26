"""Run each adversarial transform against each seed, characterise the outcome.

Outputs a JSON report shaped for skim-reading:

    per_transform: {
      <transform_name>: {
        expected_category: "should_solve" | "graceful_degrade",
        n: <int>,
        end_to_end_pass: <count>,           # gap < threshold
        recovered_with_drift: <count>,      # answered but gap >= threshold
        graceful_failure: <count>,          # buckets: extraction_fail,
                                            #          classification_miss,
                                            #          agent_infeasible
        hard_failure: <count>,              # agent_exception, solver_error
        buckets: {<bucket>: <count>, ...},
      }, ...
    }

The signal:
  - should_solve  AND end_to_end_pass low   -> brittleness against benign noise
  - graceful_degrade AND end_to_end_pass high -> *hallucination* (the agent
    silently produced a confident answer for an under-specified input)
  - either category AND hard_failure > 0    -> crash path worth investigating

Usage:
    python -m evals.adversarial_eval --domain transport --seeds 1,2,3
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


_RESULTS_DIR = Path(__file__).parent / "results"

_GRACEFUL_BUCKETS = {
    "extraction_fail", "classification_miss", "agent_infeasible",
}
_HARD_BUCKETS = {"agent_exception", "solver_error", "verbalizer_error"}


@dataclass
class _AdvRun:
    transform: str
    expected_category: str
    seed: int
    perturbed_text: str = ""
    recovered_classification: Optional[str] = None
    recovered_params: Optional[Dict[str, Any]] = None
    recovered_objective: Optional[float] = None
    param_recall_overall: Optional[float] = None
    objective_gap: Optional[float] = None
    failure_bucket: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _outcome(run: _AdvRun, gap_threshold: float) -> str:
    """Classify a run into one of: end_to_end_pass, recovered_with_drift,
    graceful_failure, hard_failure."""
    if run.failure_bucket in _HARD_BUCKETS:
        return "hard_failure"
    if run.failure_bucket in _GRACEFUL_BUCKETS:
        return "graceful_failure"
    if run.objective_gap is not None and run.objective_gap < gap_threshold:
        return "end_to_end_pass"
    # Recovered an objective but it's outside threshold, OR objective_mismatch bucket.
    return "recovered_with_drift"


def _summarize(runs: List[_AdvRun], gap_threshold: float) -> Dict[str, Any]:
    by_transform: Dict[str, List[_AdvRun]] = defaultdict(list)
    for r in runs:
        by_transform[r.transform].append(r)

    out: Dict[str, Any] = {}
    for name, group in by_transform.items():
        outcomes = Counter(_outcome(r, gap_threshold) for r in group)
        buckets = Counter(r.failure_bucket for r in group if r.failure_bucket)
        out[name] = {
            "expected_category": group[0].expected_category,
            "n": len(group),
            "end_to_end_pass": outcomes.get("end_to_end_pass", 0),
            "recovered_with_drift": outcomes.get("recovered_with_drift", 0),
            "graceful_failure": outcomes.get("graceful_failure", 0),
            "hard_failure": outcomes.get("hard_failure", 0),
            "buckets": dict(buckets),
        }
    return out


def _one_run(
    transform_name: str,
    expected_category: str,
    seed: int,
    perturbed: str,
    params: Dict[str, Any],
    true_obj: Optional[float],
    domain: str,
    expected_classification: set,
    agent,
    gap_threshold: float,
) -> _AdvRun:
    from .comparators import objective_gap as _obj_gap, param_recall as _param_recall

    run = _AdvRun(transform=transform_name, expected_category=expected_category,
                  seed=seed, perturbed_text=perturbed)
    fresh = {"last_solution": None, "messages": [], "analysis_history": []}
    try:
        result = agent.solve_natural_language(perturbed, None, fresh)
    except Exception as e:
        run.failure_bucket = "agent_exception"
        run.error = f"agent: {e}"
        return run

    classification = result.get("problem_type")
    rec_params = result.get("extracted_params")
    rec_solution = result.get("solution") or {}
    rec_obj = rec_solution.get("objective_value") or rec_solution.get("objective")
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
        return run

    recall = _param_recall(params, rec_params or {}, domain=domain)
    run.param_recall_overall = recall["overall"]
    run.objective_gap = _obj_gap(true_obj, rec_obj)
    if run.objective_gap > gap_threshold:
        run.failure_bucket = "objective_mismatch"
    return run


def main(argv=None):
    p = argparse.ArgumentParser(description="Adversarial extraction characterisation")
    p.add_argument("--domain", choices=["transport", "scheduling"], default="transport")
    p.add_argument("--seeds", default="1,2,3")
    p.add_argument("--gap-threshold", type=float, default=0.01)
    p.add_argument("--output", default="")
    args = p.parse_args(argv)

    from agent.core import OptimizationAgent
    from llm.enhanced_client import EnhancedLLMClient
    from solvers.scheduling.single_stage_ipm import SingleStageIPMSolver
    from solvers.transport.bipartite import BipartiteTransportSolver
    from .adversarial import transforms_for
    from .generators.scheduling_generator import generate as gen_sched
    from .generators.transport_generator import generate as gen_tran
    from .verbalizer import verbalize

    seeds = [int(s.strip()) for s in args.seeds.split(",") if s.strip()]
    spec = {
        "transport": (gen_tran, BipartiteTransportSolver, {"TRANSPORTATION"}),
        "scheduling": (gen_sched, SingleStageIPMSolver,
                       {"SINGLE_STAGE_SCHEDULING", "SINGLE_MACHINE_MAKESPAN",
                        "PARALLEL_MACHINE_SCHEDULING"}),
    }[args.domain]
    generator, solver_cls, expected_cls = spec

    transforms = transforms_for(args.domain)
    print(f"[adversarial] domain={args.domain} seeds={seeds} "
          f"transforms={[t.name for t in transforms]}", flush=True)

    llm = EnhancedLLMClient()
    agent = OptimizationAgent(llm)

    runs: List[_AdvRun] = []
    t0 = time.perf_counter()
    for seed in seeds:
        params = generator(seed)
        true_sol = solver_cls().solve(params)
        true_obj = (true_sol.get("objective_value") or true_sol.get("objective")
                    if true_sol.get("status") == "OPTIMAL" else None)
        if true_obj is None:
            print(f"  seed={seed} ground-truth not OPTIMAL, skipping", flush=True)
            continue
        canonical = verbalize(params, llm,
                              cache_key=f"seed:{seed}:style:neutral",
                              domain=args.domain)
        for tr in transforms:
            perturbed = tr.apply(canonical, params, seed)
            print(f"  seed={seed} transform={tr.name} ...", flush=True)
            run = _one_run(tr.name, tr.expected_category, seed, perturbed,
                           params, float(true_obj), args.domain, expected_cls,
                           agent, args.gap_threshold)
            outcome = _outcome(run, args.gap_threshold)
            print(f"     outcome={outcome} bucket={run.failure_bucket or 'ok'} "
                  f"gap={run.objective_gap}", flush=True)
            runs.append(run)

    report = {
        "domain": args.domain,
        "started_at": _dt.datetime.now().isoformat(timespec="seconds"),
        "wall_seconds": time.perf_counter() - t0,
        "per_transform": _summarize(runs, args.gap_threshold),
        "runs": [r.to_dict() for r in runs],
    }
    if args.output:
        out_path = Path(args.output)
    else:
        _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = _RESULTS_DIR / f"adversarial_{args.domain}_{ts}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\n[adversarial] wrote {out_path}", flush=True)
    print(json.dumps(report["per_transform"], indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
