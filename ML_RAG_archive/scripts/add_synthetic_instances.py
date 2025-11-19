#!/usr/bin/env python3
"""
Add Synthetic Single-Stage Scheduling Instances

The OR-Library doesn't have many single-stage scheduling instances,
but this is critical for the classifier (distinguishing from job-shop).

This script generates realistic single-stage scheduling instances with
varied phrasing to help the ML classifier learn the distinction.

Target: Add 20-30 single-stage scheduling instances
"""

import csv
import random
from pathlib import Path

# Templates for single-stage scheduling
SINGLE_STAGE_TEMPLATES = [
    # Template 1: Explicit "choose which machine" phrasing
    {
        'pattern': 'choose',
        'text': "Schedule {jobs} orders on {machines} parallel machines. Each order requires exactly one operation. "
                "Choose which machine processes each order to minimize makespan. "
                "Processing times: {examples}. No machine can process multiple orders simultaneously.",
        'key_clues': 'one_operation choose_machine parallel_machines OR_choice'
    },
    # Template 2: Assignment/allocation phrasing
    {
        'pattern': 'assign',
        'text': "Allocate {jobs} jobs to {machines} identical parallel machines. Each job has a single processing operation. "
                "Assign each job to one machine to minimize total completion time. "
                "Example processing times: {examples}. Each machine handles one job at a time.",
        'key_clues': 'one_operation assign allocate parallel identical_machines'
    },
    # Template 3: Eligible machines phrasing
    {
        'pattern': 'eligible',
        'text': "Process {jobs} tasks on {machines} machines where each task can be processed on any eligible machine. "
                "Tasks have one operation each. "
                "Task processing times: {examples}. Select which eligible machine processes each task to minimize makespan.",
        'key_clues': 'one_operation eligible_machines select_machine any_machine'
    },
    # Template 4: Parallel processing phrasing
    {
        'pattern': 'parallel',
        'text': "A parallel machine scheduling problem with {jobs} jobs and {machines} machines. "
                "Each job has one operation and can run on any machine. "
                "Jobs: {examples}. Determine the machine assignment that minimizes completion time.",
        'key_clues': 'one_operation parallel_machines can_run_on determine_assignment'
    },
    # Template 5: Unrelated machines variant
    {
        'pattern': 'unrelated',
        'text': "Schedule {jobs} independent jobs on {machines} unrelated parallel machines. "
                "Each job requires processing once (single operation) with machine-dependent processing times. "
                "Job examples: {examples}. Assign jobs to machines optimally.",
        'key_clues': 'one_operation unrelated_machines independent single_operation machine_dependent'
    },
]

def generate_processing_times(num_jobs: int, num_machines: int) -> str:
    """Generate example processing times for display."""
    examples = []
    for j in range(min(3, num_jobs)):  # Show first 3 jobs
        time = random.randint(10, 100)
        examples.append(f"Job{j+1}={time}min")
    return ", ".join(examples)


def generate_single_stage_instances(count: int = 25) -> list:
    """Generate synthetic single-stage scheduling instances."""
    instances = []

    # Vary problem sizes
    sizes = [
        (5, 2), (10, 3), (15, 4), (20, 5), (25, 5),
        (30, 6), (40, 8), (50, 10), (100, 20)
    ]

    for i in range(count):
        # Pick template and size
        template = random.choice(SINGLE_STAGE_TEMPLATES)
        jobs, machines = random.choice(sizes)

        # Generate processing time examples
        examples = generate_processing_times(jobs, machines)

        # Fill template
        text = template['text'].format(
            jobs=jobs,
            machines=machines,
            examples=examples
        )

        instances.append({
            'id': f'sched/single_stage/syn{i+1:03d}',
            'title': f'Single-Stage Scheduling Synthetic {i+1}',
            'text': text,
            'level1_family': 'scheduling',
            'subtype': 'single_stage_scheduling',
            'key_clues': template['key_clues'],
            'num_jobs': jobs,
            'num_machines': machines,
            'numbers_present': 'yes',
            'integrality_implied': 'yes',
            'source_url': 'synthetic_generated'
        })

    return instances


