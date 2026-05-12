"""
Pareto Front Generation Engine

Generates Pareto-optimal solutions for multi-objective optimization problems.
Uses weighted sum method to explore trade-offs between objectives.
"""

from typing import Dict, Any, List, Tuple
import copy
import os


def perform_pareto_analysis(
    solver,
    params: Dict[str, Any],
    solution: Dict[str, Any],
    num_points: int = 10,
    problem_type: str = None
) -> Dict[str, Any]:
    """
    Generate Pareto front for multi-objective optimization.

    Uses weighted sum method: minimize w*obj1 + (1-w)*obj2
    where w varies from 0 to 1.

    Args:
        solver: Solver instance
        params: Problem parameters
        solution: Current single-objective solution
        num_points: Number of Pareto points to generate (default: 10)
        problem_type: Problem type (e.g., 'TRANSPORTATION', 'SCHEDULING')

    Returns:
        Dictionary with:
        - success: bool
        - objectives: List[str] - Names of the two objectives
        - pareto_points: List[Dict] - Each point has {obj1, obj2, weight, solution}
        - plot_path: str - Path to saved plot (if successful)
    """

    # Infer problem type if not provided
    if problem_type is None:
        problem_type = solution.get('problem_type', 'TRANSPORTATION')

    # Define objectives based on problem type
    if problem_type.upper() == 'TRANSPORTATION':
        obj1_name = "Total Cost"
        obj2_name = "Total Distance"

        # Extract distance matrix (or use cost as proxy if no distance)
        if 'distance' in params:
            distance_matrix = params['distance']
        elif 'cost' in params:
            # Use cost as proxy for distance
            distance_matrix = params['cost']
        else:
            return {
                'success': False,
                'message': 'No distance or cost data available for second objective'
            }

    else:
        # For other problem types, use generic objectives
        obj1_name = "Primary Objective"
        obj2_name = "Secondary Objective"
        return {
            'success': False,
            'message': f'Pareto front not yet implemented for {problem_type} problems'
        }

    # Generate weights: 0, 0.1, 0.2, ..., 1.0
    weights = [i / (num_points - 1) for i in range(num_points)]

    pareto_points = []

    print(f"\n= Generating Pareto front with {num_points} points...")
    print(f"  Objective 1: {obj1_name}")
    print(f"  Objective 2: {obj2_name}\n")

    for idx, w in enumerate(weights):
        # Create modified params with weighted objective
        modified_params = copy.deepcopy(params)

        # Combine cost and distance with weight w
        # New cost = w * original_cost + (1-w) * distance
        if 'cost' in modified_params:
            original_cost = modified_params['cost']

            # Handle nested dict format {i: {j: val}}
            if isinstance(list(original_cost.values())[0] if original_cost else None, dict):
                # Nested format
                combined_cost = {}
                for source in original_cost.keys():
                    combined_cost[source] = {}
                    for sink in original_cost[source].keys():
                        cost_val = original_cost[source][sink]
                        if isinstance(list(distance_matrix.values())[0] if distance_matrix else None, dict):
                            dist_val = distance_matrix.get(source, {}).get(sink, cost_val)
                        else:
                            dist_val = cost_val  # Fallback

                        combined_cost[source][sink] = w * cost_val + (1 - w) * dist_val

                modified_params['cost'] = combined_cost

        # Solve with weighted objective
        try:
            sol = solver.solve(modified_params)

            if sol and sol.get('status') == 'OPTIMAL':
                # Calculate both objectives separately using original cost/distance
                obj1_val = _calculate_objective(sol, params, 'cost')
                obj2_val = _calculate_objective(sol, params, 'distance') if 'distance' in params else obj1_val

                pareto_points.append({
                    'weight': w,
                    obj1_name.lower().replace(' ', '_'): obj1_val,
                    obj2_name.lower().replace(' ', '_'): obj2_val,
                    'solution': sol
                })

                print(f"  Point {idx+1}/{num_points} (w={w:.2f}): {obj1_name}={obj1_val:.2f}, {obj2_name}={obj2_val:.2f}")
            else:
                print(f"  Point {idx+1}/{num_points} (w={w:.2f}): FAILED ({sol.get('status', 'UNKNOWN') if sol else 'No solution'})")

        except Exception as e:
            print(f"  Point {idx+1}/{num_points} (w={w:.2f}): ERROR - {e}")
            continue

    if len(pareto_points) < 2:
        return {
            'success': False,
            'message': f'Could not generate Pareto front (only {len(pareto_points)} points succeeded)'
        }

    # Generate plot
    plot_path = _plot_pareto_front(pareto_points, obj1_name, obj2_name)

    print(f"\n Pareto front generated with {len(pareto_points)} points")
    print(f"  Plot saved to: {plot_path}\n")

    return {
        'success': True,
        'objectives': [obj1_name, obj2_name],
        'pareto_points': pareto_points,
        'plot_path': plot_path,
        'num_points': len(pareto_points)
    }


