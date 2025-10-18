"""
Label Normalizer for OR Problem Classification
Maps aliases and variations to canonical taxonomy labels
"""

import re
from pathlib import Path
import yaml
from typing import Optional, Tuple


class LabelNormalizer:
    """Normalizes problem type labels using taxonomy and alias mappings"""

    def __init__(self, taxonomy_path: str = None, aliases_path: str = None):
        """
        Initialize normalizer with taxonomy and alias files

        Args:
            taxonomy_path: Path to taxonomy.yml (defaults to or_classify/taxonomy.yml)
            aliases_path: Path to aliases.yml (defaults to or_classify/aliases.yml)
        """
        base_dir = Path(__file__).parent

        if taxonomy_path is None:
            taxonomy_path = base_dir / "taxonomy.yml"
        if aliases_path is None:
            aliases_path = base_dir / "aliases.yml"

        # Load taxonomy
        with open(taxonomy_path, 'r') as f:
            self.taxonomy = yaml.safe_load(f)

        # Load aliases
        with open(aliases_path, 'r') as f:
            alias_data = yaml.safe_load(f)
            self.aliases = alias_data.get('aliases', {})

        # Build valid families and subtypes
        self.families = set(self.taxonomy['families'].keys())
        self.valid_labels = self._build_valid_labels()

    def _build_valid_labels(self) -> set:
        """Build set of all valid canonical labels (family and family.subtype)"""
        valid = set(self.families)  # Add all family names

        for family, family_data in self.taxonomy['families'].items():
            if 'subtypes' in family_data:
                for subtype in family_data['subtypes'].keys():
                    valid.add(f"{family}.{subtype}")

        return valid

    def _normalize_string(self, s: str) -> str:
        """
        Normalize string for comparison
        - Lowercase
        - Replace hyphens and spaces with underscores
        - Remove extra whitespace
        """
        s = s.lower().strip()
        s = re.sub(r'[-\s]+', '_', s)  # hyphens and spaces to underscores
        s = re.sub(r'_+', '_', s)  # collapse multiple underscores
        return s

    def normalise_label(self, label: str) -> Tuple[str, bool]:
        """
        Normalize a label to canonical form

        Args:
            label: Input label (e.g., "portfolio", "job-shop", "min cost flow")

        Returns:
            Tuple of (canonical_label, was_aliased)
            - canonical_label: Normalized label (e.g., "knapsack.zero_one_knapsack")
            - was_aliased: True if label was mapped via alias, False if already canonical

        Examples:
            >>> normalizer.normalise_label("portfolio")
            ("knapsack.zero_one_knapsack", True)

            >>> normalizer.normalise_label("assignment")
            ("matching_assignment.assignment", False)

            >>> normalizer.normalise_label("Job-Shop")
            ("scheduling.job_shop", False)
        """
        # Normalize input
        normalized_input = self._normalize_string(label)

        # Check if already a valid canonical label
        if normalized_input in self.valid_labels:
            return (normalized_input, False)

        # Check if it's a valid family (return family, no subtype)
        if normalized_input in self.families:
            return (normalized_input, False)

        # Check aliases (also normalized)
        normalized_aliases = {self._normalize_string(k): v for k, v in self.aliases.items()}
        if normalized_input in normalized_aliases:
            canonical = normalized_aliases[normalized_input]
            return (canonical, True)

        # Try partial matches (e.g., "knapsack problem" → "knapsack")
        # First, try exact family match
        for family in self.families:
            if family in normalized_input or normalized_input in family:
                # Return just the family if no clear subtype
                return (family, False)

        # Check if input contains a subtype keyword
        for valid_label in self.valid_labels:
            if '.' in valid_label:  # It's a family.subtype
                family, subtype = valid_label.split('.', 1)
                # Check if both family and subtype appear in input
                if family in normalized_input and subtype in normalized_input:
                    return (valid_label, False)

        # No match found - return input as-is with flag
        return (normalized_input, False)

    def is_valid_label(self, label: str) -> bool:
        """
        Check if a label is valid (exists in taxonomy)

        Args:
            label: Label to check

        Returns:
            True if label is valid (family or family.subtype), False otherwise
        """
        normalized = self._normalize_string(label)
        return normalized in self.valid_labels or normalized in self.families

    def get_family(self, label: str) -> Optional[str]:
        """
        Extract family from a label

        Args:
            label: Label (e.g., "knapsack.zero_one_knapsack" or "knapsack")

        Returns:
            Family name (e.g., "knapsack") or None if invalid
        """
        normalized = self._normalize_string(label)

        if '.' in normalized:
            family, _ = normalized.split('.', 1)
            return family if family in self.families else None

        return normalized if normalized in self.families else None

    def get_subtype(self, label: str) -> Optional[str]:
        """
        Extract subtype from a label

        Args:
            label: Label (e.g., "knapsack.zero_one_knapsack")

        Returns:
            Subtype name (e.g., "zero_one_knapsack") or None if no subtype
        """
        normalized = self._normalize_string(label)

        if '.' in normalized:
            _, subtype = normalized.split('.', 1)
            return subtype

        return None

    def to_family_only(self, label: str) -> str:
        """
        Convert a label to family-only (strip subtype)

        Args:
            label: Label (e.g., "knapsack.zero_one_knapsack" or "portfolio")

        Returns:
            Family name (e.g., "knapsack")
        """
        # First normalize to canonical form
        canonical, _ = self.normalise_label(label)

        # Extract family
        family = self.get_family(canonical)
        return family if family else canonical


# Singleton instance
_normalizer_instance = None


def get_normalizer() -> LabelNormalizer:
    """Get singleton normalizer instance"""
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = LabelNormalizer()
    return _normalizer_instance


# Convenience function
def normalise_label(label: str) -> Tuple[str, bool]:
    """
    Convenience function to normalize a label
    Uses singleton normalizer instance

    Args:
        label: Input label

    Returns:
        Tuple of (canonical_label, was_aliased)
    """
    return get_normalizer().normalise_label(label)
