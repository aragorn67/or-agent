"""
Tests for VAM transport heuristic.

These are unit tests for the heuristic itself, separate from the round-trip
eval framework under evals/. Per the locked plan: evals stay on exact MILP
only; heuristics get their own test surface.
"""

import pytest

from solvers.heuristics.transport_vam import vam_transport
from solvers.transport.bipartite import BipartiteTransportSolver


def _optimal_cost(params):
    """Run the exact Pyomo solver and return objective."""
    result = BipartiteTransportSolver().solve(params)
    assert result["status"] == "OPTIMAL", f"Exact solver failed: {result}"
    return result["objective_value"]


def test_vam_textbook_balanced_2x3():
    """
    Classic balanced 2x3 instance from OR textbooks.
    VAM is known to find the optimum on this example.
    """
    params = {
        "plants": ["A", "B"],
        "markets": ["X", "Y", "Z"],
        "capacity": {"A": 30, "B": 50},
        "demand": {"X": 20, "Y": 40, "Z": 20},
        "cost": {
            ("A", "X"): 8, ("A", "Y"): 6, ("A", "Z"): 10,
            ("B", "X"): 9, ("B", "Y"): 12, ("B", "Z"): 13,
        },
    }
    result = vam_transport(params)
    assert result.feasible
    # Supply == demand == 80; VAM produces a feasible balanced allocation.
    total_shipped = sum(result.flows.values())
    assert total_shipped == pytest.approx(80.0, abs=1e-6)
    # All demand met
    by_market = {}
    for (_, j), v in result.flows.items():
        by_market[j] = by_market.get(j, 0.0) + v
    assert by_market == pytest.approx(params["demand"], abs=1e-6)


def test_vam_matches_lp_optimum_seattle():
    """
    Seattle / San Diego example from the existing example_params.
    For pure LP transport (no fixed charge), VAM is often LP-optimal.
    We allow up to 1% gap to keep the test robust.
    """
    params = BipartiteTransportSolver().get_example_params()
    heuristic = vam_transport(params)
    optimal = _optimal_cost(params)

    assert heuristic.feasible
    gap = (heuristic.cost - optimal) / optimal
    assert gap >= -1e-6, "Heuristic must not beat the LP optimum"
    assert gap <= 0.01, f"VAM gap {gap*100:.2f}% exceeded 1% on Seattle example"


def test_vam_unbalanced_supply_greater_than_demand():
    """When supply > demand, VAM should ship only what's demanded."""
    params = {
        "plants": ["P1", "P2"],
        "markets": ["M1", "M2"],
        "capacity": {"P1": 100, "P2": 100},
        "demand": {"M1": 30, "M2": 40},
        "cost": {
            ("P1", "M1"): 4, ("P1", "M2"): 8,
            ("P2", "M1"): 5, ("P2", "M2"): 3,
        },
    }
    result = vam_transport(params)
    assert result.feasible
    total = sum(result.flows.values())
    assert total == pytest.approx(70.0, abs=1e-6)
    # Optimal: ship 30 from P1->M1 (cost 120) and 40 from P2->M2 (cost 120) = 240
    assert result.cost == pytest.approx(240.0, abs=1e-6)


def test_vam_infeasible_supply_less_than_demand():
    """Supply < demand → feasible=False."""
    params = {
        "plants": ["P1"],
        "markets": ["M1", "M2"],
        "capacity": {"P1": 50},
        "demand": {"M1": 40, "M2": 40},
        "cost": {("P1", "M1"): 1, ("P1", "M2"): 1},
    }
    result = vam_transport(params)
    assert not result.feasible
    assert "Infeasible" in result.message


def test_vam_flows_respect_supply_and_demand():
    """Random-ish instance: assert constraints are satisfied."""
    params = {
        "plants": ["P1", "P2", "P3"],
        "markets": ["M1", "M2", "M3", "M4"],
        "capacity": {"P1": 80, "P2": 100, "P3": 90},
        "demand": {"M1": 50, "M2": 60, "M3": 70, "M4": 40},
        "cost": {
            ("P1", "M1"): 4, ("P1", "M2"): 6, ("P1", "M3"): 9, ("P1", "M4"): 5,
            ("P2", "M1"): 7, ("P2", "M2"): 4, ("P2", "M3"): 3, ("P2", "M4"): 8,
            ("P3", "M1"): 6, ("P3", "M2"): 8, ("P3", "M3"): 5, ("P3", "M4"): 4,
        },
    }
    result = vam_transport(params)
    assert result.feasible

    by_plant = {}
    by_market = {}
    for (i, j), v in result.flows.items():
        by_plant[i] = by_plant.get(i, 0.0) + v
        by_market[j] = by_market.get(j, 0.0) + v

    for p, cap in params["capacity"].items():
        assert by_plant.get(p, 0.0) <= cap + 1e-6, f"Supply violated at {p}"
    for mk, dem in params["demand"].items():
        assert by_market.get(mk, 0.0) == pytest.approx(dem, abs=1e-6), \
            f"Demand mismatch at {mk}"


def test_vam_within_5pct_of_optimum_random_instance():
    """On the 3x4 instance above, VAM should be within 5% of the LP optimum."""
    params = {
        "plants": ["P1", "P2", "P3"],
        "markets": ["M1", "M2", "M3", "M4"],
        "capacity": {"P1": 80, "P2": 100, "P3": 90},
        "demand": {"M1": 50, "M2": 60, "M3": 70, "M4": 40},
        "cost": {
            ("P1", "M1"): 4, ("P1", "M2"): 6, ("P1", "M3"): 9, ("P1", "M4"): 5,
            ("P2", "M1"): 7, ("P2", "M2"): 4, ("P2", "M3"): 3, ("P2", "M4"): 8,
            ("P3", "M1"): 6, ("P3", "M2"): 8, ("P3", "M3"): 5, ("P3", "M4"): 4,
        },
    }
    heuristic = vam_transport(params)
    optimal = _optimal_cost(params)
    gap = (heuristic.cost - optimal) / optimal
    assert -1e-6 <= gap <= 0.05, f"VAM gap {gap*100:.2f}% exceeds 5%"
