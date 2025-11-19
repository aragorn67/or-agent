#!/usr/bin/env python3
"""
Create Final Comprehensive ML Classifier Dataset

Merges ALL sources:
1. OR-Library (134): job-shop, flow-shop, knapsack, facility location
2. Synthetic (83): scheduling, transportation, assignment, knapsack, facility, bin packing
3. Chain-of-Experts (306): LPWP + ComplexOR

Total: ~523 instances across 20+ problem types

Output: knowledge/FINAL_ML_DATASET.csv
"""

import csv
from pathlib import Path
from collections import defaultdict


def load_csv(filepath):
    """Load CSV and return list of dicts."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception as e:
        print(f"  Error loading {filepath}: {e}")
        return []


def standardize_fields(instance):
    """Standardize field names across all sources."""
    # Ensure all required fields exist
    required_fields = ['id', 'title', 'text', 'level1_family', 'subtype',
                      'key_clues', 'numbers_present', 'integrality_implied', 'source_url']

    standardized = {}
    for field in required_fields:
        standardized[field] = instance.get(field, '')

    # Add optional metadata fields
    optional_fields = ['num_jobs', 'num_machines', 'num_sources', 'num_sinks',
                      'num_workers', 'num_tasks', 'num_items', 'num_constraints',
                      'num_facilities', 'num_customers', 'bin_capacity', 'capacity',
                      'size', 'source_type']

    for field in optional_fields:
        if field in instance:
            standardized[field] = instance[field]

    return standardized


def main():
    print("="*80)
    print("CREATING FINAL COMPREHENSIVE ML CLASSIFIER DATASET")
    print("="*80)

    all_instances = []

    # 1. Load OR-Library scheduling (job-shop + flow-shop)
    print("\n1. Loading OR-Library scheduling...")
    orlib_data = load_csv('knowledge/ml_training_dataset.csv')
    orlib_sched = [row for row in orlib_data if row.get('subtype') in ['job_shop', 'flow_shop']]
    print(f"   ✓ {len(orlib_sched)} instances (job-shop + flow-shop)")
    all_instances.extend([standardize_fields(row) for row in orlib_sched])

    # 2. Load varied synthetic (single-stage + transportation)
    print("\n2. Loading varied synthetic...")
    varied_syn = load_csv('knowledge/synthetic_varied.csv')
    print(f"   ✓ {len(varied_syn)} instances (single-stage + transportation)")
    all_instances.extend([standardize_fields(row) for row in varied_syn])

    # 3. Load new synthetic problem types (assignment, knapsack, facility, bin packing)
    print("\n3. Loading new synthetic problem types...")
    new_types = load_csv('knowledge/all_new_problem_types.csv')
    print(f"   ✓ {len(new_types)} instances (assignment, knapsack, facility, bin packing)")
    all_instances.extend([standardize_fields(row) for row in new_types])

    # 4. Load OR-Library knapsack and facility location
    print("\n4. Loading OR-Library knapsack + facility...")
    new_or = load_csv('knowledge/new_or_problems.csv')
    print(f"   ✓ {len(new_or)} instances (knapsack + facility from OR-Library)")
    all_instances.extend([standardize_fields(row) for row in new_or])

    # 5. Load Chain-of-Experts (LPWP + ComplexOR)
    print("\n5. Loading Chain-of-Experts...")
    coe = load_csv('knowledge/chain_of_experts_problems.csv')
    print(f"   ✓ {len(coe)} instances (LPWP + ComplexOR)")
    all_instances.extend([standardize_fields(row) for row in coe])

    print(f"\n{'='*80}")
    print(f"TOTAL INSTANCES: {len(all_instances)}")
    print(f"{'='*80}")

    # Count by problem type
    type_counts = defaultdict(int)
    family_counts = defaultdict(int)
    source_counts = defaultdict(int)

    for inst in all_instances:
        subtype = inst.get('subtype', 'unknown')
        family = inst.get('level1_family', 'unknown')
        source = inst.get('source_url', 'unknown')

        type_counts[subtype] += 1
        family_counts[family] += 1

        # Simplify source tracking
        if 'OR-Library' in source or 'orlib' in source:
            source_counts['OR-Library'] += 1
        elif 'synthetic' in source.lower():
            source_counts['Synthetic'] += 1
        elif 'Chain-of-Experts' in source or 'LPWP' in source or 'ComplexOR' in source:
            source_counts['Chain-of-Experts'] += 1
        else:
            source_counts['Other'] += 1

    # Print statistics
    print(f"\nBreakdown by PROBLEM TYPE ({len(type_counts)} types):")
    for subtype in sorted(type_counts.keys(), key=lambda x: type_counts[x], reverse=True):
        print(f"  {subtype}: {type_counts[subtype]}")

    print(f"\nBreakdown by FAMILY ({len(family_counts)} families):")
    for family in sorted(family_counts.keys(), key=lambda x: family_counts[x], reverse=True):
        print(f"  {family}: {family_counts[family]}")

    print(f"\nBreakdown by SOURCE:")
    for source in sorted(source_counts.keys()):
        print(f"  {source}: {source_counts[source]}")

    # Save final dataset
    output_file = 'knowledge/FINAL_ML_DATASET.csv'

    # Collect all possible fieldnames
    all_fields = set()
    for inst in all_instances:
        all_fields.update(inst.keys())

    # Order fieldnames logically
    primary_fields = ['id', 'title', 'text', 'level1_family', 'subtype', 'key_clues',
                     'numbers_present', 'integrality_implied', 'source_url']

    fieldnames = [f for f in primary_fields if f in all_fields]
    fieldnames += sorted([f for f in all_fields if f not in primary_fields])

    print(f"\n{'='*80}")
    print(f"SAVING TO {output_file}")
    print(f"{'='*80}")

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for inst in all_instances:
            row = {k: inst.get(k, '') for k in fieldnames}
            writer.writerow(row)

    print(f"✓ Saved {len(all_instances)} instances!")
    print(f"\nColumns in CSV:")
    print(f"  {', '.join(fieldnames)}")

    print(f"\n{'='*80}")
    print("DATASET READY FOR TRAINING!")
    print(f"{'='*80}")
    print(f"\nNext step:")
    print(f"  python scripts/train_classifier.py")

    # Print final summary statistics
    print(f"\n{'='*80}")
    print("FINAL DATASET STATISTICS")
    print(f"{'='*80}")
    print(f"Total instances: {len(all_instances)}")
    print(f"Problem types: {len(type_counts)}")
    print(f"Problem families: {len(family_counts)}")
    print(f"Data sources: {len(source_counts)}")

    # Quality checks
    with_numbers = sum(1 for i in all_instances if i.get('numbers_present') == 'yes')
    print(f"\nQuality metrics:")
    print(f"  Instances with numbers: {with_numbers} ({with_numbers/len(all_instances)*100:.1f}%)")
    print(f"  Average text length: {sum(len(i.get('text', '')) for i in all_instances)//len(all_instances)} chars")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
