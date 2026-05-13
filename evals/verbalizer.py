"""Turn a transportation params dict into a natural-language problem statement.

Uses the reasoning model (deepseek-r1) for prose quality. Caches outputs by cache_key
on disk so re-running the eval doesn't re-pay the LLM cost for the same seed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional


_CACHE_DIR = Path(__file__).parent / "results" / ".verbalizer_cache"
# Bump when the system prompt changes so old cache entries are not reused.
_PROMPT_VERSION = "v2"


_SYSTEM_PROMPT = """You are an operations research problem writer.
Given a structured transportation problem, write a natural-language description that
an optimization agent could read and extract the same parameters from.

HARD REQUIREMENTS — do not violate any of these:
1. State every plant's capacity exactly once, using the plant's name and its number.
2. State every market's demand exactly once, using the market's name and its number.
3. State the unit shipping cost for EVERY plant-market pair. If there are P plants and
   M markets, you MUST mention P*M distinct cost numbers, each paired with its
   plant-name and market-name. Do not summarize, do not give "examples", do not say
   "for instance" or "the cheapest route" — every route gets its own sentence or clause.
4. State the objective: minimize total transportation cost while meeting all demand
   without exceeding any plant's capacity.

FORMAT:
- Plain prose, full sentences. No JSON, no curly braces, no key-value colons.
- Do not write key names like "capacity:" or "demand:". Phrase numbers in words like
  "Boston can supply up to 350 units" or "shipping from Boston to Rome costs $2.67 per unit".
- Output ONLY the problem statement. No preamble, no commentary, no markdown headers.
"""


def _params_to_user_message(params: Dict[str, Any]) -> str:
    """Render the params dict into a deterministic textual form for the LLM prompt."""
    cap = params["capacity"]
    dem = params["demand"]
    plants_str = ", ".join(f"{p}={cap[p]}" for p in params["plants"])
    markets_str = ", ".join(f"{m}={dem[m]}" for m in params["markets"])
    lines = [
        f"Plants and capacities: {plants_str}",
        f"Markets and demands: {markets_str}",
        "Transportation costs per unit:",
    ]
    for p in params["plants"]:
        for m in params["markets"]:
            lines.append(f"  {p} -> {m}: {params['cost'][p][m]}")
    return "\n".join(lines) + "\n\nWrite the problem statement now."


_LEAKAGE_PATTERNS = [
    re.compile(r"[{}]"),
    re.compile(r"\bplants\s*:", re.IGNORECASE),
    re.compile(r"\bmarkets\s*:", re.IGNORECASE),
    re.compile(r"\bcapacity\s*:", re.IGNORECASE),
    re.compile(r"\bdemand\s*:", re.IGNORECASE),
    re.compile(r"\bcost\s*:", re.IGNORECASE),
]


def _assert_no_leakage(text: str) -> None:
    for pat in _LEAKAGE_PATTERNS:
        if pat.search(text):
            raise ValueError(f"Verbalizer leaked structural cue matching {pat.pattern!r}")


def _coverage_missing(text: str, params: Dict[str, Any]) -> Dict[str, list]:
    """Return whatever the verbalization failed to mention. Empty dict means full coverage."""
    lower = text.lower()
    missing = {"plants": [], "markets": [], "costs": []}

    for p in params["plants"]:
        if p.lower() not in lower:
            missing["plants"].append(p)
    for m in params["markets"]:
        if m.lower() not in lower:
            missing["markets"].append(m)

    # Each cost number must appear somewhere. Costs are 2-decimal floats; allow
    # also the integer-rounded form (qwen sometimes drops trailing zeros).
    for p in params["plants"]:
        for m in params["markets"]:
            v = params["cost"][p][m]
            tokens = {f"{v:.2f}", f"{v:.1f}", f"{v:g}"}
            if not any(t in text for t in tokens):
                missing["costs"].append((p, m, v))

    return {k: v for k, v in missing.items() if v}


def _cache_path(cache_key: str) -> Path:
    versioned = f"{_PROMPT_VERSION}:{cache_key}"
    digest = hashlib.sha1(versioned.encode()).hexdigest()[:16]
    return _CACHE_DIR / f"{digest}.txt"


def verbalize(
    params: Dict[str, Any],
    llm_client,
    cache_key: Optional[str] = None,
    style: str = "neutral",
) -> str:
    """Render params as a natural-language problem statement.

    Args:
        params: transportation params dict
        llm_client: an EnhancedLLMClient (we use its reasoning_client._chat)
        cache_key: stable string (e.g., f"seed:{seed}:style:{style}") for disk cache
        style: reserved for Phase 2 robustness tests (neutral/formal/casual/noisy)

    Returns:
        Natural-language text safe to pass to agent.solve_natural_language.
    """
    if cache_key is not None:
        cpath = _cache_path(cache_key)
        if cpath.exists():
            return cpath.read_text()

    user_msg = _params_to_user_message(params)

    for attempt in range(2):
        system_prompt = _SYSTEM_PROMPT
        if attempt > 0:
            system_prompt += (
                "\nYOUR PREVIOUS ATTEMPT WAS INCOMPLETE. You MUST mention every single "
                "plant, every single market, and every single cost number. Do not "
                "summarize or skip any route."
            )
        raw = llm_client.reasoning_client._chat(system_prompt, user_msg, json_mode=False)
        text = _strip_thinking(raw).strip()
        _assert_no_leakage(text)
        missing = _coverage_missing(text, params)
        if not missing:
            break
    else:
        raise ValueError(f"Verbalizer missed required content after retry: {missing}")

    if cache_key is not None:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(cache_key).write_text(text)

    return text


def _strip_thinking(text: str) -> str:
    """deepseek-r1 wraps reasoning in <think>...</think>. Drop it."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
