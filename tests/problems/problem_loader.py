"""
New problem loader that reads from CSV + JSON instead of hardcoded Python.

This module provides the same API as or_problem_repository.py but loads data from:
- problems.csv (simple queryable fields)
- problems_metadata.json (complex nested metadata)

USAGE:
    from tests.problems.problem_loader import get_problem_by_name, get_all_problems

    problem = get_problem_by_name("european_wine_distribution")
    all_problems = get_all_problems()

API COMPATIBILITY:
    This module provides the same functions as or_problem_repository.py:
    - get_all_problems()
    - get_problem_by_name(name)
    - get_problem_by_id(problem_id)
    - get_problems_by_category(category)
    - get_solvable_problems()
    - get_categories()
    - list_problems(category, solvable_only)
    - get_solver_id(problem)
"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Optional
from enum import Enum

__all__ = [
    'ProblemCategory',
    'ProblemType',
    'get_all_problems',
    'get_problem_by_name',
    'get_problem_by_id',
    'get_problems_by_category',
    'get_solvable_problems',
    'get_categories',
    'list_problems',
    'get_solver_id'
]

# ============================================================================
# ENUMS (copied from or_problem_repository.py for compatibility)
# ============================================================================

class ProblemCategory(Enum):
    """Problem families for organization"""
    TRANSPORTATION = "transportation"
    SCHEDULING = "scheduling"
    ASSIGNMENT = "assignment"
    KNAPSACK = "knapsack"
    NETWORK_FLOW = "network_flow"
    PRODUCTION_PLANNING = "production_planning"
    FACILITY_LOCATION = "facility_location"
    VEHICLE_ROUTING = "vehicle_routing"
    SET_COVER = "set_cover"
    BIN_PACKING = "bin_packing"
    MULTICOMMODITY_FLOW = "multicommodity_flow"

class ProblemType(Enum):
    """Specific problem types for classification"""
    # Transportation
    TRANSPORTATION = "transportation"
    MIN_COST_FLOW = "min_cost_flow"

    # Scheduling
    SINGLE_STAGE_SCHEDULING = "single_stage_scheduling"
    SINGLE_MACHINE_TARDINESS = "single_machine_tardiness"
    SINGLE_MACHINE_MAKESPAN = "single_machine_makespan"
    PARALLEL_MACHINE_SCHEDULING = "parallel_machine_scheduling"
    JOB_SHOP = "job_shop"
    FLOW_SHOP = "flow_shop"
    OPEN_SHOP = "open_shop"
    SHIFT_ROSTERING = "shift_rostering"
    PROJECT_SCHEDULING = "project_scheduling"

    # Assignment
    ASSIGNMENT = "assignment"
    BIPARTITE_MATCHING = "bipartite_matching"

    # Knapsack
    ZERO_ONE_KNAPSACK = "zero_one_knapsack"
    BOUNDED_KNAPSACK = "bounded_knapsack"

    # Network
    MAX_FLOW = "max_flow"
    SHORTEST_PATH = "shortest_path"

    # Facility Location
    UNCAPACITATED_FACILITY_LOCATION = "uncapacitated_facility_location"
    CAPACITATED_FACILITY_LOCATION = "capacitated_facility_location"

    # VRP
    CVRP = "cvrp"
    VRPTW = "vrptw"

    # Set problems
    SET_COVER = "set_cover"
    SET_PACKING = "set_packing"

    # Others
    BIN_PACKING = "bin_packing"
    CUTTING_STOCK = "cutting_stock"
    LOT_SIZING = "lot_sizing"
    PRODUCTION_PLANNING = "production_planning"

# ============================================================================
# DATA LOADING
# ============================================================================

_PROBLEMS_CACHE = None
_METADATA_CACHE = None

def _load_problems_from_csv() -> List[Dict]:
    """Load problems from CSV file"""
    problems_dir = Path(__file__).parent
    csv_path = problems_dir / "problems.csv"

    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

def _load_metadata_from_json() -> Dict:
    """Load metadata from JSON file"""
    problems_dir = Path(__file__).parent
    json_path = problems_dir / "problems_metadata.json"

    with open(json_path, encoding='utf-8') as f:
        return json.load(f)

def _merge_problem_data(csv_row: Dict, metadata: Dict) -> Dict:
    """Merge CSV row with JSON metadata to create full problem dict"""
    problem = {
        'id': csv_row['problem_id'],
        'name': csv_row['name'],
        'category': csv_row['category'],
        'expected_type': csv_row['expected_type'],
        'text': csv_row['description'],
        'feasible': csv_row['feasible'].lower() == 'true',
        'solvable': csv_row['solvable'].lower() == 'true',
        'solver_id': csv_row['solver_id'],
        'notes': csv_row['notes'],
        'source': csv_row.get('source', 'manual'),
        'confidence_level': csv_row.get('confidence_level', 'gold'),
    }

    # Add optional fields
    if csv_row.get('expected_objective_value'):
        problem['expected_objective_value'] = csv_row['expected_objective_value']
    if csv_row.get('expected_objective_sense'):
        problem['expected_objective_sense'] = csv_row['expected_objective_sense']

    # Merge metadata from JSON
    problem['metadata'] = metadata.get('metadata', {})
    problem['expected_schema'] = metadata.get('expected_schema', {})

    return problem

# ============================================================================
# PUBLIC API FUNCTIONS
# ============================================================================

def get_all_problems() -> List[Dict]:
    """
    Return all problems from CSV + JSON.

    Returns:
        List of problem dicts with same structure as or_problem_repository.py
    """
    global _PROBLEMS_CACHE, _METADATA_CACHE

    # Load and cache
    if _PROBLEMS_CACHE is None:
        csv_problems = _load_problems_from_csv()
        json_metadata = _load_metadata_from_json()

        _PROBLEMS_CACHE = [
            _merge_problem_data(row, json_metadata.get(row['problem_id'], {}))
            for row in csv_problems
        ]

    return _PROBLEMS_CACHE

def get_problem_by_name(name: str) -> Optional[Dict]:
    """Get a specific problem by its name."""
    for problem in get_all_problems():
        if problem["name"] == name:
            return problem
    return None

def get_problem_by_id(problem_id: str) -> Optional[Dict]:
    """Get a specific problem by its hierarchical ID."""
    for problem in get_all_problems():
        if problem["id"] == problem_id:
            return problem
    return None

def get_problems_by_category(category: str) -> List[Dict]:
    """Get problems of a specific category."""
    return [p for p in get_all_problems() if p.get("category", "").lower() == category.lower()]

def get_solvable_problems() -> List[Dict]:
    """Return only problems that current system can solve."""
    return [p for p in get_all_problems() if p.get("solvable", False)]

def get_categories() -> List[str]:
    """Get list of all available categories."""
    return [cat.value for cat in ProblemCategory]

def list_problems(category: Optional[str] = None, solvable_only: bool = False):
    """Print a formatted list of problems."""
    if category:
        problems = get_problems_by_category(category)
        if not problems:
            print(f"Category '{category}' not found. Available: {', '.join(get_categories())}")
            return
    else:
        problems = get_all_problems()

    if solvable_only:
        problems = [p for p in problems if p.get("solvable", False)]

    print(f"\n{'='*80}")
    if category:
        print(f"  {category.upper()} PROBLEMS")
    else:
        print(f"  ALL OR PROBLEMS")
    if solvable_only:
        print(f"  (Showing only solvable problems)")
    print(f"{'='*80}\n")

    for i, problem in enumerate(problems, 1):
        solvable = "✓" if problem.get("solvable", False) else "✗"
        print(f"{i:2d}. [{solvable}] {problem['id']}")
        print(f"     Name: {problem['name']}")
        print(f"     Type: {problem['expected_type']}")
        if 'metadata' in problem and 'tags' in problem['metadata']:
            print(f"     Tags: {', '.join(problem['metadata']['tags'])}")
        print(f"     {problem['notes']}")
        print()

def get_solver_id(problem: Dict) -> str:
    """
    Map fine-grained expected_type to a solver_id.

    This function is provided for API compatibility but the solver_id
    is already stored in the CSV, so we just return it directly.
    """
    return problem.get("solver_id", "none")

# ============================================================================
# MAIN (for CLI compatibility)
# ============================================================================

def main():
    """CLI interface for compatibility with or_problem_repository.py"""
    import argparse

    parser = argparse.ArgumentParser(
        description='OR Problem Loader - Load problems from CSV + JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # List command
    list_parser = subparsers.add_parser('list', help='List problems')
    list_parser.add_argument('category', nargs='?', help='Category to filter by')
    list_parser.add_argument('--solvable', action='store_true', help='Show only solvable problems')

    # Count command
    subparsers.add_parser('count', help='Show statistics')

    # Get command
    get_parser = subparsers.add_parser('get', help='Get specific problem')
    get_parser.add_argument('name', help='Problem name or ID')

    args = parser.parse_args()

    if args.command == 'list':
        list_problems(args.category, args.solvable)
    elif args.command == 'count':
        all_probs = get_all_problems()
        solvable = get_solvable_problems()
        print(f"\n{'='*80}")
        print("  PROBLEM STATISTICS")
        print(f"{'='*80}\n")
        print(f"Total problems: {len(all_probs)}")
        print(f"Solvable: {len(solvable)}")
        print(f"Not yet solvable: {len(all_probs) - len(solvable)}")
        print()
    elif args.command == 'get':
        problem = get_problem_by_name(args.name) or get_problem_by_id(args.name)
        if problem:
            print(f"\n{'='*80}")
            print(f"Problem: {problem['name']}")
            print(f"ID: {problem['id']}")
            print(f"Category: {problem['category']}")
            print(f"Solvable: {'✓ Yes' if problem.get('solvable') else '✗ No'}")
            print(f"{'='*80}\n")
        else:
            print(f"Problem '{args.name}' not found.")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
