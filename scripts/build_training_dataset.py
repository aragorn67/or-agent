#!/usr/bin/env python3
"""
Build ML Classifier Training Dataset from OR-Library

This script downloads OR-Library instances and converts them to natural language
descriptions suitable for training an ML classifier.

Target: 100+ instances across scheduling and transportation categories

Sources:
- Job-shop scheduling: 82 instances
- Flow-shop scheduling: 31 instances
- Transportation/assignment: 20-30 instances

Output: knowledge/ml_training_dataset.csv
"""

import os
import sys
import requests
import csv
from pathlib import Path
from typing import List, Dict, Tuple


# OR-Library base URL
ORLIB_BASE = "https://people.brunel.ac.uk/~mastjjb/jeb/orlib/files"


class ORLibraryParser:
    """Parse OR-Library problem instances into natural language."""

    def __init__(self, output_dir: str = "knowledge/orlib_raw"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def download_file(self, filename: str) -> str:
        """Download a file from OR-Library."""
        url = f"{ORLIB_BASE}/{filename}"
        local_path = self.output_dir / filename

        if local_path.exists():
            print(f"  ✓ Already downloaded: {filename}")
            return str(local_path)

        try:
            print(f"  Downloading: {filename}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            with open(local_path, 'wb') as f:
                f.write(response.content)

            print(f"  ✓ Downloaded: {filename}")
            return str(local_path)

        except Exception as e:
            print(f"  ✗ Failed to download {filename}: {e}")
            return None

    def parse_jobshop(self, filepath: str, instance_id: str) -> List[Dict]:
        """
        Parse job-shop scheduling instance.

        Format (typical):
        Line 1: num_jobs num_machines
        Then for each job:
          machine_id processing_time machine_id processing_time ...
        """
        instances = []

        try:
            with open(filepath, 'r') as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            i = 0
            instance_num = 1

            while i < len(lines):
                parts = lines[i].split()
                if len(parts) < 2:
                    i += 1
                    continue

                try:
                    num_jobs = int(parts[0])
                    num_machines = int(parts[1])
                except ValueError:
                    i += 1
                    continue

                # Read job data
                job_descriptions = []
                for j in range(num_jobs):
                    i += 1
                    if i >= len(lines):
                        break

                    job_data = lines[i].split()
                    operations = []

                    # Parse machine-time pairs
                    for k in range(0, len(job_data), 2):
                        if k + 1 < len(job_data):
                            machine = int(job_data[k])
                            time = int(job_data[k + 1])
                            operations.append(f"M{machine}({time}min)")

                    if operations:
                        job_descriptions.append(f"Job{j+1}: {' → '.join(operations)}")

                # Create natural language description
                text = f"A job shop scheduling problem with {num_jobs} jobs and {num_machines} machines. "
                text += "Each job must be processed through a sequence of machines in a specific order. "
                text += f"Jobs have the following routes: {'; '.join(job_descriptions[:3])}"  # Show first 3
                if len(job_descriptions) > 3:
                    text += f" and {len(job_descriptions) - 3} more jobs"
                text += ". Each machine can process only one job at a time. Minimize makespan."

                instances.append({
                    'id': f'jobshop/{instance_id}/{instance_num:03d}',
                    'title': f'Job Shop Instance {instance_id}-{instance_num}',
                    'text': text,
                    'level1_family': 'scheduling',
                    'subtype': 'job_shop',
                    'key_clues': 'sequence routing precedence multiple_operations machine_order',
                    'num_jobs': num_jobs,
                    'num_machines': num_machines,
                    'numbers_present': 'yes',
                    'integrality_implied': 'yes',
                    'source_url': f'https://people.brunel.ac.uk/~mastjjb/jeb/orlib/jobshopinfo.html'
                })

                instance_num += 1
                i += 1

            return instances

        except Exception as e:
            print(f"  ✗ Error parsing {filepath}: {e}")
            return []

    def parse_flowshop(self, filepath: str, instance_id: str) -> List[Dict]:
        """
        Parse flow-shop scheduling instance.

        Format (typical):
        Line 1: num_jobs num_machines
        Then processing times matrix (jobs x machines)
        """
        instances = []

        try:
            with open(filepath, 'r') as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            i = 0
            instance_num = 1

            while i < len(lines):
                parts = lines[i].split()
                if len(parts) < 2:
                    i += 1
                    continue

                try:
                    num_jobs = int(parts[0])
                    num_machines = int(parts[1])
                except ValueError:
                    i += 1
                    continue

                # Read processing times
                job_descriptions = []
                for j in range(num_jobs):
                    i += 1
                    if i >= len(lines):
                        break

                    times = [int(t) for t in lines[i].split() if t.isdigit()]
                    if len(times) == num_machines:
                        operations = [f"M{k+1}({times[k]}min)" for k in range(min(3, num_machines))]
                        job_descriptions.append(f"Job{j+1}: {' → '.join(operations)}")

                # Create natural language description
                text = f"A flow shop scheduling problem where all {num_jobs} jobs follow the same machine sequence. "
                text += f"Every job must be processed on machine 1, then machine 2, up to machine {num_machines} in that order. "
                text += f"No job can skip a machine. Example routes: {'; '.join(job_descriptions[:2])}"
                if len(job_descriptions) > 2:
                    text += f" and {len(job_descriptions) - 2} more jobs"
                text += ". Minimize total completion time."

                instances.append({
                    'id': f'flowshop/{instance_id}/{instance_num:03d}',
                    'title': f'Flow Shop Instance {instance_id}-{instance_num}',
                    'text': text,
                    'level1_family': 'scheduling',
                    'subtype': 'flow_shop',
                    'key_clues': 'same_sequence all_jobs fixed_order through_all_machines',
                    'num_jobs': num_jobs,
                    'num_machines': num_machines,
                    'numbers_present': 'yes',
                    'integrality_implied': 'yes',
                    'source_url': f'https://people.brunel.ac.uk/~mastjjb/jeb/orlib/flowshopinfo.html'
                })

                instance_num += 1
                i += 1

            return instances

        except Exception as e:
            print(f"  ✗ Error parsing {filepath}: {e}")
            return []

    def parse_assignment(self, filepath: str, instance_id: str) -> List[Dict]:
        """Parse assignment problem instance."""
        instances = []

        try:
            with open(filepath, 'r') as f:
                lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            i = 0
            instance_num = 1

            while i < len(lines):
                parts = lines[i].split()
                if len(parts) < 1:
                    i += 1
                    continue

                try:
                    n = int(parts[0])  # Size of assignment problem
                except ValueError:
                    i += 1
                    continue

                # Create natural language description
                text = f"An assignment problem with {n} workers and {n} tasks. "
                text += "Each worker must be assigned to exactly one task and each task to exactly one worker. "
                text += "There is a cost matrix where each entry represents the cost of assigning worker i to task j. "
                text += "Minimize total assignment cost."

                instances.append({
                    'id': f'assignment/{instance_id}/{instance_num:03d}',
                    'title': f'Assignment Problem {instance_id}-{instance_num}',
                    'text': text,
                    'level1_family': 'assignment',
                    'subtype': 'assignment',
                    'key_clues': 'one_to_one cost_matrix workers_tasks bipartite_matching',
                    'size': n,
                    'numbers_present': 'yes',
                    'integrality_implied': 'yes',
                    'source_url': f'https://people.brunel.ac.uk/~mastjjb/jeb/orlib/assigninfo.html'
                })

                instance_num += 1
                i += n + 1  # Skip cost matrix

            return instances

        except Exception as e:
            print(f"  ✗ Error parsing {filepath}: {e}")
            return []


def build_dataset():
    """Build the complete training dataset."""

    print("="*80)
    print("  BUILDING ML CLASSIFIER TRAINING DATASET")
    print("="*80)
    print()

    parser = ORLibraryParser()
    all_instances = []

    # Job-shop scheduling instances
    print("\n[1/3] Downloading Job-Shop Scheduling Instances...")
    print("-" * 60)

    # OR-Library: jobshop1 contains 82 instances
    jobshop_files = [
        ('jobshop1.txt', 'orlib'),
    ]

    for filename, instance_id in jobshop_files:
        filepath = parser.download_file(filename)
        if filepath:
            instances = parser.parse_jobshop(filepath, instance_id)
            all_instances.extend(instances)
            print(f"    Parsed {len(instances)} instance(s)")

    # Flow-shop scheduling instances
    print("\n[2/3] Downloading Flow-Shop Scheduling Instances...")
    print("-" * 60)

    flowshop_files = [
        ('flowshop1.txt', 'orlib'),
    ]

    for filename, instance_id in flowshop_files:
        filepath = parser.download_file(filename)
        if filepath:
            instances = parser.parse_flowshop(filepath, instance_id)
            all_instances.extend(instances)
            print(f"    Parsed {len(instances)} instance(s)")

    # Assignment problems - skip for now, focus on scheduling
    print("\n[3/3] Other Problem Types...")
    print("-" * 60)
    print("    (Skipping for now - focusing on scheduling)")

    # Can add later:
    # - capinfo (Capacitated p-median)
    # - assigninfo (Assignment problems)
    # - gapinfo (Generalized assignment)

    # Write to CSV
    print("\n" + "="*80)
    print(f"  WRITING {len(all_instances)} INSTANCES TO CSV")
    print("="*80)

    output_path = Path('knowledge/ml_training_dataset.csv')
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Get all unique field names
    fieldnames = ['id', 'title', 'text', 'level1_family', 'subtype', 'key_clues',
                  'numbers_present', 'integrality_implied', 'source_url']

    # Add any additional fields from instances
    for instance in all_instances:
        for key in instance.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_instances)

    print(f"\n✓ Dataset written to: {output_path}")
    print(f"  Total instances: {len(all_instances)}")

    # Print summary by category
    from collections import Counter
    category_counts = Counter(inst['subtype'] for inst in all_instances)

    print("\n  Breakdown by subtype:")
    for subtype, count in category_counts.most_common():
        print(f"    {subtype}: {count}")

    print()
    return output_path


if __name__ == "__main__":
    try:
        output_path = build_dataset()
        print(f"\n{'='*80}")
        print(f"  SUCCESS: Dataset ready at {output_path}")
        print(f"{'='*80}\n")
        sys.exit(0)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
