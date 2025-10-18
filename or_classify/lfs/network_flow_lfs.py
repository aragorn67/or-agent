"""
Labeling Functions for Network Flow Problems
"""

import re
from or_classify.labeling_function import LabelingFunction, LFResult, LFPriority


class NetworkFlowKeywordLF(LabelingFunction):
    """Detects network flow problems by keyword"""

    def priority(self) -> LFPriority:
        return LFPriority.HIGH

    def description(self) -> str:
        return "Detects 'network flow' keyword"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        if "network flow" in text_lower or "flow network" in text_lower:
            return self._label(
                label="network_flow",
                confidence=0.95,
                evidence=["Found 'network flow' phrase"]
            )

        return self._abstain()


class MaxFlowKeywordLF(LabelingFunction):
    """Detects max flow problems"""

    def priority(self) -> LFPriority:
        return LFPriority.CRITICAL

    def description(self) -> str:
        return "Detects max flow / maximum flow keywords"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        max_flow_keywords = [
            "max flow", "maximum flow", "maxflow",
            "ford-fulkerson", "edmonds-karp"
        ]

        evidence = []
        for keyword in max_flow_keywords:
            if keyword in text_lower:
                evidence.append(f"Found '{keyword}'")

        if evidence:
            return self._label(
                label="network_flow.max_flow",
                confidence=1.0,
                evidence=evidence
            )

        return self._abstain()


class ShortestPathKeywordLF(LabelingFunction):
    """Detects shortest path problems"""

    def priority(self) -> LFPriority:
        return LFPriority.CRITICAL

    def description(self) -> str:
        return "Detects shortest path keywords and algorithms"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        shortest_path_keywords = [
            "shortest path", "shortest route", "minimum path",
            "dijkstra", "bellman-ford", "bellman ford",
            "floyd-warshall", "floyd warshall"
        ]

        evidence = []
        for keyword in shortest_path_keywords:
            if keyword in text_lower:
                evidence.append(f"Found '{keyword}'")

        if evidence:
            return self._label(
                label="network_flow.shortest_path",
                confidence=1.0,
                evidence=evidence
            )

        return self._abstain()


class MinCostFlowKeywordLF(LabelingFunction):
    """Detects min cost flow problems"""

    def priority(self) -> LFPriority:
        return LFPriority.CRITICAL

    def description(self) -> str:
        return "Detects min cost flow / MCNF keywords"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        mcf_keywords = [
            "min cost flow", "minimum cost flow",
            "min-cost flow", "minimum-cost flow",
            "mcf", "mcnf"
        ]

        evidence = []
        for keyword in mcf_keywords:
            if keyword in text_lower:
                evidence.append(f"Found '{keyword}'")

        if evidence:
            return self._label(
                label="network_flow.min_cost_flow",
                confidence=1.0,
                evidence=evidence
            )

        return self._abstain()


class TransportationKeywordLF(LabelingFunction):
    """Detects transportation problems (alias for min cost flow)"""

    def priority(self) -> LFPriority:
        return LFPriority.HIGH

    def description(self) -> str:
        return "Detects transportation problem keywords"

    def apply(self, text: str, context=None) -> LFResult:
        text_lower = text.lower()

        # Transportation-specific patterns
        transportation_patterns = [
            "transportation problem",
            "ship.*from.*to",
            "factories.*warehouses",
            "supply.*demand.*ship",
            "sources.*destinations.*transport"
        ]

        evidence = []
        for pattern in transportation_patterns:
            if re.search(pattern, text_lower):
                evidence.append(f"Transportation pattern: '{pattern}'")

        if evidence:
            return self._label(
                label="network_flow.min_cost_flow",
                confidence=0.92,
                evidence=evidence
            )

        return self._abstain()
