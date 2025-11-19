#!/usr/bin/env python3
"""
Generate Varied Synthetic OR Problem Instances

Creates diverse single-stage scheduling and transportation problems with:
- Variable length (short/medium/long descriptions)
- Different writing styles (formal/casual, creative/rigid)
- Realistic business contexts
- 15% of total dataset should be synthetic (~23 instances from 150 total)

Output: Appends to knowledge/ml_training_dataset.csv
"""

import csv
import random
from pathlib import Path


# ====================================================================================
# SINGLE-STAGE SCHEDULING TEMPLATES (15 instances)
# ====================================================================================

SINGLE_STAGE_SHORT = [
    # Very concise, rigid
    "{jobs} jobs, {machines} machines. Each job: one operation. Minimize makespan. Job1={t1}min, Job2={t2}min, Job3={t3}min.",

    # Technical, brief
    "Parallel machine problem: {jobs} independent jobs on {machines} identical machines. Single operation per job. Examples: J1={t1}, J2={t2}, J3={t3}. Minimize Cmax.",

    # Business casual, short
    "We have {jobs} orders to process using {machines} machines. Each order needs one operation. Order A takes {t1} minutes, Order B takes {t2} minutes. Which machine handles which order?",
]

SINGLE_STAGE_MEDIUM = [
    # Formal business
    "A manufacturing facility operates {machines} parallel production lines for processing {jobs} customer orders. "
    "Each order requires a single machining operation and can be assigned to any available line. "
    "Processing times vary: Order-1 requires {t1} minutes, Order-2 needs {t2} minutes, Order-3 takes {t3} minutes. "
    "Determine the optimal assignment to minimize total completion time.",

    # Creative storytelling
    "The logistics team at a warehouse must schedule {jobs} shipment packages across {machines} packing stations. "
    "Each package goes through one packing step and workers can choose any available station. "
    "Package processing: first package {t1}min, second {t2}min, third {t3}min. "
    "How should packages be distributed to finish earliest?",

    # Academic style
    "Consider a single-stage scheduling environment with {jobs} tasks and {machines} unrelated parallel processors. "
    "Task execution requires exactly one operation with machine-dependent processing times. "
    "Representative tasks: τ₁({t1}), τ₂({t2}), τ₃({t3}) time units. "
    "Objective: minimize makespan.",
]

SINGLE_STAGE_LONG = [
    # Detailed business case
    "TechPrint Solutions operates a digital printing facility with {machines} high-speed printers that can handle various job types. "
    "Today they received {jobs} urgent print jobs from different clients. Each print job consists of a single print run "
    "and can be processed on any of the available printers since they're all identical models. "
    "The print jobs have different page counts and complexity levels, resulting in varied processing times. "
    "For instance, the first job (a corporate brochure) will take approximately {t1} minutes, "
    "the second job (marketing flyers) needs about {t2} minutes, "
    "and the third job (a technical manual) requires {t3} minutes to complete. "
    "The production manager needs to decide which printer should handle which job to ensure all jobs finish as quickly as possible. "
    "This is a classic parallel machine scheduling problem where the goal is to minimize the makespan - "
    "the time when the last job finishes processing.",

    # Research/experimental
    "In our computational study, we examine a scheduling scenario common in semiconductor manufacturing. "
    "A fabrication facility has {machines} identical photolithography machines available for processing {jobs} wafer lots. "
    "Each wafer lot undergoes one photolithography step before moving to the next stage. "
    "The flexibility of the system allows any lot to be processed on any machine, creating a parallel machine environment. "
    "Processing times are determined by wafer size and pattern complexity. Sample lots: "
    "Lot A requires {t1} minutes (200mm wafers, simple pattern), "
    "Lot B needs {t2} minutes (300mm wafers, medium complexity), "
    "Lot C takes {t3} minutes (300mm wafers, advanced features). "
    "We seek an allocation strategy that minimizes the maximum completion time across all machines.",
]


# ====================================================================================
# TRANSPORTATION TEMPLATES (8 instances)
# ====================================================================================

TRANSPORT_SHORT = [
    # Minimal
    "{sources} plants, {sinks} customers. Plant A: {cap1} units. Customer X needs {dem1} units. Cost: ${cost1}/unit. Minimize total cost.",

    # Technical brief
    "Transportation LP: {sources} origins, {sinks} destinations. Supply={cap1}, demand={dem1}. Shipping costs vary. Find min-cost flow.",
]

