"""
Labeling Function Framework for OR Problem Classification
Provides base class, registry, and priority system for deterministic rules
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class LFPriority(Enum):
    """Priority levels for labeling functions"""
    CRITICAL = 1      # Grammar-based, 100% precision
    HIGH = 2          # Keyword + structure, >95% precision
    MEDIUM = 3        # Keyword-based, >90% precision
    LOW = 4           # Weak signals, use as features only


# Sentinel value for abstain
ABSTAIN = "__ABSTAIN__"


@dataclass
class LFResult:
    """
    Result from a labeling function

    Attributes:
        label: Canonical label (family.subtype or family), or ABSTAIN
        confidence: Confidence score 0-1 (1.0 for deterministic LFs)
        evidence: List of evidence strings explaining why this label was chosen
        priority: Priority level of the LF that produced this result
    """
    label: str
    confidence: float
    evidence: List[str]
    priority: LFPriority

    def is_abstain(self) -> bool:
        """Check if this result is an abstention"""
        return self.label == ABSTAIN


class LabelingFunction(ABC):
    """
    Base class for all labeling functions

    Each LF should:
    - Return a canonical label (using normalizer) OR ABSTAIN
    - Have high precision (>90%) on cases it labels
    - Include evidence strings for explainability
    - Have comprehensive unit tests (5-10 examples)
    """

    def __init__(self):
        self._name = self.__class__.__name__
        self._priority = self.priority()
        self._description = self.description()

    @property
    def name(self) -> str:
        """Human-readable name of this LF"""
        return self._name

    @abstractmethod
    def priority(self) -> LFPriority:
        """
        Priority level for this LF

        Returns:
            LFPriority enum value
        """
        pass

    @abstractmethod
    def description(self) -> str:
        """
        Human-readable description of what this LF detects

        Returns:
            Description string
        """
        pass

    @abstractmethod
    def apply(self, text: str, context: Optional[Dict[str, Any]] = None) -> LFResult:
        """
        Apply this labeling function to input text

        Args:
            text: Problem description text
            context: Optional context dict (e.g., preprocessed features)

        Returns:
            LFResult with label, confidence, evidence, and priority
        """
        pass

    def _abstain(self) -> LFResult:
        """Helper to return ABSTAIN result"""
        return LFResult(
            label=ABSTAIN,
            confidence=0.0,
            evidence=[],
            priority=self._priority
        )

    def _label(self, label: str, confidence: float, evidence: List[str]) -> LFResult:
        """
        Helper to return labeled result

        Args:
            label: Canonical label (family.subtype or family)
            confidence: Confidence 0-1
            evidence: List of evidence strings

        Returns:
            LFResult
        """
        return LFResult(
            label=label,
            confidence=confidence,
            evidence=evidence,
            priority=self._priority
        )


class LFRegistry:
    """
    Registry for all labeling functions
    Manages LF lifecycle, priorities, and execution
    """

    def __init__(self):
        self._lfs: List[LabelingFunction] = []
        self._lf_dict: Dict[str, LabelingFunction] = {}

    def register(self, lf: LabelingFunction) -> None:
        """
        Register a labeling function

        Args:
            lf: LabelingFunction instance
        """
        if lf.name in self._lf_dict:
            raise ValueError(f"LF with name '{lf.name}' already registered")

        self._lfs.append(lf)
        self._lf_dict[lf.name] = lf

        # Keep sorted by priority (CRITICAL first, LOW last)
        self._lfs.sort(key=lambda x: x._priority.value)

    def unregister(self, name: str) -> None:
        """
        Unregister a labeling function by name

        Args:
            name: Name of LF to remove
        """
        if name not in self._lf_dict:
            raise ValueError(f"LF '{name}' not found in registry")

        lf = self._lf_dict[name]
        self._lfs.remove(lf)
        del self._lf_dict[name]

    def get(self, name: str) -> Optional[LabelingFunction]:
        """
        Get LF by name

        Args:
            name: LF name

        Returns:
            LabelingFunction or None if not found
        """
        return self._lf_dict.get(name)

    def list_lfs(self, priority: Optional[LFPriority] = None) -> List[LabelingFunction]:
        """
        List all registered LFs, optionally filtered by priority

        Args:
            priority: Optional priority filter

        Returns:
            List of LabelingFunction instances
        """
        if priority is None:
            return list(self._lfs)

        return [lf for lf in self._lfs if lf._priority == priority]

    def apply_all(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        stop_on_first: bool = True
    ) -> List[LFResult]:
        """
        Apply all registered LFs to input text

        Args:
            text: Problem description
            context: Optional context dict
            stop_on_first: If True, stop after first non-ABSTAIN result (respects priority order)

        Returns:
            List of LFResult objects (non-ABSTAIN only, sorted by priority)
        """
        results = []

        for lf in self._lfs:  # Already sorted by priority
            result = lf.apply(text, context)

            if not result.is_abstain():
                results.append(result)

                if stop_on_first:
                    break

        return results

    def apply_by_priority(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        min_priority: LFPriority = LFPriority.LOW
    ) -> Optional[LFResult]:
        """
        Apply LFs in priority order until one fires

        Args:
            text: Problem description
            context: Optional context dict
            min_priority: Minimum priority to consider (e.g., LFPriority.HIGH)

        Returns:
            First non-ABSTAIN LFResult, or None if all abstain
        """
        for lf in self._lfs:
            # Skip LFs below minimum priority
            if lf._priority.value > min_priority.value:
                continue

            result = lf.apply(text, context)

            if not result.is_abstain():
                return result

        return None

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about registered LFs

        Returns:
            Dict with counts by priority, total LFs, etc.
        """
        stats = {
            "total": len(self._lfs),
            "by_priority": {}
        }

        for priority in LFPriority:
            count = sum(1 for lf in self._lfs if lf._priority == priority)
            stats["by_priority"][priority.name] = count

        return stats


# Global registry instance
_global_registry = LFRegistry()


def get_registry() -> LFRegistry:
    """Get the global LF registry"""
    return _global_registry


def register_lf(lf: LabelingFunction) -> None:
    """
    Register a labeling function to the global registry

    Args:
        lf: LabelingFunction instance
    """
    _global_registry.register(lf)


def clear_registry() -> None:
    """Clear all LFs from global registry (useful for testing)"""
    global _global_registry
    _global_registry = LFRegistry()
