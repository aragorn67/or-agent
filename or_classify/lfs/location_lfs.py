"""
Labeling Functions for Location/Allocation Problems
"""

import re
from or_classify.labeling_function import LabelingFunction, LFResult, LFPriority


class FacilityLocationKeywordLF(LabelingFunction):
    """Detects facility location problems"""

    def priority(self) -> LFPriority:
        return LFPriority.HIGH

    def description(self) -> str:
        return "Detects facility location keywords"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        facility_keywords = [
            "facility location",
            "warehouse location",
            "plant location",
            "open.*facilit",
            "locate.*facilit",
            "which.*warehouse.*open",
            "choose.*warehouse"
        ]

        evidence = []
        for keyword in facility_keywords:
            if re.search(keyword, text_lower):
                evidence.append(f"Facility location pattern: '{keyword}'")

        if evidence:
            # Check for fixed costs (distinguishes from pure transportation)
            has_fixed_cost = any(phrase in text_lower for phrase in [
                "fixed cost", "opening cost", "setup cost", "facility cost"
            ])

            if has_fixed_cost:
                evidence.append("Fixed opening costs detected")

            return self._label(
                label="location_allocation.facility_location",
                confidence=0.95 if has_fixed_cost else 0.88,
                evidence=evidence
            )

        return self._abstain()


class PMedianKeywordLF(LabelingFunction):
    """Detects p-median problems"""

    def priority(self) -> LFPriority:
        return LFPriority.CRITICAL

    def description(self) -> str:
        return "Detects p-median keywords"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        p_median_keywords = [
            "p-median", "p median",
            "p-center", "p center",
            "select exactly.*facilities",
            "choose exactly.*locations"
        ]

        evidence = []
        for keyword in p_median_keywords:
            if re.search(keyword, text_lower):
                evidence.append(f"P-median pattern: '{keyword}'")

        if evidence:
            return self._label(
                label="location_allocation.p_median",
                confidence=1.0,
                evidence=evidence
            )

        return self._abstain()


class SetCoverKeywordLF(LabelingFunction):
    """Detects set covering problems"""

    def priority(self) -> LFPriority:
        return LFPriority.CRITICAL

    def description(self) -> str:
        return "Detects set cover keywords"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        set_cover_keywords = [
            "set cover", "set covering",
            "cover all", "coverage",
            "minimum.*cover"
        ]

        evidence = []
        for keyword in set_cover_keywords:
            if re.search(keyword, text_lower):
                evidence.append(f"Set cover pattern: '{keyword}'")

        # Additional context checks
        has_cover_constraint = "cover" in text_lower
        has_minimize = "minim" in text_lower

        if evidence and has_cover_constraint and has_minimize:
            return self._label(
                label="location_allocation.set_cover",
                confidence=0.93,
                evidence=evidence
            )

        return self._abstain()
