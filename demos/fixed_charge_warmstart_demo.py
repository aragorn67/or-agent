"""
Fixed-charge transportation: cold solve vs VAM-warm-started solve.

This is the concrete demo behind the ANALYSIS.md "6.6x warm-start spike".
A fixed charge per route makes the model a MIP; the VAM heuristic gives a
complete feasible incumbent that HiGHS uses as a warm start.

Run:
    ./Tolis_Env/bin/python demos/fixed_charge_warmstart_demo.py
"""

import random
import time

from solvers.transport.bipartite import BipartiteTransportSolver
from solvers.heuristics.transport_vam import vam_transport


def make_instance(n_plants=22, n_markets=30, seed=7):
    rng = random.Random(seed)
    plants = [f"P{i}" for i in range(n_plants)]
    markets = [f"M{j}" for j in range(n_markets)]
    demand = {m: rng.randint(20, 60) for m in markets}
    total_demand = sum(demand.values())
    # Tight supply slack (~1.12x) so route selection is genuinely
    # combinatorial — this is what makes the MIP non-trivial.
    cap_each = int(total_demand / n_plants * 1.12)
    capacity = {p: cap_each for p in plants}
    cost, fixed_cost = {}, {}
    for p in plants:
        for m in markets:
            cost[(p, m)] = rng.randint(1, 20)
            # Wide fixed-cost spread rewards careful route consolidation.
            fixed_cost[(p, m)] = rng.randint(100, 1500)
    return {
        "plants": plants,
        "markets": markets,
        "capacity": capacity,
        "demand": demand,
        "cost": cost,
        "fixed_cost": fixed_cost,
    }


def main():
    params = make_instance()
    solver = BipartiteTransportSolver()

    print(f"Instance: {len(params['plants'])} plants x "
          f"{len(params['markets'])} markets, fixed charges on every route\n")

    t0 = time.time()
    cold = solver.solve(params, time_limit=120, gap_target=1e-9)
    cold_t = time.time() - t0

    vam = vam_transport(params)
    t0 = time.time()
    warm = solver.solve(params, warm_start=vam.flows,
                         time_limit=120, gap_target=1e-9)
    warm_t = time.time() - t0

    print(f"{'':14}{'cold':>14}{'warm (VAM)':>16}")
    print(f"{'status':14}{cold['status']:>14}{warm['status']:>16}")
    print(f"{'objective':14}{cold['objective_value']:>14.1f}"
          f"{warm['objective_value']:>16.1f}")
    print(f"{'open routes':14}{len(cold['open_routes']):>14}"
          f"{len(warm['open_routes']):>16}")
    print(f"{'wall time (s)':14}{cold_t:>14.2f}{warm_t:>16.2f}")
    print(f"{'warm_started':14}{'':>14}{str(warm['warm_started']):>16}")

    if warm_t > 0:
        print(f"\nspeedup: {cold_t / warm_t:.2f}x  "
              f"(VAM transport-only incumbent: {vam.cost:.0f}; "
              f"fixed charges added by the solver)")


if __name__ == "__main__":
    main()
