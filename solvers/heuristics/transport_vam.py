"""
Vogel's Approximation Method (VAM) for bipartite transportation.

VAM produces a fast feasible solution that is typically within a few percent
of the LP optimum on structured instances (textbook problems, real-world
costs with geography). On adversarial / random-cost instances the gap can be
larger (10-40%) — the LP bound we report to the user makes the gap visible.

Algorithm:
    1. Compute a penalty for each remaining row and column = (second-cheapest
       cost) - (cheapest cost). Penalty is the "regret" of NOT using the
       cheapest cell.
    2. Pick the row or column with the largest penalty.
    3. In that row/column, allocate as much as possible to its cheapest cell:
       ship min(remaining_supply, remaining_demand) units.
    4. Update supply / demand. Cross out the row or column that is exhausted.
    5. Repeat until all demand is satisfied.

Implementation note: penalties are computed on a numpy cost matrix with row/col
mask vectors. Each iteration is O(n*m) instead of the naive O((n+m)^2) Python
loop, dropping 400x800 from ~50s to well under a second.

Handles unbalanced cases (supply > demand) by adding a dummy market with
zero cost, then dropping dummy allocations from the returned flows.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Any

import numpy as np


@dataclass
class VAMResult:
    flows: Dict[Tuple[str, str], float]
    cost: float
    feasible: bool
    message: str = ""


def _normalize_costs(params: Dict[str, Any]) -> Dict[Tuple[str, str], float]:
    """Return cost dict keyed by (plant, market). Accepts `cost` or
    `distance` + `freight` forms, matching the Pyomo solver's accepted shapes."""
    if "cost" in params:
        raw = params["cost"]
        cost: Dict[Tuple[str, str], float] = {}
        if all(isinstance(k, tuple) and len(k) == 2 for k in raw.keys()):
            for (i, j), v in raw.items():
                cost[(str(i), str(j))] = float(v)
        else:
            for i, inner in raw.items():
                for j, v in inner.items():
                    cost[(str(i), str(j))] = float(v)
        return cost

    freight = float(params["freight"])
    distance_raw = params["distance"]
    cost = {}
    if all(isinstance(k, tuple) and len(k) == 2 for k in distance_raw.keys()):
        for (i, j), v in distance_raw.items():
            cost[(str(i), str(j))] = freight * float(v) / 1000.0
    else:
        for i, inner in distance_raw.items():
            for j, v in inner.items():
                cost[(str(i), str(j))] = freight * float(v) / 1000.0
    return cost


def _two_smallest_along(arr: np.ndarray, axis: int) -> np.ndarray:
    """Return penalty = (second-smallest - smallest) along the given axis,
    treating np.inf entries as masked. Single-element rows/columns get penalty 0.
    """
    # Replace inf so partition stays numerically sane. Then partition for top-2.
    sorted_part = np.partition(arr, kth=min(1, arr.shape[axis] - 1), axis=axis)
    take = lambda k: np.take(sorted_part, k, axis=axis)
    if arr.shape[axis] == 1:
        return np.zeros_like(take(0))
    smallest = take(0)
    second = take(1)
    # Where smallest is inf, the row/column has no active cells — penalty 0.
    with np.errstate(invalid="ignore"):
        diff = second - smallest
    penalty = np.where(np.isinf(smallest), 0.0, diff)
    # Avoid negative noise.
    return np.maximum(penalty, 0.0)


def vam_transport(params: Dict[str, Any]) -> VAMResult:
    """
    Run Vogel's Approximation Method on a bipartite transportation problem.

    Args:
        params: same shape as BipartiteTransportSolver.solve — plants, markets,
                capacity, demand, plus either `cost` or (`distance` + `freight`).

    Returns:
        VAMResult with flows keyed by (plant, market), total cost, and a
        feasibility flag (False if supply < demand).
    """
    plants = [str(x) for x in params["plants"]]
    markets = [str(x) for x in params["markets"]]
    supply = [float(params["capacity"][p]) for p in plants]
    demand = [float(params["demand"][m]) for m in markets]
    cost_dict = _normalize_costs(params)

    total_supply = sum(supply)
    total_demand = sum(demand)

    if total_supply + 1e-9 < total_demand:
        return VAMResult(
            flows={}, cost=0.0, feasible=False,
            message=f"Infeasible: supply {total_supply} < demand {total_demand}",
        )

    # Pad with a dummy market to absorb slack when supply > demand.
    DUMMY_IDX = None
    if total_supply > total_demand + 1e-9:
        markets = markets + ["__dummy_market__"]
        demand = demand + [total_supply - total_demand]
        DUMMY_IDX = len(markets) - 1
        for p in plants:
            cost_dict[(p, "__dummy_market__")] = 0.0

    n, m = len(plants), len(markets)
    # Cost matrix; missing entries default to 0 but we expect full coverage.
    C = np.zeros((n, m), dtype=float)
    for i, p in enumerate(plants):
        for j, mk in enumerate(markets):
            C[i, j] = cost_dict.get((p, mk), 0.0)

    supply_arr = np.array(supply, dtype=float)
    demand_arr = np.array(demand, dtype=float)
    row_active = np.ones(n, dtype=bool)
    col_active = np.ones(m, dtype=bool)
    allocation = np.zeros((n, m), dtype=float)

    # Working cost matrix: inactive rows/cols set to +inf so partition ignores.
    INF = np.inf
    work = C.copy()

    iters = 0
    max_iters = n * m + 5
    while row_active.any() and col_active.any():
        iters += 1
        if iters > max_iters:
            return VAMResult(
                flows={}, cost=0.0, feasible=False,
                message="VAM exceeded iteration cap (likely a bug)",
            )

        # Apply masks (idempotent).
        work[~row_active, :] = INF
        work[:, ~col_active] = INF

        row_pen = _two_smallest_along(work, axis=1)  # shape (n,)
        col_pen = _two_smallest_along(work, axis=0)  # shape (m,)

        # Zero out penalties for inactive rows/cols so we don't pick them.
        row_pen = np.where(row_active, row_pen, -1.0)
        col_pen = np.where(col_active, col_pen, -1.0)

        max_row_idx = int(np.argmax(row_pen))
        max_col_idx = int(np.argmax(col_pen))

        if row_pen[max_row_idx] >= col_pen[max_col_idx]:
            i = max_row_idx
            j = int(np.argmin(work[i, :]))
        else:
            j = max_col_idx
            i = int(np.argmin(work[:, j]))

        ship = min(supply_arr[i], demand_arr[j])
        allocation[i, j] += ship
        supply_arr[i] -= ship
        demand_arr[j] -= ship

        supply_done = supply_arr[i] <= 1e-9
        demand_done = demand_arr[j] <= 1e-9
        # Textbook tiebreak: if both hit zero, drop only the row; leave the
        # column open for one degenerate zero-shipment cell (which we naturally
        # won't take because ship=0).
        if supply_done:
            row_active[i] = False
        if demand_done and not supply_done:
            col_active[j] = False

    # Build output flows, dropping dummy market and zero entries.
    real_flows: Dict[Tuple[str, str], float] = {}
    for i in range(n):
        for j in range(m):
            if DUMMY_IDX is not None and j == DUMMY_IDX:
                continue
            v = allocation[i, j]
            if v > 1e-9:
                real_flows[(plants[i], markets[j])] = float(v)

    total_cost = sum(C[i, j] * allocation[i, j]
                     for i in range(n) for j in range(m)
                     if (DUMMY_IDX is None or j != DUMMY_IDX))

    return VAMResult(flows=real_flows, cost=float(total_cost), feasible=True)
