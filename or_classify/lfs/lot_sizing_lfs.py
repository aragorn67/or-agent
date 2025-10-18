"""
Labeling Functions for Lot Sizing / Production Planning Problems
"""

import re
from or_classify.labeling_function import LabelingFunction, LFResult, LFPriority


class LotSizingKeywordLF(LabelingFunction):
    """Detects lot sizing problems by keyword"""

    def priority(self) -> LFPriority:
        return LFPriority.CRITICAL

    def description(self) -> str:
        return "Detects lot sizing keywords"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        lot_sizing_keywords = [
            "lot sizing", "lot-sizing",
            "economic lot", "eoq", "economic order quantity"
        ]

        evidence = []
        for keyword in lot_sizing_keywords:
            if keyword in text_lower:
                evidence.append(f"Found '{keyword}'")

        if evidence:
            # Check for capacity constraints
            has_capacity = "capacity" in text_lower or "capacitated" in text_lower

            if "uncapacitated" in text_lower or (not has_capacity):
                return self._label(
                    label="lot_sizing.uncapacitated_lot_sizing",
                    confidence=0.95,
                    evidence=evidence + ["No capacity constraints"]
                )
            else:
                return self._label(
                    label="lot_sizing.capacitated_lot_sizing",
                    confidence=0.95,
                    evidence=evidence + ["Capacity constraints present"]
                )

        return self._abstain()


class ProductionPlanningLF(LabelingFunction):
    """Detects production planning problems"""

    def priority(self) -> LFPriority:
        return LFPriority.HIGH

    def description(self) -> str:
        return "Detects production planning keywords"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        production_keywords = [
            "production planning",
            "production schedule",
            "aggregate planning"
        ]

        evidence = []
        for keyword in production_keywords:
            if keyword in text_lower:
                evidence.append(f"Found '{keyword}'")

        # Check for multi-period structure
        has_periods = any(word in text_lower for word in [
            "period", "month", "week", "quarter", "time horizon"
        ])

        # Check for inventory
        has_inventory = "inventory" in text_lower or "holding cost" in text_lower

        if evidence and has_periods and has_inventory:
            # Check for capacity
            has_capacity = "capacity" in text_lower

            if has_capacity:
                return self._label(
                    label="lot_sizing.capacitated_lot_sizing",
                    confidence=0.90,
                    evidence=evidence + ["Multi-period", "Inventory", "Capacity"]
                )
            else:
                return self._label(
                    label="lot_sizing.uncapacitated_lot_sizing",
                    confidence=0.88,
                    evidence=evidence + ["Multi-period", "Inventory"]
                )

        return self._abstain()


class InventoryKeywordLF(LabelingFunction):
    """Detects inventory optimization problems"""

    def priority(self) -> LFPriority:
        return LFPriority.MEDIUM

    def description(self) -> str:
        return "Detects inventory keywords with production context"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        # Inventory + production context
        has_inventory = "inventory" in text_lower
        has_production = any(word in text_lower for word in ["produce", "production", "manufacturing"])
        has_periods = any(word in text_lower for word in ["period", "month", "week"])
        has_holding = "holding cost" in text_lower or "storage cost" in text_lower

        if has_inventory and has_production and (has_periods or has_holding):
            evidence = [
                "Inventory management",
                "Production context",
                "Multi-period or holding costs"
            ]

            return self._label(
                label="lot_sizing.capacitated_lot_sizing",
                confidence=0.82,
                evidence=evidence
            )

        return self._abstain()
