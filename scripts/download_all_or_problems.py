#!/usr/bin/env python3
"""
Download and Parse ALL OR Problem Types for ML Classifier

Downloads from:
1. OR-Library: Assignment, Knapsack, Facility Location, Bin Packing
2. Mathprog-ORlib: Personnel Scheduling, Hub Location, Vehicle Routing

Converts all to natural language descriptions for ML classifier training.

Target: ~250-300 instances across 10+ problem types
"""

import os
import sys
import requests
import csv
import random
from pathlib import Path
from typing import List, Dict

# Base URLs
ORLIB_BASE = "https://people.brunel.ac.uk/~mastjjb/jeb/orlib/files"
MATHPROG_BASE = "https://andreas-ernst.github.io/Mathprog-ORlib"

class ORProblemDownloader:
    """Download and parse OR problems from multiple sources."""

    def __init__(self, output_dir="knowledge/or_problems_raw"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.all_instances = []

    def download_file(self, url, filename):
        """Download a file if it doesn't exist."""
        local_path = self.output_dir / filename

        if local_path.exists():
            print(f"  ✓ Already have: {filename}")
            return str(local_path)

        try:
            print(f"  Downloading: {filename}...")
            response = requests.get(url, timeout=60)
            response.raise_for_status()

            with open(local_path, 'wb') as f:
                f.write(response.content)

            print(f"  ✓ Downloaded: {filename}")
            return str(local_path)
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            return None

    # ========================================================================
    # ASSIGNMENT PROBLEMS
    # ========================================================================

    def download_assignment_problems(self, count=15):
        """Download assignment problems from OR-Library."""
        print("\n" + "="*80)
        print("DOWNLOADING ASSIGNMENT PROBLEMS")
        print("="*80)

        # Select subset of sizes
        files = ['assign100', 'assign200', 'assign300', 'assign400', 'assign500']

        for filename in files[:count//3]:  # ~5 files
            url = f"{ORLIB_BASE}/{filename}"
            filepath = self.download_file(url, f"{filename}.txt")

            if filepath:
                instances = self.parse_assignment_file(filepath, filename)
                self.all_instances.extend(instances)

        print(f"\n✓ Total assignment instances parsed: {len([i for i in self.all_instances if i['subtype'] == 'assignment'])}")

    def parse_assignment_file(self, filepath, problem_id):
        """Parse assignment problem into natural language."""
        instances = []

        try:
            with open(filepath, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]

            # First line usually has problem size
            if not lines:
                return instances

            parts = lines[0].split()
            if len(parts) < 1:
                return instances

            n = int(parts[0])  # Number of workers/tasks

            # Create natural language description
            templates = [
                f"An assignment problem with {n} workers and {n} tasks. Each worker can perform any task but with different costs. "
                f"Worker assignments must be one-to-one: each worker assigned to exactly one task, each task assigned to exactly one worker. "
                f"The cost matrix specifies the cost for each worker-task pair. Objective: minimize total assignment cost.",

                f"A company has {n} employees that need to be assigned to {n} different projects. "
                f"Each employee has different efficiency levels for different projects, resulting in varying costs. "
                f"Each employee must work on exactly one project, and each project must have exactly one employee. "
                f"Determine the assignment that minimizes the total cost.",

                f"Assign {n} resources to {n} tasks with minimum total cost. "
                f"Each resource-task combination has a specific cost value. "
                f"Constraints: bijective matching (one-to-one assignment). "
                f"This is a classic linear assignment problem solved via Hungarian algorithm or simplex method."
            ]

            text = random.choice(templates)

            instances.append({
                'id': f'assignment/orlib/{problem_id}',
                'title': f'Assignment Problem {problem_id}',
                'text': text,
                'level1_family': 'assignment',
                'subtype': 'assignment',
                'key_clues': 'assign workers tasks one_to_one matching bipartite cost_matrix',
                'numbers_present': 'yes',
                'integrality_implied': 'yes',
                'num_workers': n,
                'num_tasks': n,
                'source_url': f'{ORLIB_BASE}/{problem_id}'
            })

        except Exception as e:
            print(f"  Error parsing {filepath}: {e}")

        return instances

    # ========================================================================
    # KNAPSACK PROBLEMS
    # ========================================================================

    def download_knapsack_problems(self, count=20):
        """Download knapsack problems from OR-Library."""
        print("\n" + "="*80)
        print("DOWNLOADING KNAPSACK PROBLEMS")
        print("="*80)

        # Download mknap1 and mknap2
        for filename in ['mknap1', 'mknap2']:
            url = f"{ORLIB_BASE}/{filename}.txt"
            filepath = self.download_file(url, f"{filename}.txt")

            if filepath:
                instances = self.parse_knapsack_file(filepath, filename)
                self.all_instances.extend(instances[:count//2])  # Take subset

        print(f"\n✓ Total knapsack instances parsed: {len([i for i in self.all_instances if i['subtype'] == 'knapsack'])}")

    def parse_knapsack_file(self, filepath, problem_id):
        """Parse multidimensional knapsack problems."""
        instances = []

        try:
            with open(filepath, 'r') as f:
                content = f.read()

            # mknap files have multiple instances
            # Format: n (items), m (constraints), optimal value, then data
            lines = [l.strip() for l in content.split('\n') if l.strip()]

            i = 0
            instance_num = 1

            while i < len(lines) - 3:
                try:
                    # Read problem size
                    parts = lines[i].split()
                    if len(parts) < 2:
                        i += 1
                        continue

                    n_items = int(parts[0])
                    m_constraints = int(parts[1])

                    templates = [
                        f"A multidimensional knapsack problem with {n_items} items and {m_constraints} resource constraints. "
                        f"Each item has a value and consumes resources across {m_constraints} dimensions (e.g., weight, volume, etc.). "
                        f"Select items to maximize total value while respecting all resource limits. "
                        f"Each item can be selected at most once (0-1 knapsack variant).",

                        f"Pack a knapsack with {n_items} available items. The knapsack has {m_constraints} capacity constraints "
                        f"(for example: weight limit, volume limit, cost limit). Each item has a profit value and resource consumption. "
                        f"Which items should be packed to maximize profit without exceeding any capacity limit?",

                        f"A resource allocation problem: {n_items} projects are available for investment. "
                        f"There are {m_constraints} types of resources (budget, personnel, equipment). "
                        f"Each project generates profit but consumes resources. Select projects that maximize total profit "
                        f"while staying within all resource limits."
                    ]

                    text = random.choice(templates)

                    instances.append({
                        'id': f'knapsack/{problem_id}/{instance_num:03d}',
                        'title': f'Knapsack {problem_id}-{instance_num}',
                        'text': text,
                        'level1_family': 'knapsack',
                        'subtype': 'knapsack',
                        'key_clues': 'select items capacity value weight profit maximize constraint',
                        'numbers_present': 'yes',
                        'integrality_implied': 'yes',
                        'num_items': n_items,
                        'num_constraints': m_constraints,
                        'source_url': f'{ORLIB_BASE}/{problem_id}.txt'
                    })

                    instance_num += 1
                    i += n_items + m_constraints + 5  # Skip to next instance

                except (ValueError, IndexError):
                    i += 1
                    continue

                if len(instances) >= 20:  # Limit per file
                    break

        except Exception as e:
            print(f"  Error parsing {filepath}: {e}")

        return instances

    # ========================================================================
    # FACILITY LOCATION
    # ========================================================================

    def download_facility_location(self, count=15):
        """Download capacitated facility location problems."""
        print("\n" + "="*80)
        print("DOWNLOADING FACILITY LOCATION PROBLEMS")
        print("="*80)

        # Select subset of cap files
        files = ['cap41', 'cap42', 'cap43', 'cap44', 'cap51',
                 'cap61', 'cap71', 'cap81', 'cap91', 'cap101']

        for filename in files[:count]:
            url = f"{ORLIB_BASE}/{filename}.txt"
            filepath = self.download_file(url, f"{filename}.txt")

            if filepath:
                instance = self.parse_facility_location_file(filepath, filename)
                if instance:
                    self.all_instances.append(instance)

        print(f"\n✓ Total facility location instances parsed: {len([i for i in self.all_instances if i['subtype'] == 'facility_location'])}")

    def parse_facility_location_file(self, filepath, problem_id):
        """Parse facility location problem."""
        try:
            with open(filepath, 'r') as f:
                lines = [l.strip() for l in f if l.strip()]

            if len(lines) < 2:
                return None

            # First line: num_facilities num_customers
            parts = lines[0].split()
            if len(parts) < 2:
                return None

            n_facilities = int(parts[0])
            n_customers = int(parts[1])

            templates = [
                f"A capacitated facility location problem with {n_facilities} potential warehouse locations and {n_customers} customers. "
                f"Each warehouse has a fixed opening cost and a capacity limit. Each customer has a demand that must be fulfilled. "
                f"Shipping costs vary by warehouse-customer pair. Decide which warehouses to open and how to assign customers "
                f"to minimize total cost (opening costs + shipping costs) while respecting capacity constraints.",

                f"A logistics company must decide which of {n_facilities} distribution centers to operate in order to serve {n_customers} customers. "
                f"Opening a distribution center incurs a fixed cost, and each center has limited capacity. "
                f"Transportation costs depend on the distance between centers and customers. "
                f"Which centers should open, and which customers should each center serve?",

                f"Facility location optimization: Choose from {n_facilities} candidate sites to establish facilities that will serve {n_customers} demand points. "
                f"Each facility has setup costs and capacity restrictions. Service costs are location-dependent. "
                f"Objective: minimize the sum of facility opening costs and customer assignment costs."
            ]

            text = random.choice(templates)

            return {
                'id': f'facility_location/orlib/{problem_id}',
                'title': f'Facility Location {problem_id}',
                'text': text,
                'level1_family': 'facility_location',
                'subtype': 'facility_location',
                'key_clues': 'facility warehouse location open fixed_cost capacity customers assign',
                'numbers_present': 'yes',
                'integrality_implied': 'yes',
                'num_facilities': n_facilities,
                'num_customers': n_customers,
                'source_url': f'{ORLIB_BASE}/{problem_id}.txt'
            }

        except Exception as e:
            print(f"  Error parsing {filepath}: {e}")
            return None

    # ========================================================================
    # BIN PACKING
    # ========================================================================

    def download_bin_packing(self, count=10):
        """Download bin packing problems."""
        print("\n" + "="*80)
        print("DOWNLOADING BIN PACKING PROBLEMS")
        print("="*80)

        # Download binpack files
        for i in range(1, min(count//2 + 1, 9)):
            filename = f"binpack{i}"
            url = f"{ORLIB_BASE}/{filename}"
            filepath = self.download_file(url, f"{filename}.txt")

            if filepath:
                instances = self.parse_bin_packing_file(filepath, filename)
                self.all_instances.extend(instances[:3])  # Take few from each file

        print(f"\n✓ Total bin packing instances parsed: {len([i for i in self.all_instances if i['subtype'] == 'bin_packing'])}")

    def parse_bin_packing_file(self, filepath, problem_id):
        """Parse bin packing problems."""
        instances = []

        try:
            with open(filepath, 'r') as f:
                lines = [l.strip() for l in f if l.strip()]

            # Bin packing files have multiple instances
            # Format varies, but typically: bin_capacity, num_items, then item sizes

            instance_num = 1
            i = 0

            while i < len(lines) - 2 and len(instances) < 5:
                try:
                    parts = lines[i].split()
                    if len(parts) < 2:
                        i += 1
                        continue

                    bin_capacity = int(parts[0])
                    num_items = int(parts[1])

                    templates = [
                        f"A bin packing problem: pack {num_items} items into bins of capacity {bin_capacity}. "
                        f"Each item has a specific size. All items must be packed, and no bin can exceed its capacity. "
                        f"Objective: minimize the number of bins used.",

                        f"A warehouse needs to pack {num_items} boxes into shipping containers. Each container has capacity {bin_capacity} units. "
                        f"Box sizes vary. How should boxes be grouped into containers to minimize the number of containers needed?",

                        f"One-dimensional bin packing: Given {num_items} items and unlimited bins of size {bin_capacity}, "
                        f"assign items to bins such that no bin is overfilled and the total number of bins is minimized. "
                        f"This is an NP-hard combinatorial optimization problem."
                    ]

                    text = random.choice(templates)

                    instances.append({
                        'id': f'bin_packing/{problem_id}/{instance_num:03d}',
                        'title': f'Bin Packing {problem_id}-{instance_num}',
                        'text': text,
                        'level1_family': 'bin_packing',
                        'subtype': 'bin_packing',
                        'key_clues': 'pack bins items capacity size minimize containers boxes',
                        'numbers_present': 'yes',
                        'integrality_implied': 'yes',
                        'bin_capacity': bin_capacity,
                        'num_items': num_items,
                        'source_url': f'{ORLIB_BASE}/{problem_id}'
                    })

                    instance_num += 1
                    i += num_items + 2

                except (ValueError, IndexError):
                    i += 1

        except Exception as e:
            print(f"  Error parsing {filepath}: {e}")

        return instances

    # ========================================================================
    # SAVE RESULTS
    # ========================================================================

    def save_to_csv(self, output_file='knowledge/new_or_problems.csv'):
        """Save all parsed instances to CSV."""
        if not self.all_instances:
            print("No instances to save!")
            return

        print(f"\n{'='*80}")
        print(f"SAVING {len(self.all_instances)} INSTANCES")
        print(f"{'='*80}")

        fieldnames = ['id', 'title', 'text', 'level1_family', 'subtype', 'key_clues',
                     'numbers_present', 'integrality_implied', 'source_url']

        # Add optional fields
        optional_fields = ['num_workers', 'num_tasks', 'num_items', 'num_constraints',
                          'num_facilities', 'num_customers', 'bin_capacity']

        for field in optional_fields:
            if any(field in inst for inst in self.all_instances):
                fieldnames.append(field)

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for inst in self.all_instances:
                # Fill missing optional fields
                row = {k: inst.get(k, '') for k in fieldnames}
                writer.writerow(row)

        print(f"✓ Saved to: {output_file}")

        # Print summary
        print(f"\nSummary by problem type:")
        type_counts = {}
        for inst in self.all_instances:
            subtype = inst['subtype']
            type_counts[subtype] = type_counts.get(subtype, 0) + 1

        for subtype in sorted(type_counts.keys()):
            print(f"  {subtype}: {type_counts[subtype]}")


def main():
    print("="*80)
    print("COMPREHENSIVE OR PROBLEM DOWNLOADER")
    print("="*80)
    print("\nThis will download and parse:")
    print("  - Assignment problems (OR-Library)")
    print("  - Knapsack problems (OR-Library)")
    print("  - Facility Location problems (OR-Library)")
    print("  - Bin Packing problems (OR-Library)")
    print()

    downloader = ORProblemDownloader()

    # Download all problem types
    downloader.download_assignment_problems(count=15)
    downloader.download_knapsack_problems(count=20)
    downloader.download_facility_location(count=15)
    downloader.download_bin_packing(count=10)

    # Save results
    downloader.save_to_csv('knowledge/new_or_problems.csv')

    print(f"\n{'='*80}")
    print("DOWNLOAD COMPLETE!")
    print(f"{'='*80}")
    print("\nNext steps:")
    print("1. Review: knowledge/new_or_problems.csv")
    print("2. Merge with existing data:")
    print("   python scripts/merge_all_datasets.py")
    print("3. Train classifier:")
    print("   python scripts/train_classifier.py")

    return 0


if __name__ == "__main__":
    sys.exit(main())
