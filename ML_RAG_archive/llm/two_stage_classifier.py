# llm/two_stage_classifier.py
"""
Two-Stage Classifier: ML suggests → LLM verifies

Stage 1: ML classifier makes fast prediction
Stage 2: LLM validates if the problem matches ML's suggestion

Strategy: Use ML's complementary strengths while letting LLM's reasoning
judge correctness. LLM sees both the problem AND the ML suggestion.
"""

import pickle
import json
from pathlib import Path
from typing import Dict, Any, Tuple

# ============================================================================
# CONFIGURATION
# ============================================================================
VERIFICATION_CONFIDENCE_THRESHOLD = 0.7  # LLM must be this confident to accept/reject

# ============================================================================
# VERIFICATION PROMPT
# ============================================================================
VERIFICATION_SYSTEM = """You are an Operations Research problem verification expert.

Your task: Given a problem description and a SUGGESTED classification, determine if the suggestion is CORRECT.

Analyze the problem structure (variables, constraints, objective) and decide:
- ACCEPT: The suggested type accurately describes this problem
- REJECT: The suggested type is wrong, provide the correct type instead

Focus on mathematical structure, not keywords."""

VERIFICATION_USER_TMPL = """Problem Description:
\"\"\"{problem_text}\"\"\"

SUGGESTED Classification: {suggested_type}

Question: Is this suggestion CORRECT?

Analyze:
1. What is the objective function? (minimize/maximize what?)
2. What are the decision variables? (binary, integer, continuous?)
3. What are the key constraints? (assignment, capacity, flow, etc.)
4. Does the structure match "{suggested_type}"?

Respond in JSON:
{{
  "verdict": "ACCEPT" or "REJECT",
  "confidence": 0.0 to 1.0,
  "reasoning": "Brief explanation of why",
  "correct_type": "only if REJECT, what is the correct type?"
}}

Valid types: {valid_types}
"""


class TwoStageClassifier:
    """
    Two-stage classification: ML suggests, LLM verifies.

    Process:
    1. ML makes fast prediction
    2. LLM validates if problem matches ML's suggestion
    3. If LLM rejects, use LLM's correction
    4. If LLM uncertain, default to ML
    """

    def __init__(self, llm_client, ml_model_path: str = "models/problem_classifier.pkl",
                 ml_vectorizer_path: str = "models/problem_vectorizer.pkl"):
        """
        Initialize two-stage classifier.

        Args:
            llm_client: OllamaClient for LLM verification
            ml_model_path: Path to ML classifier
            ml_vectorizer_path: Path to TF-IDF vectorizer
        """
        self.llm = llm_client

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
                raise RuntimeError(f"Could not load ML classifier: {e}")
        else:
            raise RuntimeError(f"ML models not found at {model_path}")

        # Valid problem types (from schemas)
        from .schemas import CLASS_ENUM
        self.valid_types = CLASS_ENUM

    def _ml_predict(self, text: str) -> Tuple[str, float]:
        """Get ML prediction."""
        X = self.ml_vectorizer.transform([text])
        predicted = self.ml_classifier.predict(X)[0]
        confidence = max(self.ml_classifier.predict_proba(X)[0])
        return predicted, confidence

    def _llm_verify(self, problem_text: str, suggested_type: str) -> Dict[str, Any]:
        """
        Ask LLM to verify if suggested_type matches the problem.

        Returns:
            {
                'verdict': 'ACCEPT' or 'REJECT',
                'confidence': float,
                'reasoning': str,
                'correct_type': str (if REJECT)
            }
        """
        user_prompt = VERIFICATION_USER_TMPL.format(
            problem_text=problem_text,
            suggested_type=suggested_type,
            valid_types=', '.join(self.valid_types)
        )

        try:
            response = self.llm._chat(VERIFICATION_SYSTEM, user_prompt, json_mode=True)
            result = json.loads(response)

            # Validate response
            if 'verdict' not in result or 'confidence' not in result:
                return {
                    'verdict': 'ACCEPT',
                    'confidence': 0.5,
                    'reasoning': 'LLM response invalid, defaulting to ML',
                    'correct_type': suggested_type
                }

            return result

        except Exception as e:
            print(f"⚠️  LLM verification error: {e}")
            return {
                'verdict': 'ACCEPT',
                'confidence': 0.5,
                'reasoning': f'Error: {str(e)}, defaulting to ML',
                'correct_type': suggested_type
            }

    def classify(self, text: str, verbose: bool = False) -> Dict[str, Any]:
        """
        Two-stage classification.

        Args:
            text: Problem description
            verbose: Show decision process

        Returns:
            {
                'problem_type': str,
                'confidence': float,
                'method': str,
                'ml_suggestion': dict,
                'llm_verification': dict,
                'reasoning': str
            }
        """
        # Stage 1: ML suggests
        ml_type, ml_conf = self._ml_predict(text)

        if verbose:
            print(f"\n  Stage 1 - ML suggests: {ml_type} (conf={ml_conf:.2f})")

        # Stage 2: LLM verifies
        verification = self._llm_verify(text, ml_type)

        if verbose:
            print(f"  Stage 2 - LLM verdict: {verification['verdict']} (conf={verification['confidence']:.2f})")
            print(f"  Reasoning: {verification['reasoning']}")

        # Decision logic
        verdict = verification['verdict']
        llm_conf = verification['confidence']

        if verdict == 'ACCEPT':
            # LLM accepts ML suggestion
            final_type = ml_type
            method = "ml_accepted"
            reasoning = f"ML suggested {ml_type}, LLM accepted"
            final_conf = max(ml_conf, llm_conf)

        elif verdict == 'REJECT' and llm_conf >= VERIFICATION_CONFIDENCE_THRESHOLD:
            # LLM rejects with high confidence, use LLM's correction
            final_type = verification.get('correct_type', ml_type)
            method = "llm_corrected"
            reasoning = f"ML suggested {ml_type}, LLM corrected to {final_type}"
            final_conf = llm_conf

        else:
            # LLM rejects but uncertain, stick with ML
            final_type = ml_type
            method = "ml_default"
            reasoning = f"LLM uncertain (conf={llm_conf:.0%}), keeping ML suggestion"
            final_conf = ml_conf

        if verbose:
            print(f"  → Final: {final_type} via {method}\n")

        return {
            'problem_type': final_type,
            'confidence': final_conf,
            'method': method,
            'ml_suggestion': {
                'type': ml_type,
                'confidence': ml_conf
            },
            'llm_verification': verification,
            'reasoning': reasoning
        }
