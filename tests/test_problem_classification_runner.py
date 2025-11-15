#!/usr/bin/env python3
"""
TEST: Problem Classification Runner - OR Repository Edition

PURPOSE: Test classifier on OR problem repository with detailed analysis
TESTS: Classification → Confidence → JSON structure → Missing keys → Optional solve
PROBLEMS: or_problem_repository.py (transportation, scheduling, assignment, etc.)

EXPECTED OUTPUT:
    ✓ Tests problems from OR repository
    ✓ Detailed output per problem: type, confidence, signals, structure
    ✓ Problem structure analysis (variables, parameters, constraints)
    ✓ Missing element detection
    ✓ Per-category and overall accuracy summary
    ✓ JSON output saved to test_output/or_repo_results_{timestamp}.json

RUN: python tests/test_problem_classification_runner.py
REQUIRES: Ollama (localhost:11434), deepseek-r1:latest model
OPTIONS:
    --filter transport,scheduling  # Test only transport and scheduling
    --solvable                     # Test only solvable problems
    --no-save                      # Don't save JSON results
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from llm.ollama_client import OllamaClient
from llm.problem_classifier import ProblemClassifier
from tests.or_problem_repository import get_all_problems, get_solvable_problems
from solvers import get_solver

# Colors
class C:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def try_solve_problem(problem_type: str, text: str, llm_client) -> Optional[Dict]:
    """
    Attempt to solve the problem if it's transportation or scheduling.
    Returns solution dict or None if not solvable/applicable.
    """
    # Map scheduling subcategories to scheduling solver
    scheduling_types = ["job_shop", "flow_shop", "single_stage_scheduling", "shift_rostering", "project_scheduling"]

    if problem_type.lower() in scheduling_types:
        solver_type = "scheduling"
    elif problem_type.lower() == "transportation":
        solver_type = "transportation"
    else:
        return None

    try:
        # Get solver (use mapped solver type)
        solver = get_solver(solver_type.lower())

        # Extract parameters using LLM
        example_params = solver.get_example_params()
        params = llm_client.extract_parameters(text, problem_type, example_params)

        if "error" in params:
            return {"error": "Parameter extraction failed", "details": params["error"]}

        # Validate parameters
        errors = solver.validate_params(params)
        if errors:
            return {"error": "Validation failed", "details": errors}

        # Solve
        solution = solver.solve(params)
        return {
            "success": True,
            "params": params,
            "solution": solution
        }

    except Exception as e:
        return {"error": str(e)}


def verify_scheduling_solution(solution: Dict, test_name: str, expected_solution: Optional[Dict] = None) -> Dict:
    """
    Verify that a scheduling solution is correct.
    Checks:
    - All orders are assigned
    - Assignments respect eligibility
    - Due dates are met
    - Precedence arcs are valid
    - Completion times are consistent
    - (Optional) Matches expected solution criteria
    """
    verification = {
        "valid": True,
        "checks": [],
        "warnings": [],
        "errors": []
    }

    if not solution.get("success"):
        verification["valid"] = False
        verification["errors"].append("Solution not successful")
        return verification

    sol = solution.get("solution", {})
    params = solution.get("params", {})

    # Check status
    status = sol.get("status", "")
    if status != "OPTIMAL":
        verification["warnings"].append(f"Non-optimal status: {status}")

    # Check all orders are assigned
    orders = params.get("orders", [])
    assignments = sol.get("assignments", [])
    assigned_orders = {a["order"] for a in assignments}

    if len(assigned_orders) == len(orders):
        verification["checks"].append(f"✓ All {len(orders)} orders assigned")
    else:
        missing = set(orders) - assigned_orders
        verification["errors"].append(f"Missing assignments for: {missing}")
        verification["valid"] = False

    # Check eligibility
    eligible = params.get("eligible", {})
    for assignment in assignments:
        order = assignment["order"]
        unit = assignment["unit"]
        if order in eligible and unit not in eligible[order]:
            verification["errors"].append(f"Order {order} assigned to ineligible unit {unit}")
            verification["valid"] = False

    if not verification["errors"]:
        verification["checks"].append("✓ All assignments respect eligibility")

    # Check due dates
    completion = sol.get("completion", {})
    due_dates = params.get("due_date", {})
    late_orders = []

    for order, comp_time in completion.items():
        if order in due_dates:
            if comp_time > due_dates[order] + 1e-6:  # Small tolerance
                late_orders.append(f"{order} (completes {comp_time:.2f}, due {due_dates[order]:.2f})")

    if late_orders:
        verification["errors"].append(f"Late orders: {', '.join(late_orders)}")
        verification["valid"] = False
    else:
        verification["checks"].append(f"✓ All orders meet due dates")

    # Check makespan
    cmax = sol.get("Cmax", 0)
    max_completion = max(completion.values()) if completion else 0

    if abs(cmax - max_completion) < 1e-6:
        verification["checks"].append(f"✓ Makespan consistent: {cmax:.2f}")
    else:
        verification["warnings"].append(f"Makespan mismatch: Cmax={cmax:.2f}, max(C)={max_completion:.2f}")

    # Verify against expected solution if provided
    if expected_solution:
        exp_status = expected_solution.get("status")
        if exp_status and status != exp_status:
            verification["errors"].append(f"Expected status '{exp_status}', got '{status}'")
            verification["valid"] = False
        else:
            verification["checks"].append(f"✓ Status matches expected: {status}")

        exp_makespan = expected_solution.get("makespan_max")
        if exp_makespan is not None:
            if cmax <= exp_makespan + 1e-6:
                verification["checks"].append(f"✓ Makespan {cmax:.2f} ≤ expected {exp_makespan:.2f}")
            else:
                verification["errors"].append(f"Makespan {cmax:.2f} exceeds expected {exp_makespan:.2f}")
                verification["valid"] = False

        exp_all_on_time = expected_solution.get("all_on_time")
        if exp_all_on_time is not None:
            actual_on_time = len(late_orders) == 0
            if actual_on_time == exp_all_on_time:
                verification["checks"].append(f"✓ On-time delivery matches expected: {exp_all_on_time}")
            else:
                verification["errors"].append(f"Expected all_on_time={exp_all_on_time}, got {actual_on_time}")
                verification["valid"] = False

        exp_num_assignments = expected_solution.get("num_assignments")
        if exp_num_assignments is not None:
            if len(assignments) == exp_num_assignments:
                verification["checks"].append(f"✓ Number of assignments matches: {len(assignments)}")
            else:
                verification["errors"].append(f"Expected {exp_num_assignments} assignments, got {len(assignments)}")
                verification["valid"] = False

    return verification


def analyze_problem_structure(text: str, classifier: ProblemClassifier) -> Dict:
    """
    Analyze problem structure and extract key information
    Returns: problem_type, confidence, signals, evidence, and structure analysis
    """
    result, votes = classifier.classify(text, n=3)

    # Extract objective from LLM response
    objective_info = result.get("objective", {})
    if objective_info:
        obj_sense = objective_info.get("sense", "")
        obj_target = objective_info.get("target", "")
        objective_str = f"{obj_sense} {obj_target}" if obj_sense and obj_target else None
    else:
        objective_str = None

    structure = {
        "problem_type": result.get("problem_type", "unknown"),
        "confidence": result.get("confidence", 0.0),
        "signals": result.get("signals", {}),
        "evidence": result.get("evidence", []),
        "why": result.get("why_short", ""),
        "objective": objective_str,  # LLM-extracted objective

        # Extracted structure elements
        "identified_elements": {
            "variables": [],
            "parameters": [],
            "constraints": [],
        },

        # Analysis
        "missing_elements": [],
        "votes_breakdown": {
            "problem_types": [v.get("problem_type") for v in votes],
            "confidences": [v.get("confidence") for v in votes]
        }
    }

    # Analyze signals to identify problem structure
    signals = result.get("signals", {})

    # Extract variables (decision variables)
    if signals.get("binary_decisions"):
        structure["identified_elements"]["variables"].append("binary_variables")
    if signals.get("continuous_flow"):
        structure["identified_elements"]["variables"].append("continuous_variables")
    if signals.get("has_one_to_one_assignment"):
        structure["identified_elements"]["variables"].append("assignment_variables")

    # Extract parameters
    if signals.get("cost_matrix_present"):
        structure["identified_elements"]["parameters"].append("cost_matrix")
    if signals.get("capacity_limit"):
        structure["identified_elements"]["parameters"].append("capacity_limits")
    if signals.get("supply_vector_present"):
        structure["identified_elements"]["parameters"].append("supply_vector")
    if signals.get("demand_vector_present"):
        structure["identified_elements"]["parameters"].append("demand_vector")
    if signals.get("processing_times"):
        structure["identified_elements"]["parameters"].append("processing_times")
    if signals.get("time_indexing"):
        structure["identified_elements"]["parameters"].append("time_periods")

    # Extract constraints
    if signals.get("has_one_to_one_assignment"):
        structure["identified_elements"]["constraints"].append("one_to_one_matching")
    if signals.get("flow_conservation"):
        structure["identified_elements"]["constraints"].append("flow_conservation")
    if signals.get("precedence_constraints"):
        structure["identified_elements"]["constraints"].append("precedence")
    if signals.get("capacity_limit"):
        structure["identified_elements"]["constraints"].append("capacity")

    return structure


def check_missing_keys(structure: Dict, expected_keys: List[str]) -> List[str]:
    """Check which expected keys are missing from the problem structure"""
    missing = []
    identified = structure["identified_elements"]

    # Map expected keys to structure elements
    key_mapping = {
        "cost_matrix": ["cost_matrix" in identified["parameters"]],
        "capacity": ["capacity_limits" in identified["parameters"]],
        "demand": ["demand_vector" in identified["parameters"]],
        "supply": ["supply_vector" in identified["parameters"]],
        "objective": [structure["objective"] is not None],  # Check LLM-extracted objective
        "one_to_one_constraint": ["one_to_one_matching" in identified["constraints"]],
        "binary_choice": ["binary_variables" in identified["variables"]],
        "continuous_flow": ["continuous_variables" in identified["variables"]],
    }

    for key in expected_keys:
        # Check if key exists in mapping and is found
        if key in key_mapping:
            if not any(key_mapping[key]):
                missing.append(key)
        else:
            # Key not in mapping, consider it missing if not in any identified element
            all_elements = (identified["variables"] + identified["parameters"] +
                          identified["constraints"])
            if key not in all_elements:
                missing.append(key)

    return missing


def save_results_to_json(results: List[Dict], output_file: str):
    """Save test results to JSON file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_file}_{timestamp}.json"

    with open(filename, 'w') as f:
        json.dump(results, f, indent=2)

    return filename


