#!/usr/bin/env python3
"""
TEST: Label Normalizer (Unit Tests)

PURPOSE: Unit tests for label normalization functionality
TESTS: Canonical labels, alias mapping, case handling, separator normalization
FRAMEWORK: pytest

EXPECTED OUTPUT:
    ✓ All normalization tests pass
    ✓ Canonical labels pass through unchanged
    ✓ Case-insensitive matching (KNAPSACK → knapsack)
    ✓ Separator normalization (network-flow → network_flow)
    ✓ Alias mapping (portfolio → knapsack, transportation → canonical)
    ✓ Utility methods: is_valid_label, get_family, get_subtype
    ✓ Convenience function works

RUN: pytest tests/test_normalizer.py -v
REQUIRES: or_classify.normalizer module
STATUS: Import error (ModuleNotFoundError: 'or_classify') - needs sys.path fix
"""

import pytest
from or_classify.normalizer import LabelNormalizer, normalise_label


def test_canonical_labels_pass_through():
    """Test that valid canonical labels are recognized"""
    normalizer = LabelNormalizer()

    # Family names should pass through
    assert normalizer.normalise_label("knapsack") == ("knapsack", False)
    assert normalizer.normalise_label("network_flow") == ("network_flow", False)

    # Family.subtype should pass through
    result, aliased = normalizer.normalise_label("knapsack.zero_one_knapsack")
    assert aliased == False


def test_case_and_separator_normalization():
    """Test case-insensitive and separator normalization"""
    normalizer = LabelNormalizer()

    # Case should not matter
    assert normalizer.normalise_label("KNAPSACK")[0] == "knapsack"

    # Hyphens and spaces convert to underscores
    assert normalizer.normalise_label("network-flow")[0] == "network_flow"
    assert normalizer.normalise_label("network flow")[0] == "network_flow"


def test_alias_mapping():
    """Test that aliases map to canonical forms"""
    normalizer = LabelNormalizer()

    # Test a few key aliases
    result, aliased = normalizer.normalise_label("portfolio")
    assert aliased == True
    assert "knapsack" in result

    result, aliased = normalizer.normalise_label("transportation")
    assert aliased == True

    result, aliased = normalizer.normalise_label("hungarian")
    assert aliased == True


def test_utility_methods():
    """Test helper methods work correctly"""
    normalizer = LabelNormalizer()

    # is_valid_label
    assert normalizer.is_valid_label("knapsack") == True
    assert normalizer.is_valid_label("invalid_xyz") == False

    # get_family
    assert normalizer.get_family("knapsack") == "knapsack"
    assert normalizer.get_family("knapsack.zero_one_knapsack") == "knapsack"

    # get_subtype
    assert normalizer.get_subtype("knapsack") == None
    assert normalizer.get_subtype("knapsack.zero_one_knapsack") == "zero_one_knapsack"


def test_convenience_function():
    """Test standalone normalise_label function"""
    result, aliased = normalise_label("portfolio")
    assert isinstance(result, str)
    assert isinstance(aliased, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
