#!/usr/bin/env python3
"""
Train ML Classifier for OR Problem Classification

Uses the 523 labeled instances from ML_approaches/ML/FINAL_ML_DATASET.csv to train
a fast, accurate classifier for problem subtype detection.

PURPOSE: Replace LLM-based classification (17-25% accuracy) with ML (target: 90-95%)

USAGE:
    python scripts/train_classifier.py

OUTPUT:
    - Trained model saved to models/problem_classifier.pkl
    - Vectorizer saved to models/problem_vectorizer.pkl
    - Classification report with accuracy metrics
    - Feature importance analysis
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
import pickle
from pathlib import Path


def load_dataset():
    """Load training dataset."""
    print("Loading dataset...")
    df = pd.read_csv('ML_approaches/ML/FINAL_ML_DATASET.csv')
    print(f"✓ Loaded {len(df)} instances")

    # Show distribution
    print("\nClass distribution:")
    for subtype, count in df['subtype'].value_counts().items():
        print(f"  {subtype}: {count} ({count/len(df)*100:.1f}%)")

    return df


def create_features(df):
    """Create feature vectors from text."""
    print("\nCreating feature vectors...")

    # Use TF-IDF with character n-grams (captures patterns like "M1→M2")
    vectorizer = TfidfVectorizer(
        max_features=1000,
        ngram_range=(1, 3),  # Unigrams, bigrams, trigrams
        analyzer='word',
        lowercase=True,
        stop_words='english',
        min_df=2,  # Ignore terms that appear in < 2 documents
        max_df=0.8  # Ignore terms that appear in > 80% of documents
    )

    X = vectorizer.fit_transform(df['text'])
    y = df['subtype'].values

    print(f"✓ Created {X.shape[0]} samples with {X.shape[1]} features")
    print(f"✓ Feature names sample: {vectorizer.get_feature_names_out()[:10].tolist()}")

    return X, y, vectorizer


def train_classifier(X_train, y_train):
    """Train Random Forest classifier."""
    print("\nTraining classifier...")

    clf = RandomForestClassifier(
        n_estimators=200,       # Number of trees
        max_depth=20,           # Max tree depth
        min_samples_split=5,    # Min samples to split node
        min_samples_leaf=2,     # Min samples in leaf
        class_weight='balanced',  # Handle class imbalance
        random_state=42,
        n_jobs=-1               # Use all CPU cores
    )

    clf.fit(X_train, y_train)
    print("✓ Classifier trained")

    return clf


def evaluate_classifier(clf, X_train, X_test, y_train, y_test, vectorizer):
    """Evaluate classifier performance."""
    print("\n" + "="*80)
    print("EVALUATION RESULTS")
    print("="*80)

    # Training accuracy
    train_score = clf.score(X_train, y_train)
    print(f"\nTraining Accuracy: {train_score:.2%}")

    # Test accuracy
    test_score = clf.score(X_test, y_test)
    print(f"Test Accuracy: {test_score:.2%}")

    # Cross-validation
    print("\nPerforming 5-fold cross-validation...")
    cv_scores = cross_val_score(clf, X_train, y_train, cv=5)
    print(f"CV Accuracy: {cv_scores.mean():.2%} (+/- {cv_scores.std() * 2:.2%})")

    # Detailed classification report
    y_pred = clf.predict(X_test)
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # Confusion matrix
    print("Confusion Matrix:")
    cm = confusion_matrix(y_test, y_pred)
    classes = sorted(set(y_test))
    print("\n" + " "*20 + "  ".join(f"{c[:8]:>8}" for c in classes))
    for i, cls in enumerate(classes):
        print(f"{cls[:18]:>18}  " + "  ".join(f"{cm[i,j]:>8}" for j in range(len(classes))))

    # Feature importance
    print("\nTop 20 Most Important Features:")
    feature_names = vectorizer.get_feature_names_out()
    importances = clf.feature_importances_
    indices = np.argsort(importances)[::-1][:20]

    for i, idx in enumerate(indices, 1):
        print(f"  {i:2d}. {feature_names[idx]:20s} {importances[idx]:.4f}")

    return test_score


def save_model(clf, vectorizer, output_dir='models'):
    """Save trained model and vectorizer."""
    print(f"\nSaving model to {output_dir}/...")

    Path(output_dir).mkdir(exist_ok=True)

    # Save classifier
    with open(f'{output_dir}/problem_classifier.pkl', 'wb') as f:
        pickle.dump(clf, f)

    # Save vectorizer
    with open(f'{output_dir}/problem_vectorizer.pkl', 'wb') as f:
        pickle.dump(vectorizer, f)

    print("✓ Model saved:")
    print(f"  - {output_dir}/problem_classifier.pkl")
    print(f"  - {output_dir}/problem_vectorizer.pkl")


def test_sample_predictions(clf, vectorizer):
    """Test classifier on sample problems."""
    print("\n" + "="*80)
    print("SAMPLE PREDICTIONS")
    print("="*80)

    test_cases = [
        {
            "text": "A job shop with 10 jobs and 5 machines. Each job follows a sequence: Job1: M1→M2→M3",
            "expected": "job_shop"
        },
        {
            "text": "Ship 500 units from Seattle to Chicago. Seattle capacity: 350, Denver: 200. Minimize cost.",
            "expected": "transportation"
        },
        {
            "text": "Schedule 5 jobs on 3 parallel machines. Each job can run on any machine. Minimize makespan.",
            "expected": "single_stage_scheduling"
        },
        {
            "text": "All jobs follow the same machine sequence: M1→M2→M3. Process all jobs through flow shop.",
            "expected": "flow_shop"
        }
    ]

    for i, case in enumerate(test_cases, 1):
        X = vectorizer.transform([case['text']])
        pred = clf.predict(X)[0]
        proba = clf.predict_proba(X)[0]
        confidence = max(proba)

        status = "✓" if pred == case['expected'] else "✗"
        print(f"\nTest {i}: {status}")
        print(f"  Text: {case['text'][:70]}...")
        print(f"  Expected: {case['expected']}")
        print(f"  Predicted: {pred} (confidence: {confidence:.2%})")


def main():
    print("="*80)
    print("ML CLASSIFIER TRAINING")
    print("="*80)

    # Load data
    df = load_dataset()

    # Create features
    X, y, vectorizer = create_features(df)

    # Split data (80/20 train/test)
    # Note: Can't use stratify for classes with only 1 instance
    print("\nSplitting data (80% train, 20% test)...")

    # Check if stratification is possible
    from collections import Counter
    class_counts = Counter(y)
    min_samples = min(class_counts.values())

    if min_samples >= 2:
        # Can use stratified split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        print("✓ Using stratified split")
    else:
        # Use regular split for rare classes
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        print(f"⚠ Using regular split (some classes have only {min_samples} instance)")

    print(f"✓ Train: {len(y_train)} samples")
    print(f"✓ Test: {len(y_test)} samples")

    # Train
    clf = train_classifier(X_train, y_train)

    # Evaluate
    test_accuracy = evaluate_classifier(clf, X_train, X_test, y_train, y_test, vectorizer)

    # Save
    save_model(clf, vectorizer)

    # Test samples
    test_sample_predictions(clf, vectorizer)

    # Summary
    print("\n" + "="*80)
    print("TRAINING COMPLETE")
    print("="*80)
    print(f"✓ Test Accuracy: {test_accuracy:.2%}")
    print(f"✓ Model saved to models/")
    print(f"\nNext steps:")
    print("  1. Integrate classifier into llm/intent_router.py")
    print("  2. Replace LLM classification calls with ML classifier")
    print("  3. Use LLM as fallback for low-confidence predictions")

    return 0


if __name__ == "__main__":
    sys.exit(main())
