#!/usr/bin/env python3
"""
Extract problems from or_problem_repository.py to CSV + JSON format.
This is a one-time migration script.
"""

import sys
import csv
import json
from pathlib import Path

# Add parent directory to path to import or_problem_repository
sys.path.insert(0, str(Path(__file__).parent.parent))

from or_problem_repository import get_all_problems

def extract_problems():
    """Extract all problems and split into CSV + JSON"""

    problems = get_all_problems()
    print(f"Loading {len(problems)} problems from or_problem_repository.py...")

    csv_data = []
    json_data = {}

    for problem in problems:
        # Extract CSV fields (simple, queryable)
        csv_row = {
            'problem_id': problem.get('id', ''),
            'name': problem.get('name', ''),
            'description': problem.get('text', ''),
            'category': problem.get('category', ''),
            'expected_type': problem.get('expected_type', ''),
            'feasible': str(problem.get('feasible', False)).lower(),
            'solvable': str(problem.get('solvable', False)).lower(),
            'solver_id': problem.get('solver_id', 'none'),
            'confidence_level': 'gold',  # All existing problems are gold
            'source': 'manual',
            'expected_objective_value': problem.get('expected_objective_value', ''),
            'expected_objective_sense': problem.get('expected_objective_sense', ''),
            'graph_signature': problem.get('metadata', {}).get('graph_signature', ''),
            'industry': problem.get('metadata', {}).get('industry', ''),
            'num_entities': problem.get('metadata', {}).get('scale', {}).get('sources', '') + problem.get('metadata', {}).get('scale', {}).get('sinks', '') if problem.get('metadata', {}).get('scale') else '',
            'notes': problem.get('notes', '')
        }
        csv_data.append(csv_row)

        # Extract JSON fields (complex, nested)
        json_data[problem.get('id', '')] = {
            'metadata': problem.get('metadata', {}),
            'expected_schema': problem.get('expected_schema', {})
        }

    # Write CSV
    csv_path = Path(__file__).parent / 'problems.csv'
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'problem_id', 'name', 'description', 'category', 'expected_type',
            'feasible', 'solvable', 'solver_id', 'confidence_level', 'source',
            'expected_objective_value', 'expected_objective_sense',
            'graph_signature', 'industry', 'num_entities', 'notes'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)

    print(f"✓ Created {csv_path} ({len(csv_data)} problems)")

    # Write JSON
    json_path = Path(__file__).parent / 'problems_metadata.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    print(f"✓ Created {json_path} ({len(json_data)} problems)")
    print("\nDone! New files created in tests/problems/")

if __name__ == '__main__':
    extract_problems()
