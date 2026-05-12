#!/usr/bin/env python3
"""
Find 20 good non-synthetic problems from ML dataset
(10 transport + 10 scheduling)
"""

import csv
from pathlib import Path

ml_csv_path = Path(__file__).parent.parent.parent / 'ML_RAG_archive' / 'ML_approaches' / 'ML' / 'FINAL_ML_DATASET.csv'

with open(ml_csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    problems = list(reader)

# Filter non-synthetic
non_synthetic = [p for p in problems if 'synthetic' not in p['id'].lower() and 'syn' not in p['id'].lower()]

print(f"Total non-synthetic problems: {len(non_synthetic)}")

# Get transportation
transport = [p for p in non_synthetic if p['level1_family'].lower() == 'transportation']
print(f"Transportation: {len(transport)}")

# Get scheduling
scheduling = [p for p in non_synthetic if p['level1_family'].lower() == 'scheduling']
print(f"Scheduling: {len(scheduling)}")

print("\n" + "="*80)
print("TRANSPORTATION PROBLEMS (first 10)")
print("="*80)
for i, p in enumerate(transport[:10], 1):
    print(f"\n{i}. {p['id']}")
    print(f"   Subtype: {p['subtype']}")
    print(f"   Description: {p['text'][:150]}...")

print("\n" + "="*80)
print("SCHEDULING PROBLEMS (first 10)")
print("="*80)
for i, p in enumerate(scheduling[:10], 1):
    print(f"\n{i}. {p['id']}")
    print(f"   Subtype: {p['subtype']}")
    print(f"   Description: {p['text'][:150]}...")

# Save to file for review
selected = transport[:10] + scheduling[:10]

output_path = Path(__file__).parent / 'selected_20_problems.csv'
with open(output_path, 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['id', 'title', 'level1_family', 'subtype', 'text']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for p in selected:
        writer.writerow({k: p[k] for k in fieldnames})

print(f"\n✓ Saved 20 problems to: {output_path}")
