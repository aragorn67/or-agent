#!/usr/bin/env python3
"""
Extract ALL Chain-of-Experts Problems for ML Classifier

Extracts:
1. LPWP: 288 Linear Programming Word Problems
2. ComplexOR: 18 Complex OR problems with descriptions

Enhances descriptions that lack detail by adding context from sample data.

Output: knowledge/chain_of_experts_problems.csv
"""

import os
import json
import csv
import re
from pathlib import Path


def extract_lpwp_problems(base_path='knowledge/Chain-of-Experts-main/dataset/LPWP'):
    """Extract all 288 LPWP problems."""
    print("\n" + "="*80)
    print("EXTRACTING LPWP (Linear Programming Word Problems)")
    print("="*80)

    instances = []
    base_dir = Path(base_path)

    # Find all prob_* directories
    prob_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith('prob_')])

    print(f"Found {len(prob_dirs)} problem directories")

    for prob_dir in prob_dirs:
        desc_file = prob_dir / 'description.txt'
        sample_file = prob_dir / 'sample.json'

        if not desc_file.exists():
            print(f"  Warning: No description for {prob_dir.name}")
            continue

        # Read description
        with open(desc_file, 'r', encoding='utf-8') as f:
            description = f.read().strip()

        # Try to read sample data for enhancement
        sample_data = None
        if sample_file.exists():
            try:
                with open(sample_file, 'r', encoding='utf-8') as f:
                    sample_data = json.load(f)
            except:
                pass

        # Enhance description if it's too short or lacks numbers
        enhanced_desc = enhance_description(description, sample_data, prob_dir.name)

        # Classify problem type
        problem_type, problem_family = classify_lpwp_problem(enhanced_desc)

        instances.append({
            'id': f'lpwp/{prob_dir.name}',
            'title': f'LPWP {prob_dir.name}',
            'text': enhanced_desc,
            'level1_family': problem_family,
            'subtype': problem_type,
            'key_clues': extract_key_clues(enhanced_desc),
            'numbers_present': 'yes' if has_numbers(enhanced_desc) else 'no',
            'integrality_implied': 'yes' if 'integer' in enhanced_desc.lower() or 'whole' in enhanced_desc.lower() else 'no',
            'source_url': 'Chain-of-Experts/LPWP',
            'source_type': 'LPWP'
        })

    print(f"✓ Extracted {len(instances)} LPWP problems")
    return instances


def extract_complexor_problems(base_path='knowledge/Chain-of-Experts-main/dataset/ComplexOR'):
    """Extract 18 ComplexOR problems."""
    print("\n" + "="*80)
    print("EXTRACTING ComplexOR Problems")
    print("="*80)

    instances = []
    base_dir = Path(base_path)

    prob_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir()])
    print(f"Found {len(prob_dirs)} problem directories")

    for prob_dir in prob_dirs:
        desc_file = prob_dir / 'description.txt'

        if not desc_file.exists():
            print(f"  Warning: No description for {prob_dir.name}")
            continue

        with open(desc_file, 'r', encoding='utf-8') as f:
            description = f.read().strip()

        # Map problem names to types
        problem_name = prob_dir.name
        problem_type, problem_family = classify_complexor_problem(problem_name, description)

        instances.append({
            'id': f'complexor/{problem_name}',
            'title': f'ComplexOR {problem_name.replace("_", " ").title()}',
            'text': description,
            'level1_family': problem_family,
            'subtype': problem_type,
            'key_clues': extract_key_clues(description),
            'numbers_present': 'yes' if has_numbers(description) else 'no',
            'integrality_implied': 'yes' if 'integer' in description.lower() else 'no',
            'source_url': 'Chain-of-Experts/ComplexOR',
            'source_type': 'ComplexOR'
        })

    print(f"✓ Extracted {len(instances)} ComplexOR problems")
    return instances


def enhance_description(desc, sample_data, prob_name):
    """Enhance descriptions that are too short or lack numerical values."""

    # Check if description needs enhancement
    word_count = len(desc.split())
    has_nums = bool(re.search(r'\d+', desc))

    # If description is good (>30 words and has numbers), return as is
    if word_count > 30 and has_nums:
        return desc

    # If very short or no numbers, try to add context from sample data
    if sample_data and word_count < 50:
        enhanced = desc + "\n\n"

        # Add sample numerical values if available
        if 'parameters' in sample_data:
            params = sample_data['parameters']
            if isinstance(params, dict):
                example_params = []
                for key, value in list(params.items())[:3]:
                    example_params.append(f"{key}={value}")
                if example_params:
                    enhanced += f"Example parameters: {', '.join(example_params)}. "

        return enhanced.strip()

    return desc


