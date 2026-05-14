"""Run one round-trip cycle: params → solve → verbalize → agent → compare.

The cycle:
    1. generate(seed)         -> params
    2. solver.solve(params)   -> true_objective (ground truth, by construction)
    3. verbalize(params)      -> natural-language problem text
    4. agent.solve(text)      -> recovered_classification, recovered_params, recovered_obj
    5. comparators            -> param_recall, objective_gap

Failure modes are captured in `error`/`failure_bucket`, not raised, so a batch
run can finish and still produce a histogram.

Domain dispatch lets the same orchestrator run transport or scheduling round-trips.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional

from solvers.scheduling.single_stage_ipm import SingleStageIPMSolver
from solvers.transport.bipartite import BipartiteTransportSolver

from .comparators import objective_gap, param_recall
from .generators.scheduling_generator import generate as generate_scheduling
from .generators.transport_generator import generate as generate_transport
from .verbalizer import verbalize


@dataclass
class RoundTripResult:
    seed: int
    domain: str = "transport"
    generated_params: Dict[str, Any] = field(default_factory=dict)
    true_objective: Optional[float] = None
    verbalized_text: Optional[str] = None
    recovered_classification: Optional[str] = None
    recovered_params: Optional[Dict[str, Any]] = None
    recovered_objective: Optional[float] = None
    param_recall: Optional[Dict[str, Any]] = None
    objective_gap: Optional[float] = None
    stage_latencies_ms: Dict[str, float] = field(default_factory=dict)
    failure_bucket: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_BUCKETS = {
    "generator_infeasible",
    "verbalizer_error",
    "classification_miss",
    "extraction_fail",
    "agent_infeasible",
    "solver_error",
    "objective_mismatch",
    "agent_exception",
}


_DOMAINS = {
    "transport": {
        "generator": generate_transport,
        "solver_factory": BipartiteTransportSolver,
        "expected_classification": {"TRANSPORTATION"},
    },
    "scheduling": {
        "generator": generate_scheduling,
        "solver_factory": SingleStageIPMSolver,
        # All three classifier labels route to the same single-stage IPM solver
        # via the fallback mapping in llm/problem_classifier.py:25.
        "expected_classification": {
            "SINGLE_STAGE_SCHEDULING",
            "SINGLE_MACHINE_MAKESPAN",
            "PARALLEL_MACHINE_SCHEDULING",
        },
    },
}


def _timed(fn, *args, **kwargs):
    t0 = time.perf_counter()
    out = fn(*args, **kwargs)
    return out, (time.perf_counter() - t0) * 1000.0


def _extract_objective(solution: Any) -> Optional[float]:
    """Solvers vary on the objective key — transport exposes `objective_value`,
    scheduling exposes `objective`. Accept either."""
    if not isinstance(solution, dict):
        return None
    val = solution.get("objective_value")
    if val is None:
        val = solution.get("objective")
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def run_one(
    seed: int,
    agent,
    llm_client,
    gap_threshold: float = 0.01,
    domain: str = "transport",
) -> RoundTripResult:
    """Run a single round-trip for one seed.

    Args:
        seed: RNG seed for generator (deterministic instance).
        agent: an OptimizationAgent instance.
        llm_client: an EnhancedLLMClient (verbalizer uses its reasoning model).
        gap_threshold: objective gap above which we bucket as 'objective_mismatch'.
        domain: "transport" or "scheduling".
    """
    if domain not in _DOMAINS:
        raise ValueError(f"Unknown domain {domain!r}; expected one of {list(_DOMAINS)}")
    spec = _DOMAINS[domain]

    params = spec["generator"](seed)
    latencies: Dict[str, float] = {}

    # Ground-truth solve
    solver = spec["solver_factory"]()
    try:
        true_solution, dt = _timed(solver.solve, params)
        latencies["true_solve"] = dt
    except Exception as e:
        return RoundTripResult(
            seed=seed, domain=domain, generated_params=params,
            failure_bucket="generator_infeasible", error=f"true_solve: {e}",
            stage_latencies_ms=latencies,
        )

    if true_solution.get("status") != "OPTIMAL":
        return RoundTripResult(
            seed=seed, domain=domain, generated_params=params,
            failure_bucket="generator_infeasible",
            error=f"true_solve status={true_solution.get('status')}",
            stage_latencies_ms=latencies,
        )

    true_obj = _extract_objective(true_solution)

    # Verbalize
    try:
        text, dt = _timed(
            verbalize, params, llm_client,
            cache_key=f"seed:{seed}:style:neutral",
            domain=domain,
        )
        latencies["verbalize"] = dt
    except Exception as e:
        return RoundTripResult(
            seed=seed, domain=domain, generated_params=params, true_objective=true_obj,
            failure_bucket="verbalizer_error", error=f"verbalize: {e}",
            stage_latencies_ms=latencies,
        )

    # Agent round-trip — use a fresh context so prior runs don't bleed in
    fresh_context = {"last_solution": None, "messages": [], "analysis_history": []}
    try:
        result, dt = _timed(
            agent.solve_natural_language, text, None, fresh_context,
        )
        latencies["agent"] = dt
    except Exception as e:
        return RoundTripResult(
            seed=seed, domain=domain, generated_params=params, true_objective=true_obj,
            verbalized_text=text,
            failure_bucket="agent_exception", error=f"agent: {e}",
            stage_latencies_ms=latencies,
        )

    classification = result.get("problem_type")
    rec_params = result.get("extracted_params")
    rec_solution = result.get("solution") or {}
    rec_obj = _extract_objective(rec_solution)

    expected = spec["expected_classification"]
    classified_ok = bool(classification) and str(classification).upper() in expected

    if not result.get("success", False):
        # Classification miss takes precedence over generic extraction failure,
        # since the agent surfaces both as success=False with no extracted_params.
        if classification and not classified_ok:
            bucket = "classification_miss"
        elif result.get("status") == "infeasible":
            bucket = "agent_infeasible"
        elif "extracted_params" not in result or rec_params is None:
            bucket = "extraction_fail"
        else:
            bucket = "solver_error"
        return RoundTripResult(
            seed=seed, domain=domain, generated_params=params, true_objective=true_obj,
            verbalized_text=text, recovered_classification=classification,
            recovered_params=rec_params, recovered_objective=rec_obj,
            failure_bucket=bucket, error=result.get("error"),
            stage_latencies_ms=latencies,
        )

    if not classified_ok:
        return RoundTripResult(
            seed=seed, domain=domain, generated_params=params, true_objective=true_obj,
            verbalized_text=text, recovered_classification=classification,
            recovered_params=rec_params, recovered_objective=rec_obj,
            failure_bucket="classification_miss",
            error=f"got {classification!r}, expected one of {sorted(expected)}",
            stage_latencies_ms=latencies,
        )

    recall = param_recall(params, rec_params or {}, domain=domain)
    gap = objective_gap(true_obj, rec_obj)

    bucket = None
    if gap > gap_threshold:
        bucket = "objective_mismatch"

    return RoundTripResult(
        seed=seed,
        domain=domain,
        generated_params=params,
        true_objective=true_obj,
        verbalized_text=text,
        recovered_classification=classification,
        recovered_params=rec_params,
        recovered_objective=rec_obj,
        param_recall=recall,
        objective_gap=gap,
        failure_bucket=bucket,
        stage_latencies_ms=latencies,
    )
