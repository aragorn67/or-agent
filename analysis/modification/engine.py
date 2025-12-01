"""
Re-Solve with Modification Engine

Permanently applies modifications to parameters and re-solves the problem.
Returns new parameters and solution for continued analysis.
"""

from typing import Dict, Any, List, Tuple


def resolve_with_modification(
    llm_client,
    solver,
    params: Dict[str, Any],
    solution: Dict[str, Any],
    query: str
) -> Dict[str, Any]:
    """
    Re-solve the problem with permanent modifications.

    Args:
        llm_client: LLM client for parsing modifications
        solver: Solver instance
        params: Current problem parameters
        solution: Current solution
        query: User's query

    Returns:
        Dictionary with:
        - success: bool
        - new_params: Dict (modified parameters)
        - new_solution: Dict (new optimal solution)
        - modifications: List[Dict]
        - old_cost: float
        - new_cost: float
        - cost_diff: float
        - cost_diff_pct: float
        - parameter_diff: List[str]
    """
    # Parse modification using LLM
    modification_result = llm_client.parse_infeasibility_fix(
        query.replace('resolve', '').replace('re-solve', ''),
        params,
        {"layer_failed": 0, "reasons": [], "suggestions": []}
    )

    modifications = modification_result.get("modifications", [])
    if not modifications:
        return {
            'success': False,
            'message': 'Could not parse modification. Try: "resolve with capacity of Plant North = 100"'
        }

    # Apply modifications
    new_params = modification_result.get("applied_params", params)

    # Store old cost for comparison
    old_cost = solution.get('objective_value') or solution.get('objective_thousand_usd') or 0

    # Re-solve
    new_solution = solver.solve(new_params)

    if not new_solution or new_solution.get('status') != 'OPTIMAL':
        return {
            'success': False,
            'message': f"Re-optimization failed: {new_solution.get('status', 'UNKNOWN') if new_solution else 'No solution'}",
            'modifications': modifications
        }

    # Calculate differences
    new_cost = new_solution.get('objective_value') or new_solution.get('objective_thousand_usd') or 0
    cost_diff = new_cost - old_cost
    cost_diff_pct = (cost_diff / old_cost * 100) if old_cost > 0 else 0

    # Generate parameter diff
    param_diff = generate_parameter_diff(params, new_params)

    return {
        'success': True,
        'new_params': new_params,
        'new_solution': new_solution,
        'modifications': modifications,
        'old_cost': old_cost,
        'new_cost': new_cost,
        'cost_diff': cost_diff,
        'cost_diff_pct': cost_diff_pct,
        'parameter_diff': param_diff
    }


def generate_parameter_diff(original_params: Dict[str, Any], modified_params: Dict[str, Any]) -> List[str]:
    """
    Generate human-readable diff of parameter changes.

    Args:
        original_params: Original parameters
        modified_params: Modified parameters

    Returns:
        List of change descriptions
    """
    diff = []

    # Check capacity changes
    if 'capacity' in original_params and 'capacity' in modified_params:
        for entity in modified_params.get('capacity', {}).keys():
            old_val = original_params.get('capacity', {}).get(entity, 0)
            new_val = modified_params.get('capacity', {}).get(entity, 0)
            if abs(old_val - new_val) > 1e-6:
                diff.append(f"Capacity[{entity}]: {old_val:.2f} → {new_val:.2f} (change: {new_val - old_val:+.2f})")

    # Check demand changes
    if 'demand' in original_params and 'demand' in modified_params:
        for entity in modified_params.get('demand', {}).keys():
            old_val = original_params.get('demand', {}).get(entity, 0)
            new_val = modified_params.get('demand', {}).get(entity, 0)
            if abs(old_val - new_val) > 1e-6:
                diff.append(f"Demand[{entity}]: {old_val:.2f} → {new_val:.2f} (change: {new_val - old_val:+.2f})")

    # Check cost changes
    if 'cost' in original_params and 'cost' in modified_params:
        orig_cost = original_params.get('cost', {})
        new_cost = modified_params.get('cost', {})

        for route in new_cost.keys():
            old_val = None
            new_val = None

            # Handle both nested dict and flat dict formats
            if isinstance(orig_cost, dict):
                if isinstance(list(orig_cost.values())[0] if orig_cost else None, dict):
                    # Nested: {plant: {market: cost}}
                    old_val = orig_cost.get(route[0], {}).get(route[1]) if isinstance(route, tuple) else None
                else:
                    # Flat: {(plant, market): cost}
                    old_val = orig_cost.get(route)

            if isinstance(new_cost, dict):
                if isinstance(list(new_cost.values())[0] if new_cost else None, dict):
                    new_val = new_cost.get(route[0], {}).get(route[1]) if isinstance(route, tuple) else None
                else:
                    new_val = new_cost.get(route)

            if old_val is not None and new_val is not None and abs(old_val - new_val) > 1e-6:
                route_str = f"{route[0]}→{route[1]}" if isinstance(route, tuple) else str(route)
                diff.append(f"Cost[{route_str}]: {old_val:.2f} → {new_val:.2f} (change: {new_val - old_val:+.2f})")

    if not diff:
        diff.append("No parameter changes detected")

    return diff


def format_modification_results(results: Dict[str, Any]) -> str:
    """
    Format re-solve modification results for display.

    Args:
        results: Results dictionary from resolve_with_modification

    Returns:
        Formatted string
    """
    if not results.get('success'):
        return f"⚠️  {results.get('message', 'Re-solve failed')}"

    output = []
    output.append("\n🔄 Re-Solve with Modifications")
    output.append("-" * 80)

    # Show modifications
    modifications = results.get('modifications', [])
    if modifications:
        output.append("Applied modifications:")
        for mod in modifications:
            output.append(f"  • {mod.get('type')} {mod.get('parameter')} of {mod.get('entity')} by/to {mod.get('value')}")
        output.append("")

    # Show cost comparison
    old_cost = results['old_cost']
    new_cost = results['new_cost']
    cost_diff = results['cost_diff']
    cost_diff_pct = results['cost_diff_pct']

    output.append("✓ Re-optimization successful!")
    output.append(f"  Old cost: €{old_cost:.2f}")
    output.append(f"  New cost: €{new_cost:.2f}")
    output.append(f"  Difference: €{cost_diff:+.2f} ({cost_diff_pct:+.1f}%)")

    # Show top flows
    new_solution = results.get('new_solution', {})
    flows = new_solution.get("flows", [])
    if flows:
        output.append("\n  Top 5 shipments in new solution:")
        for flow in sorted(flows, key=lambda f: f.get('value', 0), reverse=True)[:5]:
            if flow.get('value', 0) > 0.1:
                output.append(f"    {flow['plant']:12} → {flow['market']:12}: {flow['value']:6.1f}")

    output.append("\n  ✓ Solution updated permanently")

    return "\n".join(output)
