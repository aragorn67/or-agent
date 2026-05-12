#!/usr/bin/env python3
"""
Test that the new problem_loader.py returns the same data as or_problem_repository.py

This ensures backward compatibility when switching from hardcoded Python to CSV+JSON.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import old loader
import or_problem_repository as old_loader

# Import new loader
sys.path.insert(0, str(Path(__file__).parent))
import problem_loader as new_loader

def compare_problems(old_problem, new_problem, problem_id):
    """Compare two problem dicts and return list of differences"""
    differences = []

    # Check required fields
    required_fields = ['id', 'name', 'category', 'expected_type', 'text', 'feasible', 'solvable', 'notes']

    for field in required_fields:
        old_val = old_problem.get(field)
        new_val = new_problem.get(field)

        if old_val != new_val:
            differences.append(f"  {field}: OLD={old_val!r} vs NEW={new_val!r}")

    # Check metadata exists
    if 'metadata' in old_problem and 'metadata' not in new_problem:
        differences.append(f"  metadata: Missing in new loader")

    # Check expected_schema exists
    if 'expected_schema' in old_problem and 'expected_schema' not in new_problem:
        differences.append(f"  expected_schema: Missing in new loader")

    return differences

def test_all_problems():
    """Test that both loaders return the same problems"""
    print("="*80)
    print("TESTING PROBLEM LOADER COMPATIBILITY")
    print("="*80)

    # Load problems from both loaders
    old_problems = old_loader.get_all_problems()
    new_problems = new_loader.get_all_problems()

    print(f"\nOld loader: {len(old_problems)} problems")
    print(f"New loader: {len(new_problems)} problems")

    if len(old_problems) != len(new_problems):
        print(f"❌ FAIL: Different number of problems!")
        return False

    print(f"✓ Same number of problems")

    # Create lookup dicts by ID
    old_by_id = {p['id']: p for p in old_problems}
    new_by_id = {p['id']: p for p in new_problems}

    # Check all IDs match
    old_ids = set(old_by_id.keys())
    new_ids = set(new_by_id.keys())

    if old_ids != new_ids:
        missing_in_new = old_ids - new_ids
        extra_in_new = new_ids - old_ids
        if missing_in_new:
            print(f"❌ FAIL: Missing in new loader: {missing_in_new}")
        if extra_in_new:
            print(f"❌ FAIL: Extra in new loader: {extra_in_new}")
        return False

    print(f"✓ All problem IDs match")

    # Compare each problem
    all_match = True
    differences_count = 0

    for problem_id in old_ids:
        old_p = old_by_id[problem_id]
        new_p = new_by_id[problem_id]

        diffs = compare_problems(old_p, new_p, problem_id)

        if diffs:
            all_match = False
            differences_count += 1
            print(f"\n❌ DIFFERENCES in {problem_id}:")
            for diff in diffs:
                print(diff)

    if all_match:
        print(f"\n✓ All {len(old_problems)} problems match exactly!")
    else:
        print(f"\n❌ Found differences in {differences_count} problems")

    return all_match

def test_api_functions():
    """Test that API functions work the same"""
    print("\n" + "="*80)
    print("TESTING API COMPATIBILITY")
    print("="*80)

    tests_passed = 0
    tests_failed = 0

    # Test get_problem_by_name
    print("\n1. Testing get_problem_by_name()...")
    old_p = old_loader.get_problem_by_name("european_wine_distribution")
    new_p = new_loader.get_problem_by_name("european_wine_distribution")

    if old_p and new_p and old_p['id'] == new_p['id']:
        print("   ✓ get_problem_by_name() works")
        tests_passed += 1
    else:
        print("   ❌ get_problem_by_name() mismatch")
        tests_failed += 1

    # Test get_problem_by_id
    print("\n2. Testing get_problem_by_id()...")
    old_p = old_loader.get_problem_by_id("transport/wine_eu/001")
    new_p = new_loader.get_problem_by_id("transport/wine_eu/001")

    if old_p and new_p and old_p['name'] == new_p['name']:
        print("   ✓ get_problem_by_id() works")
        tests_passed += 1
    else:
        print("   ❌ get_problem_by_id() mismatch")
        tests_failed += 1

    # Test get_solvable_problems
    print("\n3. Testing get_solvable_problems()...")
    old_solvable = old_loader.get_solvable_problems()
    new_solvable = new_loader.get_solvable_problems()

    if len(old_solvable) == len(new_solvable):
        print(f"   ✓ get_solvable_problems() returns {len(old_solvable)} problems")
        tests_passed += 1
    else:
        print(f"   ❌ get_solvable_problems() mismatch: {len(old_solvable)} vs {len(new_solvable)}")
        tests_failed += 1

    # Test get_problems_by_category
    print("\n4. Testing get_problems_by_category('transportation')...")
    old_transport = old_loader.get_problems_by_category("transportation")
    new_transport = new_loader.get_problems_by_category("transportation")

    if len(old_transport) == len(new_transport):
        print(f"   ✓ get_problems_by_category() returns {len(old_transport)} problems")
        tests_passed += 1
    else:
        print(f"   ❌ get_problems_by_category() mismatch: {len(old_transport)} vs {len(new_transport)}")
        tests_failed += 1

    print(f"\n{'='*80}")
    print(f"API TESTS: {tests_passed} passed, {tests_failed} failed")
    print(f"{'='*80}")

    return tests_failed == 0

def main():
    print("\n" + "="*80)
    print("PROBLEM LOADER COMPATIBILITY TEST")
    print("Comparing or_problem_repository.py vs problem_loader.py")
    print("="*80 + "\n")

    # Test data compatibility
    data_match = test_all_problems()

    # Test API compatibility
    api_match = test_api_functions()

    # Overall result
    print("\n" + "="*80)
    if data_match and api_match:
        print("✅ ALL TESTS PASSED - New loader is fully compatible!")
    else:
        print("❌ SOME TESTS FAILED - Review differences above")
    print("="*80 + "\n")

    return data_match and api_match

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
