#!/usr/bin/env python3
"""
TEST: Interactive Optimization AI with Infeasibility Resolution

PURPOSE:
    Interactive test for complete optimization workflow with infeasibility fix loop.
    Tests 3-layer feasibility checking and allows user to provide modifications
    to fix infeasible problems.

WORKFLOW:
    1. Classify problem type
    2. Extract parameters from natural language
    3. Check feasibility (3 layers):
       - Layer 0: Structural validation (empty sets, negative values, dimension mismatches)
       - Layer 1: Problem-specific necessary conditions (supply/demand balance, reachability)
       - Layer 2: Solver-based LP relaxation (constraint system feasibility)
    4. If INFEASIBLE:
       - Display reasons and suggested fixes
       - Ask user for modification (max 3 attempts)
       - Parse modification using LLM
       - Apply changes and re-check feasibility
       - Loop until feasible or max retries
    5. If FEASIBLE: Solve and display solution
    6. Interactive Follow-Up Questions:
       - Sensitivity analysis: Test impact of parameter changes
       - What-if scenarios: Explore hypothetical modifications
       - Re-solve: Apply modifications and re-optimize
       - Pareto front: Multi-objective optimization (planned)

USAGE:
    python test_OptAI.py [problem_name] [--no-graphs]

EXAMPLES:
    # Feasible problem (solves directly)
    python test_OptAI.py european_wine_distribution

    # Infeasible problem - Layer 1 (supply < demand)
    python test_OptAI.py infeasible_transport_supply_less_than_demand

    # Infeasible problem - Layer 2 (arc capacity pattern)
    python test_OptAI.py infeasible_transport_capacity_pattern

AVAILABLE TEST PROBLEMS:
    Feasible:
    - european_wine_distribution
    - us_manufacturing_distribution

    Infeasible - Layer 1 (Necessary Conditions):
    - infeasible_transport_supply_less_than_demand (supply=70, demand=80)

    Infeasible - Layer 2 (Solver-based):
    - infeasible_transport_capacity_pattern (arc capacity bottleneck)

EXAMPLE MODIFICATIONS (during infeasibility fix):
    - "increase capacity of Plant North by 10"
    - "set capacity of Plant North to 50"
    - "reduce demand of Centre A by 5"
    - "increase arc capacity from F2 to B to 50"

EXAMPLE FOLLOW-UP QUESTIONS (after successful solve):
    Sensitivity Analysis:
    - "sensitivity on Plant North capacity"
    - "what is the impact of changing demand for Market A"

    What-If Scenarios:
    - "what if demand of Market A increases by 20"
    - "what if capacity of Plant South was 100"

    Re-solve with Modifications:
    - "resolve with capacity of Plant North = 100"
    - "re-solve with demand for Market A = 50"

    Type 'done' or 'quit' to exit follow-up session.

REQUIRES:
    - Ollama running on localhost:11434
    - Model: deepseek-r1:latest (for reasoning and explanations)
    - Python packages: pyomo, matplotlib, numpy
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from llm.enhanced_client import EnhancedLLMClient
from agent.core import OptimizationAgent
from tests.or_problem_repository import get_problem_by_name, get_problem_by_id, get_all_problems
from config import Config
from feasibility import check_feasibility, FeasStatus
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# Create output directory for plots
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "test_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def save_plot(fig, name):
    """Save a matplotlib figure as PNG"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{OUTPUT_DIR}/{timestamp}_{name}.png"
    fig.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"   ✓ Saved plot: {filename}")
    return filename

