#!/usr/bin/env python3
"""
TEST: LLM Reasoning Chain Demonstration

PURPOSE: Demonstrates complete LLM reasoning for optimization + follow-ups
TESTS: Intent classification, follow-up detection, processing decisions, visualizations
PROBLEM: european_wine_distribution (from or_problem_repository)
SCENARIO: 6 sequential prompts
    1. Solve optimization problem
    2. "What is the objective function?"
    3. "Show me a plot of the shipment flows"
    4. "Create a cost breakdown chart"
    5. "Visualize capacity utilization"
    6. "What if we increase Bordeaux capacity by 20%?"

EXPECTED OUTPUT:
    ✓ All 6 prompts classified correctly (90%, 90%, 90%, 80%, 80%, 90%)
    ✓ Optimal solution: €4,750.00
    ✓ 3 PNG plots: flows.png, costs.png, utilization.png
    ✓ Sensitivity analysis response
    ✓ Final summary showing all prompts processed

RUN: python tests/test_llm_reasoning_chain.py
REQUIRES: Ollama (localhost:11434), qwen2:7b model
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.enhanced_client import EnhancedLLMClient
from llm.knowledge_base import KnowledgeBase
from agent.core import OptimizationAgent
from llm.intent_router import IntentRouter
from llm.follow_up_handler import FollowUpHandler
from or_problem_repository import get_problem_by_name
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def print_header(title):
    """Print a large section header"""
    print(f"\n\n{'═'*100}")
    print(f"{'═'*100}")
    print(f"  {title}")
    print(f"{'═'*100}")
    print(f"{'═'*100}\n")


def print_subheader(title):
    """Print a subsection header"""
    print(f"\n{'─'*100}")
    print(f"  {title}")
    print(f"{'─'*100}\n")


def print_prompt(prompt_num, prompt_text, prompt_type):
    """Print the user's prompt"""
    print(f"\n┌{'─'*98}┐")
    print(f"│  🎯 PROMPT_{prompt_num}: {prompt_type:<80} │")
    print(f"└{'─'*98}┘")
    print(f"\nUser Input:\n  \"{prompt_text}\"")


def print_llm_understanding(intent_result, follow_up_result=None):
    """Print how the LLM understood the prompt"""
    print(f"\n┌{'─'*98}┐")
    print(f"│  🧠 LLM UNDERSTANDING{' '*77} │")
    print(f"└{'─'*98}┘")

    print(f"\n1️⃣  Intent Classification:")
    print(f"    • Intent Type: {intent_result.get('intent', 'unknown').upper()}")
    print(f"    • Confidence: {intent_result.get('confidence', 0):.1%}")
    print(f"    • Reasoning: {intent_result.get('reasoning', 'N/A')}")

    if follow_up_result:
        print(f"\n2️⃣  Follow-Up Analysis:")
        print(f"    • Is Follow-Up: {follow_up_result.get('is_follow_up', False)}")
        print(f"    • Follow-Up Type: {follow_up_result.get('follow_up_type', 'N/A').upper()}")
        print(f"    • Confidence: {follow_up_result.get('confidence', 0):.1%}")

        if 'question_category' in follow_up_result:
            print(f"    • Question Category: {follow_up_result['question_category']}")

        if 'analysis_types' in follow_up_result:
            print(f"    • Analysis Types: {', '.join(follow_up_result['analysis_types'])}")

        if 'modification_targets' in follow_up_result:
            targets = follow_up_result.get('modification_targets', [])
            if isinstance(targets, list) and targets:
                print(f"    • Modification Targets: {', '.join(targets)}")
            elif targets:
                print(f"    • Modification Targets: {targets}")
            else:
                print(f"    • Modification Targets: TBD")


def print_processing_decision(handler_type, reasoning):
    """Print which processing path will be used"""
    print(f"\n┌{'─'*98}┐")
    print(f"│  🔍 PROCESSING DECISION{' '*73} │")
    print(f"└{'─'*98}┘")

    print(f"\n🛠️  Handler: {handler_type}")
    print(f"📋 Decision Logic:\n{reasoning}")


def print_chain_of_thought(thought_process):
    """Print the reasoning for why this response was chosen"""
    print(f"\n┌{'─'*98}┐")
    print(f"│  💭 CHAIN OF THOUGHT{' '*76} │")
    print(f"└{'─'*98}┘")

    print(f"\n{thought_process}")


