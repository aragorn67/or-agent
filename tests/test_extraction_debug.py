"""
Debug script to test parameter extraction for specific problems.

Usage:
    python tests/test_extraction_debug.py <problem_name>

Example:
    python tests/test_extraction_debug.py infeasible_transport_capacity_pattern
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.or_problem_repository import get_problem_by_name
from llm.enhanced_client import EnhancedLLMClient
from agent.core import OptimizationAgent
from config import Config
import json


def test_extraction(problem_name):
    """Test parameter extraction for a specific problem."""

    # Get problem from repository
    problem = get_problem_by_name(problem_name)
    if not problem:
        print(f"❌ Problem '{problem_name}' not found in repository")
        return

    print("=" * 80)
    print(f"TESTING EXTRACTION FOR: {problem_name}")
    print("=" * 80)

    print("\n📄 Problem Text:")
    print("-" * 80)
    print(problem['text'])
    print("-" * 80)

    # Setup agent
    llm_client = EnhancedLLMClient(
        host=Config.OLLAMA_HOST,
        model=Config.OLLAMA_MODEL
    )
    agent = OptimizationAgent(llm_client)

    print("\n🔄 Calling LLM to extract parameters...")

    # Call just the extraction part, not the full solve
    from llm.transportation_specialist import TransportationSpecialist
    from llm.ollama_client import OllamaClient

    ollama = OllamaClient(host=Config.OLLAMA_HOST, model=Config.OLLAMA_MODEL)
    specialist = TransportationSpecialist(ollama)
    extracted_params = specialist.extract_parameters(problem['text'])

    print("\n📊 EXTRACTION RESULTS:")
    print("=" * 80)

    # Print extracted parameters
    if extracted_params and 'error' not in extracted_params:
        print("\n✅ Extracted Parameters:")
        print(json.dumps(extracted_params, indent=2, default=str))

        # Check for arc_capacity specifically
        print("\n🔍 Arc Capacity Check:")
        if 'arc_capacity' in extracted_params:
            print("  ✅ arc_capacity FOUND")
            arc_cap = extracted_params['arc_capacity']
            total_entries = sum(len(v) if isinstance(v, dict) else 1 for v in arc_cap.values())
            print(f"  Total entries: {total_entries}")
            print(f"  Structure:")
            for plant, markets in list(arc_cap.items())[:3]:
                print(f"    {plant}: {markets}")
        else:
            print("  ❌ arc_capacity NOT FOUND")
            print("  Available keys:", list(extracted_params.keys()))

        # Check for constraints
        print("\n🔍 Constraints Check:")
        if 'constraints' in extracted_params:
            print(f"  ✅ constraints FOUND: {extracted_params['constraints']}")
        else:
            print("  ❌ constraints NOT FOUND")

    elif 'error' in extracted_params:
        print(f"❌ Extraction ERROR: {extracted_params['error']}")
    else:
        print("❌ No extraction result")

    # Summary
    print("\n📋 Extraction Summary:")
    print("-" * 80)
    print(f"  Problem: {problem.get('name', 'Unknown')}")
    print(f"  Expected solvable: {problem.get('solvable', 'Unknown')}")
    if extracted_params and 'arc_capacity' in extracted_params:
        print("  ✅ Arc capacity extracted - ready for Layer 2 feasibility check")
    else:
        print("  ❌ Arc capacity missing - Layer 2 cannot catch this infeasibility")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tests/test_extraction_debug.py <problem_name>")
        print("\nAvailable infeasible problems:")
        print("  - infeasible_transport_struct_mismatched_costs")
        print("  - infeasible_transport_supply_less_than_demand")
        print("  - infeasible_transport_capacity_pattern")
        sys.exit(1)

    problem_name = sys.argv[1]
    test_extraction(problem_name)
