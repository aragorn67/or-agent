"""
Heuristic-mode handler for the two-call solve protocol.

Run after classify + extract + feasibility succeed. Produces a fast feasible
answer (VAM for transport, more domains in Phase 2) plus the LP relaxation
bound, and stores the params + heuristic in the job store so /continue can
later warm-start the exact solver.

Why this is a separate module: the existing `solve_natural_language` is the
"do everything end-to-end" entry point. Heuristic mode short-circuits the
solve step and surfaces a different result shape (gap + job_id). Keeping the
divergent logic here keeps `core.py` readable.
"""

from typing import Any, Dict, Optional

from solvers.heuristics.scheduling_lpt import lpt_schedule
from solvers.heuristics.transport_vam import vam_transport
from solvers.transport.bipartite import BipartiteTransportSolver
from solvers.scheduling.single_stage_ipm import SingleStageIPMSolver

from .job_store import JobStore, JobRecord


# Scheduling problem-type aliases coming back from the classifier all map to
# the same single-stage IPM solver and the same LPT heuristic.
_TRANSPORT_KEYS = {"TRANSPORTATION"}
_SCHEDULING_KEYS = {
    "SCHEDULING",
    "SINGLE_STAGE_SCHEDULING",
    "PARALLEL_MACHINE_SCHEDULING",
    "SINGLE_MACHINE_MAKESPAN",
}


def heuristic_mode_supported(problem_type: str) -> bool:
    pt = problem_type.upper()
    return pt in _TRANSPORT_KEYS or pt in _SCHEDULING_KEYS


def is_scheduling(problem_type: str) -> bool:
    return problem_type.upper() in _SCHEDULING_KEYS


def run_heuristic_for_transport(
    params: Dict[str, Any],
    description: str,
    problem_type: str,
    solver_id: str,
    classification: Dict[str, Any],
    job_store: JobStore,
    ask_to_continue: bool,
) -> Dict[str, Any]:
    """
    Run VAM + LP relaxation on a transport problem, persist the result in the
    job store, and return a response shaped for the API.

    Args:
        params: extracted parameters (already validated + feasibility-checked).
        description: original NL description (kept on the job for the
            explanation step later).
        problem_type: e.g. "TRANSPORTATION".
        solver_id: e.g. "transport_basic_bipartite".
        classification: dict from llm.classify_problem (confidence + type).
        job_store: where to persist the job so /continue can find it.
        ask_to_continue: True if the response should include a chat prompt
            asking the user to improve/accept/stop ("heuristic_then_ask" mode).
            False if the user just wants the heuristic answer ("heuristic").

    Returns:
        Dict suitable for API response. Always includes a `job_id` (None only
        on infeasibility — in which case `success` is False).
    """
    vam = vam_transport(params)
    if not vam.feasible:
        return {
            "success": False,
            "mode": "heuristic",
            "status": "infeasible",
            "error": vam.message,
            "problem_type": problem_type,
        }

    # VAM optimises variable cost only — it is fixed-charge-blind. But the
    # cost we *report* for its routing must include the fixed charge it
    # actually incurs on every opened route, otherwise the heuristic cost is
    # understated and the gap-vs-bound goes nonsensically negative.
    true_cost = vam.cost + _fixed_charge_total(params.get("fixed_cost"), vam.flows)

    bipartite = BipartiteTransportSolver()
    lp_result = bipartite.solve_lp_relaxation(params)
    lp_bound = lp_result.get("bound")

    gap_vs_bound: Optional[float] = None
    if lp_bound is not None and true_cost > 0:
        gap_vs_bound = (true_cost - lp_bound) / true_cost

    flows_list = [
        {"plant": str(i), "market": str(j), "value": float(v)}
        for (i, j), v in vam.flows.items()
    ]

    by_plant: Dict[str, float] = {}
    by_market: Dict[str, float] = {}
    for (i, j), v in vam.flows.items():
        by_plant[i] = by_plant.get(i, 0.0) + v
        by_market[j] = by_market.get(j, 0.0) + v

    record: JobRecord = job_store.create(
        problem_type=problem_type,
        solver_id=solver_id,
        params=params,
        heuristic_flows=vam.flows,
        heuristic_cost=true_cost,
        lp_bound=lp_bound,
        description=description,
        classification=classification,
    )

    response: Dict[str, Any] = {
        "success": True,
        "mode": "heuristic",
        "job_id": record.job_id,
        "problem_type": problem_type,
        "confidence": classification.get("confidence"),
        "extracted_params": params,
        "solution": {
            "status": "HEURISTIC_FEASIBLE",
            "solver_id": "transport_vam",
            "objective_value": true_cost,
            "objective": true_cost,
            "best_bound": lp_bound,
            "gap": gap_vs_bound,
            "flows": flows_list,
            "kpis": {"total_by_plant": by_plant, "total_by_market": by_market},
            "warm_started": False,
            "is_heuristic": True,
        },
        "summary": _format_heuristic_summary(true_cost, lp_bound, gap_vs_bound),
    }

    if ask_to_continue:
        response["follow_up_prompt"] = (
            "I have a quick feasible answer. Reply with `optimize` to run the "
            "exact solver, `accept` to use this answer as-is, or `use_heuristic` "
            "to keep the heuristic and finish."
        )
        response["available_actions"] = ["optimize", "accept", "use_heuristic"]

    return response