def print_test_result(case_num: int, total: int, test_case: Dict, structure: Dict,
                     expected: str, elapsed_ms: float, solve_result: Optional[Dict] = None):
    """Print detailed test result"""

    name = test_case["name"]
    category = test_case.get("category", "UNKNOWN")
    classified = structure["problem_type"]
    confidence = structure["confidence"]
    passed = classified.lower() == expected.lower()

    # Header
    status = f"{C.GREEN}✅" if passed else f"{C.RED}❌"
    print(f"\n{C.BOLD}[{case_num}/{total}] {category}: {name}{C.END}")
    print(f"{status} {C.BOLD}Result:{C.END} {classified} (expected: {expected})")
    print(f"   {C.BOLD}Confidence:{C.END} {confidence:.1%} | {C.BOLD}Time:{C.END} {elapsed_ms:.0f}ms")

    # Problem type analysis
    print(f"\n   {C.CYAN}Why:{C.END} {structure['why']}")

    # Identified structure
    print(f"\n   {C.YELLOW}Problem Structure:{C.END}")

    # Show LLM-extracted objective
    if structure["objective"]:
        print(f"     Objective: {structure['objective']}")

    identified = structure["identified_elements"]

    if identified["variables"]:
        print(f"     Variables: {', '.join(identified['variables'])}")

    if identified["parameters"]:
        print(f"     Parameters: {', '.join(identified['parameters'])}")

    if identified["constraints"]:
        print(f"     Constraints: {', '.join(identified['constraints'])}")

    # Key signals
    if structure["signals"]:
        print(f"\n   {C.YELLOW}Key Signals:{C.END}")
        for key, value in sorted(structure["signals"].items())[:5]:  # Show top 5
            print(f"     • {key}: {value}")

    # Missing elements
    expected_keys = test_case.get("key_elements", [])
    if expected_keys:
        missing = check_missing_keys(structure, expected_keys)
        if missing:
            print(f"\n   {C.RED}⚠️  Missing Elements:{C.END}")
            for elem in missing:
                print(f"     • {elem}")
        else:
            print(f"\n   {C.GREEN}✓ All expected elements identified{C.END}")

    # Evidence samples
    if structure["evidence"]:
        print(f"\n   {C.CYAN}Evidence (sample):{C.END}")
        for ev in structure["evidence"][:2]:  # Show 2 pieces
            field = ev.get("field", "?")
            quote = ev.get("quote", "")
            print(f"     • {field}: \"{quote[:60]}...\"")

    # Voting consistency
    votes = structure["votes_breakdown"]
    if len(set(votes["problem_types"])) > 1:
        print(f"\n   {C.YELLOW}⚠️  Vote inconsistency:{C.END} {votes['problem_types']}")

    # Solution and verification
    if solve_result:
        if solve_result.get("success"):
            sol = solve_result["solution"]
            print(f"\n   {C.CYAN}Solution:{C.END}")
            print(f"     Status: {sol.get('status', 'N/A')}")
            print(f"     Objective: {sol.get('objective', 'N/A'):.2f}")

            if classified.lower() == "scheduling":
                print(f"     Makespan: {sol.get('Cmax', 'N/A'):.2f}")
                assignments = sol.get('assignments', [])
                print(f"     Assignments: {len(assignments)}")
                for a in assignments[:3]:  # Show first 3
                    order = a['order']
                    unit = a['unit']
                    comp = sol.get('completion', {}).get(order, 0)
                    print(f"       {order} → {unit} (completes at {comp:.2f})")
                if len(assignments) > 3:
                    print(f"       ... and {len(assignments)-3} more")

                # Verification
                verification = solve_result.get("verification", {})
                if verification:
                    if verification["valid"]:
                        print(f"\n   {C.GREEN}✓ Solution Verified{C.END}")
                    else:
                        print(f"\n   {C.RED}✗ Solution Verification Failed{C.END}")

                    for check in verification["checks"]:
                        print(f"     {check}")
                    for warning in verification["warnings"]:
                        print(f"     {C.YELLOW}⚠ {warning}{C.END}")
                    for error in verification["errors"]:
                        print(f"     {C.RED}✗ {error}{C.END}")

        elif "error" in solve_result:
            print(f"\n   {C.YELLOW}Solve failed: {solve_result['error']}{C.END}")

    print(f"\n{'-' * 80}")

    return passed


