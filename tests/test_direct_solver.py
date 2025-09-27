#!/usr/bin/env python3
"""Test the enhanced solver directly"""

from solvers.transportation import TransportationSolver

def test_direct():
    solver = TransportationSolver()
    print(f"Solver class: {solver.__class__.__name__}")
    print(f"Expected params: {list(solver.get_example_params().keys())}")

if __name__ == "__main__":
    test_direct()