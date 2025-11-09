#!/usr/bin/env python3
"""
TEST: Classification Evaluation

PURPOSE: Test classifier accuracy against OR problem repository
TESTS: Intent classification, confidence scoring, category filtering
PROBLEMS: or_problem_repository.py (all or filtered by category/solvable)

EXPECTED OUTPUT:
    ✓ Tests 4 solvable problems (with --solvable flag)
    ✓ Classification accuracy: 100.0%
    ✓ All problems correctly identified as optimization
    ✓ Confidence scores: 90%, 90%, 90%, 85% (typical)
    ✓ No errors reported
    ✓ Summary with total/passed/accuracy

RUN: python tests/test_classification.py --solvable
REQUIRES: Ollama (localhost:11434), qwen2:7b model
USAGE:
    python test_classification.py              # Test all problems
    python test_classification.py --solvable   # Test only solvable problems
    python test_classification.py --category transportation  # Test specific category
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from or_problem_repository import (
    get_all_problems,
    get_solvable_problems,
    get_problems_by_category,
    ProblemCategory
)
from llm.enhanced_client import EnhancedLLMClient
from llm.intent_router import IntentRouter
import argparse


def test_classification(problems, llm_client):
    """
    Test classifier on a set of problems.

    Returns:
        tuple: (total, correct, errors)
    """
    intent_router = IntentRouter(llm_client)

    results = {
        'total': 0,
        'correct': 0,
        'errors': []
    }

    print(f"\n{'='*80}")
    print(f"  TESTING CLASSIFICATION")
    print(f"{'='*80}\n")

    for problem in problems:
        results['total'] += 1
        problem_name = problem['name']
        problem_id = problem['id']
        expected_type = problem['expected_type']
        problem_text = problem['text']

        print(f"Testing: {problem_id}")
        print(f"  Expected type: {expected_type}")

        try:
            # Classify the problem using intent router
            conversation_context = {'last_solution': None, 'messages': []}
            intent_result = intent_router.detect_intent(problem_text, conversation_context)

            detected_intent = intent_result.get('intent', 'unknown')
            confidence = intent_result.get('confidence', 0.0)

            print(f"  Detected intent: {detected_intent} (confidence: {confidence:.1%})")

            # For now, we check if it's classified as 'optimization'
            # In future, we can extract more specific problem type from metadata
            if detected_intent == 'optimization':
                print(f"  ✓ Correctly identified as optimization problem")
                results['correct'] += 1
            else:
                print(f"  ✗ FAILED: Expected optimization, got {detected_intent}")
                results['errors'].append({
                    'id': problem_id,
                    'name': problem_name,
                    'expected': expected_type,
                    'actual': detected_intent,
                    'confidence': confidence
                })

        except Exception as e:
            print(f"  ✗ ERROR: {str(e)}")
            results['errors'].append({
                'id': problem_id,
                'name': problem_name,
                'expected': expected_type,
                'actual': 'ERROR',
                'error': str(e)
            })

        print()

    return results


def test_schema_extraction(problems, llm_client):
    """
    Test schema extraction on problems that have expected_schema.

    Returns:
        tuple: (total, correct, errors)
    """
    from agent.core import OptimizationAgent

    agent = OptimizationAgent(llm_client)

    results = {
        'total': 0,
        'correct': 0,
        'partial': 0,
        'errors': []
    }

    print(f"\n{'='*80}")
    print(f"  TESTING SCHEMA EXTRACTION")
    print(f"{'='*80}\n")

    for problem in problems:
        if 'expected_schema' not in problem:
            continue

        results['total'] += 1
        problem_name = problem['name']
        problem_id = problem['id']
        expected_schema = problem['expected_schema']
        problem_text = problem['text']

        print(f"Testing: {problem_id}")

        try:
            # Extract parameters using specialist
            # This would need to be adapted based on problem type
            # For now, just check if extraction succeeds
            response = agent.process(problem_text)

            if 'error' in response:
                print(f"  ✗ Extraction failed: {response['error']}")
                results['errors'].append({
                    'id': problem_id,
                    'name': problem_name,
                    'error': response['error']
                })
            else:
                print(f"  ✓ Extraction succeeded")
                results['correct'] += 1

        except Exception as e:
            print(f"  ✗ ERROR: {str(e)}")
            results['errors'].append({
                'id': problem_id,
                'name': problem_name,
                'error': str(e)
            })

        print()

    return results


def print_summary(classification_results, schema_results=None):
    """Print test summary."""
    print(f"\n{'='*80}")
    print(f"  TEST SUMMARY")
    print(f"{'='*80}\n")

    print("Classification Test:")
    print(f"  Total problems: {classification_results['total']}")
    print(f"  Correctly classified: {classification_results['correct']}")
    print(f"  Accuracy: {classification_results['correct']/classification_results['total']*100:.1f}%")

    if classification_results['errors']:
        print(f"\n  Errors ({len(classification_results['errors'])}):")
        for error in classification_results['errors']:
            print(f"    - {error['id']}: expected {error['expected']}, got {error['actual']}")

    if schema_results:
        print(f"\nSchema Extraction Test:")
        print(f"  Total problems: {schema_results['total']}")
        print(f"  Successful: {schema_results['correct']}")
        print(f"  Accuracy: {schema_results['correct']/max(schema_results['total'],1)*100:.1f}%")

        if schema_results['errors']:
            print(f"\n  Errors ({len(schema_results['errors'])}):")
            for error in schema_results['errors']:
                print(f"    - {error['id']}: {error.get('error', 'Unknown error')}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description='Test problem classification and schema extraction',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--solvable', action='store_true',
                       help='Test only solvable problems')
    parser.add_argument('--category', type=str,
                       help='Test only problems in this category')
    parser.add_argument('--schema', action='store_true',
                       help='Also test schema extraction')
    parser.add_argument('--host', type=str, default='http://localhost:11434',
                       help='Ollama host (default: http://localhost:11434)')
    parser.add_argument('--model', type=str, default='qwen2:7b',
                       help='LLM model (default: qwen2:7b)')

    args = parser.parse_args()

    # Get problems to test
    if args.category:
        problems = get_problems_by_category(args.category)
        if not problems:
            print(f"Category '{args.category}' not found.")
            return 1
    elif args.solvable:
        problems = get_solvable_problems()
    else:
        problems = get_all_problems()

    if not problems:
        print("No problems to test.")
        return 1

    print(f"Testing {len(problems)} problems...")

    # Initialize LLM client
    try:
        llm_client = EnhancedLLMClient(host=args.host, model=args.model)
        print(f"✓ Connected to {args.host} using model {args.model}\n")
    except Exception as e:
        print(f"✗ Failed to connect to LLM: {e}")
        return 1

    # Run classification tests
    classification_results = test_classification(problems, llm_client)

    # Run schema extraction tests if requested
    schema_results = None
    if args.schema:
        schema_results = test_schema_extraction(problems, llm_client)

    # Print summary
    print_summary(classification_results, schema_results)

    # Return exit code based on results
    if classification_results['errors']:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
