#!/usr/bin/env python3
"""Debug which solvers are being registered"""

from solvers import get_solver, list_problem_types

def debug_solvers():
    problem_types = list_problem_types()
    print(f"Available problem types: {problem_types}")

    for ptype in problem_types:
        solver = get_solver(ptype)
        print(f"\nProblem type: {ptype}")
        print(f"Solver class: {solver.__class__.__name__}")
        print(f"Solver module: {solver.__class__.__module__}")

        # Check what parameters it expects
        example = solver.get_example_params()
        print(f"Expected parameters: {list(example.keys())}")

if __name__ == "__main__":
    debug_solvers()