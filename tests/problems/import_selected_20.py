#!/usr/bin/env python3
"""
Import the selected 20 problems (10 transport + 10 scheduling) into CSV + JSON
"""

import csv
import json
from pathlib import Path

def import_20_problems():
    """Import 20 selected problems"""

    # Paths
    ml_csv_path = Path(__file__).parent.parent.parent / 'ML_RAG_archive' / 'ML_approaches' / 'ML' / 'FINAL_ML_DATASET.csv'
    problems_csv_path = Path(__file__).parent / 'problems.csv'
    problems_json_path = Path(__file__).parent / 'problems_metadata.json'

    print("Loading ML dataset...")
    with open(ml_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        ml_problems = {p['id']: p for p in reader}

    # Read existing problems
    with open(problems_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        existing_problems = list(reader)

    with open(problems_json_path, 'r', encoding='utf-8') as f:
        existing_metadata = json.load(f)

    print(f"Existing: {len(existing_problems)} problems")

    # Define the 20 to import
    selected_ids = [
        # 10 Transportation (LPWP)
        'lpwp/prob_0',
        'lpwp/prob_110',
        'lpwp/prob_120',
        'lpwp/prob_130',
        'lpwp/prob_140',
        'lpwp/prob_148',
        'lpwp/prob_149',
        'lpwp/prob_150',
        'lpwp/prob_151',
        'lpwp/prob_152',
        # 10 Scheduling (OR-Library job shop)
        'jobshop/orlib/001',
        'jobshop/orlib/002',
        'jobshop/orlib/003',
        'jobshop/orlib/004',
        'jobshop/orlib/005',
        'jobshop/orlib/006',
        'jobshop/orlib/007',
        'jobshop/orlib/008',
        'jobshop/orlib/009',
        'jobshop/orlib/010'
    ]

    print(f"\nImporting {len(selected_ids)} problems...")

    new_csv_rows = []
    new_json_entries = {}

    for problem_id in selected_ids:
        if problem_id not in ml_problems:
            print(f"  ⚠️  {problem_id} not found in ML dataset")
            continue

        ml_row = ml_problems[problem_id]

        category = ml_row['level1_family'].upper()
        subtype = ml_row['subtype']

        # All are NOT solvable
        solver_id = 'none'
        solvable = False

        # Calculate problem size
        num_entities = ''
        if ml_row.get('num_jobs') and ml_row.get('num_machines'):
            try:
                num_entities = str(int(ml_row['num_jobs']) + int(ml_row['num_machines']))
            except:
                pass

        # CSV row
        csv_row = {
            'problem_id': problem_id,
            'name': ml_row['title'].lower().replace(' ', '_').replace('-', '_')[:60],
            'description': ml_row['text'],
            'category': category,
            'expected_type': subtype,
            'feasible': 'true',
            'solvable': 'false',  # None are solvable
            'solver_id': solver_id,
            'confidence_level': 'bronze',
            'source': 'ML_dataset',
            'expected_objective_value': '',
            'expected_objective_sense': 'minimize',
            'graph_signature': '',
            'industry': '',
            'num_entities': num_entities,
            'notes': f"From ML dataset - {subtype} (not solvable with current solvers)"
        }
        new_csv_rows.append(csv_row)

        # JSON metadata (minimal)
        json_entry = {
            'metadata': {
                'source_url': ml_row.get('source_url', ''),
                'tags': []
            },
            'expected_schema': None
        }
        new_json_entries[problem_id] = json_entry

        print(f"  ✓ {problem_id}")

    # Append to existing
    all_csv_rows = existing_problems + new_csv_rows
    all_json_entries = {**existing_metadata, **new_json_entries}

    # Write CSV
    with open(problems_csv_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'problem_id', 'name', 'description', 'category', 'expected_type',
            'feasible', 'solvable', 'solver_id', 'confidence_level', 'source',
            'expected_objective_value', 'expected_objective_sense',
            'graph_signature', 'industry', 'num_entities', 'notes'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_csv_rows)

    print(f"\n✓ Updated CSV: {problems_csv_path}")

    # Write JSON
    with open(problems_json_path, 'w', encoding='utf-8') as f:
        json.dump(all_json_entries, f, indent=2, ensure_ascii=False)

    print(f"✓ Updated JSON: {problems_json_path}")

    print(f"\n{'='*80}")
    print("IMPORT COMPLETE")
    print(f"{'='*80}")
    print(f"Total problems: {len(all_csv_rows)}")
    print(f"  Gold problems:  {len(existing_problems)}")
    print(f"  ML problems:    {len(new_csv_rows)}")

    # Count by category
    categories = {}
    for row in all_csv_rows:
        cat = row['category']
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\nBy category:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat:25s}: {count:3d}")

    # Count solvable
    solvable_count = sum(1 for row in all_csv_rows if row['solvable'] == 'true')
    print(f"\nSolvable:   {solvable_count}")
    print(f"Unsolvable: {len(all_csv_rows) - solvable_count}")

if __name__ == '__main__':
    import_20_problems()
