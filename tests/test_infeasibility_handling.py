#!/usr/bin/env python3
"""
Test script for infeasibility handling with follow-up questions.

Tests the complete infeasibility resolution loop:
1. Submit infeasible problem
2. Receive infeasibility report with suggestions
3. Provide modifications
4. Re-check feasibility
5. Solve if feasible, or loop back

Tests all 3 layers of infeasibility detection + one feasible problem.
"""

import sys
from llm.enhanced_client import EnhancedLLMClient
from agent.core import OptimizationAgent


def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def print_result(result):
    """Print result in a nice format"""
    if result.get("success"):
        print("✅ SUCCESS!")
        print(f"Problem Type: {result.get('problem_type')}")
        print(f"Summary: {result.get('summary', 'N/A')}")
        if result.get('diff'):
            print("\nModifications Applied:")
            for change in result['diff']:
                print(f"  - {change}")
    else:
        status = result.get("status", "error")
        if status in ["infeasible", "still_infeasible"]:
            print(f"❌ INFEASIBLE (Layer {result.get('layer_failed')} failed)")
            print(f"Retry: {result.get('retry_count')}/{result.get('max_retries')}")
            print("\nReasons:")
            for reason in result.get('reasons', []):
                print(f"  - {reason}")
            print("\nSuggested Fixes:")
            for suggestion in result.get('suggestions', [])[:3]:  # Show first 3
                print(f"  → {suggestion}")
        else:
            print(f"❌ ERROR: {result.get('error', 'Unknown error')}")


def test_layer_0_infeasibility():
    """Test Layer 0 (structural) infeasibility detection"""
    print_section("TEST 1: Layer 0 - Structural Infeasibility (Negative Capacity)")

    # From or_problem_repository.py: transport/infeasible_struct/001
    problem_text = """A company ships goods from 2 factories (F1, F2) to 3 regional warehouses (W1, W2, W3).

Weekly capacities:
- F1 can ship up to 80 tons
- F2 can ship up to -60 tons

Weekly demands:
- W1 needs 40 tons
- W2 needs 50 tons
- W3 needs 30 tons

Transportation costs (£/ton):
From F1 to W1: 10, W2: 12, W3: 15
From F2 to W1: 11, W2: 13, W3: 14

Find a minimum-cost shipping plan."""

    print("Submitting infeasible problem (negative capacity)...")
    llm = EnhancedLLMClient()
    agent = OptimizationAgent(llm)

    result1 = agent.solve_natural_language(problem_text)
    print_result(result1)

    if result1.get("status") == "infeasible":
        print("\n" + "-" * 80)
        print("Applying Fix: Set F2 capacity to 60 (positive)")
        print("-" * 80)

        fix_message = "set capacity of F2 to 60"
        result2 = agent.solve_natural_language(fix_message)
        print_result(result2)

        return result2.get("success", False)
    else:
        print("WARNING: Expected infeasibility but got different result")
        return False


def test_layer_1_infeasibility():
    """Test Layer 1 (necessary conditions) infeasibility detection"""
    print_section("TEST 2: Layer 1 - Supply/Demand Imbalance")

    # From or_problem_repository.py: transport/infeasible_aggregate/001
    problem_text = """A fertilizer producer ships product from 2 plants to 3 agricultural distribution centres.

Weekly plant capacities:
- Plant North: 40 tonnes
- Plant South: 30 tonnes

Weekly distribution centre demands:
- Centre A: 35 tonnes
- Centre B: 25 tonnes
- Centre C: 20 tonnes

Transport costs (€/tonne):
Plant North → Centre A: 10, Centre B: 8, Centre C: 12
Plant South → Centre A: 9, Centre B: 11, Centre C: 7

Determine the shipping quantities to minimise total transport cost."""

    print("Submitting infeasible problem (supply=70 < demand=80)...")
    llm = EnhancedLLMClient()
    agent = OptimizationAgent(llm)

    result1 = agent.solve_natural_language(problem_text)
    print_result(result1)

    if result1.get("status") == "infeasible":
        print("\n" + "-" * 80)
        print("Applying Fix: Increase Plant North capacity by 10 (70+10=80)")
        print("-" * 80)

        fix_message = "increase capacity of Plant North by 10"
        result2 = agent.solve_natural_language(fix_message)
        print_result(result2)

        return result2.get("success", False)
    else:
        print("WARNING: Expected infeasibility but got different result")
        return False


