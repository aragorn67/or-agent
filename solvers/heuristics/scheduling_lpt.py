"""
Longest Processing Time (LPT) heuristic for single-stage parallel-machine
makespan scheduling.

LPT is a classical result: sort jobs by processing time (descending) and assign
each to the machine that becomes free earliest. For identical parallel machines
its makespan is within 4/3 − 1/(3m) of optimal (Graham 1969). We extend the
basic algorithm with:

  - Eligibility: jobs can only go on a subset of machines.
  - Per-(job, machine) processing times (not identical machines).
  - Changeover times charged when scheduling order `ip` after `i` on machine `j`.

The output is a complete primal solution — assignment + sequence per machine +
completion time per job — suitable for warm-starting the IPM MILP. Due dates
are NOT enforced by the heuristic; if it violates a due date the MILP will
detect it and either repair the schedule or report infeasibility. Treating LPT
as best-effort keeps the heuristic simple and lets the exact solver be the
authority on feasibility.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SchedulingHeuristicResult:
    assignment: Dict[str, str]                       # order -> unit
    sequence: Dict[str, List[str]]                   # unit -> [orders in scheduling order]
    completion: Dict[str, float]                     # order -> completion time
    cmax: float
    due_date_violations: List[str] = field(default_factory=list)
    feasible: bool = True
    message: str = ""


def _normalize_matrix_ij(d: Dict[str, Any]) -> Dict[Tuple[str, str], float]:
    """{(i,j): val} or {i: {j: val}} -> flat {(i,j): float}."""
    if all(isinstance(k, tuple) and len(k) == 2 for k in d.keys()):
        return {(str(i), str(j)): float(v) for (i, j), v in d.items()}
    flat: Dict[Tuple[str, str], float] = {}
    for i, inner in d.items():
        if not isinstance(inner, dict):
            continue
        for j, v in inner.items():
            flat[(str(i), str(j))] = float(v)
    return flat


def _normalize_changeover(d: Dict[str, Any]) -> Dict[Tuple[str, str, str], float]:
    """{(i,ip,j): val} or {j: {i: {ip: val}}} -> flat."""
    if not d:
        return {}
    if all(isinstance(k, tuple) and len(k) == 3 for k in d.keys()):
        return {(str(i), str(ip), str(j)): float(v) for (i, ip, j), v in d.items()}
    flat: Dict[Tuple[str, str, str], float] = {}
    for j, level2 in d.items():
        if not isinstance(level2, dict):
            continue
        for i, level3 in level2.items():
            if not isinstance(level3, dict):
                continue
            for ip, v in level3.items():
                flat[(str(i), str(ip), str(j))] = float(v)
    return flat


def lpt_schedule(params: Dict[str, Any]) -> SchedulingHeuristicResult:
    """
    Run LPT on a single-stage scheduling problem.

    Args:
        params: same shape as SingleStageIPMSolver.solve — orders, units,
                eligible, processing_time, due_date (used only for violation
                reporting), optional changeover.

    Returns:
        SchedulingHeuristicResult. `feasible` is True if all orders were
        assigned to some eligible unit; otherwise the heuristic reports the
        infeasibility and the caller can skip warm-starting.
    """
    orders: List[str] = [str(x) for x in params["orders"]]
    units: List[str] = [str(x) for x in params["units"]]
    eligible_raw = params.get("eligible", {})
    eligible: Dict[str, List[str]] = {
        str(i): [str(u) for u in (eligible_raw.get(i, []) or [])]
        for i in orders
    }
    proc = _normalize_matrix_ij(params.get("processing_time", {}))
    changeover = _normalize_changeover(params.get("changeover", {}))
    due_date = {str(k): float(v) for k, v in params.get("due_date", {}).items()}

    # Check feasibility upfront — every order must have ≥ 1 eligible unit.
    no_eligible = [i for i in orders if not eligible[i]]
    if no_eligible:
        return SchedulingHeuristicResult(
            assignment={}, sequence={u: [] for u in units},
            completion={}, cmax=0.0, feasible=False,
            message=f"Orders without eligible units: {no_eligible}",
        )

    # LPT sort: by maximum processing time across eligible units, descending.
    def order_weight(i: str) -> float:
        return max(proc.get((i, j), 0.0) for j in eligible[i])

    order_queue = sorted(orders, key=order_weight, reverse=True)

    unit_finish: Dict[str, float] = {u: 0.0 for u in units}
    unit_last_order: Dict[str, Optional[str]] = {u: None for u in units}
    unit_sequence: Dict[str, List[str]] = {u: [] for u in units}
    assignment: Dict[str, str] = {}
    completion: Dict[str, float] = {}

    for i in order_queue:
        best_unit = None
        best_finish = float("inf")
        for j in eligible[i]:
            p_ij = proc.get((i, j), 0.0)
            last = unit_last_order[j]
            chg = changeover.get((last, i, j), 0.0) if last is not None else 0.0
            candidate_finish = unit_finish[j] + chg + p_ij
            if candidate_finish < best_finish:
                best_finish = candidate_finish
                best_unit = j

        assignment[i] = best_unit
        completion[i] = best_finish
        unit_sequence[best_unit].append(i)
        unit_finish[best_unit] = best_finish
        unit_last_order[best_unit] = i

    cmax = max(completion.values()) if completion else 0.0

    violations = [i for i, c in completion.items()
                  if i in due_date and c > due_date[i] + 1e-6]

    return SchedulingHeuristicResult(
        assignment=assignment,
        sequence=unit_sequence,
        completion=completion,
        cmax=cmax,
        due_date_violations=violations,
        feasible=True,
    )