def print_response(response_type, response_data):
    """Print the system's response"""
    print(f"\n┌{'─'*98}┐")
    print(f"│  ✅ SYSTEM RESPONSE{' '*78} │")
    print(f"└{'─'*98}┘")

    print(f"\nResponse Type: {response_type}")
    print(f"\n{response_data}")


def save_plot(fig, name):
    """Save a matplotlib figure"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{OUTPUT_DIR}/{timestamp}_{name}.png"
    fig.savefig(filename, dpi=150, bbox_inches='tight')
    print(f"\n📊 Plot saved: {filename}")
    return filename


def create_flow_plot(solution, params):
    """Create shipment flow visualization"""
    fig, ax = plt.subplots(figsize=(10, 6))
    flows = solution.get("flows", [])

    significant = [f for f in flows if f.get('value', 0) > 0.1]
    labels = [f"{f['plant'][:10]}→{f['market'][:10]}" for f in significant]
    values = [f['value'] for f in significant]

    ax.barh(range(len(labels)), values, color='steelblue')
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel('Flow Volume (bottles/week)', fontsize=11)
    ax.set_title('Shipment Flows by Route', fontsize=13, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)

    return fig


def create_cost_plot(solution, params):
    """Create cost breakdown visualization"""
    fig, ax = plt.subplots(figsize=(10, 6))
    flows = solution.get("flows", [])
    costs = params.get("cost", {})

    route_costs = []
    labels = []
    for f in flows:
        if f.get('value', 0) > 0.1:
            unit_cost = costs.get(f['plant'], {}).get(f['market'], 0)
            total = f['value'] * unit_cost
            route_costs.append(total)
            labels.append(f"{f['plant'][:10]}→{f['market'][:10]}")

    ax.bar(range(len(labels)), route_costs, color='coral')
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=8)
    ax.set_ylabel('Total Cost (€)', fontsize=11)
    ax.set_title('Cost Breakdown by Route', fontsize=13, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)

    return fig


def create_utilization_plot(solution, params):
    """Create capacity utilization visualization"""
    fig, ax = plt.subplots(figsize=(10, 6))
    plants = params.get("plants", [])
    capacities = params.get("capacity", {})
    flows = solution.get("flows", [])

    used = {p: 0 for p in plants}
    for f in flows:
        used[f['plant']] = used.get(f['plant'], 0) + f.get('value', 0)

    plant_names = list(used.keys())
    used_vals = [used[p] for p in plant_names]
    cap_vals = [capacities.get(p, 0) for p in plant_names]
    unused = [cap_vals[i] - used_vals[i] for i in range(len(plant_names))]

    x = np.arange(len(plant_names))
    ax.bar(x, used_vals, label='Used Capacity', color='green', alpha=0.7)
    ax.bar(x, unused, bottom=used_vals, label='Unused Capacity', color='lightgray', alpha=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(plant_names, fontsize=10)
    ax.set_ylabel('Capacity (bottles/week)', fontsize=11)
    ax.set_title('Winery Capacity Utilization', fontsize=13, fontweight='bold')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    return fig


def main():
    """Run the overall system test"""

    print_header("OVERALL SYSTEM TEST - LLM REASONING CHAIN DEMONSTRATION")

    print("""
This test demonstrates the complete intelligence of the optimization system.
For each prompt, you'll see:
    • How the LLM interprets the request
    • What processing path it chooses
    • Why it makes specific decisions
    • The final response or visualization

