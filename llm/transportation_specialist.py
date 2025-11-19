# llm/transportation_specialist.py
import json
from typing import Dict, Any, List, Optional
from .ollama_client import OllamaClient

class TransportationSpecialist:
    """Specialized LLM handler for transportation optimization problems"""

    def __init__(self, ollama_client: OllamaClient, knowledge_base=None):
        """
        Initialize transportation specialist.

        Args:
            ollama_client: LLM client for parameter extraction
            knowledge_base: Optional KnowledgeBase for RAG context
        """
        self.client = ollama_client
        self.kb = knowledge_base

    def extract_parameters(self, description: str) -> Dict[str, Any]:
        """Extract transportation-specific parameters with deep validation"""

        # Get relevant context from knowledge base if available
        rag_context = ""
        if self.kb is not None:
            try:
                rag_context = self.kb.get_context(
                    "transportation problem parameters supply demand cost",
                    max_tokens=500
                )
                if rag_context:
                    rag_context = f"\n\nRelevant OR knowledge:\n{rag_context}\n"
            except:
                pass  # KB not available, continue without RAG

        system = f"""
Extract parameters for a Transportation LP. Output STRICT JSON with keys:{rag_context}
- plants: string[] (factories, warehouses, sources)
- markets: string[] (customers, destinations, demand points)
- capacity: {{plant: number}} (how much each plant can produce/supply)
- demand: {{market: number}} (how much each market needs)
- cost: {{plant: {{market: number}}}} (per-unit shipping cost from plant to market)
- arc_capacity: {{plant: {{market: number}}}} (OPTIONAL: maximum flow on individual routes/lanes. e.g., "From F1 to A: max 50 units, to B: 30, to C: 0" means arc_capacity={{F1: {{A: 50, B: 30, C: 0}}}}. INCLUDE ZERO CAPACITIES! Zero means blocked route.)
- constraints: string[] (optional: special restrictions like "Plant A cannot serve Market X")
- integer_shipments: boolean (optional, default false - if shipments must be whole numbers)
- allow_unbalanced: boolean (optional, default false - if total supply != total demand is OK)

EXTRACTION RULES:
1. Use ONLY entities & numbers explicitly mentioned in the text
2. Look for various phrasings: "factories/plants/warehouses" = plants, "customers/markets/cities" = markets
3. Extract ALL capacity values mentioned (e.g., "Seattle can produce 350 units")
4. Extract ALL demand values mentioned (e.g., "Chicago needs 300 units")
5. Extract distance/cost information - convert to per-unit shipping costs
6. If freight rate given (e.g., "$90 per unit per 1000 miles"), combine with distances
7. **IMPORTANT: Extract arc_capacity if problem mentions "maximum shipping capacity", "lane capacity", "route limits", or "from X to Y: max N units"**
8. **CRITICAL: When extracting arc_capacity, include ALL routes mentioned, even if capacity is 0! A capacity of 0 means that route is blocked. Missing entries will be treated as infinite capacity!**
9. **If cost values are not specified or text says "values not important", use $1 per unit for all routes**
9. If ANY required piece (except cost) is missing, return: {{"error": "<specific missing information>"}}
10. All numbers must be numeric types, not strings
"""

        user = f"TRANSPORTATION PROBLEM:\n{description}\n\nReturn ONLY the JSON."

        try:
            content = self.client._chat(system, user, json_mode=True)
            result = json.loads(content)

            if "error" in result:
                return result

            # Deep validation for transportation
            validation_error = self._validate_transportation_deep(description, result)
            if validation_error:
                return {"error": validation_error}

            return result

        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON response from LLM: {str(e)}"}
        except Exception as e:
            return {"error": f"Transportation extraction error: {e}"}

    def _validate_transportation_deep(self, description: str, params: Dict) -> str:
        """Deep validation specifically for transportation problems"""

        # Core structure validation (cost is optional - can default to $1)
        required = ["plants", "markets", "capacity", "demand"]
        missing = [k for k in required if k not in params or not params[k]]
        if missing:
            return f"Missing required transportation data: {', '.join(missing)}. Please specify all factories, customers, capacities, and demands."

        plants = params["plants"]
        markets = params["markets"]
        capacity = params["capacity"]
        demand = params["demand"]

        # Cost is optional - generate default if missing
        if "cost" not in params or not params["cost"]:
            # Default to $1 per unit for all routes
            params["cost"] = {plant: {market: 1 for market in markets} for plant in plants}

        cost = params["cost"]

        # Entity alignment validation
        if set(capacity.keys()) != set(plants):
            missing_cap = set(plants) - set(capacity.keys())
            extra_cap = set(capacity.keys()) - set(plants)
            if missing_cap:
                return f"Missing capacity data for plants: {', '.join(missing_cap)}"
            if extra_cap:
                return f"Extra capacity data for unknown plants: {', '.join(extra_cap)}"

        if set(demand.keys()) != set(markets):
            missing_dem = set(markets) - set(demand.keys())
            extra_dem = set(demand.keys()) - set(markets)
            if missing_dem:
                return f"Missing demand data for markets: {', '.join(missing_dem)}"
            if extra_dem:
                return f"Extra demand data for unknown markets: {', '.join(extra_dem)}"

        # Cost matrix completeness
        for plant in plants:
            if plant not in cost:
                return f"Missing all shipping costs from plant '{plant}'"
            plant_costs = cost[plant]
            if not isinstance(plant_costs, dict):
                return f"Shipping costs from plant '{plant}' must be a dictionary"

            missing_routes = [market for market in markets if market not in plant_costs]
            if missing_routes:
                return f"Missing shipping costs from plant '{plant}' to markets: {', '.join(missing_routes)}"

        # Numerical validation
        for plant, cap in capacity.items():
            if not isinstance(cap, (int, float)) or cap < 0:
                return f"Plant '{plant}' capacity must be a non-negative number, got: {cap}"

        for market, dem in demand.items():
            if not isinstance(dem, (int, float)) or dem < 0:
                return f"Market '{market}' demand must be a non-negative number, got: {dem}"

        for plant in plants:
            for market in markets:
                cost_val = cost[plant][market]
                if not isinstance(cost_val, (int, float)) or cost_val < 0:
                    return f"Shipping cost from '{plant}' to '{market}' must be a non-negative number, got: {cost_val}"

        # Transportation-specific business logic checks
        # NOTE: We no longer validate feasibility here - that's done by the feasibility module
        # The extraction should extract parameters even if they describe an infeasible problem

        # Prose vs extracted validation
        import re
        text = description.lower()

        # Check mentioned counts vs extracted counts
        plant_match = re.search(r'(\d+)\s+(?:plants?|factories|warehouses|sources)', text)
        if plant_match and int(plant_match.group(1)) != len(plants):
            return f"You mentioned {plant_match.group(1)} plants/factories but I found {len(plants)} plant names. Please list all plant names clearly."

        market_match = re.search(r'(\d+)\s+(?:markets?|customers?|destinations?)', text)
        if market_match and int(market_match.group(1)) != len(markets):
            return f"You mentioned {market_match.group(1)} customers/markets but I found {len(markets)} customer names. Please list all customer names clearly."

        return None  # All validations passed

    def explain_solution(self, solution: Dict) -> str:
        """Generate transportation-specific solution explanation"""

        system = """
You are explaining a Transportation Optimization solution. Focus on:
1. Total shipping cost achieved
2. Key shipping routes chosen (which plants serve which markets)
3. Capacity utilization at plants
4. Whether all demand is satisfied
5. Any notable patterns (e.g., plants serving nearby markets)

Be clear and business-focused. Use 2-3 sentences.
"""

        user = f"Transportation Solution: {json.dumps(solution, indent=2)}"

        try:
            return self.client._chat(system, user, json_mode=False)
        except Exception:
            # Fallback explanation
            obj_cost = solution.get("objective_thousand_usd") or solution.get("objective_value", "N/A")
            return f"Optimal transportation plan found with total shipping cost of ${obj_cost}. Routes and shipment quantities are optimized to minimize cost while meeting all demand constraints."

    def detect_transportation_modifications(self, user_message: str, current_params: Dict) -> Dict[str, Any]:
        """Detect what transportation parameters the user wants to modify"""

        system = """
The user wants to modify their transportation problem. Extract changes they want:

CURRENT STATE:
- Plants and their capacities
- Markets and their demands
- Shipping costs between all plant-market pairs
- Any constraints

DETECT MODIFICATIONS like:
- Capacity changes: "increase Seattle capacity to 500", "double Plant A capacity"
- Demand changes: "Chicago now needs 400", "reduce New York demand by 50"
- Cost changes: "shipping costs increased 20%", "distance from Seattle to Chicago is now 2000 miles"
- New plants/markets: "add factory in Denver with capacity 300"
- Constraints: "Plant A cannot ship to Market X", "minimum 100 units from Seattle to Chicago"

Return JSON:
{
  "modifications": {
    "capacity": {"seattle": 500},  // new capacities
    "demand": {"chicago": 400},    // new demands
    "cost": {"seattle": {"chicago": 180}},  // new shipping costs
    "new_plants": [{"name": "denver", "capacity": 300}],
    "new_markets": [{"name": "boston", "demand": 200}],
    "constraints": ["seattle cannot ship to chicago"],
    "global_changes": {"all_costs_multiplier": 1.2}  // if "all costs up 20%"
  },
  "change_description": "Brief description of changes",
  "confidence": 0.90
}
"""

        user = f"CURRENT PARAMS: {json.dumps(current_params, indent=2)}\n\nUSER REQUEST: {user_message}"

        try:
            content = self.client._chat(system, user, json_mode=True)
            return json.loads(content)
        except Exception as e:
            return {
                "modifications": {},
                "change_description": f"Could not parse modifications: {e}",
                "confidence": 0.0
            }

    def suggest_transportation_analysis(self, solution: Dict, params: Dict) -> List[str]:
        """Suggest transportation-specific analyses based on the solution"""

        suggestions = []

        # Analyze solution characteristics
        flows = solution.get("flows", [])
        if not flows:
            return ["Basic solution visualization"]

        # Check for capacity utilization
        total_capacity = sum(params.get("capacity", {}).values())
        total_shipped = sum(flow.get("value", 0) for flow in flows)
        utilization = total_shipped / total_capacity if total_capacity > 0 else 0

        if utilization < 0.8:
            suggestions.append("Capacity utilization analysis - some plants are underutilized")

        # Check route diversity
        active_routes = len([f for f in flows if f.get("value", 0) > 0.01])
        total_routes = len(flows)

        if active_routes < total_routes * 0.6:
            suggestions.append("Route optimization analysis - many potential routes are unused")

        # Distance-based analysis
        if "distance" in str(params):
            suggestions.append("Distance vs cost trade-off analysis")

        # Sensitivity analysis suggestions
        plants = params.get("plants", [])
        if len(plants) > 1:
            suggestions.append(f"Sensitivity analysis - how capacity changes affect total cost")

        markets = params.get("markets", [])
        if len(markets) > 2:
            suggestions.append("Market demand sensitivity analysis")

        # Supply-demand balance
        total_demand = sum(params.get("demand", {}).values())
        if abs(total_capacity - total_demand) / total_demand > 0.1:
            suggestions.append("Supply-demand balance analysis")

        return suggestions[:4]  # Top 4 suggestions