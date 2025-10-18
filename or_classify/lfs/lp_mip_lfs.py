"""
Labeling Functions for LP/MIP Problems
"""

import re
from or_classify.labeling_function import LabelingFunction, LFResult, LFPriority


class LinearProgramKeywordLF(LabelingFunction):
    """Detects linear programming problems"""

    def priority(self) -> LFPriority:
        return LFPriority.MEDIUM

    def description(self) -> str:
        return "Detects linear programming / LP keywords"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        lp_keywords = [
            "linear program", "linear programming",
            "lp model", "lp formulation",
            "simplex method", "simplex algorithm"
        ]

        evidence = []
        for keyword in lp_keywords:
            if keyword in text_lower:
                evidence.append(f"Found '{keyword}'")

        if evidence:
            # Check if it's pure resource allocation
            has_resource = "resource" in text_lower
            has_continuous = "continuous" in text_lower or "fraction" in text_lower

            if has_resource:
                return self._label(
                    label="lp.resource_allocation",
                    confidence=0.85,
                    evidence=evidence + ["Resource allocation context"]
                )

            # Generic LP
            return self._label(
                label="lp.resource_allocation",
                confidence=0.80,
                evidence=evidence
            )

        return self._abstain()


class MIPKeywordLF(LabelingFunction):
    """Detects mixed integer programming problems"""

    def priority(self) -> LFPriority:
        return LFPriority.MEDIUM

    def description(self) -> str:
        return "Detects MIP / integer programming keywords"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        mip_keywords = [
            "integer program", "integer programming",
            "mixed integer", "milp", "mip",
            "binary variable", "integer variable"
        ]

        evidence = []
        for keyword in mip_keywords:
            if keyword in text_lower:
                evidence.append(f"Found '{keyword}'")

        if evidence:
            # Check for fixed charge structure
            has_fixed_charge = any(phrase in text_lower for phrase in [
                "fixed cost", "fixed charge", "setup cost"
            ])

            if has_fixed_charge:
                return self._label(
                    label="mip.fixed_charge",
                    confidence=0.88,
                    evidence=evidence + ["Fixed charge structure"]
                )

            # Generic MIP
            return self._label(
                label="mip.fixed_charge",
                confidence=0.75,
                evidence=evidence
            )

        return self._abstain()
