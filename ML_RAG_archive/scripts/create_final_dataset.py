#!/usr/bin/env python3
"""
Create Final ML Classifier Training Dataset

Merges all problem sources into one comprehensive dataset:
1. OR-Library job-shop (82)
2. OR-Library flow-shop (31)
3. OR-Library knapsack (11 from mknap files)
4. OR-Library facility location (10 from cap files)
5. Synthetic single-stage scheduling (15)
6. Synthetic transportation (8)
7. Synthetic assignment (15)
8. Synthetic knapsack (20)
9. Synthetic facility location (15)
10. Synthetic bin packing (10)

Output: knowledge/final_ml_dataset.csv with ~217 instances
"""

import csv
from pathlib import Path


def load_csv(filepath):
    """Load CSV and return list of dicts."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        print(f"  Error loading {filepath}: {e}")
        return []


def main():
    print("="*80)
    print("CREATING FINAL ML CLASSIFIER DATASET")
    print("="*80)

    all_instances = []

    # 1. Load OR-Library scheduling (job-shop + flow-shop)
    print("\n1. Loading OR-Library scheduling...")
    orlib_data = load_csv('knowledge/ml_training_dataset.csv')
    orlib_sched = [row for row in orlib_data if row.get('subtype') in ['job_shop', 'flow_shop']]
    print(f"   ✓ {len(orlib_sched)} instances (job-shop + flow-shop)")
    all_instances.extend(orlib_sched)

    # 2. Load varied synthetic (single-stage + transportation)
    print("\n2. Loading varied synthetic...")
    varied_syn = load_csv('knowledge/synthetic_varied.csv')
    print(f"   ✓ {len(varied_syn)} instances (single-stage + transportation)")
    all_instances.extend(varied_syn)

    # 3. Load new problem types (assignment, knapsack, facility, bin packing)
    print("\n3. Loading new problem types...")
    new_types = load_csv('knowledge/all_new_problem_types.csv')
    print(f"   ✓ {len(new_types)} instances (assignment, knapsack, facility, bin packing)")
    all_instances.extend(new_types)

    # 4. Load OR-Library knapsack and facility location if they exist
    print("\n4. Loading OR-Library knapsack + facility...")
    new_or = load_csv('knowledge/new_or_problems.csv')
    print(f"   ✓ {len(new_or)} instances (knapsack + facility from OR-Library)")
    all_instances.extend(new_or)

    print(f"\n{'='*80}")
    print(f"TOTAL INSTANCES: {len(all_instances)}")
    print(f"{'='*80}")

    # Count by type
    type_counts = {}
    for inst in all_instances:
        subtype = inst.get('subtype', 'unknown')
        type_counts[subtype] = type_counts.get(subtype, 0) + 1

    print(f"\nBreakdown by problem type:")
    for subtype in sorted(type_counts.keys()):
        print(f"  {subtype}: {type_counts[subtype]}")

    # Save final dataset
    output_file = 'knowledge/final_ml_dataset.csv'

    # Collect all possible fieldnames
    all_fields = set()
    for inst in all_instances:
        all_fields.update(inst.keys())

    # Order fieldnames logically
    primary_fields = ['id', 'title', 'text', 'level1_family', 'subtype', 'key_clues',
                     'numbers_present', 'integrality_implied', 'source_url']

    fieldnames = [f for f in primary_fields if f in all_fields]
    fieldnames += sorted([f for f in all_fields if f not in primary_fields])

    print(f"\nSaving to {output_file}...")

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for inst in all_instances:
            row = {k: inst.get(k, '') for k in fieldnames}
            writer.writerow(row)

    print(f"✓ Saved {len(all_instances)} instances!")

    print(f"\n{'='*80}")
    print("DATASET READY FOR TRAINING!")
    print(f"{'='*80}")
    print(f"\nNext step:")
    print(f"  python scripts/train_classifier.py")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
