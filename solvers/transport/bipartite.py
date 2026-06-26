# solvers/transport/bipartite.py
"""
Bipartite Transportation Problem Solver

Handles single-commodity transportation from plants to markets with:
- Supply capacity constraints at plants
- Demand requirements at markets
- Linear transportation costs (distance * freight rate)

Optionally supports:
- Fixed charges per route (binary open/close decision -> MIP)
- Arc capacity limits

Does NOT support:
- Transshipment / intermediate nodes
- Multi-commodity flow
- Time-indexed / multi-period
"""

from typing import Dict, List, Any, Optional, Tuple
from pyomo.environ import (
    ConcreteModel, Set, Param, Var, NonNegativeReals, Integers, Binary,
    Objective, Constraint, minimize, value, TransformationFactory,
)
from pyomo.core.base.var import VarData
from pyomo.contrib.appsi.solvers.highs import Highs
from ..base import OptimizationSolver


def _model_has_integer_vars(model: ConcreteModel) -> bool:
    """True if any variable in the model has an integer or binary domain.

    Used to gate warm-start: HiGHS LP solver doesn't benefit from a primal
    warm-start (dual simplex from scratch is faster), so we only seed values
    when the model is actually a MIP.
    """
    for v in model.component_data_objects(Var, descend_into=True):
        if v.is_integer() or v.is_binary():
            return True
    return False


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

        # Coverage checks: structural shape passed, but values must actually be
        # there. Empty/partial dicts pass type checks then crash Pyomo at
        # build time (KeyError on Param). Catch them here so the feasibility
        # gate / friendly-error path can surface a real message.
        plants = params.get("plants") or []
        markets = params.get("markets") or []
        capacity = params.get("capacity") or {}
        demand = params.get("demand") or {}

        if plants:
            missing_cap = [p for p in plants if p not in capacity]
            if missing_cap:
                errors.append(f"`capacity` missing entries for plants: {missing_cap}")
        if markets:
            missing_dem = [m for m in markets if m not in demand]
            if missing_dem:
                errors.append(f"`demand` missing entries for markets: {missing_dem}")

        if has_cost and plants and markets:
            cost = params["cost"]
            missing_pairs = []
            for p in plants:
                row = cost.get(p) if isinstance(cost, dict) else None
                for m in markets:
                    if isinstance(cost, dict) and (p, m) in cost:
                        continue
                    if isinstance(row, dict) and m in row:
                        continue
                    missing_pairs.append((p, m))
            if missing_pairs:
                errors.append(f"`cost` missing entries for pairs: {missing_pairs[:5]}{'...' if len(missing_pairs) > 5 else ''}")

        if has_distance_freight and plants and markets:
            distance = params["distance"]
            missing_pairs = []
            for p in plants:
                row = distance.get(p) if isinstance(distance, dict) else None
                for m in markets:
                    if isinstance(distance, dict) and (p, m) in distance:
                        continue
                    if isinstance(row, dict) and m in row:
                        continue
                    missing_pairs.append((p, m))
            if missing_pairs:
                errors.append(f"`distance` missing entries for pairs: {missing_pairs[:5]}{'...' if len(missing_pairs) > 5 else ''}")

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

        # Handle fixed charges (if provided) -> turns the LP into a MIP.
        # fixed_cost[i,j] is incurred once iff route (i,j) carries any flow.
        fixed_cost = params.get("fixed_cost", None)
        if fixed_cost is not None:
            fixed_cost = self._normalize_distance(fixed_cost)

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

        # Fixed-charge structure: binary "is route (i,j) open?" + big-M link.
        # big-M is the tightest valid flow upper bound on the arc:
        # min(supply_i, demand_j, arc_cap_ij) — keeps the LP relaxation strong.
        if fixed_cost is not None:
            m.fc = Param(m.I, m.J, initialize=fixed_cost, default=0.0)
            m.y = Var(m.I, m.J, domain=Binary)

            def bigM(i, j):
                ub = min(capacity[i], demand[j])
                if arc_capacity is not None and (i, j) in arc_capacity:
                    ub = min(ub, arc_capacity[(i, j)])
                return ub

            def link_rule(m, i, j):
                return m.x[i, j] <= bigM(i, j) * m.y[i, j]
            m.fixed_charge_link = Constraint(m.I, m.J, rule=link_rule)

        # Objective (total cost in thousand $); adds fixed charges when present.
        def obj_rule(m):
            transport = sum(m.c[i, j] * m.x[i, j] for i in m.I for j in m.J)
            if fixed_cost is not None:
                return transport + sum(
                    m.fc[i, j] * m.y[i, j] for i in m.I for j in m.J
                )
            return transport
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

    def solve(
        self,
        params: Dict[str, Any],
        warm_start: Optional[Dict[Tuple[str, str], float]] = None,
        time_limit: float = 60.0,
        gap_target: float = 0.01,
    ) -> Dict[str, Any]:
        """
        Build and solve the bipartite transportation model using Pyomo + HiGHS.

        Args:
            params:      problem parameters (plants, markets, capacity, demand,
                         distance, freight or cost)
            warm_start:  optional dict {(plant, market): flow_value} used to seed
                         the solver — comes from the VAM heuristic.
            time_limit:  hard time limit in seconds.
            gap_target:  acceptable relative MIP gap (passed to HiGHS as
                         mip_rel_gap; no-op for pure LP).

        Returns:
            {
                "status": "OPTIMAL" | "INFEASIBLE" | ...,
                "solver_id": "transport_basic_bipartite",
                "objective_value": float,
                "objective": float (backcompat),
                "objective_thousand_usd": float (backcompat),
                "best_bound": float | None,    # HiGHS dual bound
                "gap": float | None,           # |obj - bound| / |obj|
                "flows": [{"plant", "market", "value"}],
                "kpis": {"total_by_plant", "total_by_market"},
                "warm_started": bool,
            }
        """
        errors = self.validate_params(params)
        if errors:
            return {
                "status": "VALIDATION_ERROR",
                "solver_id": self.solver_id,
                "errors": errors,
            }

        m = self.build_model(params)

        warm_start_applied = False
        if warm_start and _model_has_integer_vars(m):
            valid_keys = {(ii, jj) for ii in m.I for jj in m.J}
            has_y = hasattr(m, "y")
            for (i, j), v in warm_start.items():
                key = (str(i), str(j))
                if key in valid_keys:
                    fv = float(v)
                    m.x[key].value = fv
                    # Seed the open/close decision consistently with the flow,
                    # so HiGHS starts from a complete feasible incumbent.
                    if has_y:
                        m.y[key].value = 1 if fv > 1e-9 else 0
            warm_start_applied = True

        solver = Highs()
        solver.config.time_limit = time_limit
        solver.config.load_solution = True
        solver.highs_options = {"mip_rel_gap": gap_target}
        res = solver.solve(m)

        status = str(res.termination_condition).upper().split(".")[-1]

        if status == "OPTIMAL":
            flows_list = [
                {"plant": str(i), "market": str(j), "value": float(value(m.x[i, j]))}
                for i in m.I for j in m.J
            ]
            objective_val = float(value(m.OBJ))
            best_bound = (
                float(res.best_objective_bound)
                if res.best_objective_bound is not None else None
            )
            gap = (
                abs(objective_val - best_bound) / abs(objective_val)
                if best_bound is not None and objective_val != 0 else 0.0
            )

            total_by_plant = {
                str(i): float(sum(value(m.x[i, j]) for j in m.J)) for i in m.I
            }
            total_by_market = {
                str(j): float(sum(value(m.x[i, j]) for i in m.I)) for j in m.J
            }

            result = {
                "status": status,
                "solver_id": self.solver_id,
                "objective_value": objective_val,
                "objective": objective_val,
                "objective_thousand_usd": objective_val,
                "best_bound": best_bound,
                "gap": gap,
                "flows": flows_list,
                "kpis": {
                    "total_by_plant": total_by_plant,
                    "total_by_market": total_by_market,
                },
                "warm_started": warm_start_applied,
            }
            if hasattr(m, "y"):
                result["open_routes"] = [
                    {"plant": str(i), "market": str(j)}
                    for i in m.I for j in m.J
                    if value(m.y[i, j]) > 0.5
                ]
            return result

        return {
            "status": status,
            "solver_id": self.solver_id,
            "objective_value": None,
            "objective": None,
            "objective_thousand_usd": None,
            "best_bound": None,
            "gap": None,
            "flows": [],
            "kpis": {},
            "warm_started": warm_start_applied,
            "message": f"Solver terminated with status: {status}",
        }

    def solve_lp_relaxation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Solve the LP relaxation of the transportation model and return the bound.

        For the current bipartite formulation (continuous vars), this is the
        model itself — the bound equals the LP optimum. Phase 2 (scheduling
        with integer vars) is where relaxation actually loosens the model.

        Returns:
            {"status": str, "bound": float | None}
        """
        errors = self.validate_params(params)
        if errors:
            return {"status": "VALIDATION_ERROR", "bound": None, "errors": errors}

        m = self.build_model(params)
        # Relax any integer/binary vars in the model (no-op today, future-proof).
        TransformationFactory("core.relax_integer_vars").apply_to(m)

        solver = Highs()
        solver.config.load_solution = True
        res = solver.solve(m)
        status = str(res.termination_condition).upper().split(".")[-1]

        if status == "OPTIMAL":
            return {"status": status, "bound": float(value(m.OBJ))}
        return {"status": status, "bound": None}

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
