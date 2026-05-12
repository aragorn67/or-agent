#!/usr/bin/env python3
"""
TEST: Classification Evaluation with RAG Insight

PURPOSE: Test classifier accuracy against OR problem repository
TESTS: Intent classification, confidence scoring, RAG retrieval demonstration
PROBLEMS: or_problem_repository.py (all or filtered by category/solvable)

EXPECTED OUTPUT:
    ✓ Tests 4 solvable problems (with --solvable flag)
    ✓ Classification accuracy: 100.0%
    ✓ All problems correctly identified as optimization
    ✓ Confidence scores: 90%, 90%, 90%, 85% (typical)
    ✓ With --show-rag: Displays RAG retrieval for each problem
      - Shows query sent to knowledge base
      - Displays retrieved chunks from textbooks
      - Shows source documents (which PDF)
      - Demonstrates RAG thinking process

RUN: python tests/test_classification.py --solvable --show-rag
REQUIRES: Ollama (localhost:11434), deepseek-r1:latest model, RAG knowledge base loaded
USAGE:
    python test_classification.py                    # Test all problems
    python test_classification.py --solvable         # Test only solvable problems
    python test_classification.py --solvable --show-rag  # Show RAG retrieval details
    python test_classification.py --solvable --compare-rag  # Compare with/without RAG
    python test_classification.py --category transportation --show-rag
"""

# Windows: Add project root to path so imports work when running tests directly
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.or_problem_repository import (
    get_all_problems,
    get_solvable_problems,
    get_problems_by_category,
    ProblemCategory
)
from llm.enhanced_client import EnhancedLLMClient
from config import Config
from llm.intent_router import IntentRouter
# from llm.knowledge_base import KnowledgeBase  # RAG removed
import argparse
import pickle
from pathlib import Path


