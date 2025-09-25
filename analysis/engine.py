# analysis/engine.py
import numpy as np
import matplotlib.pyplot as plt
import io
import base64
from typing import Dict, Any, List
from solvers import get_solver

class AnalysisEngine:
    """Performs various analyses on optimization problems"""

    def __init__(self):
        pass

    def run_sensitivity_analysis(self, params: Dict, variable: str, variable_range: tuple, steps: int = 20) -> Dict[str, Any]:
        """Run sensitivity analysis on a specific variable"""

        solver = get_solver("TRANSPORTATION")
        original_value = self._get_variable_value(params, variable)

        if original_value is None:
            return {"error": f"Variable '{variable}' not found in parameters"}

        # Create range of values to test
        min_val, max_val = variable_range
        test_values = np.linspace(min_val, max_val, steps)

        results = []

        for test_value in test_values:
            # Create modified parameters
            modified_params = self._modify_parameter(params.copy(), variable, test_value)

            try:
                # Solve with modified parameters
                solution = solver.solve(modified_params)

                # Get objective value from either field
                objective_cost = solution.get("objective_value") or solution.get("objective_thousand_usd", 0)

                results.append({
                    f"{variable}_value": float(test_value),
                    "objective_cost": objective_cost,
                    "status": solution.get("status", "UNKNOWN"),
                    "feasible": solution.get("status") == "OPTIMAL"
                })
            except Exception as e:
                results.append({
                    f"{variable}_value": float(test_value),
                    "objective_cost": None,
                    "status": "ERROR",
                    "feasible": False,
                    "error": str(e)
                })

        return {
            "analysis_type": "sensitivity",
            "variable": variable,
            "original_value": original_value,
            "range": variable_range,
            "results": results
        }

    def run_scenario_comparison(self, base_params: Dict, scenarios: List[Dict]) -> Dict[str, Any]:
        """Compare multiple scenarios"""

        solver = get_solver("TRANSPORTATION")
        results = []

        # Add base scenario
        base_solution = solver.solve(base_params)
        results.append({
            "scenario": "baseline",
            "objective_cost": base_solution.get("objective_thousand_usd", 0),
            "status": base_solution.get("status", "UNKNOWN"),
            "parameters": base_params
        })

        # Test each scenario
        for i, scenario in enumerate(scenarios):
            try:
                modified_params = base_params.copy()
                modified_params.update(scenario)

                solution = solver.solve(modified_params)
                results.append({
                    "scenario": f"scenario_{i+1}",
                    "objective_cost": solution.get("objective_thousand_usd", 0),
                    "status": solution.get("status", "UNKNOWN"),
                    "parameters": modified_params,
                    "changes": scenario
                })
            except Exception as e:
                results.append({
                    "scenario": f"scenario_{i+1}",
                    "error": str(e),
                    "status": "ERROR"
                })

        return {
            "analysis_type": "scenario_comparison",
            "results": results
        }

    def _get_variable_value(self, params: Dict, variable: str) -> float:
        """Extract variable value from parameters - GENERIC approach"""
        variable = variable.lower()

        # Handle capacity variables: capacity_plantname
        if variable.startswith("capacity_"):
            plant_name = variable.replace("capacity_", "")
            return float(params.get("capacity", {}).get(plant_name, 0))

        # Handle demand variables: demand_marketname
        elif variable.startswith("demand_"):
            market_name = variable.replace("demand_", "")
            return float(params.get("demand", {}).get(market_name, 0))

        # Handle distance variables: distance_plant_market
        elif variable.startswith("distance_"):
            parts = variable.split("_")
            if len(parts) >= 3:
                plant = parts[1]
                market = "_".join(parts[2:])
                return float(params.get("distance", {}).get(plant, {}).get(market, 0))

        # Handle freight
        elif variable == "freight":
            return float(params.get("freight", 0))

        return None

    def _modify_parameter(self, params: Dict, variable: str, new_value: float) -> Dict:
        """Modify a parameter value - GENERIC approach"""
        variable = variable.lower()

        # Handle capacity variables: capacity_plantname
        if variable.startswith("capacity_"):
            plant_name = variable.replace("capacity_", "")
            capacity_dict = params.get("capacity", {})

            # Find matching plant name (case insensitive)
            actual_plant = None
            for existing_plant in capacity_dict.keys():
                if existing_plant.lower() == plant_name.lower():
                    actual_plant = existing_plant
                    break

            if actual_plant:
                params["capacity"][actual_plant] = new_value

        # Handle demand variables: demand_marketname
        elif variable.startswith("demand_"):
            market_name = variable.replace("demand_", "")
            demand_dict = params.get("demand", {})

            # Find matching market name (case insensitive)
            actual_market = None
            for existing_market in demand_dict.keys():
                if existing_market.lower() == market_name.lower():
                    actual_market = existing_market
                    break

            if actual_market:
                params["demand"][actual_market] = new_value

        # Handle distance variables: distance_plant_market
        elif variable.startswith("distance_"):
            parts = variable.split("_")
            if len(parts) >= 3:
                plant = parts[1]
                market = "_".join(parts[2:])
                if plant in params.get("distance", {}) and market in params["distance"][plant]:
                    params["distance"][plant][market] = new_value

        # Handle freight
        elif variable == "freight":
            params["freight"] = new_value

        return params

    def create_sensitivity_plot(self, analysis_results: Dict) -> str:
        """Create sensitivity analysis plot and return as base64"""

        results = analysis_results["results"]
        variable = analysis_results["variable"]

        # Extract data
        x_values = [r[f"{variable}_value"] for r in results if r.get("feasible", False)]
        y_values = [r["objective_cost"] for r in results if r.get("feasible", False)]

        if not x_values:
            return ""

        # Create plot
        plt.figure(figsize=(10, 6))
        plt.plot(x_values, y_values, 'b-', linewidth=2, marker='o')
        plt.xlabel(f"{variable.replace('_', ' ').title()}")
        plt.ylabel("Total Cost (Thousand USD)")
        plt.title(f"Sensitivity Analysis: {variable.replace('_', ' ').title()} vs Total Cost")
        plt.grid(True, alpha=0.3)

        # Mark original value
        original_value = analysis_results.get("original_value")
        if original_value:
            plt.axvline(x=original_value, color='red', linestyle='--', alpha=0.7, label='Original Value')
            plt.legend()

        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', dpi=300)
        plt.close()

        buffer.seek(0)
        plot_data = buffer.getvalue()
        buffer.close()

        return base64.b64encode(plot_data).decode('utf-8')

    def create_scenario_plot(self, analysis_results: Dict) -> str:
        """Create scenario comparison plot and return as base64"""

        results = analysis_results["results"]

        scenarios = [r["scenario"] for r in results if r.get("status") == "OPTIMAL"]
        costs = [r["objective_cost"] for r in results if r.get("status") == "OPTIMAL"]

        if not scenarios:
            return ""

        # Create bar plot
        plt.figure(figsize=(12, 6))
        bars = plt.bar(scenarios, costs, color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'])

        plt.xlabel("Scenarios")
        plt.ylabel("Total Cost (Thousand USD)")
        plt.title("Scenario Comparison: Total Costs")
        plt.xticks(rotation=45)

        # Add value labels on bars
        for bar, cost in zip(bars, costs):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(costs)*0.01,
                    f'${cost:.1f}k', ha='center', va='bottom')

        plt.grid(True, alpha=0.3, axis='y')
        plt.tight_layout()

        # Convert to base64
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', bbox_inches='tight', dpi=300)
        plt.close()

        buffer.seek(0)
        plot_data = buffer.getvalue()
        buffer.close()

        return base64.b64encode(plot_data).decode('utf-8')