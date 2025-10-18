"""
Labeling Functions for Assignment Problems
"""

import re
from or_classify.labeling_function import LabelingFunction, LFResult, LFPriority


class AssignmentKeywordLF(LabelingFunction):
    """Detects assignment problems by keyword"""

    def priority(self) -> LFPriority:
        return LFPriority.HIGH

    def description(self) -> str:
        return "Detects 'assignment' keyword with one-to-one context"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        if "assign" not in text_lower:
            return self._abstain()

        # Check for one-to-one indicators
        one_to_one_indicators = [
            "one-to-one", "one to one", "1-to-1", "1 to 1",
            "each worker", "each machine", "each task",
            "workers to tasks", "machines to jobs"
        ]

        evidence = ["Found 'assign' keyword"]

        for indicator in one_to_one_indicators:
            if indicator in text_lower:
                evidence.append(f"One-to-one mapping: '{indicator}'")
                return self._label(
                    label="matching_assignment.assignment",
                    confidence=0.95,
                    evidence=evidence
                )

        # Just "assign" without context -> abstain (too weak)
        return self._abstain()


class HungarianMethodLF(LabelingFunction):
    """Detects Hungarian algorithm/method references"""

    def priority(self) -> LFPriority:
        return LFPriority.CRITICAL

    def description(self) -> str:
        return "Detects Hungarian algorithm/method (specific to assignment)"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        keywords = ["hungarian algorithm", "hungarian method", "kuhn-munkres"]

        for keyword in keywords:
            if keyword in text_lower:
                return self._label(
                    label="matching_assignment.assignment",
                    confidence=1.0,
                    evidence=[f"Algorithm reference: '{keyword}'"]
                )

        return self._abstain()


class OneToOneMappingLF(LabelingFunction):
    """Detects one-to-one mapping structure"""

    def priority(self) -> LFPriority:
        return LFPriority.MEDIUM

    def description(self) -> str:
        return "Detects one-to-one mapping without 'assignment' keyword"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        # Pattern: N entities to N entities
        n_to_n_pattern = r'\b(\d+)\s+(workers?|agents?|machines?)\s+.*?\s+\1\s+(tasks?|jobs?)'

        if re.search(n_to_n_pattern, text_lower):
            # Check for one-to-one constraint
            one_to_one = ["each", "exactly one", "one and only one"]
            if any(phrase in text_lower for phrase in one_to_one):
                return self._label(
                    label="matching_assignment.assignment",
                    confidence=0.90,
                    evidence=["N-to-N mapping detected", "One-to-one constraint found"]
                )

        return self._abstain()