def create_flow_network_plot(solution, params):
    """Create a network visualization of the flows"""
    fig, ax = plt.subplots(figsize=(12, 8))

    plants = params.get("plants", [])
    markets = params.get("markets", [])
    flows = solution.get("flows", [])

    # Position nodes
    n_plants = len(plants)
    n_markets = len(markets)

    plant_positions = {plant: (0, i/(n_plants-1) if n_plants > 1 else 0.5)
                      for i, plant in enumerate(plants)}
    market_positions = {market: (1, i/(n_markets-1) if n_markets > 1 else 0.5)
                       for i, market in enumerate(markets)}

    # Draw nodes
    for plant, (x, y) in plant_positions.items():
        ax.scatter(x, y, s=500, c='green', alpha=0.6, zorder=5)
        ax.text(x-0.05, y, plant, ha='right', va='center', fontsize=10, fontweight='bold')

    for market, (x, y) in market_positions.items():
        ax.scatter(x, y, s=500, c='blue', alpha=0.6, zorder=5)
        ax.text(x+0.05, y, market, ha='left', va='center', fontsize=10, fontweight='bold')

    # Draw flows (edges)
    max_flow = max(f.get('value', 0) for f in flows) if flows else 1
    for flow in flows:
        if flow.get('value', 0) > 0.1:  # Only significant flows
            plant = flow.get('plant', '')
            market = flow.get('market', '')
            value = flow.get('value', 0)

            if plant in plant_positions and market in market_positions:
                x1, y1 = plant_positions[plant]
                x2, y2 = market_positions[market]

                # Line width proportional to flow
                width = 1 + 5 * (value / max_flow)
                ax.plot([x1, x2], [y1, y2], 'gray', linewidth=width, alpha=0.5, zorder=1)

                # Add flow label
                mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
                ax.text(mid_x, mid_y, f'{value:.0f}',
                       bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
                       ha='center', va='center', fontsize=8)

    ax.set_xlim(-0.2, 1.2)
    ax.set_ylim(-0.1, 1.1)
    ax.axis('off')
    ax.set_title('Transportation Flow Network\n(line thickness = flow volume)',
                fontsize=14, fontweight='bold')

    # Legend
    ax.text(0, -0.05, '● Wineries', color='green', fontsize=10, fontweight='bold')
    ax.text(1, -0.05, '● Distribution Centers', color='blue', fontsize=10, fontweight='bold')

    return fig

def create_cost_breakdown_plot(solution, params):
    """Create a stacked bar chart of costs by route"""
    fig, ax = plt.subplots(figsize=(12, 6))

    flows = solution.get("flows", [])
    costs = params.get("cost", {})

    # Calculate cost for each flow
    route_costs = []
    route_labels = []

    for flow in flows:
        if flow.get('value', 0) > 0.1:
            plant = flow.get('plant', '')
            market = flow.get('market', '')
            value = flow.get('value', 0)
            unit_cost = costs.get(plant, {}).get(market, 0)
            total_cost = value * unit_cost

            route_costs.append(total_cost)
            route_labels.append(f"{plant}\n→\n{market}")

    # Sort by cost
    sorted_data = sorted(zip(route_costs, route_labels), reverse=True)
    route_costs, route_labels = zip(*sorted_data) if sorted_data else ([], [])

    # Create bar chart
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(route_costs)))
    bars = ax.bar(range(len(route_costs)), route_costs, color=colors)

    ax.set_xticks(range(len(route_labels)))
    ax.set_xticklabels(route_labels, rotation=0, ha='center', fontsize=9)
    ax.set_ylabel('Total Cost (€)', fontsize=12, fontweight='bold')
    ax.set_title('Cost Breakdown by Route', fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)

    # Add value labels on bars
    for i, (bar, cost) in enumerate(zip(bars, route_costs)):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
               f'€{cost:.0f}',
               ha='center', va='bottom', fontsize=9, fontweight='bold')

    # Total cost annotation
    total_cost = sum(route_costs)
    ax.text(0.98, 0.98, f'Total Cost: €{total_cost:.0f}',
           transform=ax.transAxes, ha='right', va='top',
           bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7),
           fontsize=12, fontweight='bold')

    return fig

