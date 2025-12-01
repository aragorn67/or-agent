"""
Sensitivity Analysis Engine

Analyzes the impact of parameter changes on the optimal solution.
Tests multiple values for a selected parameter and reports cost changes.
"""

from typing import Dict, Any, List, Tuple, Optional
import copy


def extract_parameter_from_query(query: str, params: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """
    Extract the parameter to analyze from user query.

    Args:
        query: User's natural language query
        params: Current problem parameters

    Returns:
        Tuple of (parameter_type, entity_name) or None if not found

    Examples:
        >>> extract_parameter_from_query("sensitivity on Plant North capacity", params)
        ('capacity', 'Plant North')
    """
    query_lower = query.lower()

    # Check for capacity/supply parameters
    if 'capacity' in query_lower or 'supply' in query_lower:
        for plant in params.get('plants', []):
            if plant.lower() in query_lower:
                return ('capacity', plant)

    # Check for demand parameters
    if 'demand' in query_lower:
        for market in params.get('markets', []):
            if market.lower() in query_lower:
                return ('demand', market)

    return None


def perform_sensitivity_analysis(
    solver,
    params: Dict[str, Any],
    solution: Dict[str, Any],
    query: str
) -> Dict[str, Any]:
    """
    Perform sensitivity analysis on a parameter.

    Args:
        solver: Solver instance
        params: Current problem parameters
        solution: Current solution
        query: User's query

    Returns:
        Dictionary with:
        - success: bool
        - parameter_type: str
        - entity: str
        - current_value: float
        - current_cost: float
        - test_values: List[float]
        - costs: List[float | None]
        - insights: Dict with cost_range, best_value, savings
    """
    # Extract parameter to analyze
    param_info = extract_parameter_from_query(query, params)
    if not param_info:
        return {
            'success': False,
            'message': 'Could not identify parameter to analyze. Try specifying a plant or market name.'
        }

    param_type, entity = param_info
    current_value = params.get(param_type, {}).get(entity, 0)
    current_cost = solution.get('objective_value') or solution.get('objective_thousand_usd') or 0

    # Define test range
    test_values = [current_value * m for m in [0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5]]

    # Run tests
    results = []
    for test_val in test_values:
        # Create modified params
        test_params = copy.deepcopy(params)
        test_params[param_type][entity] = test_val

        # Check feasibility
        from feasibility.core import check_feasibility, FeasStatus
        test_instance = _create_instance_for_feasibility(test_params)

        feas_check = check_feasibility(test_instance)
        if feas_check.status == FeasStatus.FEASIBLE:
            # Solve
            test_solution = solver.solve(test_params)
            if test_solution and test_solution.get('status') == 'OPTIMAL':
                test_cost = test_solution.get('objective_value') or test_solution.get('objective_thousand_usd') or 0
                results.append((test_val, test_cost))
            else:
                results.append((test_val, None))
        else:
            results.append((test_val, None))

    # Generate insights
    feasible_results = [(v, c) for v, c in results if c is not None]
    insights = {}

    if len(feasible_results) > 1:
        costs_only = [c for _, c in feasible_results]
        min_cost = min(costs_only)
        max_cost = max(costs_only)

        insights = {
            'cost_range': {'min': min_cost, 'max': max_cost, 'spread': max_cost - min_cost}
        }

        if min_cost < current_cost:
            best_val = [v for v, c in feasible_results if c == min_cost][0]
            savings = current_cost - min_cost
            insights['best_value'] = {
                'value': best_val,
                'cost': min_cost,
                'savings': savings,
                'savings_pct': (savings / current_cost * 100) if current_cost > 0 else 0
            }

    return {
        'success': True,
        'parameter_type': param_type,
        'entity': entity,
        'current_value': current_value,
        'current_cost': current_cost,
        'test_values': [v for v, _ in results],
        'costs': [c for _, c in results],
        'insights': insights
    }


def format_sensitivity_results(results: Dict[str, Any]) -> str:
    """
    Format sensitivity analysis results for display.

    Args:
        results: Results dictionary from perform_sensitivity_analysis

    Returns:
        Formatted string
    """
    if not results.get('success'):
        return f"⚠️  {results.get('message', 'Sensitivity analysis failed')}"

    param_type = results['parameter_type']
    entity = results['entity']
    current_value = results['current_value']
    current_cost = results['current_cost']
    test_values = results['test_values']
    costs = results['costs']
    insights = results['insights']

    output = []
    output.append(f"\n📊 Sensitivity Analysis Results")
    output.append("-" * 80)
    output.append(f"Analyzing impact of changes to {param_type}[{entity}]")
    output.append(f"Current value: {current_value:.2f}")
    output.append(f"Current optimal cost: €{current_cost:.2f}")
    output.append(f"\nTesting range: {min(test_values):.0f} to {max(test_values):.0f}")
    output.append(f"(Solved the problem {len(test_values)} times with different values)\n")

    # Results table
    output.append("Results:")
    output.append(f"{'Value':>10} | {'Cost':>12} | {'Change':>12} | {'% Change':>10}")
    output.append("-" * 60)

    for val, cost in zip(test_values, costs):
        if cost is not None:
            change = cost - current_cost
            pct_change = (change / current_cost * 100) if current_cost > 0 else 0
            marker = " ← current" if abs(val - current_value) < 0.1 else ""
            output.append(f"{val:>10.1f} | €{cost:>11.2f} | {change:>+11.2f} | {pct_change:>+9.1f}%{marker}")
        else:
            output.append(f"{val:>10.1f} | {'INFEASIBLE':>12} | {'N/A':>12} | {'N/A':>10}")

    # Insights
    if insights:
        output.append("\nInsights:")
        if 'cost_range' in insights:
            cr = insights['cost_range']
            output.append(f"  • Cost range: €{cr['min']:.2f} to €{cr['max']:.2f} (spread: €{cr['spread']:.2f})")
        if 'best_value' in insights:
            bv = insights['best_value']
            output.append(f"  • Best value: {bv['value']:.1f} (saves €{bv['savings']:.2f}, {bv['savings_pct']:.1f}%)")

    return "\n".join(output)


def _create_instance_for_feasibility(params: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to create instance dict for feasibility checking."""
    return {
        'problem_type': 'TRANSPORTATION',
        'solver_id': 'transport_basic_bipartite',
        'sets': {
            'I_plants': params.get('plants', []),
            'J_markets': params.get('markets', [])
        },
        'params': {
            'supply': params.get('capacity', {}),
            'demand': params.get('demand', {}),
            'cost': {(plant, market): cost
                     for plant, markets in params.get('cost', {}).items()
                     for market, cost in markets.items()}
        }
    }
