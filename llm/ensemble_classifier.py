# llm/ensemble_classifier.py
"""
Ensemble Classifier: Combines LLM (DeepSeek-R1) + ML (Random Forest) predictions

Strategy: Use complementary strengths of both approaches
- LLM: High confidence (95%), good reasoning, 70% accuracy
- ML: Fast (<1ms), different failure modes, 70% accuracy
- Ensemble: Potential 90% accuracy by combining both

Configuration parameters at top for easy tuning.
"""

import pickle
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from .problem_classifier import ProblemClassifier

# ============================================================================
# CONFIGURATION PARAMETERS - Tune these for best performance
# ============================================================================

# Confidence thresholds
LLM_HIGH_CONFIDENCE_THRESHOLD = 0.91  # If LLM is this confident, trust it (tune this!)
ML_CONFIDENCE_THRESHOLD = 0.15        # ML confidence above this is meaningful (tune this!)

# Agreement strategy
TRUST_AGREEMENT = True                 # If both agree, always use that result

# Fallback when both disagree with low confidence
DEFAULT_TO_LLM = True                  # True = use LLM, False = use ML

# Type mapping for ML classifier (maps specific types to ML categories)
ML_TYPE_MAPPING = {
    'single_stage_scheduling': 'single_stage_scheduling',
    'transportation': 'transportation',
    'min_cost_flow': 'transportation',  # ML doesn't distinguish this subtype
    'job_shop': 'job_shop',
    'flow_shop': 'flow_shop',
}


class EnsembleClassifier:
    """
    Ensemble classifier combining LLM and ML predictions.

    Decision logic:
    1. If both agree → use agreed result
    2. If LLM confidence > 0.95 → use LLM
    3. If ML confidence > 0.25 → use ML
    4. Else → default to LLM (has reasoning)
    """

    def __init__(self, llm_client, ml_model_path: str = "models/problem_classifier.pkl",
                 ml_vectorizer_path: str = "models/problem_vectorizer.pkl"):
        """
        Initialize ensemble classifier.

        Args:
            llm_client: OllamaClient instance for LLM classification
            ml_model_path: Path to trained ML classifier
            ml_vectorizer_path: Path to TF-IDF vectorizer
        """
        # Initialize LLM classifier
        self.llm_classifier = ProblemClassifier(llm_client)

        # Load ML classifier
        self.ml_classifier = None
        self.ml_vectorizer = None

        model_path = Path(ml_model_path)
        vectorizer_path = Path(ml_vectorizer_path)

        if model_path.exists() and vectorizer_path.exists():
            try:
                with open(model_path, 'rb') as f:
                    self.ml_classifier = pickle.load(f)
                with open(vectorizer_path, 'rb') as f:
                    self.ml_vectorizer = pickle.load(f)
                print(f"✓ ML classifier loaded")
            except Exception as e:
                print(f"⚠️  Could not load ML classifier: {e}")
                print("   Falling back to LLM-only mode")
        else:
            print(f"⚠️  ML models not found at {model_path}")
            print("   Falling back to LLM-only mode")

    def _classify_ml(self, text: str) -> Tuple[str, float]:
        """
        Classify using ML model.

        Returns:
            (predicted_type, confidence)
        """
        if self.ml_classifier is None or self.ml_vectorizer is None:
            return "unknown", 0.0

        try:
            X = self.ml_vectorizer.transform([text])
            predicted = self.ml_classifier.predict(X)[0]
            probabilities = self.ml_classifier.predict_proba(X)[0]
            confidence = max(probabilities)

            return predicted, confidence
        except Exception as e:
            print(f"⚠️  ML classification error: {e}")
            return "unknown", 0.0

    def _classify_llm(self, text: str) -> Tuple[str, float, str]:
        """
        Classify using LLM.

        Returns:
            (predicted_type, confidence, reasoning)
        """
        try:
            result, votes = self.llm_classifier.classify(text)
            predicted = result.get('problem_type', 'custom_review')
            confidence = result.get('confidence', 0.0)
            reasoning = result.get('why_short', 'No explanation')

            return predicted, confidence, reasoning
        except Exception as e:
            print(f"⚠️  LLM classification error: {e}")
            return "custom_review", 0.0, str(e)

    def _normalize_ml_type(self, ml_type: str) -> str:
        """
        Normalize ML type to match expected types.
        Some ML predictions need to be mapped (e.g., 'scheduling' → stays as is)
        """
        # ML might return general category, keep as is for comparison
        return ml_type

    def classify(self, text: str, verbose: bool = False) -> Dict[str, Any]:
        """
        Classify using ensemble approach.

        Args:
            text: Problem description
            verbose: If True, show decision process

        Returns:
            {
                'problem_type': str,
                'confidence': float,
                'method': 'llm' | 'ml' | 'ensemble_agree' | 'ensemble_llm' | 'ensemble_ml',
                'llm_result': dict,
                'ml_result': dict,
                'reasoning': str
            }
        """
        # Get predictions from both
        llm_type, llm_conf, llm_reasoning = self._classify_llm(text)
        ml_type, ml_conf = self._classify_ml(text)

        # Normalize ML type for comparison
        ml_type_normalized = self._normalize_ml_type(ml_type)

        if verbose:
            print(f"\n  LLM: {llm_type} (conf={llm_conf:.2f})")
            print(f"  ML:  {ml_type} (conf={ml_conf:.2f})")

        # Decision logic: Only use ML when LLM is uncertain (< threshold)
        decision_method = None
        final_type = None
        final_conf = None
        decision_reason = None

        # Case 1: LLM has high confidence - trust it (even if ML disagrees)
        if llm_conf >= LLM_HIGH_CONFIDENCE_THRESHOLD:
            final_type = llm_type
            final_conf = llm_conf
            decision_method = "llm_confident"
            decision_reason = f"LLM confidence {llm_conf:.0%} >= {LLM_HIGH_CONFIDENCE_THRESHOLD:.0%}"

        # Case 2: LLM is uncertain AND ML has meaningful confidence - use ML
        elif llm_conf < LLM_HIGH_CONFIDENCE_THRESHOLD and ml_conf >= ML_CONFIDENCE_THRESHOLD:
            final_type = ml_type
            final_conf = ml_conf
            decision_method = "ml_rescue"
            decision_reason = f"LLM uncertain ({llm_conf:.0%}), ML confident ({ml_conf:.0%})"

        # Case 3: Both uncertain - default to LLM (has reasoning)
        else:
            if DEFAULT_TO_LLM:
                final_type = llm_type
                final_conf = llm_conf
                decision_method = "llm_default"
                decision_reason = "Both uncertain, default to LLM"
            else:
                final_type = ml_type
                final_conf = ml_conf
                decision_method = "ml_default"
                decision_reason = "Both uncertain, default to ML"

        if verbose:
            print(f"  → Decision: {final_type} via {decision_method}")
            print(f"  → Reason: {decision_reason}")

        return {
            'problem_type': final_type,
            'confidence': final_conf,
            'method': decision_method,
            'llm_result': {
                'type': llm_type,
                'confidence': llm_conf,
                'reasoning': llm_reasoning
            },
            'ml_result': {
                'type': ml_type,
                'confidence': ml_conf
            },
            'decision_reasoning': decision_reason
        }
