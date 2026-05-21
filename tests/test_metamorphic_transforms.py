"""Phase 3 of the eval-hardening plan: deterministic metamorphic invariants.

Round-trip + heuristic tests check correctness against a known ground truth.
Metamorphic tests check the *relationship* between the solution before and
after a structure-preserving transform — so they need no new ground truth,
no LLM, and no extra labelled data. They run pure-solver-only, fast.

Invariants exercised:
    Transport
      - scale all costs by k    -> objective scales by k
      - permute plants / markets-> objective unchanged
      - add a dominated plant   -> objective unchanged
    Scheduling (makespan)
      - scale processing time   -> makespan scales by k
      - permute orders / units  -> makespan unchanged
      - add a zero-time order   -> makespan unchanged
        (the "add unused unit" variant is *not* expressible against the
         single-stage IPM: the SeqCount constraint at
         solvers/scheduling/single_stage_ipm.py:230 requires every unit
         to host ≥ 1 job, so an orphan unit is structurally infeasible.
         Adding a zero-processing-time order is the dual invariant — it
         lands on a unit and contributes nothing to its completion time,
         so the makespan must be unchanged.)

Each invariant runs across multiple generator seeds so a single anomalous
instance won't hide a regression.
"""

from __future__ import annotations

import copy
import random
from typing import Any, Dict, List

import pytest

from evals.generators.scheduling_generator import generate as gen_scheduling
from evals.generators.transport_generator import generate as gen_transport
from solvers.scheduling.single_stage_ipm import SingleStageIPMSolver
from solvers.transport.bipartite import BipartiteTransportSolver


SEEDS = [1, 2, 3, 4, 5]
SCALE_FACTORS = [0.5, 2.0, 10.0]


def _solve_transport(params: Dict[str, Any]) -> float:
    res = BipartiteTransportSolver().solve(params)
    assert res["status"] == "OPTIMAL", f"transport solve not optimal: {res}"
    return float(res["objective_value"])


def _solve_scheduling(params: Dict[str, Any]) -> float:
    res = SingleStageIPMSolver().solve(params)
    assert res["status"] == "OPTIMAL", f"scheduling solve not optimal: {res}"
    val = res.get("objective_value", res.get("objective"))
    assert val is not None
    return float(val)


def _scale_transport_costs(params: Dict[str, Any], k: float) -> Dict[str, Any]:
    out = copy.deepcopy(params)
    out["cost"] = {p: {m: cost * k for m, cost in row.items()}
                   for p, row in params["cost"].items()}
    return out


