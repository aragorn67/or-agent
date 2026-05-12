#!/usr/bin/env python3
"""
Validate that the JSON metadata is correct for all 55 problems
"""

import csv
import json
from pathlib import Path

def validate_json():
    """Validate JSON structure and completeness"""

    problems_csv = Path(__file__).parent / 'problems.csv'
    problems_json = Path(__file__).parent / 'problems_metadata.json'

    print("="*80)
    print("VALIDATING JSON METADATA")
    print("="*80)

    # Read CSV to get all problem IDs
    print("\n1. Reading CSV...")
    with open(problems_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        csv_problems = list(reader)

    csv_ids = set(p['problem_id'] for p in csv_problems)
    print(f"   Found {len(csv_ids)} problems in CSV")

    # Read JSON
    print("\n2. Reading JSON...")
    with open(problems_json, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    json_ids = set(json_data.keys())
    print(f"   Found {len(json_ids)} entries in JSON")

    # Check if counts match
    print("\n3. Checking ID consistency...")
    if len(csv_ids) == len(json_ids):
        print(f"   ✓ Both have {len(csv_ids)} problems")
    else:
        print(f"   ✗ MISMATCH: CSV has {len(csv_ids)}, JSON has {len(json_ids)}")

    # Check for missing IDs in JSON
    missing_in_json = csv_ids - json_ids
    if missing_in_json:
        print(f"\n   ✗ Missing in JSON ({len(missing_in_json)}):")
        for pid in sorted(missing_in_json):
            print(f"      - {pid}")
    else:
        print("   ✓ All CSV IDs present in JSON")

    # Check for extra IDs in JSON
    extra_in_json = json_ids - csv_ids
    if extra_in_json:
        print(f"\n   ✗ Extra in JSON ({len(extra_in_json)}):")
        for pid in sorted(extra_in_json):
            print(f"      - {pid}")
    else:
        print("   ✓ No extra IDs in JSON")

    # Validate structure of each JSON entry
    print("\n4. Validating JSON structure for each problem...")
    errors = []
    warnings = []

    for i, problem_id in enumerate(sorted(csv_ids), 1):
        if problem_id not in json_data:
            errors.append(f"{problem_id}: Missing in JSON")
            continue

        entry = json_data[problem_id]

        # Check required fields
        if 'metadata' not in entry:
            errors.append(f"{problem_id}: Missing 'metadata' field")
        elif not isinstance(entry['metadata'], dict):
            errors.append(f"{problem_id}: 'metadata' is not a dict")

        if 'expected_schema' not in entry:
            errors.append(f"{problem_id}: Missing 'expected_schema' field")

        # Check if it's a gold problem (should have expected_schema)
        csv_problem = next((p for p in csv_problems if p['problem_id'] == problem_id), None)
        if csv_problem and csv_problem['confidence_level'] == 'gold':
            if entry.get('expected_schema') is None:
                warnings.append(f"{problem_id}: Gold problem but expected_schema is None")
            else:
                schema = entry['expected_schema']
                # Validate schema structure
                if not isinstance(schema, dict):
                    errors.append(f"{problem_id}: expected_schema is not a dict")
                else:
                    required_schema_keys = ['sets', 'params', 'vars', 'objective', 'constraints']
                    for key in required_schema_keys:
                        if key not in schema:
                            warnings.append(f"{problem_id}: expected_schema missing '{key}'")

        # Check metadata structure
        if 'metadata' in entry and isinstance(entry['metadata'], dict):
            metadata = entry['metadata']
            # For gold problems, should have more metadata
            if csv_problem and csv_problem['confidence_level'] == 'gold':
                if not metadata.get('units'):
                    warnings.append(f"{problem_id}: Gold problem missing 'units' in metadata")
                if not metadata.get('scale'):
                    warnings.append(f"{problem_id}: Gold problem missing 'scale' in metadata")
                if not metadata.get('tags'):
                    warnings.append(f"{problem_id}: Gold problem missing 'tags' in metadata")

        # Progress indicator
        if i % 10 == 0:
            print(f"   Checked {i}/{len(csv_ids)} problems...")

    print(f"   ✓ Checked all {len(csv_ids)} problems")

    # Summary
    print("\n" + "="*80)
    print("VALIDATION SUMMARY")
    print("="*80)

    if not errors and not warnings:
        print("✅ ALL CHECKS PASSED - JSON is valid!")
    else:
        if errors:
            print(f"\n❌ ERRORS ({len(errors)}):")
            for err in errors:
                print(f"   {err}")

        if warnings:
            print(f"\n⚠️  WARNINGS ({len(warnings)}):")
            for warn in warnings[:20]:  # Show first 20
                print(f"   {warn}")
            if len(warnings) > 20:
                print(f"   ... and {len(warnings) - 20} more warnings")

    # Detailed breakdown by source
    print("\n" + "="*80)
    print("BREAKDOWN BY SOURCE")
    print("="*80)

    gold_problems = [p for p in csv_problems if p['confidence_level'] == 'gold']
    bronze_problems = [p for p in csv_problems if p['confidence_level'] == 'bronze']

    print(f"\nGold problems ({len(gold_problems)}):")
    gold_with_schema = 0
    gold_without_schema = 0
    for p in gold_problems:
        pid = p['problem_id']
        if pid in json_data and json_data[pid].get('expected_schema'):
            gold_with_schema += 1
        else:
            gold_without_schema += 1
    print(f"   With schema:    {gold_with_schema}")
    print(f"   Without schema: {gold_without_schema}")

    print(f"\nBronze problems ({len(bronze_problems)}):")
    bronze_with_schema = 0
    bronze_without_schema = 0
    for p in bronze_problems:
        pid = p['problem_id']
        if pid in json_data and json_data[pid].get('expected_schema'):
            bronze_with_schema += 1
        else:
            bronze_without_schema += 1
    print(f"   With schema:    {bronze_with_schema}")
    print(f"   Without schema: {bronze_without_schema}")

    print("\n" + "="*80)

    return len(errors) == 0

if __name__ == '__main__':
    import sys
    success = validate_json()
    sys.exit(0 if success else 1)