TRANSPORT_MEDIUM = [
    # Business formal
    "A beverage distribution company operates {sources} regional warehouses supplying {sinks} retail chains. "
    "Warehouse Alpha can supply up to {cap1} pallets weekly, while warehouse Beta handles {cap2} pallets. "
    "Retail chain North requires {dem1} pallets, South needs {dem2} pallets. "
    "Transportation costs: Alpha→North ${cost1}/pallet, Alpha→South ${cost2}/pallet. "
    "Determine shipment quantities to minimize total distribution cost.",

    # Operational context
    "GlobalTech manufactures laptops at {sources} factories: Singapore (capacity {cap1} units/month) and Mexico (capacity {cap2} units/month). "
    "They serve {sinks} distribution hubs: USA hub (demand {dem1} units), Europe hub (demand {dem2} units). "
    "Shipping costs per unit: Singapore→USA ${cost1}, Singapore→Europe ${cost2}, Mexico→USA ${cost3}, Mexico→Europe ${cost4}. "
    "What shipping plan minimizes total logistics costs?",
]

TRANSPORT_LONG = [
    # Detailed case study
    "EuroSteel AG is a major steel producer with manufacturing plants in two locations: "
    "the Ruhr Valley plant in Germany with a monthly production capacity of {cap1} tonnes, "
    "and the Sheffield plant in the UK capable of producing {cap2} tonnes per month. "
    "The company supplies steel to three major construction projects across Europe. "
    "Project A in Amsterdam requires {dem1} tonnes monthly for a new bridge construction, "
    "Project B in Paris needs {dem2} tonnes for a high-rise development, "
    "and Project C in Brussels demands {dem3} tonnes for infrastructure renewal. "
    "Transportation costs vary significantly based on distance and logistics infrastructure: "
    "shipping from Ruhr Valley to Amsterdam costs €{cost1} per tonne, to Paris €{cost2} per tonne, to Brussels €{cost3} per tonne; "
    "while from Sheffield, costs are €{cost4} to Amsterdam, €{cost5} to Paris, and €{cost6} to Brussels. "
    "The logistics director must determine the optimal shipping quantities from each plant to each project "
    "to minimize total transportation expenditure while meeting all project demands and respecting plant capacities.",
]


# ====================================================================================
# GENERATION FUNCTIONS
# ====================================================================================

def generate_single_stage_instance(idx, length='medium'):
    """Generate one single-stage scheduling instance."""

    # Pick size
    if length == 'short':
        jobs = random.choice([5, 8, 10])
        machines = random.choice([2, 3])
        templates = SINGLE_STAGE_SHORT
    elif length == 'medium':
        jobs = random.choice([15, 20, 25, 30])
        machines = random.choice([3, 4, 5])
        templates = SINGLE_STAGE_MEDIUM
    else:  # long
        jobs = random.choice([40, 50, 60, 100])
        machines = random.choice([6, 8, 10, 15])
        templates = SINGLE_STAGE_LONG

    # Generate times
    t1 = random.randint(10, 50)
    t2 = random.randint(15, 60)
    t3 = random.randint(20, 70)

    # Pick template and fill
    template = random.choice(templates)
    text = template.format(jobs=jobs, machines=machines, t1=t1, t2=t2, t3=t3)

    return {
        'id': f'sched/single_stage/syn{idx:03d}',
        'title': f'Single-Stage Scheduling Synthetic {idx}',
        'text': text,
        'level1_family': 'scheduling',
        'subtype': 'single_stage_scheduling',
        'key_clues': 'one_operation parallel_machines choose_machine single_stage',
        'numbers_present': 'yes',
        'integrality_implied': 'yes',
        'num_jobs': jobs,
        'num_machines': machines,
        'num_sources': '',
        'num_sinks': '',
        'source_url': 'synthetic_generated'
    }


