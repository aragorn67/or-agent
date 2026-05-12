"""
What-If Scenario Analysis Engine

Analyzes hypothetical modifications to the problem without permanently changing it.
Compares scenario results with the original solution.
"""

from typing import Dict, Any, List
import copy
from analysis.instance_builder import build_instance_from_params


def perform_what_if_scenario(
    llm_client,
    solver,
    params: Dict[str, Any],
    solution: Dict[str, Any],
    query: str,
    problem_type: str = None,
    solver_id: str = None
) -> Dict[str, Any]:
    """
    Perform a what-if scenario analysis.

    Args:
        llm_client: LLM client for parsing modifications
        solver: Solver instance
        params: Current problem parameters
        solution: Current solution
        query: User's query
        problem_type: Problem type (extracted from solution if not provided)
        solver_id: Solver identifier (extracted from solver if not provided)

    Returns:
        Dictionary with:
        - success: bool
        - modifications: List[Dict]
        - feasible: bool
        - scenario_cost: float
        - original_cost: float
        - cost_diff: float
        - cost_diff_pct: float
        - flow_changes: List[Dict]
    """
    # Extract problem_type and solver_id if not provided
    if problem_type is None:
        problem_type = solution.get('problem_type', 'TRANSPORTATION')
    if solver_id is None:
        solver_id = getattr(solver, 'solver_id', 'unknown')
    # Parse modification using LLM
    modification_result = llm_client.parse_infeasibility_fix(
        query,
        params,
        {"layer_failed": 0, "reasons": [], "suggestions": []}
    )

    modifications = modification_result.get("modifications", [])
    if not modifications:
        return {
            'success': False,
            'message': 'Could not parse modification. Try: "what if capacity of Plant North was 100"'
        }

    # Apply modification to a deep copy
    scenario_params = copy.deepcopy(modification_result.get("applied_params", params))

    # Check feasibility BEFORE solving using generic instance builder
    from feasibility.core import check_feasibility, FeasStatus
    scenario_instance = build_instance_from_params(scenario_params, problem_type, solver_id)
    feas_report = check_feasibility(scenario_instance)

    if feas_report.status == FeasStatus.INFEASIBLE:
        return {
            'success': False,
            'feasible': False,
            'modifications': modifications,
            'layer_failed': feas_report.layer_passed,
            'reasons': feas_report.reasons,
            'suggestions': feas_report.suggestions or [],
            'message': f"Scenario is infeasible (failed at layer {feas_report.layer_passed})"
        }

    # Solve the scenario (only if feasible)
    scenario_solution = solver.solve(scenario_params)

    if not scenario_solution or scenario_solution.get('status') != 'OPTIMAL':
        return {
            'success': False,
            'feasible': False,
            'modifications': modifications,
            'message': f"Scenario solver failed: {scenario_solution.get('status', 'UNKNOWN') if scenario_solution else 'No solution'}"
        }

    # Get costs
    original_cost = solution.get('objective_value') or solution.get('objective_thousand_usd') or 0
    scenario_cost = scenario_solution.get('objective_value') or scenario_solution.get('objective_thousand_usd') or 0
    cost_diff = scenario_cost - original_cost
    cost_diff_pct = (cost_diff / original_cost * 100) if original_cost > 0 else 0

    # Compare flows
    flow_changes = compare_solutions(solution, scenario_solution)

    return {
        'success': True,
        'feasible': True,
        'modifications': modifications,
        'original_cost': original_cost,
        'scenario_cost': scenario_cost,
        'cost_diff': cost_diff,
        'cost_diff_pct': cost_diff_pct,
        'flow_changes': flow_changes
    }


def compare_solutions(original_solution: Dict[str, Any], scenario_solution: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Compare two solutions and identify flow changes.

    Args:
        original_solution: Original solution
        scenario_solution: Scenario solution

    Returns:
        List of flow changes with route, old_value, new_value, diff
    """
    original_flows = original_solution.get("flows", [])
    scenario_flows = scenario_solution.get("flows", [])

    # Create flow dicts for easy comparison
    orig_flow_dict = {(f['plant'], f['market']): f['value'] for f in original_flows}
    scen_flow_dict = {(f['plant'], f['market']): f['value'] for f in scenario_flows}

    # Find all changed routes
    all_routes = set(orig_flow_dict.keys()) | set(scen_flow_dict.keys())
    changes = []

    for route in sorted(all_routes):
        orig_val = orig_flow_dict.get(route, 0)
        scen_val = scen_flow_dict.get(route, 0)
        if abs(orig_val - scen_val) > 0.1:  # Significant change
            changes.append({
                'route': route,
                'old_value': orig_val,
                'new_value': scen_val,
                'diff': scen_val - orig_val
            })

    return changes


def format_scenario_results(results: Dict[str, Any]) -> str:
    """
    Format what-if scenario results for display.

    Args:
        results: Results dictionary from perform_what_if_scenario

    Returns:
        Formatted string
    """
    output = []
    output.append("\n🔮 What-If Scenario Analysis")
    output.append("-" * 80)

    # Show modifications
    modifications = results.get('modifications', [])
    if modifications:
        mod = modifications[0]
        output.append(f"Scenario: {mod.get('type')} {mod.get('parameter')} of '{mod.get('entity')}' by/to {mod.get('value')}\n")

    # Handle infeasible scenarios
    if not results.get('success') or not results.get('feasible', True):
        output.append(f"✗ Scenario is INFEASIBLE\n")

        # Show layer and reasons
        layer_failed = results.get('layer_failed')
        if layer_failed is not None:
            layer_names = {
                0: "Layer 1 (Structural Validation)",
                1: "Layer 2 (Problem-Specific Conditions)",
                2: "Layer 3 (LP Relaxation)"
            }
            output.append(f"Failed at: {layer_names.get(layer_failed, f'Layer {layer_failed}')}")

        reasons = results.get('reasons', [])
        if reasons:
            output.append("\nReasons:")
            for reason in reasons:
                output.append(f"  • {reason}")

        suggestions = results.get('suggestions', [])
        if suggestions:
            output.append("\n💡 Suggestions to make scenario feasible:")
            for suggestion in suggestions[:3]:  # Show top 3
                output.append(f"  • {suggestion}")

        output.append(f"\n{results.get('message', 'Cannot solve this scenario')}")
        return "\n".join(output)

    # Cost comparison
    original_cost = results['original_cost']
    scenario_cost = results['scenario_cost']
    cost_diff = results['cost_diff']
    cost_diff_pct = results['cost_diff_pct']

    output.append("✓ Scenario is FEASIBLE and OPTIMAL")
    output.append(f"  Original cost: €{original_cost:.2f}")
    output.append(f"  Scenario cost: €{scenario_cost:.2f}")
    output.append(f"  Difference: €{cost_diff:+.2f} ({cost_diff_pct:+.1f}%)")

    # Flow changes
    flow_changes = results.get('flow_changes', [])
    if flow_changes:
        output.append("\n  Shipment changes:")
        for i, change in enumerate(flow_changes[:5]):  # Show top 5
            route = change['route']
            old_val = change['old_value']
            new_val = change['new_value']
            diff = change['diff']
            output.append(f"    {route[0]:12} → {route[1]:12}: {old_val:6.1f} → {new_val:6.1f} ({diff:+6.1f})")
        if len(flow_changes) > 5:
            output.append(f"    ... and {len(flow_changes) - 5} more changes")
    else:
        output.append("\n  (No significant flow changes)")

    return "\n".join(output)


