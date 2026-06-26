"""
Ground-truth verification for the single-stage IPM scheduler.

The scheduling solver has no textbook instance with a *stated* optimum that
matches its model (parallel units + eligibility + sequence-dependent changeover
+ due dates). So we anchor correctness on a published *instance* whose optimum
we obtain by exhaustive enumeration — the method the source exercise itself
prescribes — rather than by trusting the solver or an LLM.

Source: Hillier & Lieberman, Introduction to Operations Research (2015),
Problem 12.6-8 — five jobs, one machine, sequence-dependent setups, minimize
total setup. Posed as a branch-and-bound exercise; no optimum is printed.

This test independently enumerates all 5! = 120 sequences, then asserts that
  (a) the enumerated optimum is 36 at sequence 2->1->4->5->3, and
  (b) single_stage_ipm_scheduling reproduces it at 0.00% gap on the exact
      ground_truth_params stored in the repository,
  (c) those two agree with the repository's published_optimum.
If any drift appears, this fails — it is the only real correctness check the
scheduler has.
"""
from itertools import permutations

from solvers.scheduling.single_stage_ipm import SingleStageIPMSolver
from tests.or_problem_repository import get_problem_by_name

# Hillier 12.6-8 setup matrix: SETUP[prev][job] = setup before `job` when
# `prev` ran immediately before it; INITIAL[job] = setup when `job` runs first.
SETUP = {
    1: {2: 7, 3: 12, 4: 10, 5: 9},
    2: {1: 6, 3: 10, 4: 14, 5: 11},
    3: {1: 10, 2: 11, 4: 12, 5: 10},
    4: {1: 7, 2: 8, 3: 15, 5: 7},
    5: {1: 12, 2: 9, 3: 8, 4: 16},
}
INITIAL = {1: 4, 2: 5, 3: 8, 4: 9, 5: 4}
JOBS = [1, 2, 3, 4, 5]


def _total_setup(seq):
    """Total setup for a full sequence: initial setup of the first job plus
    each inter-job changeover."""
    total = INITIAL[seq[0]]
    for prev, nxt in zip(seq, seq[1:]):
        total += SETUP[prev][nxt]
    return total


def _enumerate_optimum():
    best = min(permutations(JOBS), key=_total_setup)
    return _total_setup(best), best


def test_enumeration_is_the_documented_optimum():
    z, seq = _enumerate_optimum()
    assert z == 36, f"enumerated optimum drifted: {z}"
    assert seq == (2, 1, 4, 5, 3), f"optimal sequence drifted: {seq}"


def test_solver_reproduces_enumerated_optimum():
    problem = get_problem_by_name("hillier_sequence_dependent_setup")
    params = problem["ground_truth_params"]

    result = SingleStageIPMSolver().solve(params, time_limit=30, gap_target=0.0)

    assert result["status"] == "OPTIMAL", result
    assert result["gap"] is not None and result["gap"] <= 1e-6, result
    enum_z, _ = _enumerate_optimum()
    assert abs(result["objective"] - enum_z) < 1e-6, (
        f"solver {result['objective']} != enumeration {enum_z}")
    assert abs(result["objective"] - problem["published_optimum"]) < 1e-6, (
        f"solver {result['objective']} != published_optimum {problem['published_optimum']}")


def test_solver_recovers_optimal_sequence():
    problem = get_problem_by_name("hillier_sequence_dependent_setup")
    result = SingleStageIPMSolver().solve(problem["ground_truth_params"],
                                          time_limit=30, gap_target=0.0)
    succ = {a["pred"]: a["succ"] for a in result["arcs"]}
    preds = {a["succ"] for a in result["arcs"]}
    first = next(o for o in ["1", "2", "3", "4", "5"] if o not in preds)
    seq, cur = [], first
    while cur is not None:
        seq.append(int(cur))
        cur = succ.get(cur)
    assert tuple(seq) == (2, 1, 4, 5, 3), f"solver sequence {seq}"