def generate_transport_instance(idx, length='medium'):
    """Generate one transportation instance."""

    # Pick size
    if length == 'short':
        sources = random.choice([2, 3])
        sinks = random.choice([2, 3])
        templates = TRANSPORT_SHORT
    elif length == 'medium':
        sources = random.choice([2, 3])
        sinks = random.choice([3, 4])
        templates = TRANSPORT_MEDIUM
    else:  # long
        sources = random.choice([2, 3])
        sinks = random.choice([3, 4, 5])
        templates = TRANSPORT_LONG

    # Generate values
    cap1 = random.randint(100, 500)
    cap2 = random.randint(150, 400)
    dem1 = random.randint(80, 250)
    dem2 = random.randint(100, 300)
    dem3 = random.randint(50, 200)
    cost1 = random.randint(2, 10)
    cost2 = random.randint(3, 12)
    cost3 = random.randint(2, 8)
    cost4 = random.randint(4, 15)
    cost5 = random.randint(3, 10)
    cost6 = random.randint(2, 9)

    # Pick template and fill
    template = random.choice(templates)
    text = template.format(
        sources=sources, sinks=sinks,
        cap1=cap1, cap2=cap2,
        dem1=dem1, dem2=dem2, dem3=dem3,
        cost1=cost1, cost2=cost2, cost3=cost3,
        cost4=cost4, cost5=cost5, cost6=cost6
    )

    return {
        'id': f'transport/synthetic/syn{idx:03d}',
        'title': f'Transportation Synthetic {idx}',
        'text': text,
        'level1_family': 'transportation',
        'subtype': 'transportation',
        'key_clues': 'ship transport sources sinks supply demand cost minimize',
        'numbers_present': 'yes',
        'integrality_implied': 'no',
        'num_jobs': '',
        'num_machines': '',
        'num_sources': sources,
        'num_sinks': sinks,
        'source_url': 'synthetic_generated'
    }


def generate_varied_synthetic(total_count=23):
    """
    Generate 23 varied synthetic instances (15% of ~150 total).

    Distribution:
    - 15 single-stage scheduling (5 short, 6 medium, 4 long)
    - 8 transportation (2 short, 4 medium, 2 long)
    """

    instances = []

    # Single-stage scheduling (15 instances)
    print("Generating single-stage scheduling instances...")
    for i in range(5):
        instances.append(generate_single_stage_instance(i+1, 'short'))
    for i in range(6):
        instances.append(generate_single_stage_instance(i+6, 'medium'))
    for i in range(4):
        instances.append(generate_single_stage_instance(i+12, 'long'))

    # Transportation (8 instances)
    print("Generating transportation instances...")
    for i in range(2):
        instances.append(generate_transport_instance(i+1, 'short'))
    for i in range(4):
        instances.append(generate_transport_instance(i+3, 'medium'))
    for i in range(2):
        instances.append(generate_transport_instance(i+7, 'long'))

    return instances


def main():
    print("="*80)
    print("GENERATING VARIED SYNTHETIC INSTANCES")
    print("="*80)
    print("\nTarget: 23 instances (15% of ~150 total)")
    print("  - 15 single-stage scheduling (5 short, 6 medium, 4 long)")
    print("  - 8 transportation (2 short, 4 medium, 2 long)")
    print()

    # Generate instances
    instances = generate_varied_synthetic(23)

    # Save to CSV
    output_file = 'knowledge/synthetic_varied.csv'

    fieldnames = ['id', 'title', 'text', 'level1_family', 'subtype', 'key_clues',
                  'numbers_present', 'integrality_implied', 'num_jobs', 'num_machines',
                  'num_sources', 'num_sinks', 'source_url']

    print(f"Writing to {output_file}...")
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(instances)

    print(f"✓ Generated {len(instances)} instances")
    print(f"\nBreakdown:")
    print(f"  Single-stage scheduling: {sum(1 for i in instances if i['subtype'] == 'single_stage_scheduling')}")
    print(f"  Transportation: {sum(1 for i in instances if i['subtype'] == 'transportation')}")

    # Show samples
    print(f"\n{'='*80}")
    print("SAMPLE SHORT INSTANCE:")
    print(f"{'='*80}")
    short = [i for i in instances if 'syn001' in i['id'] or 'syn001' in i['id']][0]
    print(f"ID: {short['id']}")
    print(f"Text: {short['text'][:150]}...")

    print(f"\n{'='*80}")
    print("SAMPLE LONG INSTANCE:")
    print(f"{'='*80}")
    long = [i for i in instances if 'syn012' in i['id'] or 'syn015' in i['id']][0]
    print(f"ID: {long['id']}")
    print(f"Text: {long['text'][:200]}...")

    print(f"\n{'='*80}")
    print("NEXT STEPS:")
    print(f"{'='*80}")
    print("1. Review knowledge/synthetic_varied.csv")
    print("2. Merge with OR-Library data: python scripts/merge_datasets.py")
    print("3. Train classifier: python scripts/train_classifier.py")


if __name__ == "__main__":
    main()
