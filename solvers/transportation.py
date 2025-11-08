# solvers/enhanced_transportation.py
from typing import Dict, Any, List, Optional
from .base import OptimizationSolver
from pyomo.environ import (
    ConcreteModel, Set, Param, Var, NonNegativeReals, Binary,
    Objective, Constraint, minimize, value, SolverFactory
)

class TransportationSolver(OptimizationSolver):
    """Enhanced transportation solver with advanced features"""

    @property
    def problem_type(self) -> str:
        return "transportation"

    @property
    def description(self) -> str:
        return "Advanced transportation optimization with multiple variants and constraints"

    def solve(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Solve transportation problem with enhanced features"""

        # Extract parameters
        plants = params["plants"]
        markets = params["markets"]
        capacity = {k: float(v) for k, v in params["capacity"].items()}
        demand = {k: float(v) for k, v in params["demand"].items()}
        cost = params["cost"]  # Already in cost[plant][market] format

        # Optional parameters
        integer_shipments = params.get("integer_shipments", False)
        allow_unbalanced = params.get("allow_unbalanced", False)
        constraints = params.get("constraints", [])

        # Build Pyomo model
        m = ConcreteModel()

        # Sets
        m.I = Set(initialize=plants)  # Plants
        m.J = Set(initialize=markets)  # Markets

        # Parameters
        m.capacity = Param(m.I, initialize=capacity)
        m.demand = Param(m.J, initialize=demand)

        # Cost parameter - flatten the nested dict
        cost_flat = {}
        for i in plants:
            for j in markets:
                cost_flat[(i, j)] = float(cost[i][j])
        m.cost = Param(m.I, m.J, initialize=cost_flat)

        # Variables
        if integer_shipments:
            m.x = Var(m.I, m.J, domain=NonNegativeReals, within=NonNegativeReals)
            # Note: For true integer, would use Integers domain
        else:
            m.x = Var(m.I, m.J, domain=NonNegativeReals)

        # Objective - minimize total shipping cost
        def obj_rule(m):
            return sum(m.cost[i, j] * m.x[i, j] for i in m.I for j in m.J)
        m.objective = Objective(rule=obj_rule, sense=minimize)

        # Supply constraints
        def supply_rule(m, i):
            return sum(m.x[i, j] for j in m.J) <= m.capacity[i]
        m.supply_constraint = Constraint(m.I, rule=supply_rule)

        # Demand constraints
        if allow_unbalanced:
            # Allow unmet demand (soft constraint)
            def demand_rule(m, j):
                return sum(m.x[i, j] for i in m.I) <= m.demand[j]
        else:
            # Demand must be exactly met
            def demand_rule(m, j):
                return sum(m.x[i, j] for i in m.I) >= m.demand[j]
        m.demand_constraint = Constraint(m.J, rule=demand_rule)

        # Additional custom constraints
        self._add_custom_constraints(m, constraints)

        # Solve
        solver = SolverFactory("glpk")
        result = solver.solve(m, tee=False)

        status = str(result.solver.termination_condition).upper()

        # Extract solution
        if status == "OPTIMAL":
            return self._extract_solution(m, plants, markets, status)
        else:
            return {
                "status": status,
                "error": f"Solver terminated with status: {status}",
                "objective_value": None,
                "flows": [],
                "utilization": {}
            }

    def _add_custom_constraints(self, model, constraints: List[str]):
        """Add custom constraints based on natural language descriptions"""

        for i, constraint_text in enumerate(constraints):
            constraint_lower = constraint_text.lower()

            try:
                # Parse "Plant X cannot ship to Market Y"
                if "cannot ship to" in constraint_lower:
                    parts = constraint_lower.split("cannot ship to")
                    if len(parts) == 2:
                        plant = parts[0].strip().replace("plant ", "").replace("factory ", "")
                        market = parts[1].strip().replace("market ", "").replace("customer ", "")

                        # Find matching plant and market names
                        plant_match = self._find_entity_match(plant, model.I)
                        market_match = self._find_entity_match(market, model.J)

                        if plant_match and market_match:
                            # Add constraint: x[plant, market] = 0
                            setattr(model, f"no_ship_constraint_{i}",
                                   Constraint(expr=model.x[plant_match, market_match] == 0))

                # Parse "minimum X units from Plant Y to Market Z"
                elif "minimum" in constraint_lower and "from" in constraint_lower and "to" in constraint_lower:
                    import re
                    match = re.search(r'minimum\s+(\d+(?:\.\d+)?)\s+units\s+from\s+([^to]+)\s+to\s+(.+)',
                                    constraint_lower)
                    if match:
                        min_amount = float(match.group(1))
                        plant = match.group(2).strip().replace("plant ", "").replace("factory ", "")
                        market = match.group(3).strip().replace("market ", "").replace("customer ", "")

                        plant_match = self._find_entity_match(plant, model.I)
                        market_match = self._find_entity_match(market, model.J)

                        if plant_match and market_match:
                            setattr(model, f"min_ship_constraint_{i}",
                                   Constraint(expr=model.x[plant_match, market_match] >= min_amount))

                # More constraint types can be added here...

            except Exception as e:
                print(f"Warning: Could not parse constraint '{constraint_text}': {e}")
                continue

    def _find_entity_match(self, name: str, entity_set) -> Optional[str]:
        """Find best matching entity name in the set"""
        name_lower = name.lower()

        # Try exact match first
        for entity in entity_set:
            if entity.lower() == name_lower:
                return entity

        # Try partial match
        for entity in entity_set:
            if name_lower in entity.lower() or entity.lower() in name_lower:
                return entity

        return None

    def _extract_solution(self, model, plants: List[str], markets: List[str], status: str) -> Dict[str, Any]:
        """Extract comprehensive solution information"""

        # Extract flows
        flows = []
        for i in plants:
            for j in markets:
                flow_value = value(model.x[i, j])
                if flow_value > 1e-6:  # Only include meaningful flows
                    flows.append({
                        "plant": i,
                        "market": j,
                        "value": float(flow_value)
                    })

        # Calculate utilization metrics
        utilization = {}
        for plant in plants:
            plant_capacity = float(value(model.capacity[plant]))
            plant_usage = sum(value(model.x[plant, market]) for market in markets)
            utilization[plant] = {
                "capacity": plant_capacity,
                "used": float(plant_usage),
                "utilization_rate": float(plant_usage / plant_capacity) if plant_capacity > 0 else 0
            }

        # Calculate market fulfillment
        market_fulfillment = {}
        for market in markets:
            market_demand = float(value(model.demand[market]))
            market_received = sum(value(model.x[plant, market]) for plant in plants)
            market_fulfillment[market] = {
                "demand": market_demand,
                "received": float(market_received),
                "fulfillment_rate": float(market_received / market_demand) if market_demand > 0 else 0
            }

        # Calculate totals
        total_cost = float(value(model.objective))
        total_shipped = sum(flow["value"] for flow in flows)

        return {
            "status": status,
            "objective_value": total_cost,
            "objective_thousand_usd": total_cost,  # For backward compatibility
            "flows": flows,
            "utilization": utilization,
            "market_fulfillment": market_fulfillment,
            "summary": {
                "total_cost": total_cost,
                "total_shipped": float(total_shipped),
                "average_utilization": float(sum(u["utilization_rate"] for u in utilization.values()) / len(utilization)),
                "average_fulfillment": float(sum(f["fulfillment_rate"] for f in market_fulfillment.values()) / len(market_fulfillment))
            },
            "kpis": {
                "total_by_plant": {plant: float(sum(flow["value"] for flow in flows if flow["plant"] == plant)) for plant in plants},
                "total_by_market": {market: float(sum(flow["value"] for flow in flows if flow["market"] == market)) for market in markets}
            }
        }

    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        """Enhanced validation with business logic checks"""
        errors = []

        # Direct validation without circular dependency
        required = ["plants", "markets", "capacity", "demand", "cost"]
        missing = [k for k in required if k not in params or not params[k]]
        if missing:
            return [f"Missing required transportation data: {', '.join(missing)}. Please specify all factories, customers, capacities, demands, and shipping costs."]

        plants = params.get("plants", [])
        markets = params.get("markets", [])
        capacity = params.get("capacity", {})
        demand = params.get("demand", {})
        cost = params.get("cost", {})

        # Entity alignment validation
        if set(capacity.keys()) != set(plants):
            missing_cap = set(plants) - set(capacity.keys())
            if missing_cap:
                errors.append(f"Missing capacity data for plants: {', '.join(missing_cap)}")

        if set(demand.keys()) != set(markets):
            missing_dem = set(markets) - set(demand.keys())
            if missing_dem:
                errors.append(f"Missing demand data for markets: {', '.join(missing_dem)}")

        # Cost matrix completeness
        for plant in plants:
            if plant not in cost:
                errors.append(f"Missing all shipping costs from plant '{plant}'")
            else:
                plant_costs = cost[plant]
                if not isinstance(plant_costs, dict):
                    errors.append(f"Shipping costs from plant '{plant}' must be a dictionary")
                    continue

                missing_routes = [market for market in markets if market not in plant_costs]
                if missing_routes:
                    errors.append(f"Missing shipping costs from plant '{plant}' to markets: {', '.join(missing_routes)}")

        # Numerical validation
        for plant, cap in capacity.items():
            if not isinstance(cap, (int, float)) or cap < 0:
                errors.append(f"Plant '{plant}' capacity must be a non-negative number, got: {cap}")

        for market, dem in demand.items():
            if not isinstance(dem, (int, float)) or dem < 0:
                errors.append(f"Market '{market}' demand must be a non-negative number, got: {dem}")

        # Supply-demand balance check
        total_capacity = sum(capacity.values())
        total_demand = sum(demand.values())

        if total_capacity < total_demand and not params.get("allow_unbalanced", False):
            errors.append(f"Total capacity ({total_capacity}) is less than total demand ({total_demand}). This problem is infeasible unless you allow unmet demand.")

        return errors

    def get_example_params(self) -> Dict[str, Any]:
        """Return enhanced example parameters"""
        return {
            "plants": ["seattle", "san_diego", "chicago"],
            "markets": ["new_york", "denver", "los_angeles", "miami"],
            "capacity": {"seattle": 400, "san_diego": 500, "chicago": 300},
            "demand": {"new_york": 250, "denver": 200, "los_angeles": 300, "miami": 150},
            "cost": {
                "seattle": {"new_york": 225, "denver": 120, "los_angeles": 90, "miami": 280},
                "san_diego": {"new_york": 250, "denver": 150, "los_angeles": 80, "miami": 220},
                "chicago": {"new_york": 180, "denver": 160, "los_angeles": 200, "miami": 190}
            },
            "integer_shipments": False,
            "allow_unbalanced": False,
            "constraints": [
                "seattle cannot ship to miami",
                "minimum 50 units from chicago to new_york"
            ]
        }