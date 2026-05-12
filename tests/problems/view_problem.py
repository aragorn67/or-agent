#!/usr/bin/env python3
"""
Pretty print problem details from CSV + JSON

Usage:
    python view_problem.py transport/wine_eu/001
    python view_problem.py --list                    # List all problems
    python view_problem.py --list --solvable         # List solvable only
    python view_problem.py --count                   # Show statistics
    python view_problem.py --test transport/wine_eu/001  # Test load problem
"""

import csv
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional

def load_problem(problem_id: str) -> Optional[Dict]:
    """Load problem from CSV + JSON"""
    problems_dir = Path(__file__).parent

    # Read CSV
    csv_path = problems_dir / "problems.csv"
    problem = None
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['problem_id'] == problem_id:
                problem = dict(row)
                break

    if not problem:
        return None

    # Read JSON metadata
    json_path = problems_dir / "problems_metadata.json"
    with open(json_path, encoding='utf-8') as f:
        metadata = json.load(f)

    # Merge
    problem['full_metadata'] = metadata.get(problem_id, {})
    return problem

def load_all_problems() -> List[Dict]:
    """Load all problems from CSV"""
    problems_dir = Path(__file__).parent
    csv_path = problems_dir / "problems.csv"

    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

def print_problem(problem_id: str):
    """Pretty print a problem"""
    problem = load_problem(problem_id)
    if not problem:
        print(f"❌ Problem '{problem_id}' not found")
        return

    print("\n" + "="*80)
    print(f"  {problem['name'].upper().replace('_', ' ')}")
    print("="*80)
    print(f"ID:                 {problem['problem_id']}")
    print(f"Category:           {problem['category']}")
    print(f"Type:               {problem['expected_type']}")
    print(f"Feasible:           {'✓' if problem['feasible'] == 'true' else '✗'}")
    print(f"Solvable:           {'✓' if problem['solvable'] == 'true' else '✗'}")
    print(f"Source:             {problem['source']}")
    print(f"Solver:             {problem['solver_id']}")
    print(f"Confidence:         {problem['confidence_level']}")

    if problem.get('expected_objective_value'):
        print(f"Expected Objective: {problem['expected_objective_value']}")
    if problem.get('expected_objective_sense'):
        print(f"Objective Sense:    {problem['expected_objective_sense']}")
    if problem.get('graph_signature'):
        print(f"Graph Signature:    {problem['graph_signature']}")
    if problem.get('industry'):
        print(f"Industry:           {problem['industry']}")
    if problem.get('num_entities'):
        print(f"Problem Size:       {problem['num_entities']} entities")

    print("\n" + "-"*80)
    print("DESCRIPTION:")
    print("-"*80)
    # Wrap long lines
    desc = problem['description']
    print(desc)

    # Print metadata from JSON
    meta = problem.get('full_metadata', {}).get('metadata', {})
    if meta.get('tags'):
        print("\n" + "-"*80)
        print("TAGS:")
        print("-"*80)
        print(", ".join(meta['tags']))

    if meta.get('units'):
        print("\n" + "-"*80)
        print("UNITS:")
        print("-"*80)
        for key, value in meta['units'].items():
            print(f"  {key:15s}: {value}")

    if meta.get('scale'):
        print("\n" + "-"*80)
        print("SCALE:")
        print("-"*80)
        for key, value in meta['scale'].items():
            print(f"  {key:15s}: {value}")

    schema = problem.get('full_metadata', {}).get('expected_schema', {})
    if schema:
        print("\n" + "-"*80)
        print("EXPECTED SCHEMA:")
        print("-"*80)
        if schema.get('sets'):
            print(f"Sets:        {', '.join(schema['sets'])}")
        if schema.get('params'):
            print(f"Params:      {', '.join(schema['params'])}")
        if schema.get('objective'):
            print(f"Objective:   {schema['objective']}")
        if schema.get('constraints'):
            print(f"Constraints: ({len(schema['constraints'])} total)")
            for i, constraint in enumerate(schema['constraints'][:3], 1):  # Show first 3
                print(f"  {i}. {constraint}")
            if len(schema['constraints']) > 3:
                print(f"  ... and {len(schema['constraints']) - 3} more")

    if problem.get('notes'):
        print("\n" + "-"*80)
        print("NOTES:")
        print("-"*80)
        print(problem['notes'])

    print("\n" + "="*80 + "\n")