def _calculate_objective(solution: Dict, params: Dict, param_type: str) -> float:
    """
    Calculate objective value (cost or distance) from solution.

    Args:
        solution: Solution dict with flows
        params: Problem parameters
        param_type: 'cost' or 'distance'

    Returns:
        Objective value
    """
    flows = solution.get('flows', [])
    param_dict = params.get(param_type, {})

    total = 0.0

    # Handle nested dict format
    if isinstance(list(param_dict.values())[0] if param_dict else None, dict):
        # Nested: {plant: {market: val}}
        for flow in flows:
            plant = flow.get('plant')
            market = flow.get('market')
            value = flow.get('value', 0)

            if plant in param_dict and market in param_dict[plant]:
                total += param_dict[plant][market] * value
    else:
        # Flat: {(plant, market): val}
        for flow in flows:
            plant = flow.get('plant')
            market = flow.get('market')
            value = flow.get('value', 0)

            key = (plant, market)
            if key in param_dict:
                total += param_dict[key] * value

    return total


def _plot_pareto_front(pareto_points: List[Dict], obj1_name: str, obj2_name: str) -> str:
    """
    Plot Pareto front and save to file.

    Args:
        pareto_points: List of Pareto points
        obj1_name: Name of first objective
        obj2_name: Name of second objective

    Returns:
        Path to saved plot file
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
    except ImportError:
        print("Warning: matplotlib not available, cannot generate plot")
        return None

    # Extract objective values
    obj1_key = obj1_name.lower().replace(' ', '_')
    obj2_key = obj2_name.lower().replace(' ', '_')

    obj1_vals = [p[obj1_key] for p in pareto_points]
    obj2_vals = [p[obj2_key] for p in pareto_points]
    weights = [p['weight'] for p in pareto_points]

    # Create plot
    plt.figure(figsize=(10, 7))

    # Plot Pareto front
    scatter = plt.scatter(obj1_vals, obj2_vals, c=weights, cmap='viridis',
                         s=100, edgecolors='black', linewidths=1.5, alpha=0.8)

    # Connect points with line
    plt.plot(obj1_vals, obj2_vals, 'k--', alpha=0.3, linewidth=1)

    # Colorbar showing weight
    cbar = plt.colorbar(scatter)
    cbar.set_label('Weight (w)', rotation=270, labelpad=20, fontsize=12)

    # Labels and title
    plt.xlabel(obj1_name, fontsize=14, fontweight='bold')
    plt.ylabel(obj2_name, fontsize=14, fontweight='bold')
    plt.title('Pareto Front: Multi-Objective Trade-off Analysis', fontsize=16, fontweight='bold')

    # Grid
    plt.grid(True, alpha=0.3, linestyle='--')

    # Annotate extremes
    plt.annotate(f'Minimize {obj1_name}\n(w=1.0)',
                xy=(obj1_vals[0], obj2_vals[0]),
                xytext=(10, 10), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

    plt.annotate(f'Minimize {obj2_name}\n(w=0.0)',
                xy=(obj1_vals[-1], obj2_vals[-1]),
                xytext=(10, -30), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', fc='lightblue', alpha=0.7),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

    plt.tight_layout()

    # Save plot
    output_dir = 'tests/test_output'
    os.makedirs(output_dir, exist_ok=True)
    plot_path = os.path.join(output_dir, 'pareto_front.png')

    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()

    return plot_path


def format_pareto_results(results: Dict[str, Any]) -> str:
    """
    Format Pareto front results for display.

    Args:
        results: Results from perform_pareto_analysis

    Returns:
        Formatted string
    """
    if not results.get('success'):
        return f"   {results.get('message', 'Pareto front generation failed')}"

    output = []
    output.append("\n=Ê Pareto Front Analysis")
    output.append("=" * 80)

    objectives = results['objectives']
    pareto_points = results['pareto_points']

    output.append(f"Generated {results['num_points']} Pareto-optimal solutions")
    output.append(f"Trade-off between: {objectives[0]} vs {objectives[1]}\n")

    # Show table of points
    obj1_key = objectives[0].lower().replace(' ', '_')
    obj2_key = objectives[1].lower().replace(' ', '_')

    output.append(f"{'Weight':>8} | {objectives[0]:>15} | {objectives[1]:>15}")
    output.append("-" * 50)

    for point in pareto_points:
        w = point['weight']
        obj1 = point[obj1_key]
        obj2 = point[obj2_key]
        output.append(f"{w:>8.2f} | {obj1:>15.2f} | {obj2:>15.2f}")

    # Show plot location
    plot_path = results.get('plot_path')
    if plot_path:
        output.append(f"\n Plot saved to: {plot_path}")

    # Show insights
    output.append("\n=¡ Insights:")

    # Find extremes
    obj1_min = min(p[obj1_key] for p in pareto_points)
    obj1_max = max(p[obj1_key] for p in pareto_points)
    obj2_min = min(p[obj2_key] for p in pareto_points)
    obj2_max = max(p[obj2_key] for p in pareto_points)

    output.append(f"  " {objectives[0]} range: {obj1_min:.2f} to {obj1_max:.2f}")
    output.append(f"  " {objectives[1]} range: {obj2_min:.2f} to {obj2_max:.2f}")
    output.append(f"  " Trade-off: Reducing {objectives[0]} increases {objectives[1]}, and vice versa")
    output.append(f"  " Choose a point on the Pareto front based on your priorities")

    return "\n".join(output)