def _permute_transport(params: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    out = copy.deepcopy(params)
    out["plants"] = list(params["plants"]); rng.shuffle(out["plants"])
    out["markets"] = list(params["markets"]); rng.shuffle(out["markets"])
    return out


def _add_dominated_plant(params: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a plant whose cost to every market is much higher than any
    existing edge. With enough native supply to cover demand, the LP optimum
    will not use it; the objective is unchanged.
    """
    out = copy.deepcopy(params)
    max_cost = max(c for row in params["cost"].values() for c in row.values())
    huge_cost = max_cost * 1000.0 + 1.0
    new_plant = "Ghost_Dominated_Plant"
    out["plants"] = list(params["plants"]) + [new_plant]
    # Capacity large enough to be a real option were it cheap — we want the
    # LP to choose to ignore it because of cost, not capacity.
    out["capacity"] = dict(params["capacity"])
    out["capacity"][new_plant] = sum(params["demand"].values())
    out["cost"] = {p: dict(row) for p, row in params["cost"].items()}
    out["cost"][new_plant] = {m: huge_cost for m in params["markets"]}
    return out


def _scale_processing_time(params: Dict[str, Any], k: float) -> Dict[str, Any]:
    out = copy.deepcopy(params)
    out["processing_time"] = {
        o: {u: pt * k for u, pt in row.items()}
        for o, row in params["processing_time"].items()
    }
    # Due dates must scale too, otherwise infeasibility, not invariance, is what
    # we measure. Generator gives all orders the same safe_due, so scaling here
    # preserves the relative slack.
    out["due_date"] = {o: d * k for o, d in params["due_date"].items()}
    return out


def _permute_scheduling(params: Dict[str, Any], rng: random.Random) -> Dict[str, Any]:
    out = copy.deepcopy(params)
    out["orders"] = list(params["orders"]); rng.shuffle(out["orders"])
    out["units"] = list(params["units"]); rng.shuffle(out["units"])
    return out


def _add_zero_time_order(params: Dict[str, Any]) -> Dict[str, Any]:
    """Add an order whose processing time is zero on every unit. The solver
    must assign it (Σ_j Y[i,j] = 1), but it adds nothing to any unit's
    completion time and so cannot push the makespan up."""
    out = copy.deepcopy(params)
    new_order = "Ghost_Order_Z"
    out["orders"] = list(params["orders"]) + [new_order]
    out["eligible"] = {o: list(units) for o, units in params["eligible"].items()}
    out["eligible"][new_order] = list(params["units"])
    out["processing_time"] = {
        o: dict(row) for o, row in params["processing_time"].items()
    }
    out["processing_time"][new_order] = {u: 0.0 for u in params["units"]}
    out["due_date"] = dict(params["due_date"])
    out["due_date"][new_order] = max(params["due_date"].values())
    return out


# ---------------------------------------------------------------------------
# Transport invariants
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("k", SCALE_FACTORS)
def test_transport_cost_scaling_scales_objective(seed: int, k: float):
    params = gen_transport(seed)
    base = _solve_transport(params)
    scaled = _solve_transport(_scale_transport_costs(params, k))
    assert scaled == pytest.approx(base * k, rel=1e-6, abs=1e-6)


@pytest.mark.parametrize("seed", SEEDS)
def test_transport_permutation_preserves_objective(seed: int):
    params = gen_transport(seed)
    base = _solve_transport(params)
    rng = random.Random(seed + 10_000)
    permuted = _solve_transport(_permute_transport(params, rng))
    assert permuted == pytest.approx(base, rel=1e-6, abs=1e-6)


@pytest.mark.parametrize("seed", SEEDS)
def test_transport_dominated_plant_unused(seed: int):
    params = gen_transport(seed)
    base = _solve_transport(params)
    extended = _solve_transport(_add_dominated_plant(params))
    assert extended == pytest.approx(base, rel=1e-6, abs=1e-6)


# ---------------------------------------------------------------------------
# Scheduling invariants
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("k", SCALE_FACTORS)
def test_scheduling_time_scaling_scales_makespan(seed: int, k: float):
    params = gen_scheduling(seed)
    base = _solve_scheduling(params)
    scaled = _solve_scheduling(_scale_processing_time(params, k))
    # MIP makespan tolerance is looser than LP cost — solver reports a default
    # mipgap; use rel=1e-4 to absorb that without masking genuine drift.
    assert scaled == pytest.approx(base * k, rel=1e-4, abs=1e-6)


@pytest.mark.parametrize("seed", SEEDS)
def test_scheduling_permutation_preserves_makespan(seed: int):
    params = gen_scheduling(seed)
    base = _solve_scheduling(params)
    rng = random.Random(seed + 20_000)
    permuted = _solve_scheduling(_permute_scheduling(params, rng))
    assert permuted == pytest.approx(base, rel=1e-4, abs=1e-6)


@pytest.mark.parametrize("seed", SEEDS)
def test_scheduling_zero_time_order_preserves_makespan(seed: int):
    params = gen_scheduling(seed)
    base = _solve_scheduling(params)
    extended = _solve_scheduling(_add_zero_time_order(params))
    assert extended == pytest.approx(base, rel=1e-4, abs=1e-6)