def test_layer_2_infeasibility():
    """Test Layer 2 (solver-based) infeasibility detection with 2 fix attempts"""
    print_section("TEST 3: Layer 2 - Arc Capacity Pattern Infeasibility")

    # From or_problem_repository.py: transport/infeasible_network/001
    problem_text = """Three factories (F1, F2, F3) deliver components to three assembly plants (A, B, C).

Weekly factory supplies:
- F1: up to 60 units
- F2: up to 60 units
- F3: up to 30 units

Weekly assembly plant demands:
- Plant A: 50 units
- Plant B: 50 units
- Plant C: 50 units

Maximum shipping capacities per week (units):
- From F1 to A: 50, to B: 50, to C: 0
- From F2 to A: 0, to B: 10, to C: 60
- From F3 to A: 10, to B: 10, to C: 10

Transport costs ($/unit): all routes cost $1.

Find a shipping plan that meets all demands."""

    print("Submitting infeasible problem (arc capacity constraints)...")
    llm = EnhancedLLMClient()
    agent = OptimizationAgent(llm)

    result1 = agent.solve_natural_language(problem_text)
    print_result(result1)

    if result1.get("status") == "infeasible":
        # First fix attempt - insufficient
        print("\n" + "-" * 80)
        print("Applying Fix #1: Increase F3→B from 10 to 20 (insufficient)")
        print("-" * 80)

        fix_message = "increase arc capacity from F3 to B from 10 to 20"
        result2 = agent.solve_natural_language(fix_message)
        print_result(result2)

        if result2.get("status") == "still_infeasible":
            # Second fix attempt - should work
            print("\n" + "-" * 80)
            print("Applying Fix #2: Increase F2→B from 10 to 50 (should resolve)")
            print("-" * 80)

            fix_message2 = "increase arc capacity from F2 to B to 50"
            result3 = agent.solve_natural_language(fix_message2)
            print_result(result3)

            return result3.get("success", False)
        else:
            print("WARNING: Expected first fix to still be infeasible")
            return False
    else:
        print("WARNING: Expected infeasibility but got different result")
        return False


def test_feasible_problem():
    """Test a feasible problem to ensure it goes through normally"""
    print_section("TEST 4: Feasible Problem (Should Solve Directly)")

    # A simple feasible transportation problem
    problem_text = """A company needs to ship products from 2 warehouses to 3 stores.

Weekly warehouse capacities:
- Warehouse Seattle: 350 units
- Warehouse San Diego: 600 units

Weekly store demands:
- Store New York: 325 units
- Store Chicago: 300 units
- Store Topeka: 275 units

Shipping costs ($/unit):
Seattle → New York: 2.5, Chicago: 1.7, Topeka: 1.8
San Diego → New York: 2.5, Chicago: 1.8, Topeka: 1.4

Find the minimum cost shipping plan."""

    print("Submitting feasible problem...")
    llm = EnhancedLLMClient()
    agent = OptimizationAgent(llm)

    result = agent.solve_natural_language(problem_text)
    print_result(result)

    return result.get("success", False)


def main():
    """Run all infeasibility tests"""
    print_section("Infeasibility Handling Test Suite")
    print("Testing 3-layer feasibility checking with follow-up question handling")

    results = {}

    # Test Layer 0
    print("\n")
    try:
        results['layer_0'] = test_layer_0_infeasibility()
    except Exception as e:
        print(f"\n❌ Layer 0 test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results['layer_0'] = False

    # Test Layer 1
    print("\n")
    try:
        results['layer_1'] = test_layer_1_infeasibility()
    except Exception as e:
        print(f"\n❌ Layer 1 test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results['layer_1'] = False

    # Test Layer 2
    print("\n")
    try:
        results['layer_2'] = test_layer_2_infeasibility()
    except Exception as e:
        print(f"\n❌ Layer 2 test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results['layer_2'] = False

    # Test Feasible Problem
    print("\n")
    try:
        results['feasible'] = test_feasible_problem()
    except Exception as e:
        print(f"\n❌ Feasible test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results['feasible'] = False

    # Summary
    print_section("TEST SUMMARY")
    print(f"Layer 0 (Structural):         {'✅ PASS' if results.get('layer_0') else '❌ FAIL'}")
    print(f"Layer 1 (Necessary Conds):    {'✅ PASS' if results.get('layer_1') else '❌ FAIL'}")
    print(f"Layer 2 (Solver-based):       {'✅ PASS' if results.get('layer_2') else '❌ FAIL'}")
    print(f"Feasible Problem:             {'✅ PASS' if results.get('feasible') else '❌ FAIL'}")

    total = sum(1 for v in results.values() if v)
    print(f"\nPassed: {total}/4")

    return total == 4


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
