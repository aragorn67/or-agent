"""Generate feasible bipartite-transportation problem instances with known ground truth.

The output shape exactly matches what BipartiteTransportSolver.solve() consumes:
    {plants, markets, capacity, demand, cost}

Uses the `cost` form (not distance+freight) so the verbalizer doesn't need to encode
a unit conversion the agent might handle inconsistently.
"""

from __future__ import annotations

import random
from typing import Dict, Any, List


_PLANT_POOL = [
    "Atlanta", "Boston", "Chicago", "Denver", "Phoenix",
    "Seattle", "Houston", "Detroit", "Miami", "Portland",
]
_MARKET_POOL = [
    "Tokyo", "London", "Paris", "Berlin", "Sydney",
    "Toronto", "Madrid", "Rome", "Mumbai", "Cairo",
]


def generate(seed: int) -> Dict[str, Any]:
    """Return a feasible bipartite-transportation params dict.

    Guarantees:
      - 2-5 plants, 2-6 markets
      - total_supply >= total_demand * 1.05 (slack to avoid edge-case infeasibility)
      - costs uniform in [0.5, 10.0], two decimals
      - deterministic given the same seed
    """
    rng = random.Random(seed)

    n_plants = rng.randint(2, 5)
    n_markets = rng.randint(2, 6)
    plants = rng.sample(_PLANT_POOL, n_plants)
    markets = rng.sample(_MARKET_POOL, n_markets)

    demand = {m: rng.randint(50, 400) for m in markets}
    total_demand = sum(demand.values())

    raw_caps = [rng.random() for _ in plants]
    cap_sum = sum(raw_caps)
    target_supply = total_demand * rng.uniform(1.05, 1.6)
    capacity = {
        p: max(50, round(target_supply * (raw / cap_sum)))
        for p, raw in zip(plants, raw_caps)
    }

    cost = {
        p: {m: round(rng.uniform(0.5, 10.0), 2) for m in markets}
        for p in plants
    }

    return {
        "plants": plants,
        "markets": markets,
        "capacity": capacity,
        "demand": demand,
        "cost": cost,
    }


def generate_batch(seeds: List[int]) -> List[Dict[str, Any]]:
    return [generate(s) for s in seeds]
