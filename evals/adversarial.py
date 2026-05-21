"""Adversarial extraction tests — characterise agent behaviour under imperfect prose.

Phase 3 (metamorphic) verified the *solver* is invariant under structure-
preserving transforms. Phase 4 (paraphrase) verified the *pipeline* is stable
across phrasing variation that preserves all content. This module covers the
third axis: what happens when the prose is *broken* — missing entities,
contradictory facts, dropped units, irrelevant noise.

These are **characterisation** tests, not pass/fail assertions. The point is to
report:
  - how often the agent gracefully degrades (correct partial answer or clean error)
  - how often it silently drifts (wrong answer, no surfaced doubt)
  - how often it hard-fails (extraction crashes, no answer at all)

Each transform declares its `expected_category`:
  "should_solve"      — the noise is recoverable; agent should still produce a
                        correct answer (e.g. inserting irrelevant facts).
  "graceful_degrade"  — the input is genuinely under-specified or contradictory;
                        agent should either flag, ask, or produce a clearly
                        partial result rather than silently guessing.

The runner records the actual outcome and the operator compares against the
expectation — a "should_solve" transform that fails reveals a brittleness; a
"graceful_degrade" transform that silently succeeds reveals a hallucinated
answer the agent had no business producing.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass(frozen=True)
class AdversarialTransform:
    name: str
    description: str
    expected_category: str   # "should_solve" | "graceful_degrade"
    apply: Callable[[str, Dict[str, Any], int], str]


# ---------------------------------------------------------------------------
# Transport-domain transforms
# ---------------------------------------------------------------------------

def _drop_one_plant(text: str, params: Dict[str, Any], seed: int) -> str:
    """Strip every sentence that mentions the first plant in alphabetical
    order. The remaining prose describes a *smaller* problem; the agent
    should either recover that smaller problem or flag the inconsistency
    with the unmentioned cost rows."""
    target = sorted(params["plants"])[0]
    out_lines = []
    for line in text.splitlines():
        if target.lower() in line.lower():
            continue
        out_lines.append(line)
    if "\n" not in text:
        # Single paragraph: drop by sentence instead of by line
        sentences = re.split(r"(?<=[.!?])\s+", text)
        out = " ".join(s for s in sentences if target.lower() not in s.lower())
        return out
    return "\n".join(out_lines)


def _contradict_one_capacity(text: str, params: Dict[str, Any], seed: int) -> str:
    """Append a sentence that restates one plant's capacity with a *different*
    number. The agent must pick one — the test characterises which (and
    whether it surfaces the conflict at all)."""
    rng = random.Random(seed)
    plant = rng.choice(list(params["plants"]))
    real = params["capacity"][plant]
    fake = int(real * 0.5) or 1
    injection = (
        f" In an updated note from operations, {plant} actually has only "
        f"{fake} units of capacity available."
    )
    return text.rstrip() + injection


def _drop_units_suffix(text: str, params: Dict[str, Any], seed: int) -> str:
    """Strip the literal word "units" everywhere. Numbers remain, but now
    bare — the extractor has to infer the unit context. Real user prose
    often omits units (especially in tabular dumps)."""
    return re.sub(r"\bunits\b", "", text, flags=re.IGNORECASE)


def _inject_irrelevant_fact(text: str, params: Dict[str, Any], seed: int) -> str:
    """Insert a plausible-but-irrelevant operational detail in the middle of
    the prose. The agent should ignore it; if extraction starts picking it
    up as a parameter, that's a real brittleness."""
    rng = random.Random(seed)
    plant = rng.choice(list(params["plants"]))
    injection = (
        f" Note: {plant} also operates a fleet of 5 maintenance trucks and "
        f"runs a quarterly safety audit, neither of which affects the "
        f"shipping problem."
    )
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) < 2:
        return text + injection
    mid = len(sentences) // 2
    sentences.insert(mid, injection.strip())
    return " ".join(sentences)


# ---------------------------------------------------------------------------
# Scheduling-domain transforms
# ---------------------------------------------------------------------------

def _drop_one_order(text: str, params: Dict[str, Any], seed: int) -> str:
    target = sorted(params["orders"])[0]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(s for s in sentences if target.lower() not in s.lower())


def _contradict_one_due_date(text: str, params: Dict[str, Any], seed: int) -> str:
    rng = random.Random(seed)
    order = rng.choice(list(params["orders"]))
    real = params["due_date"][order]
    fake = max(1.0, real - 5.0)
    injection = (
        f" Correction from planning: {order}'s due date has been moved up "
        f"to hour {fake}."
    )
    return text.rstrip() + injection


def _drop_hours_suffix(text: str, params: Dict[str, Any], seed: int) -> str:
    return re.sub(r"\bhours?\b", "", text, flags=re.IGNORECASE)


def _inject_irrelevant_scheduling_fact(text: str, params: Dict[str, Any], seed: int) -> str:
    rng = random.Random(seed)
    unit = rng.choice(list(params["units"]))
    injection = (
        f" Note: {unit} was installed in 2018 and is scheduled for "
        f"preventive maintenance next quarter, which doesn't affect this "
        f"week's schedule."
    )
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) < 2:
        return text + injection
    mid = len(sentences) // 2
    sentences.insert(mid, injection.strip())
    return " ".join(sentences)


_TRANSFORMS: Dict[str, List[AdversarialTransform]] = {
    "transport": [
        AdversarialTransform(
            "drop_one_plant",
            "Remove all mention of one plant; smaller problem remains.",
            "graceful_degrade",
            _drop_one_plant,
        ),
        AdversarialTransform(
            "contradict_one_capacity",
            "Append a contradictory capacity for one plant.",
            "graceful_degrade",
            _contradict_one_capacity,
        ),
        AdversarialTransform(
            "drop_units_suffix",
            'Strip the word "units" globally; numbers remain bare.',
            "should_solve",
            _drop_units_suffix,
        ),
        AdversarialTransform(
            "inject_irrelevant_fact",
            "Insert a plausible operational detail that should be ignored.",
            "should_solve",
            _inject_irrelevant_fact,
        ),
    ],
    "scheduling": [
        AdversarialTransform(
            "drop_one_order",
            "Remove all mention of one order.",
            "graceful_degrade",
            _drop_one_order,
        ),
        AdversarialTransform(
            "contradict_one_due_date",
            "Append a contradictory due date for one order.",
            "graceful_degrade",
            _contradict_one_due_date,
        ),
        AdversarialTransform(
            "drop_hours_suffix",
            'Strip the word "hour(s)" globally.',
            "should_solve",
            _drop_hours_suffix,
        ),
        AdversarialTransform(
            "inject_irrelevant_fact",
            "Insert a plausible scheduling detail that should be ignored.",
            "should_solve",
            _inject_irrelevant_scheduling_fact,
        ),
    ],
}


def transforms_for(domain: str) -> List[AdversarialTransform]:
    if domain not in _TRANSFORMS:
        raise ValueError(f"Unknown domain {domain!r}; expected one of {list(_TRANSFORMS)}")
    return _TRANSFORMS[domain]
