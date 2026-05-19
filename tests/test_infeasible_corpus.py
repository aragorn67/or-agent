"""
Deterministic (LLM-free) check of the curated infeasible corpus.

`tests/or_problem_repository.py` carries infeasible OR problems tagged
with the feasibility layer that *should* reject them. This iterates the
machine-checkable subset (those with structured `params` +
`expected_infeasible_layer`) and asserts each instance is rejected at
exactly its tagged layer — across BOTH transportation and single-stage
scheduling, Layers 0/1/2. No agent / LLM in the loop, so it's a stable
regression net (unlike the NL-driven repository tests).
"""

import pytest

from analysis.instance_builder import build_instance_from_params
from feasibility import check_feasibility, FeasStatus
from tests.or_problem_repository import (
    get_infeasible_problems,
    get_solver_id,
)

CORPUS = get_infeasible_problems(machine_checkable=True)


def test_corpus_covers_both_domains_and_all_layers():
    """The curated set must not silently regress to transport-only or
    drop a layer (the gap this work closed: scheduling had 0)."""
    cats = {p["category"] for p in CORPUS}
    assert {"transportation", "scheduling"} <= cats

    def layers(cat):
        return {
            p["expected_infeasible_layer"]
            for p in CORPUS if p["category"] == cat
        }
    assert {0, 1, 2} <= layers("transportation")
    assert {0, 1, 2} <= layers("scheduling")


@pytest.mark.parametrize(
    "problem",
    CORPUS,
    ids=[p["name"] for p in CORPUS],
)
def test_infeasible_at_expected_layer(problem):
    inst = build_instance_from_params(
        problem["params"],
        problem["expected_type"],
        get_solver_id(problem),
    )
    report = check_feasibility(inst)

    assert report.status == FeasStatus.INFEASIBLE, (
        f"{problem['name']} expected INFEASIBLE, got {report.status} "
        f"— reasons: {report.reasons}"
    )
    assert report.layer_passed == problem["expected_infeasible_layer"], (
        f"{problem['name']} expected rejection at Layer "
        f"{problem['expected_infeasible_layer']}, got Layer "
        f"{report.layer_passed} — reasons: {report.reasons}"
    )