def classify_lpwp_problem(description):
    """Classify LPWP problem into type and family."""
    desc_lower = description.lower()

    # Check for specific problem types
    if any(word in desc_lower for word in ['transport', 'ship', 'deliver', 'route', 'truck', 'vehicle']):
        if 'route' in desc_lower or 'path' in desc_lower or 'tsp' in desc_lower:
            return 'vehicle_routing', 'routing'
        return 'transportation', 'transportation'

    if any(word in desc_lower for word in ['schedule', 'shift', 'job', 'task', 'machine', 'time']):
        if 'job' in desc_lower and 'machine' in desc_lower:
            return 'job_shop', 'scheduling'
        return 'scheduling', 'scheduling'

    if any(word in desc_lower for word in ['blend', 'mix', 'diet', 'recipe', 'ingredient']):
        return 'blending', 'production_planning'

    if any(word in desc_lower for word in ['invest', 'portfolio', 'stock', 'bond', 'asset']):
        return 'portfolio_optimization', 'financial'

    if any(word in desc_lower for word in ['facility', 'warehouse', 'location', 'site', 'open']):
        return 'facility_location', 'facility_location'

    if any(word in desc_lower for word in ['assign', 'allocat', 'match']):
        return 'assignment', 'assignment'

    if any(word in desc_lower for word in ['production', 'manufactur', 'produce', 'unit']):
        return 'production_planning', 'production_planning'

    if any(word in desc_lower for word in ['staff', 'worker', 'employee', 'personnel', 'crew']):
        return 'workforce_planning', 'scheduling'

    # Default to linear programming
    return 'linear_programming', 'optimization'


def classify_complexor_problem(name, description):
    """Classify ComplexOR problem."""
    name_lower = name.lower()
    desc_lower = description.lower()

    mapping = {
        'flowshop': ('flow_shop', 'scheduling'),
        'knapsack': ('knapsack', 'knapsack'),
        'cell_tower': ('facility_location', 'facility_location'),
        'aircraft': ('aircraft_assignment', 'scheduling'),
        'cutting': ('cutting_stock', 'cutting_packing'),
        'diet': ('diet_problem', 'production_planning'),
        'vehicle': ('vehicle_routing', 'routing'),
        'media': ('media_selection', 'optimization'),
        'steel': ('production_planning', 'production_planning'),
        'revenue': ('revenue_maximization', 'optimization'),
        'blend': ('blending', 'production_planning'),
        'car': ('selection_problem', 'optimization'),
        'nltrans': ('network_flow', 'network_flow'),
        'netasgn': ('network_assignment', 'network_flow'),
        'netmcol': ('network_multicommodity', 'network_flow'),
        'multi': ('multicommodity_flow', 'network_flow'),
        'prod': ('production_planning', 'production_planning')
    }

    for key, (subtype, family) in mapping.items():
        if key in name_lower:
            return subtype, family

    return 'optimization', 'optimization'


def extract_key_clues(text):
    """Extract key clue words from description."""
    clue_words = []
    text_lower = text.lower()

    # Common OR keywords
    keywords = {
        'minimize', 'maximize', 'optimize', 'constraint', 'budget',
        'capacity', 'demand', 'supply', 'cost', 'profit', 'revenue',
        'schedule', 'assign', 'allocate', 'transport', 'ship',
        'produce', 'manufacture', 'blend', 'mix', 'select', 'choose'
    }

    for keyword in keywords:
        if keyword in text_lower:
            clue_words.append(keyword)

    return ' '.join(clue_words[:10])  # Limit to 10 clues


def has_numbers(text):
    """Check if text contains numerical values."""
    return bool(re.search(r'\d+', text))


def main():
    print("="*80)
    print("CHAIN-OF-EXPERTS PROBLEM EXTRACTION")
    print("="*80)

    all_instances = []

    # Extract LPWP problems
    lpwp_instances = extract_lpwp_problems()
    all_instances.extend(lpwp_instances)

    # Extract ComplexOR problems
    complexor_instances = extract_complexor_problems()
    all_instances.extend(complexor_instances)

    # Save to CSV
    output_file = 'knowledge/chain_of_experts_problems.csv'

    fieldnames = ['id', 'title', 'text', 'level1_family', 'subtype', 'key_clues',
                  'numbers_present', 'integrality_implied', 'source_url', 'source_type']

    print(f"\n{'='*80}")
    print(f"SAVING {len(all_instances)} PROBLEMS")
    print(f"{'='*80}")

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_instances)

    print(f"✓ Saved to: {output_file}")

    # Print summary
    print(f"\n{'='*80}")
    print("SUMMARY BY PROBLEM TYPE")
    print(f"{'='*80}")

    type_counts = {}
    for inst in all_instances:
        subtype = inst['subtype']
        type_counts[subtype] = type_counts.get(subtype, 0) + 1

    for subtype in sorted(type_counts.keys()):
        print(f"  {subtype}: {type_counts[subtype]}")

    print(f"\nTotal: {len(all_instances)} problems")
    print(f"  - LPWP: {len(lpwp_instances)}")
    print(f"  - ComplexOR: {len(complexor_instances)}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