def _fixed_charge_total(fixed_cost: Any, flows: Dict) -> float:
    """
    Sum the fixed charge incurred by a heuristic's routing: one charge per
    route that carries any flow. Returns 0.0 when the problem has no fixed
    charges. Accepts either nested ({i: {j: c}}) or flat ({(i, j): c})
    fixed-cost specs, matching what the solver/extractor produce.
    """
    if not fixed_cost:
        return 0.0

    def _lookup(i, j) -> float:
        if isinstance(fixed_cost, dict):
            if (i, j) in fixed_cost:
                return float(fixed_cost[(i, j)])
            row = fixed_cost.get(i)
            if isinstance(row, dict) and j in row:
                return float(row[j])
        return 0.0

    total = 0.0
    for (i, j), v in flows.items():
        if v and abs(v) > 1e-9:
            total += _lookup(i, j)
    return total


def _format_heuristic_summary(
    cost: float, lp_bound: Optional[float], gap: Optional[float]
) -> str:
    """One-line summary of the heuristic answer in plain language."""
    if lp_bound is None or gap is None:
        return f"Heuristic solution found with cost {cost:.2f}."
    if gap < 1e-6:
        return (
            f"Heuristic solution found with cost {cost:.2f}. This already "
            f"matches the LP lower bound — it's provably optimal."
        )
    return (
        f"Heuristic solution found with cost {cost:.2f}. The LP lower bound "
        f"is {lp_bound:.2f}, so this answer is at most {gap*100:.1f}% above "
        f"the theoretical optimum."
    )


def run_heuristic_for_scheduling(
    params: Dict[str, Any],
    description: str,
    problem_type: str,
    solver_id: str,
    classification: Dict[str, Any],
    job_store: JobStore,
    ask_to_continue: bool,
) -> Dict[str, Any]:
    """
    Run LPT on a single-stage scheduling problem, persist a warm-start payload,
    and return an API-shaped response. LP relaxation for scheduling isn't yet
    wired, so the response omits `best_bound` and reports the heuristic Cmax
    as the headline figure with a note about the exact-solver alternative.
    """
    lpt = lpt_schedule(params)
    if not lpt.feasible:
        return {
            "success": False,
            "mode": "heuristic",
            "status": "infeasible",
            "error": lpt.message,
            "problem_type": problem_type,
        }

    warm_payload = {
        "assignment": lpt.assignment,
        "sequence": lpt.sequence,
        "completion": lpt.completion,
        "cmax": lpt.cmax,
    }

    record = job_store.create(
        problem_type=problem_type,
        solver_id=solver_id,
        params=params,
        heuristic_flows={},  # not applicable to scheduling
        heuristic_cost=lpt.cmax,
        lp_bound=None,
        description=description,
        classification=classification,
    )
    # Stash the scheduling-specific warm-start payload on the record. We attach
    # it as a free-form attribute since JobRecord doesn't model scheduling
    # state directly — this keeps the dataclass small and Phase 1-compatible.
    record.heuristic_flows = warm_payload  # type: ignore[assignment]

    summary = (
        f"Heuristic schedule found with makespan {lpt.cmax:.2f}. "
        f"Reply `optimize` to run the exact solver and prove optimality."
    )
    if lpt.due_date_violations:
        summary += (
            f" Note: the heuristic violates due dates for "
            f"{lpt.due_date_violations}; the exact solver will repair or "
            f"report infeasibility."
        )

    response: Dict[str, Any] = {
        "success": True,
        "mode": "heuristic",
        "job_id": record.job_id,
        "problem_type": problem_type,
        "confidence": classification.get("confidence"),
        "extracted_params": params,
        "solution": {
            "status": "HEURISTIC_FEASIBLE",
            "solver_id": "scheduling_lpt",
            "objective_value": lpt.cmax,
            "objective": lpt.cmax,
            "Cmax": lpt.cmax,
            "assignments": [{"order": o, "unit": u} for o, u in lpt.assignment.items()],
            "sequence": lpt.sequence,
            "completion": lpt.completion,
            "due_date_violations": lpt.due_date_violations,
            "is_heuristic": True,
            "warm_started": False,
        },
        "summary": summary,
    }

    if ask_to_continue:
        response["follow_up_prompt"] = (
            "I have a feasible schedule. Reply with `optimize` to run the "
            "exact MILP (warm-started from this schedule), `accept` to keep "
            "this answer, or `use_heuristic` to finalize the heuristic."
        )
        response["available_actions"] = ["optimize", "accept", "use_heuristic"]

    return response
