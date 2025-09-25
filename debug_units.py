#!/usr/bin/env python3
"""Debug the units handler"""

from llm.units_handler import UnitsHandler

def test_units():
    handler = UnitsHandler()

    description = """
A company operates two production sites in Greece: Athens and Thessaloniki.
Athens can make up to 120 units per week,
Thessaloniki can supply 200 pieces.
Transport costs (in € per unit) are:
From Athens to Patras: 5
From Athens to Larisa: 4
From Athens to Heraklion: 7
"""

    print("Testing units detection:")
    units_info = handler.detect_units(description)
    print(f"Units info: {units_info}")

    print("\nTesting cost formatting:")
    formatted = handler.format_cost(1600, units_info, is_total=True)
    print(f"Formatted cost: {formatted}")

    # Mock solution
    solution = {"objective_value": 1600, "status": "OPTIMAL"}
    summary = handler.format_solution_summary(solution, units_info)
    print(f"Summary: {summary}")

if __name__ == "__main__":
    test_units()