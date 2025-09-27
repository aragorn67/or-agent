#!/usr/bin/env python3
"""
Test the Greek transportation problem to see what validation error occurs
"""

from config import config
from agent.core import OptimizationAgent

def test_greek_problem():
    """Test the Greek transportation problem"""

    # Your exact problem description
    description = """
A company operates two production sites in Greece: Athens and Thessaloniki.

Athens can make up to 120 units per week,
Thessaloniki can supply 200 pieces.

They deliver products to three customer areas: Patras, Larisa, and Heraklion.

Patras requires 100 units,
Larisa needs 80,
Heraklion has a demand of 110.

Transport costs (in € per unit) are:
From Athens to Patras: 5
From Athens to Larisa: 4
From Athens to Heraklion: 7
From Thessaloniki to Patras: 6
From Thessaloniki to Larisa: 3
From Thessaloniki to Heraklion: 8

The company wants to find the cheapest shipping plan that respects production limits and fulfils all customer needs.
"""

    print("🇬🇷 Testing Greek Transportation Problem")
    print("=" * 50)

    try:
        # Initialize agent
        llm_client = config.get_llm_client()
        agent = OptimizationAgent(llm_client)

        print("✅ Agent initialized successfully")

        # Test problem classification
        print("\n🔍 Step 1: Problem Classification")
        from solvers import list_problem_types
        classification = agent.llm.classify_problem(description, list_problem_types())
        print(f"Classification: {classification}")

        # Test parameter extraction
        print("\n📋 Step 2: Parameter Extraction")
        problem_type = classification.get('type', 'TRANSPORTATION')
        example_params = {}

        try:
            params = agent.llm.extract_parameters(description, problem_type, example_params)
            print(f"Extracted parameters: {params}")

            if "error" in params:
                print(f"❌ Parameter extraction failed: {params['error']}")
                return

        except Exception as e:
            print(f"❌ Parameter extraction exception: {e}")
            return

        # Test validation
        print("\n✅ Step 3: Parameter Validation")
        from solvers import get_solver
        solver = get_solver(problem_type)
        validation_errors = solver.validate_params(params)

        if validation_errors:
            print(f"❌ Validation errors found:")
            for error in validation_errors:
                print(f"  • {error}")
            return
        else:
            print("✅ Parameters passed validation")

        # Test solving
        print("\n🔧 Step 4: Solving")
        solution = solver.solve(params)
        print(f"Solution status: {solution.get('status', 'UNKNOWN')}")

        if solution.get('status') == 'OPTIMAL':
            print(f"Total cost: €{solution.get('objective_value', 'N/A')}")
            print(f"Flows: {len(solution.get('flows', []))} routes")
            print(f"Raw solution flows: {solution.get('flows', [])}")
            print(f"Raw objective: {solution.get('objective_value')}")
        else:
            print(f"❌ Solver failed: {solution}")

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_greek_problem()