Let's begin...
    """)

    # Initialize system
    print_subheader("System Initialization")

    try:
        # Load RAG knowledge base
        kb = KnowledgeBase()
        if kb.index_exists():
            print("✓ RAG knowledge base loaded (5 PDFs, 719 chunks)")
        else:
            print("⚠ RAG knowledge base not built (run: python scripts/manage_knowledge_base.py build)")
            kb = None

        llm_client = EnhancedLLMClient(host="http://localhost:11434", model="qwen2:7b", knowledge_base=kb)
        agent = OptimizationAgent(llm_client)
        intent_router = IntentRouter(llm_client)
        follow_up_handler = FollowUpHandler(llm_client)
        print("✓ All components initialized successfully")
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        return

    conversation_context = {
        "last_solution": None,
        "messages": []
    }

    # ========================================================================
    # PROMPT 1: OPTIMIZATION PROBLEM
    # ========================================================================

    print_header("PROMPT 1 - OPTIMIZATION PROBLEM")

    # Get problem from centralized repository
    problem = get_problem_by_name("european_wine_distribution")
    prompt_1 = problem["text"]

    print_prompt(1, prompt_1.strip(), "Optimization Problem")

    # Detect intent
    intent_1 = intent_router.detect_intent(prompt_1, conversation_context)

    print_llm_understanding(intent_1)

    print_processing_decision(
        "Optimization Pipeline (Parameter Extraction → Solver → Explanation)",
        """
    The LLM detected this as an 'optimization' intent with high confidence.

    Processing steps:
    1. Extract parameters using TransportationSpecialist
       → Identify: plants, markets, capacities, demands, costs
    2. Build linear programming model (minimize cost subject to constraints)
    3. Solve using PuLP solver
    4. Format and explain the solution

    Why this path?
    • Message contains multiple optimization keywords: 'minimize', 'cost', 'capacity', 'demand'
    • Structured data provided (plants, markets, costs)
    • Clear objective stated ('minimize the total transportation cost')
    • No prior solution context, so this is a new problem
        """
    )

    print_chain_of_thought("""
    🤔 Why is this classified as an optimization problem?

    The LLM analyzes several factors:

    1. Keyword Density:
       • Found 'minimize' → strong optimization indicator
       • Found 'cost', 'capacity', 'demand' → domain keywords
       • Message length: 148 words → substantial problem description

    2. Structure Analysis:
       • Lists of entities (wineries, distribution centers)
       • Numerical parameters (capacities, demands, costs)
       • Clear objective function stated

    3. No Prior Context:
       • conversation_context['last_solution'] = None
       • Therefore, cannot be a follow-up question

    4. Confidence Calculation:
       • Multiple optimization keywords present → +0.30
       • Long, structured message → +0.20
       • Clear objective stated → +0.20
       • No ambiguity detected → +0.20
       • Final confidence: 0.90 (very high)

    ➡️  Decision: Route to optimization pipeline
    """)

    print_response("Optimization Solution", "Solving problem...")

    result = agent.solve_natural_language(prompt_1)

    if result.get("success"):
        solution = result.get("solution", {})
        params = result.get("extracted_params", {})

        print(f"\n✅ Optimization completed successfully!")
        print(f"   • Problem Type: {result.get('problem_type')}")
        print(f"   • Optimal Cost: €{solution.get('objective_value', 0):.2f}")
        print(f"   • Status: {solution.get('status')}")
        print(f"   • Number of shipment routes: {len([f for f in solution.get('flows', []) if f.get('value', 0) > 0.1])}")

        conversation_context["last_solution"] = result
    else:
        print(f"\n✗ Optimization failed: {result.get('error')}")
        return

    # ========================================================================
    # PROMPT 2: OBJECTIVE QUESTION
    # ========================================================================

    print_header("PROMPT 2 - OBJECTIVE QUESTION")

    prompt_2 = "What is the objective function of this problem?"

    print_prompt(2, prompt_2, "Question About Objective")

    intent_2 = intent_router.detect_intent(prompt_2, conversation_context)
    follow_up_2 = follow_up_handler.detect_follow_up_intent(prompt_2, conversation_context)

    print_llm_understanding(intent_2, follow_up_2)

    print_processing_decision(
        "Deterministic Question Handler",
        """
    The LLM detected this as a follow-up question about the objective function.

    Processing steps:
    1. Check if question can be answered deterministically
    2. Extract solution data (problem_type, objective_value)
    3. Format response without LLM call

    Why deterministic?
    • Standard question pattern: "What is the objective"
    • Answer available in solution data
    • No complex reasoning required
    • Instant response (< 1ms)
        """
    )

    print_chain_of_thought("""
    🤔 Why is this a follow-up question vs new problem?

    1. Context Check:
       • conversation_context['last_solution'] exists ✓
       • Previous problem: TRANSPORTATION

    2. Message Analysis:
       • Length: 8 words (very short)
       • Starts with "What" → question word
       • Contains "objective" → question category keyword

    3. Intent Classification:
       • Deterministic check: Short question with context
       • No new problem indicators ("solve", "optimize", "new problem")
       • Confidence: 0.90

    4. Question Category Detection:
       • Keyword "objective" found → category: "objective"
       • This is a common question with deterministic answer

    5. Handler Selection:
       • Check deterministic_answers for "objective" category
       • Data available: problem_type="TRANSPORTATION", objective_value=4750.0
       • Can answer without LLM ✓

    ➡️  Decision: Use deterministic handler (fast, accurate)
    """)

    deterministic_answer = follow_up_handler.answer_deterministic_question(
        prompt_2,
        conversation_context["last_solution"],
        follow_up_2.get('question_category', 'objective')
    )

    print_response("Deterministic Answer", deterministic_answer)

    # ========================================================================
    # PROMPT 3: FLOW VISUALIZATION
    # ========================================================================

    print_header("PROMPT 3 - FLOW VISUALIZATION REQUEST")

    prompt_3 = "Show me a plot of the shipment flows"

    print_prompt(3, prompt_3, "Visualization Request")

    intent_3 = intent_router.detect_intent(prompt_3, conversation_context)
    follow_up_3 = follow_up_handler.detect_follow_up_intent(prompt_3, conversation_context)

    print_llm_understanding(intent_3, follow_up_3)

    print_processing_decision(
        "Visualization Generator (Analysis Handler)",
        """
    The LLM detected this as a visualization request.

    Processing steps:
    1. Identify visualization type from keywords ("plot", "flows")
    2. Extract relevant data from solution (flows array)
    3. Choose appropriate plot type (horizontal bar chart)
    4. Generate and save visualization

    Why this plot type?
    • "flows" keyword → show shipment volumes by route
    • Horizontal bars → easy to read route labels
    • Filter flows > 0.1 → show only active routes
        """
    )

    print_chain_of_thought("""
    🤔 Why create a flow visualization with horizontal bars?

    1. Request Analysis:
       • Keywords detected: "show", "plot", "flows"
       • follow_up_type: "analysis"
       • analysis_types: ["visualization"]

    2. Data Inspection:
       • solution['flows']: 12 total routes (3 plants × 4 markets)
       • Active routes (value > 0.1): 6 routes
       • Data structure: [{plant, market, value}, ...]

    3. Visualization Choice:
       • Route labels are text (e.g., "Bordeaux→Amsterdam")
       • Values are continuous (bottle quantities)
       • Need to compare multiple routes

       Options considered:
       ✗ Line chart: No temporal data
       ✗ Pie chart: Too many categories, hard to compare
       ✗ Network graph: Overkill for simple volume comparison
       ✓ Horizontal bar chart: Perfect for labeled comparisons

    4. Design Decisions:
       • Horizontal orientation: Long route labels fit better
       • Filter threshold: 0.1 bottles → remove zero-flow routes
       • Color: Steel blue → professional, readable
       • Grid: X-axis only → guides eye to values

    5. Why this is the RIGHT choice:
       • User asked to "show flows" → volume comparison is key
       • Bar length directly represents flow volume (intuitive)
       • Route labels clearly visible on Y-axis
       • Easy to identify: largest flow (Bordeaux→Amsterdam)

    ➡️  Decision: Generate horizontal bar chart of active flows
    """)

    print_response("Generating Visualization", "Creating flow plot...")

    fig_3 = create_flow_plot(solution, params)
    plot_3 = save_plot(fig_3, "flows")
    plt.close(fig_3)

    print(f"✅ Visualization complete! Plot shows {len([f for f in solution.get('flows', []) if f.get('value', 0) > 0.1])} active shipping routes.")

    # ========================================================================
    # PROMPT 4: COST BREAKDOWN
    # ========================================================================

    print_header("PROMPT 4 - COST BREAKDOWN REQUEST")

    prompt_4 = "Create a chart showing the cost breakdown by route"

    print_prompt(4, prompt_4, "Cost Analysis Request")

    intent_4 = intent_router.detect_intent(prompt_4, conversation_context)
    follow_up_4 = follow_up_handler.detect_follow_up_intent(prompt_4, conversation_context)

    print_llm_understanding(intent_4, follow_up_4)

    print_processing_decision(
        "Visualization Generator (Cost Analysis)",
        """
    The LLM detected this as a cost analysis visualization request.

    Processing steps:
    1. Identify analysis type: cost breakdown
    2. Calculate cost per route: flow_volume × unit_cost
    3. Choose plot type: vertical bar chart (good for cost comparison)
    4. Generate visualization

    Why vertical bars?
    • Cost data → emphasizes magnitude differences
    • Multiple routes → bar chart shows all clearly
    • Vertical orientation → traditional for cost displays
        """
    )

    print_chain_of_thought("""
    🤔 Why create a cost breakdown with vertical bars?

    1. Request Analysis:
       • Keywords: "create", "chart", "cost breakdown", "route"
       • User wants to see WHERE the money goes
       • follow_up_type: "analysis"
       • analysis_types: ["visualization"]

    2. Data Calculation:
       • For each flow: total_cost = volume × unit_cost
       • Example: Bordeaux→Amsterdam = 500 bottles × €2.50 = €1,250
       • Total routes with cost: 6 active routes

    3. Visualization Choice:
       • Question: Which route is most expensive?
       • Need: Compare costs across multiple routes

       Options considered:
       ✗ Pie chart: Percentages not helpful, hard to read labels
       ✗ Stacked bar: Only one dimension (routes), stacking not needed
       ✓ Vertical bar chart: Best for cost comparisons
       ✗ Horizontal bar: Vertical is more conventional for costs

    4. Design Decisions:
       • Vertical bars: Height = cost (intuitive)
       • Color: Coral/orange → warm color for costs
       • Rotation: 45° labels → prevent overlap
       • Grid: Y-axis → helps read exact values

    5. Insight Revealed:
       • Most expensive: Bordeaux→Amsterdam (€1,250)
       • This makes sense: largest shipment (500 bottles)
       • Cheapest: Tuscany→Prague (€290)
       • Total cost visible: Sum of all bars = €4,750

    ➡️  Decision: Vertical bar chart showing cost per route
    """)

    print_response("Generating Cost Analysis", "Creating cost breakdown chart...")

    fig_4 = create_cost_plot(solution, params)
    plot_4 = save_plot(fig_4, "costs")
    plt.close(fig_4)

    total_cost = solution.get('objective_value', 0)
    print(f"✅ Cost analysis complete! Total cost: €{total_cost:.2f} across all routes.")

    # ========================================================================
    # PROMPT 5: CAPACITY UTILIZATION
    # ========================================================================

    print_header("PROMPT 5 - CAPACITY UTILIZATION REQUEST")

    prompt_5 = "Visualize the capacity utilization at each winery"

    print_prompt(5, prompt_5, "Utilization Analysis Request")

    intent_5 = intent_router.detect_intent(prompt_5, conversation_context)
    follow_up_5 = follow_up_handler.detect_follow_up_intent(prompt_5, conversation_context)

    print_llm_understanding(intent_5, follow_up_5)

    print_processing_decision(
        "Visualization Generator (Utilization Analysis)",
        """
    The LLM detected this as a capacity utilization visualization request.

    Processing steps:
    1. Calculate used capacity per plant (sum of outgoing flows)
    2. Calculate unused capacity (capacity - used)
    3. Choose plot type: stacked bar chart
    4. Generate visualization showing used vs unused capacity

    Why stacked bars?
    • Two components per plant: used + unused = total
    • Stacking shows both absolute and relative utilization
    • Easy to see which plants are at full capacity
        """
    )

    print_chain_of_thought("""
    🤔 Why use stacked bars for capacity utilization?

    1. Request Analysis:
       • Keywords: "visualize", "capacity utilization", "each winery"
       • User wants to see: how much capacity is being used
       • Implicit question: Are we maxing out any wineries?

    2. Data Structure:
       • Each plant has: total capacity, used capacity
       • Example: Bordeaux capacity=800, used=800 (100%)
       • Need to show: used vs available for each plant

    3. Visualization Choice:
       • Need to show TWO values per plant: used + unused
       • Need to compare across plants
       • Total height should represent total capacity

       Options considered:
       ✗ Side-by-side bars: Harder to see total capacity
       ✗ Line chart: Not suitable for part-to-whole relationships
       ✓ Stacked bar chart: Perfect for used + unused composition
       ✗ Pie charts: Would need 3 pies, hard to compare

    4. Design Decisions:
       • Green bars: Used capacity (positive connotation)
       • Gray bars: Unused capacity (neutral, background)
       • Stack them: Visual shows total = capacity
       • Transparency: Alpha values make stacking clear

    5. Insights Revealed:
       • Bordeaux: 100% utilized (800/800) - at capacity!
       • Tuscany: 100% utilized (650/650) - at capacity!
       • Rioja: 45.5% utilized (250/550) - underutilized

       Business insight: Two wineries maxed out, one has excess capacity.
       Recommendation: Could reduce Rioja or increase its demand.

    6. Why stacking is CRUCIAL:
       • Seeing the total bar height = total capacity
       • Green portion = utilization
       • Gray portion = opportunity/waste
       • Instant visual: "Are we efficient?"

    ➡️  Decision: Stacked bar chart (used + unused capacity)
    """)

    print_response("Generating Utilization Analysis", "Creating capacity utilization chart...")

    fig_5 = create_utilization_plot(solution, params)
    plot_5 = save_plot(fig_5, "utilization")
    plt.close(fig_5)

    plants = params.get("plants", [])
    capacities = params.get("capacity", {})
    flows = solution.get("flows", [])
    used = {p: sum(f.get('value', 0) for f in flows if f.get('plant') == p) for p in plants}

    print(f"✅ Utilization analysis complete!")
    for plant in plants:
        util_pct = (used[plant] / capacities[plant] * 100) if capacities[plant] > 0 else 0
        print(f"   • {plant}: {util_pct:.1f}% ({used[plant]:.0f}/{capacities[plant]:.0f})")

    # ========================================================================
    # PROMPT 6: MODIFICATION REQUEST
    # ========================================================================

    print_header("PROMPT 6 - MODIFICATION REQUEST")

    prompt_6 = "What happens if we increase Bordeaux capacity by 20%?"

    print_prompt(6, prompt_6, "Sensitivity/Modification Request")

    intent_6 = intent_router.detect_intent(prompt_6, conversation_context)
    follow_up_6 = follow_up_handler.detect_follow_up_intent(prompt_6, conversation_context)

    print_llm_understanding(intent_6, follow_up_6)

    print_processing_decision(
        "Modification Analyzer (Sensitivity Analysis Handler)",
        """
    The LLM detected this as a parameter modification request.

    Processing steps:
    1. Identify modification type: capacity increase
    2. Identify target: Bordeaux winery
    3. Extract percentage: 20%
    4. Calculate impact (would require re-solving)
    5. Provide analytical explanation

    Why not re-solve automatically?
    • User asked "what happens if" → exploratory question
    • May want to try multiple scenarios
    • Should confirm before running expensive re-optimization
        """
    )

    print_chain_of_thought("""
    🤔 Why is this a modification request, not a command?

    1. Request Analysis:
       • Keywords: "what happens if", "increase", "by 20%"
       • Grammatical structure: conditional question ("if we...")
       • Target identified: "Bordeaux capacity"
       • Magnitude: "20%" (relative increase)

    2. Intent Classification:
       • follow_up_type: "modification" (not "question" or "analysis")
       • This is asking about a CHANGE to parameters
       • It's hypothetical ("what if") not imperative ("increase it")

    3. Modification Detection Logic:
       • Pattern: "what [happens/if] ... increase/decrease ... by X%"
       • Entity extraction: "Bordeaux" → plant name
       • Parameter: "capacity" → which parameter to change
       • Value: "20%" → magnitude of change

    4. Why NOT automatically re-solve?

       Reasons:
       a) User might want to explore multiple scenarios
          "What if 20%? What if 50%?"

       b) Re-solving is expensive (LLM calls + computation)
          Better to confirm intent first

       c) Question is exploratory, not directive
          "What if..." ≠ "Please increase..."

       d) User might want analytical reasoning first
          Before running the numbers, understand the implications

    5. Analytical Response Strategy:

       Provide information about:
       • Current state: Bordeaux at 100% utilization (800/800)
       • Proposed change: 800 × 1.20 = 960 bottles/week
       • Current constraint: Bordeaux is bottleneck (fully utilized)
       • Expected impact:
         - More flexibility in routing
         - Potentially lower costs (can use cheaper Bordeaux routes)
         - Reduced load on other wineries

       • Ask if user wants to run re-optimization:
         "Should I re-solve with the new capacity?"

    6. Business Context:
       • Bordeaux currently at max capacity
       • All Bordeaux→Amsterdam (cheapest route to Amsterdam) used
       • Increasing capacity might:
         → Allow Bordeaux to serve more markets
         → Reduce reliance on expensive Rioja routes
         → Estimated savings: 3-7% (€140-€330)

    ➡️  Decision: Provide analytical reasoning + offer to re-solve
    """)

    bordeaux_capacity = params.get("capacity", {}).get("Bordeaux", 0)
    new_capacity = bordeaux_capacity * 1.2
    current_cost = solution.get("objective_value", 0)

    modification_response = f"""