def create_capacity_utilization_plot(solution, params):
    """Create a bar chart showing capacity utilization"""
    fig, ax = plt.subplots(figsize=(10, 6))

    plants = params.get("plants", [])
    capacities = params.get("capacity", {})
    flows = solution.get("flows", [])

    # Calculate utilization for each plant
    plant_utilization = {plant: 0 for plant in plants}
    for flow in flows:
        plant = flow.get('plant', '')
        if plant in plant_utilization:
            plant_utilization[plant] += flow.get('value', 0)

    # Prepare data
    plant_names = list(plant_utilization.keys())
    used = [plant_utilization[p] for p in plant_names]
    capacity = [capacities.get(p, 0) for p in plant_names]
    unused = [capacity[i] - used[i] for i in range(len(plant_names))]
    utilization_pct = [(used[i]/capacity[i]*100) if capacity[i] > 0 else 0
                       for i in range(len(plant_names))]

    # Create stacked bar chart
    x = np.arange(len(plant_names))
    width = 0.6

    bars1 = ax.bar(x, used, width, label='Used Capacity', color='steelblue')
    bars2 = ax.bar(x, unused, width, bottom=used, label='Unused Capacity',
                   color='lightgray', alpha=0.5)

    ax.set_ylabel('Capacity (units)', fontsize=12, fontweight='bold')
    ax.set_title('Winery Capacity Utilization', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(plant_names, fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(axis='y', alpha=0.3)

    # Add utilization percentage labels
    for i, (bar, pct, u, c) in enumerate(zip(bars1, utilization_pct, used, capacity)):
        ax.text(bar.get_x() + bar.get_width()/2., c + 5,
               f'{pct:.1f}%\n({u:.0f}/{c:.0f})',
               ha='center', va='bottom', fontsize=9, fontweight='bold')

    return fig

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def main():
    """Run the complete workflow"""

    # Parse command-line arguments
    problem_name = "european_wine_distribution"  # Default
    generate_graphs = False  # Default: no graphs

    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg == "--no-graphs":
                generate_graphs = False
            elif not arg.startswith("--"):
                problem_name = arg

    print_section(f"COMPLETE WORKFLOW TEST: {problem_name}")

    # Step 1: Define the optimization problem
    print_section("STEP 1: Define Optimization Problem")

    # Get problem from centralized repository
    # Try by ID first (e.g., transport/wine_eu/001), then by name
    problem = get_problem_by_id(problem_name) or get_problem_by_name(problem_name)
    if not problem:
        print(f"✗ Error: Problem '{problem_name}' not found in repository")
        print("\nAvailable problems:")
        all_probs = get_all_problems()
        for p in all_probs:
            print(f"  - {p['id']}")
        return

    problem_description = problem["text"]

    print(f"Problem: {problem['name']}")
    print(f"Expected solvable: {problem.get('solvable', 'Unknown')}")
    print("-" * 80)
    print(problem_description)

    # Step 2: Initialize the optimization agent
    print_section("STEP 2: Initialize Optimization Agent")

    try:
        llm_client = EnhancedLLMClient(
            host=Config.OLLAMA_HOST,
            model=Config.OLLAMA_MODEL
        )
        agent = OptimizationAgent(llm_client)
        print("✓ Agent initialized successfully")
    except Exception as e:
        print(f"✗ Error initializing agent: {e}")
        return

    # Step 3: Classify and Extract Parameters
    print_section("STEP 3: Classify Problem Type and Extract Parameters")

    print("Classifying problem type...")
    from llm.problem_classifier import ProblemClassifier
    from llm.ollama_client import OllamaClient

    ollama = OllamaClient(host=Config.OLLAMA_HOST, model=Config.OLLAMA_MODEL)
    classifier = ProblemClassifier(ollama)
    classification, votes = classifier.classify(problem_description)

    expected_type = problem.get('expected_type', 'UNKNOWN')
    classified_type = classification.get('problem_type', 'UNKNOWN')

    if expected_type == classified_type:
        print(f"✓ Problem type: {classified_type} ✅ CORRECT")
    else:
        print(f"✗ Problem type: {classified_type} ❌ WRONG (expected: {expected_type})")

    print(f"  Confidence: {classification.get('confidence', 0):.2f}")
    print(f"  Solver: {classification.get('solver_id', 'UNKNOWN')}")

    print("\nExtracting parameters...")
    from llm.transportation_specialist import TransportationSpecialist
    specialist = TransportationSpecialist(ollama)
    extracted_params = specialist.extract_parameters(problem_description)

    if "error" in extracted_params:
        print(f"✗ Extraction failed: {extracted_params['error']}")
        return

    print("✓ Parameters extracted successfully")
    print(f"  Plants: {len(extracted_params.get('plants', []))}")
    print(f"  Markets: {len(extracted_params.get('markets', []))}")

    # Step 4: Check Feasibility (NEW!)
    print_section("STEP 4: Feasibility Checking (3 Layers)")

    print("Running 3-layer feasibility check before optimization...")
    print("")
    print("  LAYER 1: Structural Validation")
    print("    • Check for empty sets, missing data")
    print("    • Verify dimension consistency")
    print("    • Validate domain constraints (e.g., no negative values)")
    print("")
    print("  LAYER 2: Problem-Specific Necessary Conditions")
    print("    • Check total supply ≥ total demand")
    print("    • Verify all markets are reachable")
    print("    • Validate individual route capacity limits")
    print("")
    print("  LAYER 3: Solver-Based LP Relaxation")
    print("    • Build full optimization model")
    print("    • Relax integer variables to continuous")
    print("    • Check if LP has any feasible solution")
    print("")

    # Build instance for feasibility checking
    from solvers.transport.bipartite import BipartiteTransportSolver
    solver_instance = BipartiteTransportSolver()

    # Convert extracted params to solver format
    instance = {
        'problem_type': 'TRANSPORTATION',
        'solver_id': 'transport_basic_bipartite',
        'sets': {
            'I_plants': extracted_params.get('plants', []),
            'J_markets': extracted_params.get('markets', [])
        },
        'params': {
            'supply': extracted_params.get('capacity', {}),
            'demand': extracted_params.get('demand', {}),
            'cost': {(plant, market): cost
                     for plant, markets in extracted_params.get('cost', {}).items()
                     for market, cost in markets.items()}
        }
    }

    # Add arc_capacity if present
    if 'arc_capacity' in extracted_params and extracted_params['arc_capacity']:
        instance['params']['arc_capacity'] = {
            (plant, market): cap
            for plant, markets in extracted_params['arc_capacity'].items()
            for market, cap in markets.items()
        }

    # Run feasibility check
    report = check_feasibility(instance)

    print(f"\n{'='*80}")
    print(f"  FEASIBILITY RESULT: {report.status.value}")
    print(f"{'='*80}\n")

    # Map layer numbers to descriptive names
    layer_names = {
        0: "Layer 1 (Structural Validation)",
        1: "Layer 2 (Problem-Specific Conditions)",
        2: "Layer 3 (LP Relaxation)"
    }

    print(f"Highest layer passed: {layer_names.get(report.layer_passed, f'Layer {report.layer_passed}')}")
    print(f"\nDetails:")
    for i, reason in enumerate(report.reasons, 1):
        print(f"  {i}. {reason}")

    # If INFEASIBLE, enter interactive fix loop
    retry_count = 0
    max_retries = 3
    original_params = extracted_params.copy()
    previous_report = report  # Track previous state to detect if problem got worse

    while report.status == FeasStatus.INFEASIBLE and retry_count < max_retries:
        print_section(f"INFEASIBILITY DETECTED (Attempt {retry_count + 1}/{max_retries})")

        print("❌ This problem CANNOT be solved because:\n")

        # Categorize by layer
        if report.layer_passed == 0:
            print("🔍 LAYER 1 (Structural Validation) Issues:")
            print("   The problem has structural defects in its formulation:")
        elif report.layer_passed == 1:
            print("🔍 LAYER 2 (Problem-Specific Conditions) Issues:")
            print("   The problem violates necessary conditions:")
        else:
            print("🔍 LAYER 3 (LP Relaxation) Issues:")
            print("   The constraint system is infeasible:")

        for reason in report.reasons:
            print(f"   • {reason}")

        print("\n💡 Suggested Fixes:")
        if report.suggestions:
            for suggestion in report.suggestions:
                print(f"   • {suggestion}")
        else:
            # Generic suggestions based on layer
            if report.layer_passed == 0:
                print("   • Check that all cost matrix entries are defined")
                print("   • Verify that plant and market names match across all parameters")
            elif report.layer_passed == 1:
                print("   • Increase plant capacities to meet total demand")
                print("   • Reduce market demands to match available supply")
                print("   • Check individual route capacity limits")
            else:
                print("   • Review arc capacity constraints")
                print("   • Check if constraint pattern creates bottlenecks")

        print("\n" + "-"*80)
        print("What would you like to do?")
        print("  1. Type a modification (e.g., 'increase capacity of Plant North by 10')")
        print("  2. Type 'quit' to exit")
        print("-"*80)

        user_input = input("\nYour modification: ").strip()

        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n" + "="*80)
            print("  User quit - workflow stopped")
            print("="*80 + "\n")
            return

        # Parse and apply modification using LLM
        print("\n🔄 Parsing your modification...")
        modification_result = llm_client.parse_infeasibility_fix(
            user_input,
            extracted_params,
            {
                "layer_failed": report.layer_passed,
                "reasons": report.reasons,
                "suggestions": report.suggestions
            }
        )

        if modification_result.get("is_complete_redescription"):
            print("⚠️  Detected complete redescription - please use modifications instead")
            continue

        # Apply modifications
        extracted_params = modification_result.get("applied_params", extracted_params)
        modifications = modification_result.get("modifications", [])

        if modifications:
            print(f"✓ Applied {len(modifications)} modification(s):")
            for mod in modifications:
                print(f"   • {mod.get('type')} {mod.get('parameter')} of {mod.get('entity')} by/to {mod.get('value')}")
        else:
            print("⚠️  No modifications detected - please try rephrasing")
            continue

        # Rebuild instance with modified params
        instance = {
            'problem_type': 'TRANSPORTATION',
            'solver_id': 'transport_basic_bipartite',
            'sets': {
                'I_plants': extracted_params.get('plants', []),
                'J_markets': extracted_params.get('markets', [])
            },
            'params': {
                'supply': extracted_params.get('capacity', {}),
                'demand': extracted_params.get('demand', {}),
                'cost': {(plant, market): cost
                         for plant, markets in extracted_params.get('cost', {}).items()
                         for market, cost in markets.items()}
            }
        }

        # Add arc_capacity if present
        if 'arc_capacity' in extracted_params and extracted_params['arc_capacity']:
            instance['params']['arc_capacity'] = {
                (plant, market): cap
                for plant, markets in extracted_params['arc_capacity'].items()
                for market, cap in markets.items()
            }

        # Re-check feasibility
        print("\n🔄 Re-checking feasibility...")
        new_report = check_feasibility(instance)
        retry_count += 1

        print(f"\n{'='*80}")
        print(f"  FEASIBILITY RESULT: {new_report.status.value}")
        print(f"{'='*80}\n")

        # Check if problem got WORSE
        if new_report.status == FeasStatus.INFEASIBLE:
            # Extract shortfall from reasons if it exists
            def extract_shortfall(reasons):
                for reason in reasons:
                    if "Shortfall:" in reason:
                        # Extract number after "Shortfall:" (handle trailing period)
                        import re
                        match = re.search(r'Shortfall:\s*([\d.]+)', reason)
                        if match:
                            # Remove trailing period if present
                            value_str = match.group(1).rstrip('.')
                            return float(value_str)
                return None

            prev_shortfall = extract_shortfall(previous_report.reasons)
            new_shortfall = extract_shortfall(new_report.reasons)

            if prev_shortfall is not None and new_shortfall is not None and new_shortfall > prev_shortfall:
                print(f"⚠️  WARNING: Your modification made the problem WORSE!")
                print(f"   Shortfall INCREASED from {prev_shortfall:.2f} to {new_shortfall:.2f}\n")
                print(f"💡 HINT: You need to INCREASE supply or DECREASE demand.")
                print(f"   Did you accidentally increase demand when you meant to increase supply?\n")

        # Update tracking
        previous_report = new_report
        report = new_report

    # Check if we exhausted retries
    if report.status == FeasStatus.INFEASIBLE:
        print("\n" + "="*80)
        print(f"  Maximum retries ({max_retries}) reached - problem still infeasible")
        print("="*80 + "\n")
        return

    # If FEASIBLE, proceed to solve
    print("\n✅ Problem is FEASIBLE - proceeding to solve...\n")

    # Show modifications if any were made
    if retry_count > 0:
        print("📝 Modifications Applied to Make Problem Feasible:")
        print("-" * 80)
        # Show diff
        if 'capacity' in original_params and 'capacity' in extracted_params:
            for entity in extracted_params.get('capacity', {}):
                old_val = original_params.get('capacity', {}).get(entity, 0)
                new_val = extracted_params.get('capacity', {}).get(entity, 0)
                if abs(old_val - new_val) > 1e-6:
                    print(f"  Capacity[{entity}]: {old_val} → {new_val} (change: {new_val - old_val:+.2f})")
        if 'demand' in original_params and 'demand' in extracted_params:
            for entity in extracted_params.get('demand', {}):
                old_val = original_params.get('demand', {}).get(entity, 0)
                new_val = extracted_params.get('demand', {}).get(entity, 0)
                if abs(old_val - new_val) > 1e-6:
                    print(f"  Demand[{entity}]: {old_val} → {new_val} (change: {new_val - old_val:+.2f})")
        print()

    # Step 5: Solve the optimization problem
    print_section("STEP 5: Solve Optimization Problem")

    print("Sending problem to solver...")

    # Use the solver directly with (possibly modified) parameters
    solution = solver_instance.solve(extracted_params)

    if not solution or solution.get("status") != "OPTIMAL":
        print(f"✗ Optimization failed: {solution.get('status', 'UNKNOWN')}")
        return

    print("✓ Optimization completed successfully!\n")

    # Generate explanation using LLM
    explanation_result = llm_client.explain_solution(solution, "TRANSPORTATION", problem_description)
    explanation = explanation_result.get('explanation', '')
    params = extracted_params

    print("SOLUTION SUMMARY")
    print("-" * 80)
    print(f"Problem Type: TRANSPORTATION")
    print(f"Confidence: {classification.get('confidence', 0):.2f}")
    print(f"Optimal Cost: €{solution.get('objective_value', 0):.2f}")
    print(f"Status: {solution.get('status', 'UNKNOWN')}")
    print(f"\n{explanation}\n")

    # Display flows
    flows = solution.get("flows", [])
    print("OPTIMAL SHIPMENTS:")
    print("-" * 80)
    for flow in sorted(flows, key=lambda f: f.get('value', 0), reverse=True):
        if flow.get('value', 0) > 0.1:
            print(f"  {flow['plant']:12} → {flow['market']:12}: {flow['value']:6.1f} bottles")

    # Step 6: Interactive Follow-Up Questions Loop
    print_section("STEP 6: Follow-Up Questions & Analysis")

    print("The problem has been solved successfully! You can now:")
    print("  1. Perform sensitivity analysis (e.g., 'sensitivity on Plant North capacity')")
    print("  2. Run what-if scenarios (e.g., 'what if demand of Market A increases by 20')")
    print("  3. Re-solve with modifications (e.g., 'resolve with capacity of Plant North = 100')")
    print("  4. Generate Pareto front (multi-objective)")
    print("  5. Type 'done' or 'quit' to finish")
    print()

    # Import analysis module
    from analysis import detect_analysis_type, execute_analysis, format_analysis_output

    while True:
        print("-" * 80)
        user_query = input("Your question/request (or 'done' to finish): ").strip()

        if user_query.lower() in ['done', 'quit', 'exit', 'q', '']:
            print("\n✓ Follow-up session ended\n")
            break

        try:
            # Detect analysis type (with LLM for robust detection)
            analysis_type = detect_analysis_type(user_query, llm_client)

            if analysis_type == 'unknown':
                print("\n⚠️  Unsupported query type. Try:")
                print("  - 'sensitivity on [parameter]'")
                print("  - 'what if [modification]'")
                print("  - 'resolve with [modification]'")
                print("  - 'pareto front'")
                continue

            # Execute analysis
            results = execute_analysis(
                analysis_type=analysis_type,
                solver=solver_instance,
                params=extracted_params,
                solution=solution,
                query=user_query,
                llm_client=llm_client
            )

            # Handle infeasible what-if scenarios with retry loop
            if analysis_type == 'what_if' and not results.get('success') and not results.get('feasible'):
                # Show initial failure
                output = format_analysis_output(analysis_type, results)
                print(output)

                # Offer retry for what-if scenarios
                max_scenario_retries = 3
                scenario_retry_count = 0

                while scenario_retry_count < max_scenario_retries:
                    print("\n" + "-" * 80)
                    print("What would you like to do?")
                    print("  1. Try a different scenario modification")
                    print("  2. Type 'cancel' to return to analysis menu")
                    print("-" * 80)

                    retry_query = input("\nModified scenario (or 'cancel'): ").strip()

                    if retry_query.lower() in ['cancel', 'quit', 'exit', 'q']:
                        print("\n✓ Scenario cancelled\n")
                        break

                    # Try the modified scenario
                    scenario_retry_count += 1
                    try:
                        results = execute_analysis(
                            analysis_type='what_if',
                            solver=solver_instance,
                            params=extracted_params,
                            solution=solution,
                            query=retry_query,
                            llm_client=llm_client
                        )

                        output = format_analysis_output('what_if', results)
                        print(output)

                        # If successful, break retry loop
                        if results.get('success'):
                            break

                    except Exception as e:
                        print(f"\n⚠️  Scenario analysis failed: {e}")

                continue  # Return to main analysis loop

            # Format and display results (non-what-if or successful what-if)
            output = format_analysis_output(analysis_type, results)
            print(output)

            # For re-solve, update params and solution permanently
            if analysis_type == 'resolve' and results.get('success'):
                extracted_params = results['new_params']
                solution = results['new_solution']

        except Exception as e:
            print(f"\n⚠️  Analysis failed: {e}")
            import traceback
            traceback.print_exc()

    # Continue with remaining sections
    # Step 7: Request Analysis #1 - Flow Network Visualization
    plot1_file = None
    plot2_file = None
    plot3_file = None

    if generate_graphs:
        print_section("ANALYSIS #1: Flow Network Visualization")

        print("Creating network visualization of flows...")
        fig1 = create_flow_network_plot(solution, params)
        plot1_file = save_plot(fig1, "flow_network")
        plt.close(fig1)

        # Step 7: Request Analysis #2 - Cost Breakdown
        print_section("ANALYSIS #2: Cost Breakdown by Route")

        print("Analyzing cost distribution across routes...")
        fig2 = create_cost_breakdown_plot(solution, params)
        plot2_file = save_plot(fig2, "cost_breakdown")
        plt.close(fig2)

        # Step 8: Request Analysis #3 - Capacity Utilization
        print_section("ANALYSIS #3: Winery Capacity Utilization")

        print("Analyzing capacity utilization at each plant...")
        fig3 = create_capacity_utilization_plot(solution, params)
        plot3_file = save_plot(fig3, "capacity_utilization")
        plt.close(fig3)
    else:
        print_section("GRAPHS DISABLED (--no-graphs flag)")
        print("Skipping graph generation as requested.")

    # Step 7: Request Analysis #4 - Textual Sensitivity Analysis
    print_section("ANALYSIS #4: Sensitivity Analysis")

    print("What happens if we increase Bordeaux capacity by 20%?")
    print("-" * 80)

    # Calculate impact
    bordeaux_capacity = params.get("capacity", {}).get("Bordeaux", 0)
    new_capacity = bordeaux_capacity * 1.2
    current_cost = solution.get("objective_value", 0)

    print(f"Current Bordeaux capacity: {bordeaux_capacity:.0f} bottles/week")
    print(f"Proposed capacity: {new_capacity:.0f} bottles/week (+{bordeaux_capacity*0.2:.0f})")
    print(f"\nCurrent optimal cost: €{current_cost:.2f}")
    print(f"\nPotential impact:")
    print(f"  • More flexibility in routing decisions")
    print(f"  • Could reduce reliance on more expensive routes")
    print(f"  • Estimated cost reduction: 3-7% (€{current_cost*0.03:.2f} - €{current_cost*0.07:.2f})")
    print(f"\nNote: Run re-optimization with updated capacity for exact savings")

    # Step 8: Request Analysis #5 - What-if Scenario
    print_section("ANALYSIS #5: What-If Scenario Analysis")

    print("What if Berlin's demand increases by 100 bottles?")
    print("-" * 80)

    berlin_demand = params.get("demand", {}).get("Berlin", 0)
    total_capacity = sum(params.get("capacity", {}).values())
    total_demand = sum(params.get("demand", {}).values())

    print(f"Current Berlin demand: {berlin_demand:.0f} bottles/week")
    print(f"Proposed demand: {berlin_demand + 100:.0f} bottles/week (+100)")
    print(f"\nCurrent supply/demand balance:")
    print(f"  Total capacity: {total_capacity:.0f} bottles")
    print(f"  Total demand: {total_demand:.0f} bottles")
    print(f"  Surplus: {total_capacity - total_demand:.0f} bottles")
    print(f"\nAfter increase:")
    print(f"  New total demand: {total_demand + 100:.0f} bottles")
    print(f"  Remaining surplus: {total_capacity - total_demand - 100:.0f} bottles")

    if total_capacity - total_demand >= 100:
        print(f"\n✓ Feasible - sufficient capacity to meet increased demand")
        print(f"  Estimated cost increase: €{100 * 3.5:.2f} (avg. €3.50/bottle to Berlin)")
    else:
        print(f"\n✗ Warning - may exceed total capacity")
        print(f"  Consider increasing production capacity")

    # Final Summary
    print_section("WORKFLOW COMPLETE - SUMMARY")

    print("Generated Artifacts:")
    print("-" * 80)
    print(f"✓ Optimization solution: €{solution.get('objective_value', 0):.2f} optimal cost")
    if generate_graphs:
        print(f"✓ Plot 1: {plot1_file}")
        print(f"✓ Plot 2: {plot2_file}")
        print(f"✓ Plot 3: {plot3_file}")
    else:
        print(f"  (Graphs disabled with --no-graphs flag)")
    print(f"✓ Analysis 4: Sensitivity analysis (textual)")
    print(f"✓ Analysis 5: What-if scenario (textual)")

    if generate_graphs:
        print(f"\nAll plots saved to: {OUTPUT_DIR}/")
    print("\nKey Insights:")
    print("-" * 80)

    # Calculate some insights
    total_shipped = sum(f.get('value', 0) for f in flows)
    avg_cost_per_bottle = current_cost / total_shipped if total_shipped > 0 else 0

    print(f"• Total bottles shipped: {total_shipped:.0f}")
    print(f"• Average cost per bottle: €{avg_cost_per_bottle:.2f}")
    print(f"• Most expensive route: Check cost breakdown plot")
    print(f"• Capacity utilization: Check utilization plot")
    print(f"• Network efficiency: Check flow network plot")

    print("\n" + "="*80)
    print("  Test completed successfully!")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