def generate_transportation_instances(count: int = 15) -> list:
    """Generate synthetic transportation instances."""
    instances = []

    # Transportation templates
    templates = [
        {
            'pattern': 'ship',
            'text': "Ship from {sources} warehouses to {sinks} customers. "
                    "Warehouse supply: {supply_ex}. Customer demand: {demand_ex}. "
                    "Shipping costs per unit: {cost_ex}. Minimize total shipping cost.",
            'key_clues': 'ship warehouses customers supply_demand bipartite sources_sinks'
        },
        {
            'pattern': 'transport',
            'text': "A transportation problem with {sources} factories and {sinks} markets. "
                    "Factory capacities: {supply_ex}. Market requirements: {demand_ex}. "
                    "Transportation costs: {cost_ex}. Minimize total cost.",
            'key_clues': 'factories markets capacities requirements transport minimize_cost'
        },
        {
            'pattern': 'distribute',
            'text': "Distribute goods from {sources} distribution centers to {sinks} retail stores. "
                    "Center inventory: {supply_ex}. Store demand: {demand_ex}. "
                    "Distribution cost matrix given. Find minimum cost distribution plan.",
            'key_clues': 'distribute centers stores inventory_demand distribution_plan'
        },
    ]

    # Vary problem sizes
    sizes = [
        (2, 3), (3, 4), (4, 5), (5, 6), (10, 15)
    ]

    for i in range(count):
        template = random.choice(templates)
        sources, sinks = random.choice(sizes)

        # Generate examples
        supply_ex = ", ".join([f"S{j+1}={random.randint(100,500)}" for j in range(min(2, sources))])
        demand_ex = ", ".join([f"D{j+1}={random.randint(50,200)}" for j in range(min(2, sinks))])
        cost_ex = f"S1→D1=${random.uniform(1,10):.2f}/unit"

        text = template['text'].format(
            sources=sources,
            sinks=sinks,
            supply_ex=supply_ex,
            demand_ex=demand_ex,
            cost_ex=cost_ex
        )

        instances.append({
            'id': f'transport/synthetic/syn{i+1:03d}',
            'title': f'Transportation Synthetic {i+1}',
            'text': text,
            'level1_family': 'transportation',
            'subtype': 'transportation',
            'key_clues': template['key_clues'],
            'num_sources': sources,
            'num_sinks': sinks,
            'numbers_present': 'yes',
            'integrality_implied': 'no',
            'source_url': 'synthetic_generated'
        })

    return instances


def main():
    print("="*80)
    print("  ADDING SYNTHETIC INSTANCES")
    print("="*80)
    print()

    # Load existing dataset
    existing_path = Path('knowledge/ml_training_dataset.csv')

    if not existing_path.exists():
        print(f"✗ ERROR: {existing_path} not found. Run build_training_dataset.py first.")
        return 1

    # Read existing instances
    with open(existing_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        existing = list(reader)
        fieldnames = reader.fieldnames

    print(f"Loaded {len(existing)} existing instances")
    print()

    # Generate new instances
    print("[1/2] Generating Single-Stage Scheduling Instances...")
    single_stage = generate_single_stage_instances(25)
    print(f"  ✓ Generated {len(single_stage)} instances")

    print("\n[2/2] Generating Transportation Instances...")
    transportation = generate_transportation_instances(15)
    print(f"  ✓ Generated {len(transportation)} instances")

    # Merge all instances
    all_instances = existing + single_stage + transportation

    # Get all field names
    all_fieldnames = set(fieldnames)
    for inst in all_instances:
        all_fieldnames.update(inst.keys())

    all_fieldnames = sorted(list(all_fieldnames))

    # Write combined dataset
    print(f"\n{'='*80}")
    print(f"  WRITING {len(all_instances)} INSTANCES")
    print(f"{'='*80}\n")

    with open(existing_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_fieldnames)
        writer.writeheader()
        writer.writerows(all_instances)

    print(f"✓ Dataset updated: {existing_path}")
    print(f"  Total instances: {len(all_instances)}")

    # Print breakdown
    from collections import Counter
    subtype_counts = Counter(inst['subtype'] for inst in all_instances)

    print(f"\n  Breakdown by subtype:")
    for subtype, count in subtype_counts.most_common():
        print(f"    {subtype}: {count}")

    print()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
