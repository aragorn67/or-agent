"""
Sensitivity Analysis Engine

Analyzes the impact of parameter changes on the optimal solution.
Tests multiple values for a selected parameter and reports cost changes.
"""

from typing import Dict, Any, List, Tuple, Optional
import copy
from analysis.parameter_detector import detect_parameter_from_query
from analysis.instance_builder import build_instance_from_params


def perform_sensitivity_analysis(
    solver,
    params: Dict[str, Any],
    solution: Dict[str, Any],
    query: str,
    llm_client=None,
    problem_type: str = None,
    solver_id: str = None
) -> Dict[str, Any]:
    """
    Perform sensitivity analysis on a parameter.

    Args:
        solver: Solver instance
        params: Current problem parameters
        solution: Current solution
        query: User's query
        llm_client: LLM client for parameter detection (optional for backward compatibility)
        problem_type: Problem type (e.g., 'TRANSPORTATION', 'SCHEDULING') - extracted from solution if not provided
        solver_id: Solver identifier - extracted from solver if not provided

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
    # Extract problem_type and solver_id if not provided
    if problem_type is None:
        problem_type = solution.get('problem_type', 'TRANSPORTATION')
    if solver_id is None:
        solver_id = getattr(solver, 'solver_id', 'unknown')
    # Extract parameter to analyze using dynamic detector
    param_info = detect_parameter_from_query(query, params, llm_client) if llm_client else None
    if not param_info:
        return {
            'success': False,
            'message': 'Could not identify parameter to analyze. Try specifying an entity name (e.g., "sensitivity on Plant North capacity")'
        }

    param_type = param_info['parameter_name']
    entity = param_info['entity']
    current_value = param_info['current_value']
    current_cost = solution.get('objective_value') or solution.get('objective_thousand_usd') or 0

    # Define test range
    test_values = [current_value * m for m in [0.5, 0.75, 0.9, 1.0, 1.1, 1.25, 1.5]]

    # Run tests
    results = []
    for test_val in test_values:
        # Create modified params
        test_params = copy.deepcopy(params)
        test_params[param_type][entity] = test_val

        # Check feasibility using generic instance builder
        from feasibility.core import check_feasibility, FeasStatus
        test_instance = build_instance_from_params(test_params, problem_type, solver_id)

        feas_check = check_feasibility(test_instance)
        # Proceed unless PROVABLY infeasible. A non-FEASIBLE/UNKNOWN
        # verdict (e.g. scheduling, whose Layer-2 LP path is inconclusive)
        # must not silently drop the point — the solver is the backstop
        # and the `status == 'OPTIMAL'` guard below is the real gate.
        if feas_check.status != FeasStatus.INFEASIBLE:
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