def run_or_repo_tests(save_json: bool = True, filter_types: List[str] = None, solvable_only: bool = False):
    """
    Run classification tests on OR problem repository with detailed analysis

    Args:
        save_json: Whether to save results to JSON file
        filter_types: List of problem types/categories to test (e.g., ['transportation', 'single_stage_scheduling'])
                     If None, all problems will be tested
        solvable_only: Only test problems marked as solvable
    """

    print(f"\n{C.BOLD}{C.BLUE}")
    print("╔══════════════════════════════════════════════════════════════════════════════╗")
    print("║              OR REPOSITORY CLASSIFICATION TEST                               ║")
    print("║         Detailed Analysis: Type, Confidence, Structure                       ║")
    print("╚══════════════════════════════════════════════════════════════════════════════╝")
    print(f"{C.END}\n")

    # Get problems from repository
    if solvable_only:
        problems = get_solvable_problems()
        print(f"{C.YELLOW}Testing only solvable problems{C.END}")
    else:
        problems = get_all_problems()

    # Filter by type/category if specified
    if filter_types:
        filter_lower = [f.lower() for f in filter_types]
        problems = [
            p for p in problems
            if p['category'].lower() in filter_lower or p['expected_type'].lower() in filter_lower
        ]
        if not problems:
            print(f"{C.RED}❌ No matching problems found for filters: {filter_types}{C.END}")
            return []
        print(f"{C.YELLOW}Filtered to {len(problems)} problems matching: {filter_types}{C.END}\n")
    else:
        print(f"Testing {len(problems)} problems from repository\n")

    # Initialize
    print(f"{C.YELLOW}Initializing LLM classifier...{C.END}")
    try:
        # Try available models in order of preference
        available_models = ['deepseek-r1:latest', 'llama3.1:8b-instruct-q8_0', 'qwen2:7b-instruct', 'mistral:7b-instruct']
        model = available_models[0]  # Use deepseek-r1 by default

        client = OllamaClient(host='http://localhost:11434', model=model)
        classifier = ProblemClassifier(client)
        print(f"{C.GREEN}✅ Ready (using {model}){C.END}\n")
    except Exception as e:
        print(f"{C.RED}❌ Failed: {e}{C.END}")
        return []

    # Run tests
    all_results = []
    total_cases = len(problems)

    for case_num, problem in enumerate(problems, 1):
        problem_id = problem['id']
        problem_name = problem['name']
        category = problem['category']
        expected_type = problem['expected_type']
        text = problem['text']
        is_solvable = problem.get('solvable', False)

        # Analyze
        start = time.time()
        try:
            print(f"\n{C.BOLD}{C.MAGENTA}[{case_num}/{total_cases}] {problem_id}{C.END}")

            structure = analyze_problem_structure(text, classifier)
            classified = structure["problem_type"]

            # Check correctness
            passed = (classified.lower() == expected_type.lower())
            elapsed_ms = (time.time() - start) * 1000

            # Print compact result
            status = f"{C.GREEN}✅" if passed else f"{C.RED}❌"
            print(f"{status} Expected: {expected_type:30s} | Got: {classified:30s} ({structure['confidence']:.0%})")

            if not passed:
                print(f"   {C.YELLOW}Why: {structure['why']}{C.END}")

            # Store result
            result = {
                "test_number": case_num,
                "problem_id": problem_id,
                "problem_name": problem_name,
                "category": category,
                "expected_type": expected_type,
                "classified_as": classified,
                "confidence": structure["confidence"],
                "objective": structure["objective"],
                "passed": passed,
                "time_ms": elapsed_ms,
                "structure": structure["identified_elements"],
                "signals": structure["signals"],
                "why": structure["why"],
                "solvable": is_solvable
            }

            all_results.append(result)

        except Exception as e:
            print(f"\n{C.RED}❌ ERROR: {e}{C.END}")
            all_results.append({
                "test_number": case_num,
                "problem_id": problem_id,
                "problem_name": problem_name,
                "category": category,
                "expected_type": expected_type,
                "classified_as": "ERROR",
                "confidence": 0.0,
                "passed": False,
                "error": str(e)
            })

    # Summary
    print(f"\n\n{C.BOLD}{C.CYAN}{'═' * 80}")
    print("SUMMARY")
    print(f"{'═' * 80}{C.END}\n")

    total = len(all_results)
    passed = sum(1 for r in all_results if r.get("passed", False))
    failed = total - passed
    pass_rate = (passed / total * 100) if total > 0 else 0
    avg_confidence = sum(r.get("confidence", 0) for r in all_results if r.get("passed", False)) / passed if passed > 0 else 0

    print(f"{C.BOLD}Total Tests:        {total}{C.END}")
    print(f"{C.GREEN}Passed:             {passed}{C.END}")
    print(f"{C.RED}Failed:             {failed}{C.END}")
    print(f"{C.BOLD}Pass Rate:          {pass_rate:.1f}%{C.END}")
    print(f"{C.BOLD}Avg Confidence:     {avg_confidence:.1%}{C.END} (on passed tests)\n")

    # Per-category breakdown
    print(f"{C.YELLOW}Per-Category Results:{C.END}")
    categories = set(r.get("category") for r in all_results)
    for category in sorted(categories):
        cat_results = [r for r in all_results if r.get("category") == category]
        cat_passed = sum(1 for r in cat_results if r.get("passed", False))
        cat_total = len(cat_results)
        cat_rate = (cat_passed / cat_total * 100) if cat_total > 0 else 0
        print(f"  {category:25s}: {cat_passed}/{cat_total} ({cat_rate:.0f}%)")

    # Per-expected-type breakdown
    print(f"\n{C.YELLOW}Per-Problem-Type Results:{C.END}")
    expected_types = set(r.get("expected_type") for r in all_results)
    for exp_type in sorted(expected_types):
        type_results = [r for r in all_results if r.get("expected_type") == exp_type]
        type_passed = sum(1 for r in type_results if r.get("passed", False))
        type_total = len(type_results)
        type_rate = (type_passed / type_total * 100) if type_total > 0 else 0
        status = '✅' if type_rate == 100 else '❌'
        print(f"  {status} {exp_type:35s}: {type_passed}/{type_total} ({type_rate:.0f}%)")

    # Failed tests
    if failed > 0:
        print(f"\n{C.RED}Failed Tests:{C.END}")
        for r in all_results:
            if not r.get("passed", False):
                print(f"  ❌ {r['problem_id']}")
                print(f"     Expected: {r['expected_type']} | Got: {r.get('classified_as', 'ERROR')} ({r.get('confidence', 0):.0%})")

    # Goal achievement message
    if pass_rate == 100:
        print(f"\n{C.GREEN}{C.BOLD}🎉 SUCCESS: 100% classification accuracy achieved!{C.END}")
        print(f"{C.GREEN}   Ready to proceed with parameter extraction.{C.END}\n")
    else:
        print(f"\n{C.YELLOW}⚠️  INCOMPLETE: {failed}/{total} problems misclassified{C.END}")
        print(f"{C.YELLOW}   Need to investigate classification failures.{C.END}\n")

    # Save to JSON
    if save_json:
        try:
            filename = save_results_to_json(all_results, "test_output/or_repo_results")
            print(f"{C.GREEN}✅ Results saved to: {filename}{C.END}\n")
        except Exception as e:
            print(f"{C.YELLOW}⚠️  Could not save JSON: {e}{C.END}\n")

    return all_results


