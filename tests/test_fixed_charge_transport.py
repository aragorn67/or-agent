"""
Tests for the fixed-charge transportation variant.

Fixed charges turn the pure-LP transport model into a MIP: a binary y[i,j]
decides whether route (i,j) is opened, with a one-time cost fc[i,j]. This is
the formulation behind the 6.6x warm-start spike documented in ANALYSIS.md.
"""

import pytest

from solvers.transport.bipartite import (
    BipartiteTransportSolver,
    _model_has_integer_vars,
)
from solvers.heuristics.transport_vam import vam_transport


def _fixed_charge_params():
    """Small instance where high fixed charges make route consolidation
    strictly cheaper than the LP-optimal spread-out flow."""
    return {
        "plants": ["P1", "P2"],
        "markets": ["M1", "M2", "M3"],
        "capacity": {"P1": 100, "P2": 100},
        "demand": {"M1": 40, "M2": 40, "M3": 40},
        "cost": {
            ("P1", "M1"): 1, ("P1", "M2"): 2, ("P1", "M3"): 3,
            ("P2", "M1"): 3, ("P2", "M2"): 2, ("P2", "M3"): 1,
        },
        "fixed_cost": {
            ("P1", "M1"): 500, ("P1", "M2"): 500, ("P1", "M3"): 500,
            ("P2", "M1"): 500, ("P2", "M2"): 500, ("P2", "M3"): 500,
        },
    }


def test_fixed_charge_builds_a_mip():
    """Presence of fixed_cost must introduce binary vars."""
    solver = BipartiteTransportSolver()
    m = solver.build_model(_fixed_charge_params())
    assert _model_has_integer_vars(m), "fixed_cost should add binary y vars"
    assert hasattr(m, "y")
    assert hasattr(m, "fixed_charge_link")


def test_fixed_charge_solves_and_reports_open_routes():
    solver = BipartiteTransportSolver()
    result = solver.solve(_fixed_charge_params())
    assert result["status"] == "OPTIMAL", result
    assert "open_routes" in result
    # 120 units of demand, every route capacity-limited to <=100, so at least
    # 2 routes must open; high fixed cost discourages opening all 6.
    assert 2 <= len(result["open_routes"]) <= 5
    # Objective must include the fixed charges that were paid.
    n_open = len(result["open_routes"])
    assert result["objective_value"] >= 500 * n_open


def test_no_fixed_cost_stays_pure_lp():
    """Regression: omitting fixed_cost keeps the model continuous (LP)."""
    params = _fixed_charge_params()
    del params["fixed_cost"]
    m = BipartiteTransportSolver().build_model(params)
    assert not _model_has_integer_vars(m)
    assert not hasattr(m, "y")


def test_lp_relaxation_drops_below_mip_optimum():
    """The relaxed bound must be <= the integer optimum (valid lower bound)."""
    solver = BipartiteTransportSolver()
    params = _fixed_charge_params()
    mip = solver.solve(params)
    relaxed = solver.solve_lp_relaxation(params)
    assert relaxed["status"] == "OPTIMAL"
    assert relaxed["bound"] <= mip["objective_value"] + 1e-6


def test_warm_start_seeds_binary_and_matches_cold():
    """Warm-starting from the VAM flows must reach the same optimum as cold."""
    solver = BipartiteTransportSolver()
    params = _fixed_charge_params()

    cold = solver.solve(params)
    vam = vam_transport(params)
    assert vam.feasible
    warm = solver.solve(params, warm_start=vam.flows)

    assert warm["warm_started"] is True
    assert cold["status"] == warm["status"] == "OPTIMAL"
    assert warm["objective_value"] == pytest.approx(
        cold["objective_value"], rel=1e-6
    )
