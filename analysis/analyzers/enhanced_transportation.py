# analysis/analyzers/enhanced_transportation.py
from typing import Dict, Any, Tuple, Optional, List
from .base import BaseAnalyzer
import json

class EnhancedTransportationAnalyzer(BaseAnalyzer):
    """Enhanced LLM-driven analyzer for transportation optimization with deep analysis"""

    def get_problem_type(self) -> str:
        return "TRANSPORTATION"

    def get_supported_variable_types(self) -> Dict[str, Dict[str, Any]]:
        return {
            "capacity": {"description": "Production/supply capacity at plants"},
            "demand": {"description": "Demand requirements at markets"},
            "cost": {"description": "Per-unit shipping costs between plants and markets"},
            "global_cost": {"description": "Overall cost scaling factors"}
        }

    def extract_variable_from_message(self, user_message: str, available_params: Dict) -> Tuple[Optional[str], Optional[float]]:
        """Enhanced LLM extraction for transportation variables"""

        if not self.llm:
            return self._enhanced_fallback(user_message, available_params)

        # Build context about available variables
        plants = available_params.get('plants', [])
        markets = available_params.get('markets', [])
        capacity = available_params.get('capacity', {})
        demand = available_params.get('demand', {})
        costs = available_params.get('cost', {})

        context = f"""
Available plants: {plants}
Plant capacities: {capacity}
Available markets: {markets}
Market demands: {demand}
Cost matrix available: {bool(costs)}
"""

        prompt = f"""
User wants to analyze: "{user_message}"

Context: {context}

Determine which specific variable they want to analyze. Return the exact parameter path:

For plant capacity: "capacity_plantname" (e.g., "capacity_seattle")
For market demand: "demand_marketname" (e.g., "demand_chicago")
For specific shipping cost: "cost_plant_market" (e.g., "cost_seattle_chicago")
For all shipping costs proportionally: "all_costs"

Return JSON: {{"variable_name": "exact_parameter_path", "confidence": 0.9}}
"""

        try:
            response = self.llm._generate(prompt)

            # Extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx == -1 or end_idx == 0:
                return self._enhanced_fallback(user_message, available_params)

            json_str = response[start_idx:end_idx]
            result = json.loads(json_str)

            variable_name = result.get("variable_name")
            confidence = result.get("confidence", 0.0)

            if not variable_name or confidence < 0.3:
                return self._enhanced_fallback(user_message, available_params)

            # Get the original value
            original_value = self._get_enhanced_original_value(variable_name, available_params)

            return variable_name, original_value

        except Exception as e:
            print(f"Enhanced LLM extraction failed: {e}")
            return self._enhanced_fallback(user_message, available_params)

    def _get_enhanced_original_value(self, variable_name: str, params: Dict) -> Optional[float]:
        """Get the original value with enhanced support for cost matrices"""

        try:
            if variable_name == "all_costs":
                # Return average cost as representative
                costs = params.get("cost", {})
                if costs:
                    total_cost = 0
                    count = 0
                    for plant_costs in costs.values():
                        for cost in plant_costs.values():
                            total_cost += float(cost)
                            count += 1
                    return total_cost / count if count > 0 else None
                return None

            elif variable_name.startswith("capacity_"):
                plant = variable_name.replace("capacity_", "")
                return float(params.get("capacity", {}).get(plant, 0))

            elif variable_name.startswith("demand_"):
                market = variable_name.replace("demand_", "")
                return float(params.get("demand", {}).get(market, 0))

            elif variable_name.startswith("cost_"):
                parts = variable_name.replace("cost_", "").split("_")
                if len(parts) >= 2:
                    plant = parts[0]
                    market = "_".join(parts[1:])
                    costs = params.get("cost", {})
                    return float(costs.get(plant, {}).get(market, 0))

        except (ValueError, TypeError, KeyError):
            pass

        return None

    def _enhanced_fallback(self, user_message: str, available_params: Dict) -> Tuple[Optional[str], Optional[float]]:
        """Enhanced fallback with better pattern matching"""
        message_lower = user_message.lower()

        plants = available_params.get('plants', [])
        markets = available_params.get('markets', [])

        # Check for specific plant/market mentions
        for plant in plants:
            plant_lower = plant.lower()
            if plant_lower in message_lower:
                if any(word in message_lower for word in ['capacity', 'produce', 'supply', 'output']):
                    capacity = available_params.get("capacity", {}).get(plant)
                    if capacity is not None:
                        return f"capacity_{plant_lower}", float(capacity)

        for market in markets:
            market_lower = market.lower()
            if market_lower in message_lower:
                if any(word in message_lower for word in ['demand', 'need', 'require', 'want']):
                    demand = available_params.get("demand", {}).get(market)
                    if demand is not None:
                        return f"demand_{market_lower}", float(demand)

        # Check for route-specific cost mentions
        for plant in plants:
            for market in markets:
                plant_lower = plant.lower()
                market_lower = market.lower()
                if (plant_lower in message_lower and market_lower in message_lower and
                    any(word in message_lower for word in ['cost', 'shipping', 'transport', 'distance'])):
                    costs = available_params.get("cost", {})
                    cost_val = costs.get(plant, {}).get(market)
                    if cost_val is not None:
                        return f"cost_{plant_lower}_{market_lower}", float(cost_val)

        # Check for global cost factors
        if any(phrase in message_lower for phrase in ['all cost', 'shipping cost', 'transport cost', 'freight']):
            costs = available_params.get("cost", {})
            if costs:
                return "all_costs", self._get_enhanced_original_value("all_costs", available_params)

        return None, None

    def get_variable_description(self, variable_name: str, original_value: float) -> str:
        """Get enhanced human-readable description"""

        if variable_name.startswith("capacity_"):
            plant_name = variable_name.replace("capacity_", "").replace("_", " ").title()
            return f"🏭 **{plant_name} Capacity Analysis**\n\nCurrently {plant_name} can supply {original_value} units. This analysis shows how changing this plant's capacity affects total transportation cost, route utilization, and market service patterns."

        elif variable_name.startswith("demand_"):
            market_name = variable_name.replace("demand_", "").replace("_", " ").title()
            return f"🎯 **{market_name} Demand Analysis**\n\nCurrently {market_name} requires {original_value} units. This analysis shows how changing this market's demand affects total cost, supply allocation, and plant utilization."

        elif variable_name.startswith("cost_"):
            parts = variable_name.replace("cost_", "").split("_")
            if len(parts) >= 2:
                plant_name = parts[0].replace("_", " ").title()
                market_name = "_".join(parts[1:]).replace("_", " ").title()
                return f"💰 **{plant_name} → {market_name} Route Cost Analysis**\n\nCurrently shipping from {plant_name} to {market_name} costs ${original_value} per unit. This analysis shows how this specific route cost affects overall optimization and route selection."

        elif variable_name == "all_costs":
            return f"💰 **Global Shipping Cost Analysis**\n\nAnalyzing proportional changes to all shipping costs. Current average cost: ${original_value:.2f} per unit. This shows how overall cost inflation/reduction affects the transportation network."

        else:
            return f"📊 **{variable_name.replace('_', ' ').title()} Analysis**\n\nAnalysis of how {variable_name} (current value: {original_value}) affects the transportation optimization."

    def suggest_analysis_variables(self, params: Dict[str, Any]) -> List[str]:
        """Suggest interesting variables for analysis"""
        suggestions = []

        plants = params.get('plants', [])
        markets = params.get('markets', [])
        capacities = params.get('capacity', {})
        demands = params.get('demand', {})
        costs = params.get('cost', {})

        # Suggest capacity variables (prioritize larger capacities)
        capacity_items = [(plant, cap) for plant, cap in capacities.items()]
        capacity_items.sort(key=lambda x: x[1], reverse=True)
        for plant, _ in capacity_items[:2]:  # Top 2 capacities
            suggestions.append(f"capacity_{plant.lower()}")

        # Suggest demand variables (prioritize larger demands)
        demand_items = [(market, dem) for market, dem in demands.items()]
        demand_items.sort(key=lambda x: x[1], reverse=True)
        for market, _ in demand_items[:2]:  # Top 2 demands
            suggestions.append(f"demand_{market.lower()}")

        # Suggest high-cost routes
        if costs:
            route_costs = []
            for plant in plants:
                if plant in costs:
                    for market in markets:
                        if market in costs[plant]:
                            route_costs.append((costs[plant][market], plant, market))

            route_costs.sort(reverse=True)  # Highest cost first
            for cost_val, plant, market in route_costs[:2]:  # Top 2 expensive routes
                suggestions.append(f"cost_{plant.lower()}_{market.lower()}")

        # Always suggest global cost analysis
        suggestions.append("all_costs")

        return suggestions[:5]  # Return top 5

    def analyze_solution_insights(self, solution: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate business insights from the transportation solution"""

        insights = {
            "efficiency_metrics": self._calculate_efficiency_metrics(solution, params),
            "route_patterns": self._analyze_route_patterns(solution, params),
            "capacity_insights": self._analyze_capacity_utilization(solution, params),
            "cost_insights": self._analyze_cost_structure(solution, params),
            "recommendations": self._generate_recommendations(solution, params)
        }

        return insights

    def _calculate_efficiency_metrics(self, solution: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate key efficiency metrics"""

        total_cost = solution.get('objective_value', 0)
        flows = solution.get('flows', [])

        if not flows:
            return {"error": "No flow data available"}

        total_units = sum(flow.get('value', 0) for flow in flows)
        cost_per_unit = total_cost / total_units if total_units > 0 else 0

        return {
            "cost_per_unit": round(cost_per_unit, 2),
            "total_units_shipped": round(total_units, 2),
            "total_cost": round(total_cost, 2)
        }

    def _analyze_route_patterns(self, solution: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze shipping route patterns"""

        flows = solution.get('flows', [])
        active_flows = [f for f in flows if f.get('value', 0) > 0.01]

        if not active_flows:
            return {"error": "No active routes"}

        # Find dominant routes
        active_flows.sort(key=lambda x: x.get('value', 0), reverse=True)
        top_routes = active_flows[:3]

        return {
            "total_active_routes": len(active_flows),
            "top_routes": [
                {
                    "route": f"{route['plant']} → {route['market']}",
                    "volume": round(route['value'], 1),
                    "percentage": round((route['value'] / sum(f['value'] for f in active_flows)) * 100, 1)
                }
                for route in top_routes
            ]
        }

    def _analyze_capacity_utilization(self, solution: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze plant capacity utilization"""

        utilization_data = solution.get('utilization', {})

        if not utilization_data:
            return {"error": "No utilization data available"}

        avg_utilization = sum(u.get('utilization_rate', 0) for u in utilization_data.values()) / len(utilization_data)

        underutilized = [plant for plant, data in utilization_data.items()
                        if data.get('utilization_rate', 0) < 0.7]

        return {
            "average_utilization": round(avg_utilization * 100, 1),
            "underutilized_plants": underutilized,
            "utilization_by_plant": {
                plant: round(data.get('utilization_rate', 0) * 100, 1)
                for plant, data in utilization_data.items()
            }
        }

    def _analyze_cost_structure(self, solution: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze cost structure and efficiency"""

        flows = solution.get('flows', [])
        costs = params.get('cost', {})

        if not flows or not costs:
            return {"error": "Insufficient data for cost analysis"}

        # Calculate cost breakdown by plant
        cost_by_plant = {}
        for flow in flows:
            plant = flow.get('plant')
            market = flow.get('market')
            volume = flow.get('value', 0)

            if plant in costs and market in costs[plant] and volume > 0:
                unit_cost = costs[plant][market]
                total_route_cost = unit_cost * volume

                if plant not in cost_by_plant:
                    cost_by_plant[plant] = 0
                cost_by_plant[plant] += total_route_cost

        return {
            "cost_by_plant": {plant: round(cost, 2) for plant, cost in cost_by_plant.items()},
            "highest_cost_plant": max(cost_by_plant.items(), key=lambda x: x[1]) if cost_by_plant else None
        }

    def _generate_recommendations(self, solution: Dict[str, Any], params: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations"""

        recommendations = []

        # Check utilization
        utilization_data = solution.get('utilization', {})
        if utilization_data:
            underutilized = [plant for plant, data in utilization_data.items()
                           if data.get('utilization_rate', 0) < 0.6]

            if underutilized:
                recommendations.append(f"Consider reducing capacity or finding new demand for underutilized plants: {', '.join(underutilized)}")

        # Check market fulfillment
        fulfillment_data = solution.get('market_fulfillment', {})
        if fulfillment_data:
            unfulfilled = [market for market, data in fulfillment_data.items()
                          if data.get('fulfillment_rate', 0) < 0.95]

            if unfulfilled:
                recommendations.append(f"Consider increasing capacity to better serve markets: {', '.join(unfulfilled)}")

        # Route efficiency
        flows = solution.get('flows', [])
        active_flows = [f for f in flows if f.get('value', 0) > 0.01]
        total_flows = len(flows)

        if len(active_flows) < total_flows * 0.5:
            recommendations.append("Many potential routes are unused. Consider if route costs accurately reflect true shipping costs.")

        if not recommendations:
            recommendations.append("Transportation plan appears well-optimized with good utilization and market service.")

        return recommendations