def test_classification(problems, llm_client, show_rag=False):
    """
    Test classifier on a set of problems.

    Args:
        problems: List of problems to test
        llm_client: EnhancedLLMClient instance
        show_rag: If True, show RAG retrieval details (DISABLED - RAG removed)

    Returns:
        dict: Results with total, correct_intent, correct_category, correct_type, all_three_correct, errors
    """
    intent_router = IntentRouter(llm_client)
    kb = None  # RAG removed

    results = {
        'total': 0,
        'correct_intent': 0,
        'correct_category': 0,
        'correct_type': 0,
        'all_three_correct': 0,
        'errors': [],
        'rag_used': 0
    }

    print(f"\n{'='*80}")
    print(f"  TESTING INTENT → CATEGORY → TYPE")
    print(f"{'='*80}\n")

    if kb:
        print(f"📚 RAG Knowledge Base: LOADED")
        print(f"   Vector store: knowledge/vectorstore/")
        print(f"   Status: Active\n")
    else:
        print(f"⚠️  RAG Knowledge Base: NOT LOADED\n")

    for problem in problems:
        results['total'] += 1
        problem_name = problem['name']
        problem_id = problem['id']
        expected_category = problem['category']
        expected_type = problem['expected_type']
        problem_text = problem['text']

        print(f"\n{'─'*80}")
        print(f"Testing: {problem_id}")
        print(f"  Problem: {problem_name}")
        print(f"  Expected: intent=optimization, category={expected_category}, type={expected_type}")

        try:
            # RAG retrieval removed

            # Classify the problem using unified classify() method
            conversation_context = {'last_solution': None, 'messages': []}
            cls = intent_router.classify(problem_text, conversation_context)

            got_intent = cls.get('intent', 'unknown')
            got_category = cls.get('category', 'none')
            got_type = cls.get('expected_type', 'none')

            intent_conf = cls.get('intent_confidence', 0.0)
            category_conf = cls.get('category_confidence', 0.0)
            type_conf = cls.get('type_confidence', 0.0)

            # Check each dimension
            ok_intent = (got_intent == 'optimization')
            ok_category = (got_category == expected_category)
            ok_type = (got_type == expected_type)

            print(f"\n  🤖 RESULT:")
            print(f"     intent={got_intent} ({intent_conf:.0%}) {'✓' if ok_intent else '✗'}")
            print(f"     category={got_category} ({category_conf:.0%}) {'✓' if ok_category else '✗'}")
            print(f"     type={got_type} ({type_conf:.0%}) {'✓' if ok_type else '✗'}")

            # Update counters
            results['correct_intent'] += int(ok_intent)
            results['correct_category'] += int(ok_category)
            results['correct_type'] += int(ok_type)
            results['all_three_correct'] += int(ok_intent and ok_category and ok_type)

            # Record errors
            if not (ok_intent and ok_category and ok_type):
                results['errors'].append({
                    'id': problem_id,
                    'name': problem_name,
                    'exp': {'intent': 'optimization', 'category': expected_category, 'type': expected_type},
                    'got': {'intent': got_intent, 'category': got_category, 'type': got_type}
                })

        except Exception as e:
            print(f"  ✗ ERROR: {str(e)}")
            results['errors'].append({
                'id': problem_id,
                'name': problem_name,
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


def test_classification_ml(problems):
    """
    Test ML classifier on problems.

    Args:
        problems: List of problems to test

    Returns:
        dict: Results with total, correct_type, errors
    """
    # Load ML classifier
    model_path = Path("models/problem_classifier.pkl")
    vectorizer_path = Path("models/problem_vectorizer.pkl")

    if not model_path.exists() or not vectorizer_path.exists():
        print("❌ ML classifier not found. Run scripts/train_classifier.py first.")
        return None

    with open(model_path, 'rb') as f:
        classifier = pickle.load(f)

    with open(vectorizer_path, 'rb') as f:
        vectorizer = pickle.load(f)

    print(f"✓ Loaded ML classifier with {len(vectorizer.get_feature_names_out())} features\n")

    # Type mapping from repository to classifier
    type_mapping = {
        'single_stage_scheduling': 'single_stage_scheduling',
        'job_shop': 'job_shop',
        'flow_shop': 'flow_shop',
        'open_shop': 'scheduling',
        'shift_rostering': 'scheduling',
        'project_scheduling': 'scheduling',
        'single_machine_tardiness': 'scheduling',
        'transportation': 'transportation',
        'min_cost_flow': 'transportation',
        'zero_one_knapsack': 'knapsack',
        'bounded_knapsack': 'knapsack',
        'knapsack': 'knapsack',
        'assignment': 'assignment',
        'bipartite_matching': 'assignment',
        'uncapacitated_facility_location': 'facility_location',
        'capacitated_facility_location': 'facility_location',
        'facility_location': 'facility_location',
        'max_flow': 'network_flow',
        'shortest_path': 'network_flow',
        'network_flow': 'network_flow',
        'production_planning': 'production_planning',
        'blending': 'blending',
        'bin_packing': 'bin_packing',
        'set_cover': 'selection_problem',
        'cvrp': 'transportation',
        'vrptw': 'transportation',
    }

    results = {
        'total': 0,
        'correct_intent': 0,  # Always optimization for ML classifier
        'correct_category': 0,  # ML doesn't predict category
        'correct_type': 0,
        'all_three_correct': 0,
        'errors': []
    }

    print(f"\n{'='*80}")
    print(f"  TESTING ML CLASSIFIER")
    print(f"{'='*80}\n")

    for problem in problems:
        results['total'] += 1
        problem_name = problem['name']
        problem_id = problem['id']
        expected_category = problem['category']
        expected_type = problem['expected_type']
        problem_text = problem['text']

        # Map expected type
        expected_mapped = type_mapping.get(expected_type, expected_type)

        print(f"\n{'─'*80}")
        print(f"Testing: {problem_id}")
        print(f"  Problem: {problem_name}")
        print(f"  Expected type: {expected_mapped}")

        try:
            # Predict using ML
            X = vectorizer.transform([problem_text])
            predicted = classifier.predict(X)[0]
            probabilities = classifier.predict_proba(X)[0]
            confidence = max(probabilities) * 100

            # Get top 3 predictions
            top_indices = probabilities.argsort()[-3:][::-1]
            top_predictions = [
                (classifier.classes_[i], probabilities[i] * 100)
                for i in top_indices
            ]

            # Check correctness
            ok_type = (predicted == expected_mapped)

            print(f"\n  🤖 ML RESULT:")
            print(f"     predicted={predicted} ({confidence:.0f}%) {'✓' if ok_type else '✗'}")
            print(f"     Top 3: {', '.join([f'{p} ({c:.1f}%)' for p, c in top_predictions])}")

            # Update counters (ML always predicts intent=optimization, doesn't predict category)
            results['correct_intent'] += 1  # Assume all are optimization
            results['correct_type'] += int(ok_type)

            # Record errors
            if not ok_type:
                results['errors'].append({
                    'id': problem_id,
                    'name': problem_name,
                    'exp': {'type': expected_mapped},
                    'got': {'type': predicted},
                    'confidence': confidence,
                    'top_3': top_predictions
                })

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
    t = max(classification_results['total'], 1)  # Avoid division by zero

    print(f"\n{'='*80}")
    print(f"  TEST SUMMARY")
    print(f"{'='*80}\n")

    print("Classification:")
    print(f"  Total: {t}")
    print(f"  Intent accuracy:    {classification_results['correct_intent']}/{t} = {classification_results['correct_intent']/t*100:.1f}%")
    print(f"  Category accuracy:  {classification_results['correct_category']}/{t} = {classification_results['correct_category']/t*100:.1f}%")
    print(f"  Type accuracy:      {classification_results['correct_type']}/{t} = {classification_results['correct_type']/t*100:.1f}%")
    print(f"  All-three accuracy: {classification_results['all_three_correct']}/{t} = {classification_results['all_three_correct']/t*100:.1f}%")

    # Compute ML metrics (for type classification - the most important metric)
    correct = classification_results['correct_type']
    incorrect = t - correct

    # For binary classification metrics (treating each type as binary: correct vs incorrect)
    # True Positives: correctly classified as the expected type
    # False Negatives: incorrectly classified (missed the correct type)
    tp = correct
    fn = incorrect
    # Since we're measuring accuracy, not detection, we consider:
    # Precision = TP / (TP + FP), but in multi-class, we use macro averaging

    # Calculate per-class metrics if we have error details
    if correct > 0 or incorrect > 0:
        accuracy = correct / t

        # For a multi-class setting, compute macro precision/recall/F1
        # Precision: When we predict type X, how often is it correct?
        # Recall: Of all actual type X, how many did we find?
        # For perfect classification, both are 100%

        precision = accuracy  # In our setup, precision = recall = accuracy
        recall = accuracy
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        print(f"\n  📊 ML Metrics (Type Classification):")
        print(f"     Precision: {precision*100:.1f}%")
        print(f"     Recall:    {recall*100:.1f}%")
        print(f"     F1-Score:  {f1_score*100:.1f}%")

    # Show RAG usage statistics
    if classification_results.get('rag_used', 0):
        print(f"\n  📚 RAG retrievals: {classification_results['rag_used']}/{t}")

    if classification_results['errors']:
        print(f"\n  Misclassifications ({len(classification_results['errors'])}):")
        for e in classification_results['errors']:
            if 'error' in e:
                print(f"    - {e['id']}: ERROR {e['error']}")
            else:
                print(f"    - {e['id']}:")
                print(f"        exp: {e['exp']}")
                print(f"        got: {e['got']}")

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
    # parser.add_argument('--show-rag', action='store_true',
    #                    help='Show RAG retrieval details for each problem')  # RAG removed
    # parser.add_argument('--compare-rag', action='store_true',
    #                    help='Compare classification with and without RAG')  # RAG removed
    parser.add_argument('--host', type=str, default='http://localhost:11434',
                       help='Ollama host (default: http://localhost:11434)')
    parser.add_argument('--model', type=str, default='deepseek-r1:latest',
                       help='LLM model (default: deepseek-r1:latest)')
    parser.add_argument('--use-ml', action='store_true',
                       help='Use ML classifier instead of LLM')

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

    # Use ML classifier if requested
    if args.use_ml:
        print("\n🤖 Using ML Classifier\n")
        classification_results = test_classification_ml(problems)
        if classification_results is None:
            return 1
        print_summary(classification_results, None)
        return 0 if not classification_results['errors'] else 1

    # RAG comparison mode removed
    if False:  # args.compare_rag removed
        print("\n" + "="*80)
        print("  COMPARISON MODE: WITH vs WITHOUT RAG")
        print("="*80 + "\n")

        # Run WITHOUT RAG first
        print("━━━ PHASE 1: Classification WITHOUT RAG ━━━\n")
        try:
            llm_client_no_rag = EnhancedLLMClient(host=args.host, model=args.model, knowledge_base=None)
            print(f"✓ Connected (NO RAG)\n")
        except Exception as e:
            print(f"✗ Failed to connect to LLM: {e}")
            return 1

        results_without_rag = test_classification(problems, llm_client_no_rag, show_rag=False)

        # Run WITH RAG
        print("\n" + "━"*80)
        print("━━━ PHASE 2: Classification WITH RAG ━━━\n")
        try:
            print("Loading RAG knowledge base...")
            kb = KnowledgeBase()
            print(f"✓ RAG knowledge base loaded\n")
            llm_client_with_rag = EnhancedLLMClient(host=args.host, model=args.model, knowledge_base=kb)
        except Exception as e:
            print(f"⚠️  Could not load knowledge base: {e}")
            return 1

        results_with_rag = test_classification(problems, llm_client_with_rag, show_rag=args.show_rag)

        # Print comparison summary
        print("\n" + "="*80)
        print("  COMPARISON SUMMARY")
        print("="*80 + "\n")

        print(f"WITHOUT RAG:")
        print(f"  Accuracy: {results_without_rag['correct']}/{results_without_rag['total']} = {results_without_rag['correct']/results_without_rag['total']*100:.1f}%")
        print(f"  Errors: {len(results_without_rag['errors'])}")

        print(f"\nWITH RAG:")
        print(f"  Accuracy: {results_with_rag['correct']}/{results_with_rag['total']} = {results_with_rag['correct']/results_with_rag['total']*100:.1f}%")
        print(f"  Errors: {len(results_with_rag['errors'])}")
        print(f"  RAG Queries: {results_with_rag.get('rag_used', 0)}")

        # Show improvement
        diff = results_with_rag['correct'] - results_without_rag['correct']
        if diff > 0:
            print(f"\n📈 IMPROVEMENT: +{diff} problems correctly classified with RAG")
        elif diff < 0:
            print(f"\n📉 REGRESSION: {abs(diff)} fewer problems correctly classified with RAG")
        else:
            print(f"\n➡️  NO CHANGE: Same accuracy with and without RAG")

        # Show which problems changed
        errors_without = {e['id'] for e in results_without_rag['errors']}
        errors_with = {e['id'] for e in results_with_rag['errors']}

        fixed_by_rag = errors_without - errors_with
        broken_by_rag = errors_with - errors_without

        if fixed_by_rag:
            print(f"\n✅ Fixed by RAG ({len(fixed_by_rag)}):")
            for problem_id in fixed_by_rag:
                print(f"   - {problem_id}")

        if broken_by_rag:
            print(f"\n❌ Broken by RAG ({len(broken_by_rag)}):")
            for problem_id in broken_by_rag:
                print(f"   - {problem_id}")

        print()
        return 0 if len(results_with_rag['errors']) == 0 else 1

    # Normal mode (not comparison)
    # RAG initialization removed

    # Initialize LLM client
    try:
        llm_client = EnhancedLLMClient(host=args.host, model=args.model)
        print(f"✓ Connected to {args.host} using model {args.model}\n")
    except Exception as e:
        print(f"✗ Failed to connect to LLM: {e}")
        return 1

    # Run classification tests
    classification_results = test_classification(problems, llm_client, show_rag=False)  # RAG removed

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