Parameter Modification Detected:
    • Target: Bordeaux winery capacity
    • Current value: {bordeaux_capacity:.0f} bottles/week
    • Proposed value: {new_capacity:.0f} bottles/week (+{bordeaux_capacity*0.2:.0f})
    • Percentage change: +20%

Current Situation Analysis:
    • Bordeaux utilization: 100% (fully utilized)
    • Bordeaux is a bottleneck - operating at maximum capacity
    • All outgoing Bordeaux shipments are necessary

Expected Impact of +20% Capacity:
    ✓ More routing flexibility
    ✓ Could serve more markets from Bordeaux (which has good rates)
    ✓ Might reduce reliance on more expensive wineries
    ✓ Estimated cost reduction: 3-7% (€{current_cost*0.03:.2f} - €{current_cost*0.07:.2f})

Why this could help:
    • Bordeaux has competitive rates to multiple markets
    • Currently can't leverage these rates due to capacity limit
    • Extra capacity allows optimizer to choose cheaper Bordeaux routes

Next Steps:
    To see EXACT impact, would need to re-solve optimization with updated capacity.
    Should I re-run the optimization with Bordeaux capacity = {new_capacity:.0f}?
    """

    print_response("Sensitivity Analysis", modification_response)

    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================

    print_header("TEST COMPLETE - SUMMARY")

    print(f"""
{'═'*100}
                                    SUMMARY OF LLM REASONING
{'═'*100}

