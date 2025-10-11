#!/usr/bin/env python3
"""Full pipeline test: Classification -> Parameters -> Solution (for transportation)"""

import sys
import json
import time
from llm.enhanced_client import EnhancedLLMClient
from transportation_test_cases import get_cases
from agent.core import OptimizationAgent

def print_stats(stage, **kwargs):
    """Print statistics in a consistent format"""
    print(f"📊 {stage} Stats:")
    for key, value in kwargs.items():
        if isinstance(value, float):
            print(f"   {key}: {value:.2f}")
        elif isinstance(value, (list, dict)):
            print(f"   {key}: {len(value)} items")
        else:
            print(f"   {key}: {value}")

def test_full_pipeline():
    """Test full pipeline: classify -> extract params -> solve"""

    client = EnhancedLLMClient()
    agent = OptimizationAgent(client)

    # Mix of problem types for testing
    test_cases = [
        {
            "name": "Assignment Problem",
            "text": """I have 4 workers and 4 tasks. Each worker has different costs for each task.
            Worker A costs 9, 2, 7, 8 for tasks 1, 2, 3, 4 respectively.
            Each worker can only be assigned to one task, and each task needs exactly one worker.""",
            "expected": "ASSIGNMENT"
        },
        {
            "name": "Knapsack Problem",
            "text": """I have a knapsack with capacity 50kg. I have items with different weights and values:
            Item 1: weight 10kg, value $60. Item 2: weight 20kg, value $100.
            Item 3: weight 30kg, value $120. Which items should I select to maximize value?""",
            "expected": "KNAPSACK"
        }
    ]

    # Add first 5 transportation cases
    transport_cases = get_cases()[:5]
    for case in transport_cases:
        test_cases.append({
            "name": f"Transport: {case['name']}",
            "text": case['text'],
            "expected": "TRANSPORTATION"
        })

    print("🚀 Full Pipeline Test (Classification -> Parameters -> Solution)")
    print("=" * 80)
    print(f"Testing {len(test_cases)} cases...")

    for i, case in enumerate(test_cases, 1):
        print(f"\n{'='*20} CASE {i}: {case['name']} {'='*20}")
        print(f"📝 Input: {case['text'][:100]}...")

        # STEP 1: Classification
        print(f"\n🔍 STEP 1: Classifying...")
        start_time = time.time()

        try:
            classification = client.classify_problem(case['text'])
            classify_time = time.time() - start_time

            is_correct = classification['type'].upper() == case['expected']
            status = "✅" if is_correct else "❌"

            print(f"{status} Classification: {classification['type']} (expected: {case['expected']})")
            print_stats("Classification",
                       confidence=classification['confidence'],
                       time_sec=classify_time,
                       signals=classification.get('signals', {}))

            # STEP 2: Parameter Extraction (if transportation)
            if classification['type'].upper() == 'TRANSPORTATION':
                print(f"\n⚙️  STEP 2: Extracting parameters...")
                start_time = time.time()

                params = client.extract_parameters(case['text'], 'TRANSPORTATION', {})
                extract_time = time.time() - start_time

                if 'error' in params:
                    print(f"❌ Parameter Error: {params['error']}")
                    print_stats("Extraction", time_sec=extract_time, status="failed")
                else:
                    total_supply = sum(params.get('capacity', {}).values())
                    total_demand = sum(params.get('demand', {}).values())

                    print(f"✅ Parameters extracted successfully")
                    print_stats("Extraction",
                               plants=params.get('plants', []),
                               markets=params.get('markets', []),
                               total_supply=total_supply,
                               total_demand=total_demand,
                               time_sec=extract_time)

                    # STEP 3: Solve
                    print(f"\n🎯 STEP 3: Solving...")
                    start_time = time.time()

                    try:
                        result = agent.solve_natural_language(case['text'])
                        solve_time = time.time() - start_time

                        if result.get('success'):
                            solution = result.get('solution', {})
                            objective = solution.get('objective_thousand_usd', 0)
                            shipments = solution.get('shipments', {})

                            # Count active routes
                            active_routes = sum(1 for plant_routes in shipments.values()
                                              for qty in plant_routes.values() if qty > 0)

                            print(f"✅ Solution found!")
                            print_stats("Solution",
                                       objective_k_usd=objective,
                                       active_routes=active_routes,
                                       total_variables=len(params['plants']) * len(params['markets']),
                                       time_sec=solve_time)
                        else:
                            print(f"❌ Solver failed: {result.get('error', 'Unknown')}")
                            print_stats("Solution", status="failed", time_sec=solve_time)

                    except Exception as e:
                        solve_time = time.time() - start_time
                        print(f"❌ Solving error: {e}")
                        print_stats("Solution", status="error", time_sec=solve_time)
            else:
                print(f"⚠️  Non-transportation problem - skipping parameters and solving")

        except Exception as e:
            classify_time = time.time() - start_time
            print(f"❌ Classification error: {e}")
            print_stats("Classification", status="error", time_sec=classify_time)

        print(f"\n{'='*60}")

        # Pause between cases for readability
        if i < len(test_cases):
            input("Press Enter to continue to next case...")

    print(f"\n🎯 Pipeline test complete!")

if __name__ == "__main__":
    test_full_pipeline()