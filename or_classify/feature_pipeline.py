"""
Feature Pipeline for Hybrid OR Classifier
Combines TF-IDF, LF outputs, and engineered features
"""

import numpy as np
from typing import List, Dict, Any, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.sparse import hstack, csr_matrix
import re

from or_classify.labeling_function import LFRegistry, ABSTAIN
from or_classify.normalizer import LabelNormalizer


class FeaturePipeline:
    """
    Extracts features for ML classifier

    Features include:
    1. TF-IDF vectors from problem text
    2. LF outputs (one-hot encoded labels + confidence scores)
    3. Engineered flags (has_numbers, has_time_periods, etc.)
    """

    def __init__(
        self,
        lf_registry: LFRegistry,
        normalizer: LabelNormalizer,
        max_tfidf_features: int = 500,
        tfidf_ngram_range: Tuple[int, int] = (1, 2)
    ):
        """
        Initialize feature pipeline

        Args:
            lf_registry: Registry of labeling functions
            normalizer: Label normalizer
            max_tfidf_features: Max TF-IDF features to extract
            tfidf_ngram_range: N-gram range for TF-IDF (default: unigrams + bigrams)
        """
        self.lf_registry = lf_registry
        self.normalizer = normalizer
        self.max_tfidf_features = max_tfidf_features
        self.tfidf_ngram_range = tfidf_ngram_range

        # TF-IDF vectorizer (fit during training)
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=max_tfidf_features,
            ngram_range=tfidf_ngram_range,
            lowercase=True,
            stop_words='english',
            min_df=2  # Ignore terms that appear in fewer than 2 documents
        )

        # Label vocabulary (built from taxonomy)
        self.label_vocab = sorted(list(normalizer.valid_labels))
        self.label_to_idx = {label: idx for idx, label in enumerate(self.label_vocab)}

        self._is_fitted = False

    def fit(self, texts: List[str]) -> 'FeaturePipeline':
        """
        Fit the pipeline on training texts (TF-IDF vocabulary)

        Args:
            texts: List of problem descriptions

        Returns:
            Self (for chaining)
        """
        # Fit TF-IDF vectorizer
        self.tfidf_vectorizer.fit(texts)
        self._is_fitted = True

        return self

    def transform(self, texts: List[str]) -> Tuple[csr_matrix, List[Dict[str, Any]]]:
        """
        Transform texts into feature vectors

        Args:
            texts: List of problem descriptions

        Returns:
            Tuple of (feature_matrix, metadata)
            - feature_matrix: Sparse matrix (n_samples x n_features)
            - metadata: List of dicts with LF info for each sample
        """
        if not self._is_fitted:
            raise ValueError("Pipeline not fitted. Call fit() first.")

        n_samples = len(texts)

        # 1. TF-IDF features
        tfidf_features = self.tfidf_vectorizer.transform(texts)

        # 2. LF features
        lf_features = []
        metadata = []

        for text in texts:
            lf_vector, lf_meta = self._extract_lf_features(text)
            lf_features.append(lf_vector)
            metadata.append(lf_meta)

        lf_features = np.array(lf_features)

        # 3. Engineered features
        engineered_features = np.array([
            self._extract_engineered_features(text) for text in texts
        ])

        # Combine all features
        feature_matrix = hstack([
            tfidf_features,
            csr_matrix(lf_features),
            csr_matrix(engineered_features)
        ])

        return feature_matrix, metadata

    def _extract_lf_features(self, text: str) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Extract LF features for a single text

        Returns:
            Tuple of (feature_vector, metadata)
            - feature_vector: One-hot encoded labels + confidence scores
            - metadata: Dict with LF results for explainability
        """
        # Apply all LFs
        lf_results = self.lf_registry.apply_all(text, stop_on_first=False)

        # Initialize feature vector
        # Features: [label_one_hot (len=vocab_size), max_confidence, num_lfs_fired]
        n_labels = len(self.label_vocab)
        label_one_hot = np.zeros(n_labels)
        confidences = []

        metadata = {
            "lf_results": lf_results,
            "num_fired": len(lf_results),
            "labels": []
        }

        for result in lf_results:
            if not result.is_abstain():
                # Normalize label
                canonical_label, _ = self.normalizer.normalise_label(result.label)

                # Mark in one-hot (can have multiple LFs voting for different labels)
                if canonical_label in self.label_to_idx:
                    idx = self.label_to_idx[canonical_label]
                    label_one_hot[idx] = 1

                confidences.append(result.confidence)
                metadata["labels"].append(canonical_label)

        max_confidence = max(confidences) if confidences else 0.0
        num_fired = len(lf_results)

        # Feature vector: [label_one_hot, max_confidence, num_fired]
        feature_vector = np.concatenate([
            label_one_hot,
            [max_confidence],
            [num_fired]
        ])

        return feature_vector, metadata

    def _extract_engineered_features(self, text: str) -> np.ndarray:
        """
        Extract hand-engineered features from text

        Returns:
            Feature vector with boolean/count features
        """
        text_lower = text.lower()

        features = [
            # Structural indicators
            1 if re.search(r'\d+', text) else 0,  # Has numbers
            1 if re.search(r'(period|month|week|time|horizon)', text_lower) else 0,  # Time-related
            1 if re.search(r'(capacity|limit|constraint)', text_lower) else 0,  # Capacity constraint
            1 if re.search(r'(cost|price|profit|benefit|value)', text_lower) else 0,  # Economic objective

            # Problem indicators
            1 if re.search(r'(minim|min\b)', text_lower) else 0,  # Minimization
            1 if re.search(r'(maxim|max\b)', text_lower) else 0,  # Maximization
            1 if 'inventory' in text_lower else 0,  # Inventory
            1 if 'schedule' in text_lower or 'schedul' in text_lower else 0,  # Scheduling
            1 if 'flow' in text_lower else 0,  # Flow
            1 if 'assign' in text_lower else 0,  # Assignment

            # Complexity indicators
            len(text.split()),  # Word count
            text.count(','),  # Number of commas (proxy for complexity)
            1 if 'binary' in text_lower or '0-1' in text or '0/1' in text else 0,  # Binary variables
            1 if 'integer' in text_lower else 0,  # Integer variables
        ]

        return np.array(features, dtype=float)

    def get_feature_names(self) -> List[str]:
        """
        Get names of all features

        Returns:
            List of feature names
        """
        if not self._is_fitted:
            raise ValueError("Pipeline not fitted")

        feature_names = []

        # TF-IDF features
        tfidf_names = [f"tfidf_{name}" for name in self.tfidf_vectorizer.get_feature_names_out()]
        feature_names.extend(tfidf_names)

        # LF one-hot features
        lf_onehot_names = [f"lf_label_{label}" for label in self.label_vocab]
        feature_names.extend(lf_onehot_names)

        # LF summary features
        feature_names.extend(["lf_max_confidence", "lf_num_fired"])

        # Engineered features
        engineered_names = [
            "has_numbers",
            "has_time_periods",
            "has_capacity",
            "has_economic_objective",
            "has_minimization",
            "has_maximization",
            "has_inventory",
            "has_scheduling",
            "has_flow",
            "has_assignment",
            "word_count",
            "comma_count",
            "has_binary_vars",
            "has_integer_vars"
        ]
        feature_names.extend(engineered_names)

        return feature_names

    def get_n_features(self) -> int:
        """Get total number of features"""
        if not self._is_fitted:
            raise ValueError("Pipeline not fitted")

        n_tfidf = len(self.tfidf_vectorizer.get_feature_names_out())
        n_lf = len(self.label_vocab) + 2  # one-hot + max_conf + num_fired
        n_engineered = 14

        return n_tfidf + n_lf + n_engineered
