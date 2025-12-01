# solvers/transport/bipartite.py
"""
Bipartite Transportation Problem Solver

Handles single-commodity transportation from plants to markets with:
- Supply capacity constraints at plants
- Demand requirements at markets
- Linear transportation costs (distance * freight rate)

Does NOT support:
- Transshipment / intermediate nodes
- Multi-commodity flow
- Time-indexed / multi-period
- Fixed charges
- Arc capacity limits
"""

from typing import Dict, List, Any
from pyomo.environ import (
    ConcreteModel, Set, Param, Var, NonNegativeReals,
    Objective, Constraint, minimize, value, SolverFactory
)
from ..base import OptimizationSolver


class BipartiteTransportSolver(OptimizationSolver):
    """
    Bipartite transportation problem solver.

    Mathematical formulation:
        Sets:
            I = plants (sources)
            J = markets (sinks)

        Parameters:
            a[i] = capacity at plant i
            b[j] = demand at market j
            c[i,j] = unit transportation cost from i to j

        Variables:
            x[i,j] >= 0 = shipment from plant i to market j

        Objective:
            minimize Σ c[i,j] * x[i,j]

        Constraints:
            Σ_j x[i,j] <= a[i]  ∀i  (supply)
            Σ_i x[i,j] >= b[j]  ∀j  (demand)
    """

    @property
    def solver_id(self) -> str:
        return "transport_basic_bipartite"

    @property
    def problem_type(self) -> str:
        return "transportation"

    @property
    def description(self) -> str:
        return "Single-commodity bipartite transportation (plants → markets)"

    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        """Validate bipartite transportation parameters"""
        errors = []

        # Required base fields
        required_base = ["plants", "markets", "capacity", "demand"]
        missing = [k for k in required_base if k not in params]
        if missing:
            errors.append(f"Missing required keys: {missing}")
            return errors

        # Cost specification: either `cost` OR (`distance` + `freight`)
        has_cost = "cost" in params
        has_distance_freight = "distance" in params and "freight" in params

        if not (has_cost or has_distance_freight):
            errors.append("Must provide either `cost` OR (`distance` + `freight`)")
            return errors

        if not isinstance(params["plants"], list):
            errors.append("`plants` must be a list of plant IDs")

        if not isinstance(params["markets"], list):
            errors.append("`markets` must be a list of market IDs")

        if not isinstance(params["capacity"], dict):
            errors.append("`capacity` must be a dict {plant: capacity}")

        if not isinstance(params["demand"], dict):
            errors.append("`demand` must be a dict {market: demand}")

        if has_cost and not isinstance(params["cost"], dict):
            errors.append("`cost` must be a dict {(plant, market): cost} or {plant: {market: cost}}")

        if has_distance_freight:
            if not isinstance(params["distance"], dict):
                errors.append("`distance` must be a dict {(plant, market): distance} or {plant: {market: distance}}")
            if not isinstance(params["freight"], (int, float)):
                errors.append("`freight` must be a number")

        return errors

    def get_example_params(self) -> Dict[str, Any]:
        """Return example bipartite transportation parameters"""
        return {
            "plants": ["Seattle", "San Diego"],
            "markets": ["New York", "Chicago", "Topeka"],
            "capacity": {
                "Seattle": 350,
                "San Diego": 600
            },
            "demand": {
                "New York": 325,
                "Chicago": 300,
                "Topeka": 275
            },
            "distance": {
                "Seattle": {"New York": 2.5, "Chicago": 1.7, "Topeka": 1.8},
                "San Diego": {"New York": 2.5, "Chicago": 1.8, "Topeka": 1.4}
            },
            "freight": 90  # $/thousand cases per thousand miles
        }

    def build_model(self, params: Dict[str, Any]):
        """
        Build the Pyomo model for bipartite transportation.

        Separated from solve() to allow feasibility checking to reuse model structure.

        Args:
            params: Problem parameters (plants, markets, capacity, demand, distance/cost, freight)

        Returns:
            ConcreteModel: Pyomo model ready to solve
        """
        # Extract and normalize parameters
        plants: List[str] = [str(x) for x in params["plants"]]
        markets: List[str] = [str(x) for x in params["markets"]]
        capacity: Dict[str, float] = {str(k): float(v) for k, v in params["capacity"].items()}
        demand: Dict[str, float] = {str(k): float(v) for k, v in params["demand"].items()}

        # Handle cost specification: either `cost` OR (`distance` + `freight`)
        if "cost" in params:
            # Direct cost matrix provided
            cost = self._normalize_distance(params["cost"])  # reuse normalizer
            use_direct_cost = True
        else:
            # Distance + freight rate provided
            distance = self._normalize_distance(params["distance"])
            freight: float = float(params["freight"])
            use_direct_cost = False

        # Handle arc capacities (if provided)
        arc_capacity = params.get("arc_capacity", None)
        if arc_capacity is not None:
            arc_capacity = self._normalize_distance(arc_capacity)

        # Build Pyomo model
        m = ConcreteModel()

        # Sets
        m.I = Set(initialize=plants)
        m.J = Set(initialize=markets)

        # Parameters
        m.a = Param(m.I, initialize=capacity)
        m.b = Param(m.J, initialize=demand)

        # Cost parameter: either direct cost or computed from distance + freight
        if use_direct_cost:
            m.c = Param(m.I, m.J, initialize=cost)
        else:
            m.d = Param(m.I, m.J, initialize=distance)
            # Transport cost in thousand $/case: c = freight * d / 1000
            def c_init(m, i, j):
                return freight * m.d[i, j] / 1000.0
            m.c = Param(m.I, m.J, initialize=c_init, mutable=False)

        # Variables
        m.x = Var(m.I, m.J, domain=NonNegativeReals)

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

        # Arc capacity constraints (if provided)
        if arc_capacity is not None:
            m.arc_cap = Param(m.I, m.J, initialize=arc_capacity, default=float('inf'))

            def arc_capacity_rule(m, i, j):
                return m.x[i, j] <= m.arc_cap[i, j]
            m.arc_capacity_constraint = Constraint(m.I, m.J, rule=arc_capacity_rule)

        return m

    def solve(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build and solve the bipartite transportation model using Pyomo + GLPK.

        Args:
            params: Problem parameters (plants, markets, capacity, demand, distance, freight)

        Returns:
            {
                "status": "OPTIMAL" | "INFEASIBLE" | ...,
                "solver_id": "transport_basic_bipartite",
                "objective": float,
                "objective_thousand_usd": float (for backward compatibility),
                "flows": [{"plant": str, "market": str, "value": float}, ...],
                "kpis": {"total_by_plant": {...}, "total_by_market": {...}}
            }
        """
        # Validate
        errors = self.validate_params(params)
        if errors:
            return {
                "status": "VALIDATION_ERROR",
                "solver_id": self.solver_id,
                "errors": errors
            }

        # Build model
        m = self.build_model(params)

        # Solve
        solver = SolverFactory("glpk")
        res = solver.solve(m, tee=False)

        status = str(res.solver.termination_condition).upper()

        # Only extract results if solution is OPTIMAL
        if status == 'OPTIMAL':
            # Extract results (JSON-safe)
            flows_list = [
                {"plant": str(i), "market": str(j), "value": float(value(m.x[i, j]))}
                for i in m.I for j in m.J
            ]
            objective_val = float(value(m.OBJ))

            total_by_plant = {
                str(i): float(sum(value(m.x[i, j]) for j in m.J))
                for i in m.I
            }
            total_by_market = {
                str(j): float(sum(value(m.x[i, j]) for i in m.I))
                for j in m.J
            }

            return {
                "status": status,
                "solver_id": self.solver_id,
                "objective_value": objective_val,  # Standard key name
                "objective": objective_val,  # backward compatibility
                "objective_thousand_usd": objective_val,  # backward compatibility
                "flows": flows_list,
                "kpis": {
                    "total_by_plant": total_by_plant,
                    "total_by_market": total_by_market
                }
            }
        else:
            # Return status without trying to extract uninitialized values
            return {
                "status": status,
                "solver_id": self.solver_id,
                "objective": None,
                "objective_thousand_usd": None,
                "flows": [],
                "kpis": {},
                "message": f"Solver terminated with status: {status}"
            }

    def _normalize_distance(self, distance: Dict[str, Any]) -> Dict[tuple, float]:
        """
        Normalize distance parameter to flat dict with tuple keys.

        Accepts:
            - nested dict: {i: {j: val}}
            - flat dict: {(i, j): val}

        Returns:
            {(i, j): float(val)}
        """
        # If keys are already tuples, return as-is
        if all(isinstance(k, tuple) and len(k) == 2 for k in distance.keys()):
            return {(str(i), str(j)): float(v) for (i, j), v in distance.items()}

        # Otherwise assume nested dict form
        flat: Dict[tuple, float] = {}
        for i, inner in distance.items():
            if not isinstance(inner, dict):
                raise ValueError("`distance` must be {plant: {market: value}} or {(plant, market): value}")
            for j, val in inner.items():
                flat[(str(i), str(j))] = float(val)
        return flat


# Convenience function for backward compatibility
def solve_transport(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Backward-compatible function-based interface.

    Use BipartiteTransportSolver().solve(params) for new code.
    """
    solver = BipartiteTransportSolver()
    return solver.solve(params)
