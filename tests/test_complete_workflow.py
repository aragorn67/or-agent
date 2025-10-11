#!/usr/bin/env python3
"""
Complete Workflow Test: Optimization + Multiple Analyses + Plots

This script demonstrates a full end-to-end workflow:
1. Submit a NEW optimization problem (European wine distribution)
2. Get the solution
3. Request 4-5 different analyses including 3 plots
4. Save all plots as PNG files
5. Display results

Problem: European Wine Distribution
- 3 Wineries in different regions
- 4 Distribution centers across Europe
- Minimize transportation costs while meeting demand
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.enhanced_client import EnhancedLLMClient
from agent.core import OptimizationAgent
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# Create output directory for plots
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_output")
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

    print_section("COMPLETE WORKFLOW TEST: European Wine Distribution")

    # Step 1: Define the NEW optimization problem
    print_section("STEP 1: Define Optimization Problem")

    problem_description = """
    A European wine distribution company operates three wineries:
    - Bordeaux (France) can produce 800 bottles per week
    - Tuscany (Italy) can produce 650 bottles per week
    - Rioja (Spain) can produce 550 bottles per week

    They supply four distribution centers:
    - Amsterdam needs 500 bottles per week
    - Berlin requires 450 bottles per week
    - Vienna demands 400 bottles per week
    - Prague needs 350 bottles per week

    Transportation costs (€ per bottle):
    Bordeaux to Amsterdam: 2.50, Berlin: 3.20, Vienna: 4.10, Prague: 3.80
    Tuscany to Amsterdam: 4.50, Berlin: 3.80, Vienna: 2.20, Prague: 2.90
    Rioja to Amsterdam: 3.80, Berlin: 4.20, Vienna: 3.50, Prague: 3.20

    Minimize the total transportation cost while meeting all demand.
    """

    print("Problem: European Wine Distribution")
    print("-" * 80)
    print(problem_description)

    # Step 2: Initialize the optimization agent
    print_section("STEP 2: Initialize Optimization Agent")

    try:
        llm_client = EnhancedLLMClient(
            host="http://localhost:11434",
            model="qwen2:7b"
        )
        agent = OptimizationAgent(llm_client)
        print("✓ Agent initialized successfully")
    except Exception as e:
        print(f"✗ Error initializing agent: {e}")
        return

    # Step 3: Solve the optimization problem
    print_section("STEP 3: Solve Optimization Problem")

    print("Sending problem to solver...")
    result = agent.solve_natural_language(problem_description)

    if not result.get("success"):
        print(f"✗ Optimization failed: {result.get('error')}")
        return

    print("✓ Optimization completed successfully!\n")

    # Extract results
    solution = result.get("solution", {})
    params = result.get("extracted_params", {})
    explanation = result.get("explanation", "")

    print("SOLUTION SUMMARY")
    print("-" * 80)
    print(f"Problem Type: {result.get('problem_type')}")
    print(f"Confidence: {result.get('confidence', 0):.2f}")
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

    # Step 4: Request Analysis #1 - Flow Network Visualization
    print_section("ANALYSIS #1: Flow Network Visualization")

    print("Creating network visualization of wine flows...")
    fig1 = create_flow_network_plot(solution, params)
    plot1_file = save_plot(fig1, "flow_network")
    plt.close(fig1)

    # Step 5: Request Analysis #2 - Cost Breakdown
    print_section("ANALYSIS #2: Cost Breakdown by Route")

    print("Analyzing cost distribution across routes...")
    fig2 = create_cost_breakdown_plot(solution, params)
    plot2_file = save_plot(fig2, "cost_breakdown")
    plt.close(fig2)

    # Step 6: Request Analysis #3 - Capacity Utilization
    print_section("ANALYSIS #3: Winery Capacity Utilization")

    print("Analyzing capacity utilization at each winery...")
    fig3 = create_capacity_utilization_plot(solution, params)
    plot3_file = save_plot(fig3, "capacity_utilization")
    plt.close(fig3)

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
    print(f"✓ Plot 1: {plot1_file}")
    print(f"✓ Plot 2: {plot2_file}")
    print(f"✓ Plot 3: {plot3_file}")
    print(f"✓ Analysis 4: Sensitivity analysis (textual)")
    print(f"✓ Analysis 5: What-if scenario (textual)")

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
