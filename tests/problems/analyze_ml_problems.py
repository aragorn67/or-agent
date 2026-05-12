#!/usr/bin/env python3
"""
Analyze each problem in ML dataset and categorize them properly.
Check if classification is correct and if we can solve them.
"""

import csv
import sys
from pathlib import Path

# Add parent to path for LLM imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llm.enhanced_client import EnhancedLLMClient
from or_classify.problem_classifier import ProblemClassifier

def analyze_problems():
    """Analyze all ML problems one by one"""

    ml_csv_path = Path(__file__).parent.parent.parent / 'ML_RAG_archive' / 'ML_approaches' / 'ML' / 'FINAL_ML_DATASET.csv'

    print("Loading ML dataset...")
    with open(ml_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        problems = list(reader)

    print(f"Total problems: {len(problems)}")

    # Initialize LLM
    print("\nInitializing LLM for classification...")
    llm = EnhancedLLMClient()
    classifier = ProblemClassifier(llm)

    # Results
    results = []
    correct = 0
    incorrect = 0
    errors = 0

    print("\n" + "="*80)
    print("ANALYZING PROBLEMS")
    print("="*80)

    for i, problem in enumerate(problems, 1):
        problem_id = problem['id']
        expected_category = problem['level1_family']
        expected_subtype = problem['subtype']
        text = problem['text']

        print(f"\n[{i}/{len(problems)}] {problem_id}")
        print(f"  Expected: {expected_category} / {expected_subtype}")

        try:
            # Classify using our LLM
            result = classifier.classify_problem(text)

            actual_category = result.get('level1_family', '')
            actual_subtype = result.get('subtype', '')

            print(f"  Actual:   {actual_category} / {actual_subtype}")

            # Check if matches
            category_match = actual_category.lower() == expected_category.lower()
            subtype_match = actual_subtype.lower() == expected_subtype.lower()

            match_status = "✓ MATCH" if (category_match and subtype_match) else "✗ MISMATCH"
            print(f"  Status:   {match_status}")

            if category_match and subtype_match:
                correct += 1
            else:
                incorrect += 1

            results.append({
                'problem_id': problem_id,
                'expected_category': expected_category,
                'expected_subtype': expected_subtype,
                'actual_category': actual_category,
                'actual_subtype': actual_subtype,
                'category_match': category_match,
                'subtype_match': subtype_match,
                'text': text
            })

        except Exception as e:
            print(f"  ERROR: {e}")
            errors += 1
            results.append({
                'problem_id': problem_id,
                'expected_category': expected_category,
                'expected_subtype': expected_subtype,
                'actual_category': 'ERROR',
                'actual_subtype': 'ERROR',
                'category_match': False,
                'subtype_match': False,
                'error': str(e),
                'text': text
            })

        # Progress every 10 problems
        if i % 10 == 0:
            print(f"\n--- Progress: {i}/{len(problems)} ({correct} correct, {incorrect} incorrect, {errors} errors) ---")

    # Final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)
    print(f"Total problems:   {len(problems)}")
    print(f"Correct:          {correct} ({100*correct/len(problems):.1f}%)")
    print(f"Incorrect:        {incorrect} ({100*incorrect/len(problems):.1f}%)")
    print(f"Errors:           {errors}")

    # Save results
    output_csv = Path(__file__).parent / 'ml_analysis_results.csv'
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['problem_id', 'expected_category', 'expected_subtype',
                      'actual_category', 'actual_subtype', 'category_match', 'subtype_match']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r.get(k, '') for k in fieldnames})

    print(f"\n✓ Results saved to: {output_csv}")

    # Show mismatches
    mismatches = [r for r in results if not (r['category_match'] and r['subtype_match'])]
    if mismatches:
        print(f"\n{'='*80}")
        print(f"MISMATCHES ({len(mismatches)} problems)")
        print(f"{'='*80}")
        for r in mismatches[:20]:  # Show first 20
            print(f"\n{r['problem_id']}")
            print(f"  Expected: {r['expected_category']} / {r['expected_subtype']}")
            print(f"  Actual:   {r['actual_category']} / {r['actual_subtype']}")

if __name__ == '__main__':
    analyze_problems()