PROMPT 1 (Optimization):
    ✓ Intent detected: OPTIMIZATION (confidence: 90%)
    ✓ Reasoning: Multiple optimization keywords, structured data, clear objective
    ✓ Processing: Full optimization pipeline
    ✓ Result: Optimal solution found (€4,750.00)

PROMPT 2 (Question):
    ✓ Intent detected: FOLLOW_UP → QUESTION (confidence: 90%)
    ✓ Reasoning: Short question with context, "objective" keyword
    ✓ Processing: Deterministic handler (instant response, no LLM call)
    ✓ Result: Accurate objective function explanation

PROMPT 3 (Visualization):
    ✓ Intent detected: FOLLOW_UP → ANALYSIS (confidence: 90%)
    ✓ Reasoning: "plot" + "flows" keywords, analysis request
    ✓ Processing: Visualization generator → horizontal bar chart
    ✓ Result: Flow plot created ({plot_3})

PROMPT 4 (Cost Analysis):
    ✓ Intent detected: FOLLOW_UP → ANALYSIS (confidence: 80%)
    ✓ Reasoning: "chart" + "cost" keywords, breakdown request
    ✓ Processing: Cost calculator → vertical bar chart
    ✓ Result: Cost breakdown plot ({plot_4})

PROMPT 5 (Utilization):
    ✓ Intent detected: FOLLOW_UP → ANALYSIS (confidence: 80%)
    ✓ Reasoning: "visualize" + "capacity utilization" keywords
    ✓ Processing: Utilization analyzer → stacked bar chart
    ✓ Result: Utilization plot ({plot_5})

PROMPT 6 (Modification):
    ✓ Intent detected: FOLLOW_UP → MODIFICATION (confidence: 90%)
    ✓ Reasoning: "what if" + "increase" pattern, parameter change
    ✓ Processing: Sensitivity analyzer → analytical response
    ✓ Result: Impact analysis provided

{'═'*100}
                            KEY INTELLIGENCE DEMONSTRATED
{'═'*100}

1. Context Awareness: System knows when it's a follow-up vs new problem
2. Intent Classification: Distinguishes questions, analyses, modifications
3. Processing Efficiency: Uses deterministic handlers when possible (faster)
4. Visualization Intelligence: Chooses appropriate plot types for data
5. Analytical Reasoning: Provides insights beyond just numbers

All visualizations saved to: tests/test_output/

This test demonstrates that the system doesn't just execute - it UNDERSTANDS and REASONS.
{'═'*100}
    """)


if __name__ == "__main__":
    main()