if __name__ == "__main__":
    import argparse

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Run OR repository classification tests',
        epilog='''
Examples:
  python test_problem_classification_runner.py                                    # Run all tests
  python test_problem_classification_runner.py --filter transportation            # Run only transport
  python test_problem_classification_runner.py --filter transportation,scheduling # Run transport and scheduling
  python test_problem_classification_runner.py --filter single_stage_scheduling  # Run single-stage scheduling
  python test_problem_classification_runner.py --solvable                         # Run only solvable problems
  python test_problem_classification_runner.py --no-save                          # Don't save JSON results
        ''',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--filter',
        type=str,
        metavar='TYPES',
        help='Comma-separated list of problem types/categories to test (e.g., transportation,single_stage_scheduling)'
    )

    parser.add_argument(
        '--solvable',
        action='store_true',
        help='Test only problems marked as solvable'
    )

    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save results to JSON file'
    )

    args = parser.parse_args()

    # Parse filter list
    filter_types = None
    if args.filter:
        filter_types = [f.strip() for f in args.filter.split(',')]

    # Create output directory if needed
    Path("test_output").mkdir(exist_ok=True)

    # Run tests
    results = run_or_repo_tests(
        save_json=not args.no_save,
        filter_types=filter_types,
        solvable_only=args.solvable
    )

    # Exit code
    if results:
        failed = sum(1 for r in results if not r.get("passed", False))
        sys.exit(0 if failed == 0 else 1)
    else:
        sys.exit(1)
