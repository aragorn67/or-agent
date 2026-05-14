"""Tests for free-text → continue-action parser."""

import pytest

from llm.continue_intent import parse_continue_action


@pytest.mark.parametrize("text", [
    "optimize",
    "Optimize it",
    "please optimize",
    "make it better",
    "can we improve it",
    "improve",
    "keep going",
    "to optimum",
    "run the solver",
    "yes",
    "yep",
    "sure",
    "ok",
    "continue please",
    "tighten the gap",
    "do better please",
])
def test_optimize_phrases(text):
    assert parse_continue_action(text) == "optimize"


@pytest.mark.parametrize("text", [
    "accept",
    "good enough",
    "this is fine",
    "that works",
    "i'm done",
    "we're good",
    "stop",
    "cancel",
    "no thanks",
    "finalize",
    "that'll do",
])
def test_accept_phrases(text):
    assert parse_continue_action(text) == "accept"


@pytest.mark.parametrize("text", [
    "use the heuristic",
    "keep heuristic",
    "stick with the heuristic",
    "stay on heuristic",
    "heuristic is fine",
    "heuristic is good",
    "heuristic is enough",
])
def test_use_heuristic_phrases(text):
    assert parse_continue_action(text) == "use_heuristic"


@pytest.mark.parametrize("text", [
    "",
    "   ",
    "what is the weather today",
    "hello there",
])
def test_no_match_returns_none(text):
    assert parse_continue_action(text) is None
