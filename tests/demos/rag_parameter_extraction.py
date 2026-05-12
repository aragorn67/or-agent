#!/usr/bin/env python3
"""
TEST: RAG Impact on Parameter Extraction

PURPOSE: Compare parameter extraction accuracy with and without RAG
TESTS: Extract parameters from problems using specialists with/without RAG
METRIC: Completeness, correctness of extracted parameters

EXPECTED OUTPUT:
    ✓ Tests transportation and scheduling problems
    ✓ Shows parameter extraction quality with RAG
    ✓ Shows parameter extraction quality without RAG
    ✓ Compares: missing fields, incorrect values, validation errors

RUN: python tests/test_rag_parameter_extraction.py --solvable
REQUIRES: Ollama (localhost:11434), deepseek-r1:latest model
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tests.or_problem_repository import get_solvable_problems
from llm.enhanced_client import EnhancedLLMClient
from config import Config
from llm.knowledge_base import KnowledgeBase
from llm.transportation_specialist import TransportationSpecialist
from llm.scheduling_specialist import SchedulingSpecialist
from llm.ollama_client import OllamaClient
import argparse
import json


def validate_transportation_params(params, problem):
    """Check if transportation parameters are complete and correct."""
    issues = []
    
    # Check required fields
    required = ['sources', 'sinks', 'supply', 'demand', 'costs']
    for field in required:
        if field not in params:
            issues.append(f"Missing field: {field}")
    
    if 'sources' in params and 'supply' in params:
        if len(params['sources']) != len(params['supply']):
            issues.append(f"Mismatch: {len(params['sources'])} sources but {len(params['supply'])} supply values")
    
    if 'sinks' in params and 'demand' in params:
        if len(params['sinks']) != len(params['demand']):
            issues.append(f"Mismatch: {len(params['sinks'])} sinks but {len(params['demand'])} demand values")
    
    if 'costs' in params and 'sources' in params and 'sinks' in params:
        expected_costs = len(params['sources']) * len(params['sinks'])
        actual_costs = len(params['costs'])
        if actual_costs != expected_costs:
            issues.append(f"Cost matrix incomplete: expected {expected_costs}, got {actual_costs}")
    
    return issues


def validate_scheduling_params(params, problem):
    """Check if scheduling parameters are complete and correct."""
    issues = []
    
    # Check required fields
    required = ['orders', 'machines', 'processing_times']
    for field in required:
        if field not in params:
            issues.append(f"Missing field: {field}")
    
    if 'orders' in params and 'processing_times' in params:
        # Check if all orders have processing times
        for order in params['orders']:
            found = False
            for pt in params['processing_times']:
                if pt.get('order') == order or pt.get('job') == order:
                    found = True
                    break
            if not found:
                issues.append(f"No processing time for order: {order}")
    
    return issues


def get_expected_params(problem):
    """Extract expected parameters from problem definition."""
    problem_id = problem['id']
    text = problem['text']

    if problem['category'] == 'transportation':
        # Parse expected parameters from the text
        if 'wine_eu' in problem_id:
            return {
                'sources': ['Bordeaux', 'Tuscany', 'Rioja'],
                'sinks': ['Amsterdam', 'Berlin', 'Vienna', 'Prague'],
                'supply': {'Bordeaux': 800, 'Tuscany': 650, 'Rioja': 550},
                'demand': {'Amsterdam': 500, 'Berlin': 450, 'Vienna': 400, 'Prague': 350},
                'costs': {
                    'Bordeaux': {'Amsterdam': 2.50, 'Berlin': 3.20, 'Vienna': 4.10, 'Prague': 3.80},
                    'Tuscany': {'Amsterdam': 4.50, 'Berlin': 3.80, 'Vienna': 2.20, 'Prague': 2.90},
                    'Rioja': {'Amsterdam': 3.80, 'Berlin': 4.20, 'Vienna': 3.50, 'Prague': 3.20}
                }
            }
        elif 'us_mfg' in problem_id:
            return {
                'sources': ['Seattle', 'Denver', 'Detroit'],
                'sinks': ['Chicago', 'New York', 'Atlanta'],
                'supply': {'Seattle': 350, 'Denver': 200, 'Detroit': 150},
                'demand': {'Chicago': 250, 'New York': 180, 'Atlanta': 270},
                'costs': {
                    'Seattle': {'Chicago': 2, 'New York': 4, 'Atlanta': 5},
                    'Denver': {'Chicago': 3, 'New York': 6, 'Atlanta': 2},
                    'Detroit': {'Chicago': 5, 'New York': 3, 'Atlanta': 4}
                }
            }
    return None


def compare_params(extracted, expected, category):
    """Compare extracted vs expected parameters and return differences."""
    differences = []

    if category == 'transportation':
        # Map possible field name variations
        sources_key = 'plants' if 'plants' in extracted else 'sources'
        sinks_key = 'markets' if 'markets' in extracted else 'sinks'
        supply_key = 'capacity' if 'capacity' in extracted else 'supply'
        demand_key = 'demand'
        costs_key = 'cost' if 'cost' in extracted else 'costs'

        # Check sources/plants
        if sources_key in extracted:
            ext_sources = set(extracted[sources_key])
            exp_sources = set(expected['sources'])
            if ext_sources != exp_sources:
                differences.append(f"Sources mismatch: got {ext_sources}, expected {exp_sources}")
        else:
            differences.append("Missing sources/plants field")

        # Check sinks/markets
        if sinks_key in extracted:
            ext_sinks = set(extracted[sinks_key])
            exp_sinks = set(expected['sinks'])
            if ext_sinks != exp_sinks:
                differences.append(f"Sinks mismatch: got {ext_sinks}, expected {exp_sinks}")
        else:
            differences.append("Missing sinks/markets field")

        # Check supply/capacity
        if supply_key in extracted:
            for source in expected['sources']:
                if source in extracted[supply_key]:
                    if extracted[supply_key][source] != expected['supply'][source]:
                        differences.append(f"Supply mismatch for {source}: got {extracted[supply_key][source]}, expected {expected['supply'][source]}")
                else:
                    differences.append(f"Missing supply for {source}")
        else:
            differences.append("Missing supply/capacity field")

        # Check demand
        if demand_key in extracted:
            for sink in expected['sinks']:
                if sink in extracted[demand_key]:
                    if extracted[demand_key][sink] != expected['demand'][sink]:
                        differences.append(f"Demand mismatch for {sink}: got {extracted[demand_key][sink]}, expected {expected['demand'][sink]}")
                else:
                    differences.append(f"Missing demand for {sink}")
        else:
            differences.append("Missing demand field")

        # Check costs
        if costs_key in extracted:
            for source in expected['sources']:
                if source in extracted[costs_key]:
                    for sink in expected['sinks']:
                        if sink in extracted[costs_key][source]:
                            if extracted[costs_key][source][sink] != expected['costs'][source][sink]:
                                differences.append(f"Cost mismatch {source}→{sink}: got {extracted[costs_key][source][sink]}, expected {expected['costs'][source][sink]}")
                        else:
                            differences.append(f"Missing cost {source}→{sink}")
                else:
                    differences.append(f"Missing costs from {source}")
        else:
            differences.append("Missing cost/costs field")

    return differences


def test_parameter_extraction(problems, with_rag=False):
    """Test parameter extraction with or without RAG."""

    # Initialize clients
    host = "http://localhost:11434"
    model = Config.OLLAMA_MODEL

    kb = None
    if with_rag:
        try:
            print("Loading RAG knowledge base...")
            kb = KnowledgeBase()
            print("✓ RAG knowledge base loaded\n")
        except Exception as e:
            print(f"⚠️  Could not load knowledge base: {e}\n")
            return None

    base_client = OllamaClient(host, model)
    transport_specialist = TransportationSpecialist(base_client, kb)
    scheduling_specialist = SchedulingSpecialist(base_client, kb)

    results = {
        'total': 0,
        'complete': 0,  # All required fields present
        'partial': 0,   # Some fields missing
        'failed': 0,    # Extraction failed
        'details': []
    }

    rag_status = "WITH RAG" if with_rag else "WITHOUT RAG"
    print(f"\n{'='*80}")
    print(f"  TESTING PARAMETER EXTRACTION {rag_status}")
    print(f"{'='*80}\n")

    for problem in problems:
        results['total'] += 1
        problem_id = problem['id']
        problem_name = problem['name']
        category = problem['category']
        problem_text = problem['text']

        print(f"\n{'='*80}")
        print(f"Problem: {problem_id} ({problem_name})")
        print(f"Category: {category}")
        print(f"{'='*80}")

        # Get expected parameters
        expected = get_expected_params(problem)

        try:
            # Extract parameters using appropriate specialist
            if category == 'transportation':
                params = transport_specialist.extract_parameters(problem_text)
                issues = validate_transportation_params(params, problem)
            elif category == 'scheduling':
                params = scheduling_specialist.extract_parameters(problem_text)
                issues = validate_scheduling_params(params, problem)
            else:
                print(f"  ⚠️  Skipping: Category {category} not supported")
                continue

            # Check for errors in extraction
            if 'error' in params:
                print(f"\n  ✗ EXTRACTION FAILED: {params['error']}\n")
                results['failed'] += 1
                results['details'].append({
                    'id': problem_id,
                    'status': 'failed',
                    'error': params['error']
                })
                continue

            # Print extracted vs expected
            print("\n📋 EXTRACTED PARAMETERS:")
            print(json.dumps(params, indent=2))

            if expected:
                print("\n✓ EXPECTED PARAMETERS:")
                print(json.dumps(expected, indent=2))

                # Compare
                differences = compare_params(params, expected, category)
                if differences:
                    print(f"\n⚠️  DIFFERENCES FOUND ({len(differences)}):")
                    for diff in differences:
                        print(f"  - {diff}")
                else:
                    print("\n✓ PERFECT MATCH: Extracted parameters match expected values!")

            # Validate completeness
            if not issues:
                print(f"\n✓ VALIDATION: All required fields present and valid")
                results['complete'] += 1
                results['details'].append({
                    'id': problem_id,
                    'status': 'complete',
                    'params': params
                })
            else:
                print(f"\n⚠️  VALIDATION: {len(issues)} issues found")
                for issue in issues:
                    print(f"     - {issue}")
                results['partial'] += 1
                results['details'].append({
                    'id': problem_id,
                    'status': 'partial',
                    'issues': issues,
                    'params': params
                })

        except Exception as e:
            print(f"\n  ✗ ERROR: {str(e)}")
            results['failed'] += 1
            results['details'].append({
                'id': problem_id,
                'status': 'error',
                'error': str(e)
            })

    return results


def print_summary(results_without, results_with):
    """Print comparison summary."""
    print(f"\n{'='*80}")
    print(f"  COMPARISON SUMMARY")
    print(f"{'='*80}\n")
    
    if results_without:
        print("WITHOUT RAG:")
        t = results_without['total']
        print(f"  Total: {t}")
        print(f"  Complete: {results_without['complete']}/{t} = {results_without['complete']/max(t,1)*100:.1f}%")
        print(f"  Partial:  {results_without['partial']}/{t} = {results_without['partial']/max(t,1)*100:.1f}%")
        print(f"  Failed:   {results_without['failed']}/{t} = {results_without['failed']/max(t,1)*100:.1f}%")
    
    if results_with:
        print("\nWITH RAG:")
        t = results_with['total']
        print(f"  Total: {t}")
        print(f"  Complete: {results_with['complete']}/{t} = {results_with['complete']/max(t,1)*100:.1f}%")
        print(f"  Partial:  {results_with['partial']}/{t} = {results_with['partial']/max(t,1)*100:.1f}%")
        print(f"  Failed:   {results_with['failed']}/{t} = {results_with['failed']/max(t,1)*100:.1f}%")
    
    if results_without and results_with:
        # Calculate improvement
        complete_diff = results_with['complete'] - results_without['complete']
        failed_diff = results_without['failed'] - results_with['failed']  # Reduction in failures
        
        print("\n📊 IMPACT:")
        if complete_diff > 0:
            print(f"  ✅ +{complete_diff} more complete extractions with RAG")
        elif complete_diff < 0:
            print(f"  ❌ {abs(complete_diff)} fewer complete extractions with RAG")
        else:
            print(f"  ➡️  Same number of complete extractions")
        
        if failed_diff > 0:
            print(f"  ✅ {failed_diff} fewer failures with RAG")
        elif failed_diff < 0:
            print(f"  ❌ {abs(failed_diff)} more failures with RAG")
        
        # Show which problems improved
        if results_without['details'] and results_with['details']:
            improved = []
            regressed = []
            
            for i in range(len(results_without['details'])):
                without = results_without['details'][i]
                with_rag = results_with['details'][i]
                
                if without['status'] != 'complete' and with_rag['status'] == 'complete':
                    improved.append(without['id'])
                elif without['status'] == 'complete' and with_rag['status'] != 'complete':
                    regressed.append(without['id'])
            
            if improved:
                print(f"\n  ✅ Improved by RAG ({len(improved)}):")
                for pid in improved:
                    print(f"     - {pid}")
            
            if regressed:
                print(f"\n  ❌ Regressed with RAG ({len(regressed)}):")
                for pid in regressed:
                    print(f"     - {pid}")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Test RAG impact on parameter extraction'
    )

    args = parser.parse_args()

    # Get 2 transportation problems
    from tests.or_problem_repository import get_problem_by_id

    test_problems = [
        get_problem_by_id('transport/wine_eu/001'),           # Transportation
        get_problem_by_id('transport/us_mfg/001'),            # Transportation
    ]

    problems = [p for p in test_problems if p is not None]

    if not problems:
        print("No problems to test.")
        return 1

    print(f"Testing {len(problems)} transportation problems...")

    # Test WITHOUT RAG
    print("\n━━━ PHASE 1: Parameter Extraction WITHOUT RAG ━━━")
    results_without = test_parameter_extraction(problems, with_rag=False)

    # Test WITH RAG
    print("\n━━━ PHASE 2: Parameter Extraction WITH RAG ━━━")
    results_with = test_parameter_extraction(problems, with_rag=True)

    # Print comparison
    print_summary(results_without, results_with)

    return 0


if __name__ == "__main__":
    sys.exit(main())