def list_problems(solvable_only: bool = False):
    """List all problems"""
    problems = load_all_problems()

    if solvable_only:
        problems = [p for p in problems if p['solvable'] == 'true']

    print("\n" + "="*80)
    print(f"  {'SOLVABLE PROBLEMS' if solvable_only else 'ALL PROBLEMS'}")
    print("="*80 + "\n")

    for i, p in enumerate(problems, 1):
        solvable = "✓" if p['solvable'] == 'true' else "✗"
        feasible = "✓" if p['feasible'] == 'true' else "✗"
        print(f"{i:3d}. [{solvable}] [{feasible}] {p['problem_id']:40s} {p['name']}")

    print(f"\nTotal: {len(problems)} problems")
    if solvable_only:
        all_problems = load_all_problems()
        print(f"(Showing {len(problems)} of {len(all_problems)} total)")
    print()

def show_stats():
    """Show statistics"""
    problems = load_all_problems()

    solvable = [p for p in problems if p['solvable'] == 'true']
    feasible = [p for p in problems if p['feasible'] == 'true']
    infeasible = [p for p in problems if p['feasible'] == 'false']

    # Count by category
    categories = {}
    for p in problems:
        cat = p['category']
        categories[cat] = categories.get(cat, 0) + 1

    # Count by solver
    solvers = {}
    for p in problems:
        solver = p['solver_id']
        solvers[solver] = solvers.get(solver, 0) + 1

    print("\n" + "="*80)
    print("  PROBLEM STATISTICS")
    print("="*80)
    print(f"\nTotal problems:     {len(problems)}")
    print(f"Feasible:           {len(feasible)}")
    print(f"Infeasible:         {len(infeasible)} (test cases)")
    print(f"Solvable:           {len(solvable)}")
    print(f"Not solvable:       {len(problems) - len(solvable)}")

    print("\nBy category:")
    for cat, count in sorted(categories.items()):
        cat_solvable = [p for p in problems if p['category'] == cat and p['solvable'] == 'true']
        print(f"  {cat:25s}: {count:3d} total, {len(cat_solvable):3d} solvable")

    print("\nBy solver:")
    for solver, count in sorted(solvers.items()):
        print(f"  {solver:35s}: {count:3d}")

    print()

def test_load(problem_id: str):
    """Test loading a problem and show what was loaded"""
    print(f"\n🧪 Testing load of problem: {problem_id}")
    problem = load_problem(problem_id)

    if not problem:
        print(f"❌ Failed to load problem '{problem_id}'")
        return

    print(f"✓ Loaded problem successfully")
    print(f"\nCSV fields:")
    for key in ['problem_id', 'name', 'category', 'expected_type', 'feasible', 'solvable', 'solver_id']:
        print(f"  {key:20s}: {problem.get(key, 'N/A')}")

    print(f"\nJSON metadata fields:")
    meta = problem.get('full_metadata', {})
    print(f"  Has metadata:        {bool(meta.get('metadata'))}")
    print(f"  Has expected_schema: {bool(meta.get('expected_schema'))}")

    if meta.get('metadata'):
        print(f"  Metadata keys:       {list(meta['metadata'].keys())}")
    if meta.get('expected_schema'):
        print(f"  Schema keys:         {list(meta['expected_schema'].keys())}")

    print()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='View OR problems from CSV + JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python view_problem.py transport/wine_eu/001
  python view_problem.py --list
  python view_problem.py --list --solvable
  python view_problem.py --count
  python view_problem.py --test transport/wine_eu/001
        """
    )
    parser.add_argument('problem_id', nargs='?', help='Problem ID to view')
    parser.add_argument('--list', action='store_true', help='List all problems')
    parser.add_argument('--solvable', action='store_true', help='Show only solvable')
    parser.add_argument('--count', action='store_true', help='Show statistics')
    parser.add_argument('--test', metavar='ID', help='Test loading a problem')

    args = parser.parse_args()

    if args.count:
        show_stats()
    elif args.list:
        list_problems(args.solvable)
    elif args.test:
        test_load(args.test)
    elif args.problem_id:
        print_problem(args.problem_id)
    else:
        parser.print_help()
