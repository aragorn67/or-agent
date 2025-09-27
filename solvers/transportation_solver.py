# solvers/transportation_solver.py
from typing import Dict, List, Any
from pyomo.environ import (
    ConcreteModel, Set, Param, Var, NonNegativeReals,
    Objective, Constraint, minimize, value, SolverFactory
)


def _validate_params(params: Dict[str, Any]) -> None:
    """Basic validation to fail fast with clear errors."""
    required = ["plants", "markets", "capacity", "demand", "distance", "freight"]
    missing = [k for k in required if k not in params]
    if missing:
        raise ValueError(f"Missing required keys: {missing}")

    if not isinstance(params["plants"], list) or not isinstance(params["markets"], list):
        raise ValueError("`plants` and `markets` must be lists of strings.")

    if not isinstance(params["capacity"], dict) or not isinstance(params["demand"], dict):
        raise ValueError("`capacity` and `demand` must be dicts.")

    if not isinstance(params["distance"], dict):
        raise ValueError("`distance` must be a dict (nested dict form supported).")

    if "freight" not in params or not isinstance(params["freight"], (int, float)):
        raise ValueError("`freight` must be a number.")


def _normalize_distance(distance: Dict[str, Any]) -> Dict[tuple, float]:
    """
    Accepts either:
      - nested dict: {i: {j: val}}, or
      - flat dict with tuple keys: {(i, j): val}
    Returns flat dict {(i, j): val}.
    """
    # If keys look like tuples already, return as-is
    if all(isinstance(k, tuple) and len(k) == 2 for k in distance.keys()):
        return distance  # type: ignore[return-value]

    # Otherwise assume nested dict form
    flat: Dict[tuple, float] = {}
    for i, inner in distance.items():
        if not isinstance(inner, dict):
            raise ValueError("`distance` must be a nested dict: {plant: {market: value}}.")
        for j, val in inner.items():
            flat[(i, j)] = float(val)
    return flat


def solve_transport(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build and solve the transportation model using Pyomo + GLPK.
    Returns a JSON-serializable dict with status, objective, flows, and simple KPIs.
    """
    # ---- Validation & normalization ----
    _validate_params(params)
    plants: List[str] = params["plants"]
    markets: List[str] = params["markets"]
    capacity: Dict[str, float] = {k: float(v) for k, v in params["capacity"].items()}
    demand: Dict[str, float] = {k: float(v) for k, v in params["demand"].items()}
    distance = _normalize_distance(params["distance"])
    freight: float = float(params["freight"])

    # ---- Pyomo model ----
    m = ConcreteModel()

    # Sets
    m.I = Set(initialize=plants)
    m.J = Set(initialize=markets)

    # Parameters
    m.a = Param(m.I, initialize=capacity)            # plant capacities (cases)
    m.b = Param(m.J, initialize=demand)              # market demand (cases)
    m.d = Param(m.I, m.J, initialize=distance)       # distance (thousand miles)

    # Transport cost in thousand $/case: c = freight * d / 1000
    def c_init(m, i, j):
        return freight * m.d[i, j] / 1000.0
    m.c = Param(m.I, m.J, initialize=c_init, mutable=False)

    # Variables
    m.x = Var(m.I, m.J, domain=NonNegativeReals)     # shipments (cases)

    # Objective (total cost in thousand $)
    def obj_rule(m):
        return sum(m.c[i, j] * m.x[i, j] for i in m.I for j in m.J)
    m.OBJ = Objective(rule=obj_rule, sense=minimize)

    # Constraints
    def supply_rule(m, i):
        return sum(m.x[i, j] for j in m.J) <= m.a[i]
    m.supply = Constraint(m.I, rule=supply_rule)

    def demand_rule(m, j):
        return sum(m.x[i, j] for i in m.I) >= m.b[j]
    m.demand = Constraint(m.J, rule=demand_rule)

    # ---- Solve ----
    solver = SolverFactory("glpk")
    res = solver.solve(m, tee=False)

    status = str(res.solver.termination_condition).upper()

    # ---- Extract results (JSON-safe) ----
    flows_list = [
        {"plant": i, "market": j, "value": float(value(m.x[i, j]))}
        for i in m.I for j in m.J
    ]
    objective_val = float(value(m.OBJ))

    total_by_plant = {
        i: float(sum(value(m.x[i, j]) for j in m.J))
        for i in m.I
    }
    total_by_market = {
        j: float(sum(value(m.x[i, j]) for i in m.I))
        for j in m.J
    }

    return {
        "status": status,                               # e.g., "OPTIMAL"
        "objective_thousand_usd": objective_val,        # total cost in thousand $
        "flows": flows_list,                             # list of {plant, market, value}
        "kpis": {
            "total_by_plant": total_by_plant,
            "total_by_market": total_by_market
        }
    }