"""Generate feasible single-stage scheduling problem instances with known ground truth.

The output shape matches what SingleStageIPMSolver.solve() consumes:
    {orders, units, eligible, processing_time, due_date, objective}

Generator deliberately stays minimal in Phase 2 — no changeovers, no time windows,
all-eligible-on-all-units, makespan objective. The combinatorics of changeover +
window + partial eligibility blow up extractor recall, and we want the eval to
exercise the full round-trip on the simplest scheduling shape first.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List


_ORDER_POOL = [
    "OrderA", "OrderB", "OrderC", "OrderD", "OrderE",
    "OrderF", "OrderG", "OrderH",
]
_UNIT_POOL = ["Unit1", "Unit2", "Unit3", "Unit4"]


def generate(seed: int) -> Dict[str, Any]:
    """Return a feasible single-stage scheduling params dict.

    Guarantees:
      - 3-4 orders, 2-3 units
      - every order eligible on every unit (simplifies extractor + verbalizer)
      - processing_time integer hours in [1, 5]
      - due_date >> max possible completion, so the instance is always feasible
      - deterministic given the same seed
      - makespan objective
    """
    rng = random.Random(seed)

    n_orders = rng.randint(3, 4)
    n_units = rng.randint(2, 3)
    orders = rng.sample(_ORDER_POOL, n_orders)
    units = rng.sample(_UNIT_POOL, n_units)

    eligible = {o: list(units) for o in orders}

    processing_time = {
        o: {u: float(rng.randint(1, 5)) for u in units}
        for o in orders
    }

    # Loose due dates: sum of max times across orders gives a safe upper bound,
    # even if all orders end up on the same unit. Use that for every order.
    worst_case = sum(max(processing_time[o].values()) for o in orders)
    safe_due = float(worst_case + 5)
    due_date = {o: safe_due for o in orders}

    return {
        "orders": orders,
        "units": units,
        "eligible": eligible,
        "processing_time": processing_time,
        "due_date": due_date,
        "objective": "makespan",
    }


def generate_batch(seeds: List[int]) -> List[Dict[str, Any]]:
    return [generate(s) for s in seeds]
