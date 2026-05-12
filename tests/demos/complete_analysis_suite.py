#!/usr/bin/env python3
"""
Comprehensive Analysis Suite Test

Tests the complete workflow for:
1. 3 infeasible problems (one from each layer)
2. 1 feasible problem
3. For each: solve/fix → sensitivity → what-if → resolve
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from tests.or_problem_repository import get_problem_by_name
from llm.enhanced_client import EnhancedLLMClient
from agent.core import OptimizationAgent
from solvers import get_solver
from feasibility.core import check_feasibility, FeasStatus
from analysis import detect_analysis_type, execute_analysis, format_analysis_output


def print_header(title, char="="):
    """Print formatted section header"""
    print(f"\n{char * 80}")
    print(f"  {title}")
    print(f"{char * 80}\n")


def run_infeasible_test(problem_name, fix_query, analysis_queries):
    """
    Test workflow for an infeasible problem.
    
    Args:
        problem_name: Name of problem in OR repo
        fix_query: Query to make problem feasible
        analysis_queries: List of analysis queries to test
    """
    print_header(f"TEST: {problem_name}", "=")
    
    # Get problem from repository
    problem_data = get_problem_by_name(problem_name)

    if not problem_data:
        print(f"❌ Problem '{problem_name}' not found in repository")
        return False
    
    print(f"Description: {problem_data['text'][:100]}...")
    print(f"Expected: Infeasible (solvable={problem_data.get('solvable', 'unknown')})")
    
    # Initialize
    llm_client = EnhancedLLMClient()
    agent = OptimizationAgent(llm_client)
    
    # Step 1: Try to solve (should be infeasible)
    print_header("Step 1: Classify and Extract Parameters", "-")
    result = agent.solve_natural_language(problem_data['text'])
    
    if result.get('status') != 'infeasible':
        print(f"❌ FAILED: Expected infeasible, got {result.get('status')}")
        return False
    
    print(f"✓ Correctly detected as INFEASIBLE")
    print(f"  Layer failed: {result.get('layer_failed')}")
    print(f"  Reasons: {result['reasons'][0] if result.get('reasons') else 'None'}")
    
    # Step 2: Apply fix
    print_header("Step 2: Apply Modification to Make Feasible", "-")
    print(f"Fix query: '{fix_query}'")
    
    # Parse and apply fix
    params = result.get('extracted_params', {})
    if not params:
        # Need to re-extract
        available_types = ['TRANSPORTATION']
        classification = llm_client.classify_problem(problem_data['text'], available_types)
        solver = get_solver(classification.get('solver_id', 'transport_basic_bipartite'))
        params = llm_client.extract_parameters(
            problem_data['text'],
            classification.get('type'),
            solver.get_example_params()
        )
    
    fix_result = llm_client.parse_infeasibility_fix(
        fix_query,
        params,
        {
            "layer_failed": result.get('layer_failed'),
            "reasons": result.get('reasons', []),
            "suggestions": result.get('suggestions', [])
        }
    )
    
    modified_params = fix_result.get('applied_params', params)
    print(f"✓ Applied {len(fix_result.get('modifications', []))} modification(s)")
    
    # Re-check feasibility
    from feasibility.schemas import ParsedInstance
    instance = ParsedInstance(
        problem_type='TRANSPORTATION',
        solver_id='transport_basic_bipartite',
        sets={
            'I_plants': modified_params.get('plants', []),
            'J_markets': modified_params.get('markets', [])
        },
        params={
            'supply': modified_params.get('capacity', {}),
            'demand': modified_params.get('demand', {}),
            'cost': {(plant, market): cost
                     for plant, markets in modified_params.get('cost', {}).items()
                     for market, cost in markets.items()}
        }
    )
    
    feas_report = check_feasibility(instance)
    if feas_report.status != FeasStatus.FEASIBLE:
        print(f"❌ FAILED: Still infeasible after fix")
        return False
    
    print(f"✓ Problem is now FEASIBLE")
    
    # Step 3: Solve
    print_header("Step 3: Solve Modified Problem", "-")
    solver = get_solver('transport_basic_bipartite')
    solution = solver.solve(modified_params)
    
    if solution.get('status') != 'OPTIMAL':
        print(f"❌ FAILED: Solver returned {solution.get('status')}")
        return False
    
    optimal_cost = solution.get('objective_value', 0)
    print(f"✓ Solved successfully")
    print(f"  Optimal cost: €{optimal_cost:.2f}")
    print(f"  Number of flows: {len([f for f in solution.get('flows', []) if f.get('value', 0) > 0.1])}")
    
    # Step 4: Run analysis queries
    print_header("Step 4: Test Analysis Capabilities", "-")
    
    for i, query in enumerate(analysis_queries, 1):
        print(f"\nAnalysis {i}: '{query}'")
        print("-" * 60)
        
        try:
            analysis_type = detect_analysis_type(query, llm_client)
            print(f"Detected type: {analysis_type}")
            
            if analysis_type == 'unknown':
                print(f"⚠️  Could not detect analysis type")
                continue
            
            results = execute_analysis(
                analysis_type=analysis_type,
                solver=solver,
                params=modified_params,
                solution=solution,
                query=query,
                llm_client=llm_client
            )
            
            if results.get('success'):
                print(f"✓ Analysis successful")
                # Show brief summary
                if analysis_type == 'sensitivity':
                    feasible_count = sum(1 for c in results.get('costs', []) if c is not None)
                    print(f"  Tested {len(results.get('test_values', []))} values, {feasible_count} feasible")
                elif analysis_type == 'what_if':
                    cost_diff = results.get('cost_diff', 0)
                    print(f"  Cost change: €{cost_diff:+.2f}")
                elif analysis_type == 'resolve':
                    new_cost = results.get('new_cost', 0)
                    print(f"  New optimal cost: €{new_cost:.2f}")
            else:
                print(f"⚠️  Analysis failed: {results.get('message', 'Unknown error')}")
        
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    print_header(f"✓ {problem_name} - ALL TESTS PASSED", "=")
    return True


def run_feasible_test(problem_name, analysis_queries):
    """Test workflow for a feasible problem."""
    print_header(f"TEST: {problem_name}", "=")
    
    # Get problem from repository
    problem_data = get_problem_by_name(problem_name)

    if not problem_data:
        print(f"❌ Problem '{problem_name}' not found in repository")
        return False
    
    print(f"Description: {problem_data['text'][:100]}...")
    print(f"Expected: Feasible and solvable")
    
    # Initialize and solve
    llm_client = EnhancedLLMClient()
    agent = OptimizationAgent(llm_client)
    
    print_header("Step 1: Solve Problem", "-")
    result = agent.solve_natural_language(problem_data['text'])
    
    if not result.get('success'):
        print(f"❌ FAILED: Problem failed to solve")
        return False
    
    optimal_cost = result['solution'].get('objective_value', 0)
    print(f"✓ Solved successfully")
    print(f"  Optimal cost: €{optimal_cost:.2f}")
    
    # Run analyses
    print_header("Step 2: Test Analysis Capabilities", "-")
    
    solver = get_solver('transport_basic_bipartite')
    params = result['extracted_params']
    solution = result['solution']
    
    for i, query in enumerate(analysis_queries, 1):
        print(f"\nAnalysis {i}: '{query}'")
        print("-" * 60)
        
        try:
            analysis_type = detect_analysis_type(query, llm_client)
            print(f"Detected type: {analysis_type}")
            
            results = execute_analysis(
                analysis_type=analysis_type,
                solver=solver,
                params=params,
                solution=solution,
                query=query,
                llm_client=llm_client
            )
            
            if results.get('success'):
                print(f"✓ Analysis successful")
            else:
                print(f"⚠️  Analysis failed: {results.get('message', 'Unknown')}")
        
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    print_header(f"✓ {problem_name} - ALL TESTS PASSED", "=")
    return True


def main():
    """Run complete test suite"""
    print_header("COMPREHENSIVE ANALYSIS SUITE TEST", "=")
    print("Testing 3 infeasible + 1 feasible problem")
    print("Each test includes: solve/fix → sensitivity → what-if → resolve\n")
    
    results = {}
    
    # Test 1: Layer 0 - Structural Infeasibility
    results['layer0'] = run_infeasible_test(
        problem_name='infeasible_transport_struct_mismatched_costs',
        fix_query='Set capacity of F2 to 60',  # Fix negative capacity
        analysis_queries=[
            'sensitivity on F1 capacity',
            'what if demand of W1 decreases by 10',
            'resolve with capacity of F1 = 90'
        ]
    )
    
    # Test 2: Layer 1 - Aggregate Infeasibility
    results['layer1'] = run_infeasible_test(
        problem_name='infeasible_transport_supply_less_than_demand',
        fix_query='Decrease demand of Centre C by 10',
        analysis_queries=[
            'sensitivity on Plant North capacity',
            'what if demand of Centre A decreases by 5',
            'resolve with capacity of Plant South = 35'
        ]
    )
    
    # Test 3: Layer 2 - Network Capacity Infeasibility
    results['layer2'] = run_infeasible_test(
        problem_name='infeasible_transport_capacity_pattern',
        fix_query='Increase arc capacity from F2 to A to 50',  # Open up F2→A to relieve bottleneck
        analysis_queries=[
            'sensitivity on F1 capacity',
            'what if arc capacity from F2 to B increases by 20',
        ]
    )
    
    # Test 4: Feasible Problem
    results['feasible'] = run_feasible_test(
        problem_name='european_wine_distribution',
        analysis_queries=[
            'sensitivity on Bordeaux capacity',
            'what if demand of Amsterdam decreases by 50',
            'resolve with capacity of Rioja = 600'
        ]
    )
    
    # Summary
    print_header("TEST SUITE SUMMARY", "=")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_flag in results.items():
        status = "✓ PASSED" if passed_flag else "❌ FAILED"
        print(f"{test_name:20}: {status}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
