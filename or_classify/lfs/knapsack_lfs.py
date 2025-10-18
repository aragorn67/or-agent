"""
Labeling Functions for Knapsack Problems
"""

import re
from or_classify.labeling_function import LabelingFunction, LFResult, LFPriority


class KnapsackKeywordLF(LabelingFunction):
    """Detects knapsack problems by keyword"""

    def priority(self) -> LFPriority:
        return LFPriority.CRITICAL

    def description(self) -> str:
        return "Detects 'knapsack' keyword"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        if "knapsack" in text_lower:
            # Check for subtype indicators
            if "0-1" in text or "0/1" in text or "zero-one" in text_lower or "binary" in text_lower:
                return self._label(
                    label="knapsack.zero_one_knapsack",
                    confidence=1.0,
                    evidence=["Found 'knapsack'", "Binary/0-1 indicator"]
                )

            if "unbounded" in text_lower or "unlimited" in text_lower:
                return self._label(
                    label="knapsack.unbounded_knapsack",
                    confidence=1.0,
                    evidence=["Found 'knapsack'", "Unbounded indicator"]
                )

            if "bounded" in text_lower:
                return self._label(
                    label="knapsack.bounded_knapsack",
                    confidence=1.0,
                    evidence=["Found 'knapsack'", "Bounded indicator"]
                )

            # Default to 0-1 (most common)
            return self._label(
                label="knapsack.zero_one_knapsack",
                confidence=0.90,
                evidence=["Found 'knapsack'"]
            )

        return self._abstain()


class PortfolioKeywordLF(LabelingFunction):
    """Detects portfolio optimization (alias for knapsack)"""

    def priority(self) -> LFPriority:
        return LFPriority.HIGH

    def description(self) -> str:
        return "Detects portfolio optimization keywords"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        portfolio_keywords = [
            "portfolio optimization",
            "portfolio selection",
            "investment selection",
            "capital budgeting",
            "project selection"
        ]

        evidence = []
        for keyword in portfolio_keywords:
            if keyword in text_lower:
                evidence.append(f"Found '{keyword}'")

        # Check for binary selection indicators
        binary_indicators = [
            "fund or not", "invest or not", "select or not",
            "binary decision", "0 or 1", "yes or no"
        ]

        if evidence:
            for indicator in binary_indicators:
                if indicator in text_lower:
                    evidence.append(f"Binary selection: '{indicator}'")
                    break

            return self._label(
                label="knapsack.zero_one_knapsack",
                confidence=0.93,
                evidence=evidence
            )

        return self._abstain()


class ZeroOneKnapsackLF(LabelingFunction):
    """Detects 0-1 selection structure"""

    def priority(self) -> LFPriority:
        return LFPriority.MEDIUM

    def description(self) -> str:
        return "Detects binary selection with capacity constraint"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        # Look for selection + capacity + value patterns
        has_selection = any(word in text_lower for word in ["select", "choose", "pick"])
        has_capacity = any(word in text_lower for word in ["capacity", "budget", "limit", "constraint"])
        has_value = any(word in text_lower for word in ["value", "profit", "benefit", "utility", "maximize"])

        # Binary indicators
        binary = any(phrase in text_lower for phrase in ["0 or 1", "take or leave", "binary"])

        if has_selection and has_capacity and has_value:
            evidence = ["Selection decision", "Capacity constraint", "Value objective"]

            if binary:
                evidence.append("Binary indicator")
                return self._label(
                    label="knapsack.zero_one_knapsack",
                    confidence=0.88,
                    evidence=evidence
                )

        return self._abstain()


class BinPackingLF(LabelingFunction):
    """Detects bin packing problems"""

    def priority(self) -> LFPriority:
        return LFPriority.HIGH

    def description(self) -> str:
        return "Detects bin packing keywords"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        bin_packing_keywords = [
            "bin packing",
            "bin-packing",
            "pack items into bins",
            "minimize.*bins",
            "minimize.*containers"
        ]

        evidence = []
        for keyword in bin_packing_keywords:
            if re.search(keyword, text_lower):
                evidence.append(f"Bin packing pattern: '{keyword}'")

        if evidence:
            # Bin packing is a variant of knapsack
            return self._label(
                label="knapsack.zero_one_knapsack",
                confidence=0.85,
                evidence=evidence
            )

        return self._abstain()
