"""Turn a generated params dict into a natural-language problem statement.

Uses the reasoning model for prose quality. Caches outputs by cache_key on disk so
re-running the eval doesn't re-pay the LLM cost for the same seed.

Supports two domains: "transport" (bipartite transportation) and "scheduling"
(single-stage IPM). Each domain plugs in its own system prompt, user-message
renderer, and coverage check.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


_CACHE_DIR = Path(__file__).parent / "results" / ".verbalizer_cache"
# Bump when any system prompt OR coverage check changes so old cache entries
# (which may have passed a weaker coverage gate) aren't silently reused.
_PROMPT_VERSION = "v6"


_TRANSPORT_SYSTEM_PROMPT = """You are an operations research problem writer.
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
- ALL numeric values MUST appear as digits (350, 2.67), never as English words
  ("three hundred fifty", "two and sixty-seven hundredths"). Digit form is the
  contract the downstream extractor relies on.
- Output ONLY the problem statement. No preamble, no commentary, no markdown headers.
"""


_SCHEDULING_SYSTEM_PROMPT = """You are an operations research problem writer.
Given a structured single-stage scheduling problem, write a natural-language
description that an optimization agent could read and extract the same
parameters from.

HARD REQUIREMENTS — do not violate any of these:
1. Open by clearly stating this is a SCHEDULING problem, e.g. "We need to
   schedule a set of production orders on parallel processing units." Use the
   words "schedule" and "processing units" (or "machines") explicitly.
2. State that there are N orders and M processing units, using the exact
   count words ("3 orders", "2 units").
3. Name every order exactly as given.
4. Name every unit exactly as given.
5. State that every order can be processed on any of the units (full eligibility).
6. State the processing time for EVERY order-unit pair. If there are N orders
   and M units, you MUST mention N*M distinct processing times, each paired
   with its order name and unit name. No summaries, no "for example".
7. State the due date / deadline for every order as an absolute number of hours.
8. State the objective: minimize the makespan (the time at which the last
   order completes).

FORMAT:
- Plain prose, full sentences. No JSON, no curly braces, no key-value colons.
- Do not write key names like "orders:" or "processing_time:". Phrase numbers in
  words like "OrderA takes 3 hours on Unit1" or "OrderB is due by hour 18".
- ALL numeric values MUST appear as digits (3, 18), never as English words
  ("three", "eighteen"). Digit form is the contract the downstream extractor
  relies on.
- Output ONLY the problem statement. No preamble, no commentary, no markdown.
"""


def _transport_user_message(params: Dict[str, Any]) -> str:
    """Render the transport params dict into a deterministic textual form."""
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


def _scheduling_user_message(params: Dict[str, Any]) -> str:
    """Render the scheduling params dict into a deterministic textual form."""
    orders = params["orders"]
    units = params["units"]
    pt = params["processing_time"]
    dd = params["due_date"]
    lines = [
        f"Orders ({len(orders)}): {', '.join(orders)}",
        f"Units ({len(units)}): {', '.join(units)}",
        "Eligibility: every order can run on any unit.",
        "Processing times (hours):",
    ]
    for o in orders:
        for u in units:
            lines.append(f"  {o} on {u}: {pt[o][u]}")
    lines.append("Due dates:")
    for o in orders:
        lines.append(f"  {o}: {dd[o]}")
    lines.append("Objective: minimize makespan.")
    return "\n".join(lines) + "\n\nWrite the problem statement now."


_TRANSPORT_LEAKAGE_PATTERNS = [
    re.compile(r"[{}]"),
    re.compile(r"\bplants\s*:", re.IGNORECASE),
    re.compile(r"\bmarkets\s*:", re.IGNORECASE),
    re.compile(r"\bcapacity\s*:", re.IGNORECASE),
    re.compile(r"\bdemand\s*:", re.IGNORECASE),
    re.compile(r"\bcost\s*:", re.IGNORECASE),
]

_SCHEDULING_LEAKAGE_PATTERNS = [
    re.compile(r"[{}]"),
    # Underscored JSON keys would indicate structural leakage. Bare "Orders:"
    # or "Units:" are valid English headings (e.g. "Orders: A, B, C need to..."),
    # so they're not treated as leakage here.
    re.compile(r"\bprocessing_time\s*:", re.IGNORECASE),
    re.compile(r"\bdue_date\s*:", re.IGNORECASE),
]


def _assert_no_leakage(text: str, patterns: list) -> None:
    for pat in patterns:
        if pat.search(text):
            raise ValueError(f"Verbalizer leaked structural cue matching {pat.pattern!r}")


def _transport_coverage_missing(text: str, params: Dict[str, Any]) -> Dict[str, list]:
    """Return whatever the verbalization failed to mention. Empty dict means full coverage.

    Historically only names and cost numbers were checked, which let some
    seeds slip through with capacity/demand written as English words
    ("one thousand two hundred twenty-three units") — fuzzy enough to pass
    coverage, too fuzzy for the agent extractor to recover. Capacities and
    demands are now number-checked the same way scheduling's
    processing_time + due_date are.
    """
    lower = text.lower()
    missing = {"plants": [], "markets": [], "capacities": [], "demands": [], "costs": []}

    for p in params["plants"]:
        if p.lower() not in lower:
            missing["plants"].append(p)
    for m in params["markets"]:
        if m.lower() not in lower:
            missing["markets"].append(m)

    def _int_tokens(v):
        # Capacities and demands are integers per the generator; accept the
        # bare digit form plus a comma-grouped form (verbalizers occasionally
        # write "1,223" for 1223). Reject English-word forms by construction
        # because none of these tokens match "one thousand two hundred...".
        v_int = int(v)
        tokens = {str(v_int)}
        if v_int >= 1000:
            tokens.add(f"{v_int:,}")
        return tokens

    for p in params["plants"]:
        v = params["capacity"][p]
        if not any(t in text for t in _int_tokens(v)):
            missing["capacities"].append((p, v))
    for m in params["markets"]:
        v = params["demand"][m]
        if not any(t in text for t in _int_tokens(v)):
            missing["demands"].append((m, v))

    # Each cost number must appear somewhere. Costs are 2-decimal floats; allow
    # also the integer-rounded form (qwen sometimes drops trailing zeros).
    for p in params["plants"]:
        for m in params["markets"]:
            v = params["cost"][p][m]
            tokens = {f"{v:.2f}", f"{v:.1f}", f"{v:g}"}
            if not any(t in text for t in tokens):
                missing["costs"].append((p, m, v))

    return {k: v for k, v in missing.items() if v}


def _scheduling_coverage_missing(text: str, params: Dict[str, Any]) -> Dict[str, list]:
    """Return whatever the scheduling verbalization failed to mention."""
    lower = text.lower()
    missing = {"orders": [], "units": [], "processing_times": [], "due_dates": []}

    for o in params["orders"]:
        if o.lower() not in lower:
            missing["orders"].append(o)
    for u in params["units"]:
        if u.lower() not in lower:
            missing["units"].append(u)

    for o in params["orders"]:
        for u in params["units"]:
            v = params["processing_time"][o][u]
            tokens = {f"{v:.2f}", f"{v:.1f}", f"{v:g}", str(int(v)) if float(v).is_integer() else f"{v}"}
            if not any(t in text for t in tokens):
                missing["processing_times"].append((o, u, v))

    for o in params["orders"]:
        v = params["due_date"][o]
        tokens = {f"{v:.2f}", f"{v:.1f}", f"{v:g}", str(int(v)) if float(v).is_integer() else f"{v}"}
        if not any(t in text for t in tokens):
            missing["due_dates"].append((o, v))

    return {k: v for k, v in missing.items() if v}


_DOMAINS = {
    "transport": {
        "system_prompt": _TRANSPORT_SYSTEM_PROMPT,
        "user_message": _transport_user_message,
        "leakage_patterns": _TRANSPORT_LEAKAGE_PATTERNS,
        "coverage_missing": _transport_coverage_missing,
    },
    "scheduling": {
        "system_prompt": _SCHEDULING_SYSTEM_PROMPT,
        "user_message": _scheduling_user_message,
        "leakage_patterns": _SCHEDULING_LEAKAGE_PATTERNS,
        "coverage_missing": _scheduling_coverage_missing,
    },
}


def _cache_path(cache_key: str) -> Path:
    versioned = f"{_PROMPT_VERSION}:{cache_key}"
    digest = hashlib.sha1(versioned.encode()).hexdigest()[:16]
    return _CACHE_DIR / f"{digest}.txt"


_VALID_STYLES = {"neutral", "noisy"}


def _inject_noise(text: str, rng_seed: int) -> str:
    """Apply realistic, number-preserving prose noise.

    The transformations target *function words and whitespace only*, never
    numeric or proper-noun tokens — so the coverage check still passes after
    noise injection and we measure agent robustness, not the verbalizer's
    fidelity. Deterministic given ``rng_seed``.

    Transformations applied (each at low independent probability):
      - drop articles ("the", "a", "an")
      - duplicate a small filler word ("the the", "to to")
      - collapse a spacing into none, or expand single space to double
      - drop a sentence-final period
      - swap two adjacent letters inside a short lowercase function word
    """
    rng = random.Random(rng_seed)

    # Tokenise on whitespace, perturb token-by-token, rejoin. Numbers and
    # capitalised tokens (entity names) are skipped entirely.
    _NUMERIC = re.compile(r"^\$?\d")
    _ARTICLE = {"the", "a", "an"}
    _FILLER = {"to", "of", "from", "in", "on", "and"}

    tokens = text.split(" ")
    out: List[str] = []
    for tok in tokens:
        stripped = tok.strip(".,;:!?")
        lower = stripped.lower()
        # Skip protected tokens
        if _NUMERIC.search(stripped) or (stripped and stripped[0].isupper()):
            out.append(tok)
            continue
        # Drop article ~15%
        if lower in _ARTICLE and rng.random() < 0.15:
            continue
        # Duplicate filler ~5%
        if lower in _FILLER and rng.random() < 0.05:
            out.append(tok)
            out.append(tok)
            continue
        # Swap two adjacent inner letters in a short lowercase function word ~3%
        if (lower == stripped and stripped.isalpha() and len(stripped) >= 4
                and rng.random() < 0.03):
            i = rng.randint(1, len(stripped) - 3)
            stripped2 = stripped[:i] + stripped[i + 1] + stripped[i] + stripped[i + 2:]
            out.append(stripped2)
            continue
        # Drop a sentence-final period ~5%
        if tok.endswith(".") and rng.random() < 0.05:
            out.append(tok[:-1])
            continue
        out.append(tok)

    noisy = " ".join(out)
    # Light whitespace drift on a small fraction of single-spaces
    chars: List[str] = []
    for ch in noisy:
        if ch == " " and rng.random() < 0.02:
            chars.append("  ")
        else:
            chars.append(ch)
    return "".join(chars)


def verbalize(
    params: Dict[str, Any],
    llm_client,
    cache_key: Optional[str] = None,
    style: str = "neutral",
    domain: str = "transport",
) -> str:
    """Render params as a natural-language problem statement.

    Args:
        params: params dict for the chosen domain
        llm_client: an EnhancedLLMClient (we use its reasoning_client._chat)
        cache_key: stable string (e.g., f"seed:{seed}:style:{style}") for disk cache
        style: reserved for robustness tests (neutral/formal/casual/noisy)
        domain: "transport" or "scheduling"

    Returns:
        Natural-language text safe to pass to agent.solve_natural_language.
    """
    if domain not in _DOMAINS:
        raise ValueError(f"Unknown domain {domain!r}; expected one of {list(_DOMAINS)}")
    if style not in _VALID_STYLES:
        raise ValueError(f"Unknown style {style!r}; expected one of {sorted(_VALID_STYLES)}")
    spec = _DOMAINS[domain]

    if cache_key is not None:
        cpath = _cache_path(f"{domain}:{cache_key}")
        if cpath.exists():
            return cpath.read_text()

    user_msg = spec["user_message"](params)
    base_prompt = spec["system_prompt"]

    for attempt in range(2):
        system_prompt = base_prompt
        if attempt > 0:
            system_prompt += (
                "\nYOUR PREVIOUS ATTEMPT WAS INCOMPLETE. You MUST mention every "
                "entity and every number from the input. Do not summarize or skip."
            )
        raw = llm_client.reasoning_client._chat(system_prompt, user_msg, json_mode=False)
        text = _strip_thinking(raw).strip()
        _assert_no_leakage(text, spec["leakage_patterns"])
        missing = spec["coverage_missing"](text, params)
        if not missing:
            break
    else:
        raise ValueError(f"Verbalizer missed required content after retry: {missing}")

    if style == "noisy":
        # Deterministic seed off the cache_key so re-runs produce the same noise.
        noise_seed = int(hashlib.sha1(
            f"noise:{cache_key or ''}:{domain}".encode()
        ).hexdigest()[:8], 16)
        text = _inject_noise(text, noise_seed)
        # Noise only touches lowercase function words + whitespace, so the
        # coverage assertion should still hold; if a future tweak breaks that
        # invariant, fail loudly rather than silently shrinking the test.
        missing = spec["coverage_missing"](text, params)
        if missing:
            raise ValueError(
                f"Noise injection dropped required content (would invalidate "
                f"the robustness measurement): {missing}"
            )

    if cache_key is not None:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _cache_path(f"{domain}:{cache_key}").write_text(text)

    return text


def _strip_thinking(text: str) -> str:
    """deepseek-r1 wraps reasoning in <think>...</think>. Drop it."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# ---------------------------------------------------------------------------
# Paraphrase support (Phase 4 — paraphrase holdout)
# ---------------------------------------------------------------------------
#
# A paraphrase preserves every number and entity name from the canonical text,
# but varies tone, sentence structure, ordering, and word choice. Running the
# pipeline over many paraphrases of the same instance measures *robustness to
# phrasing alone*: ground truth is constant, only the prose changes.

_PARAPHRASE_STYLES = [
    "formal corporate memo (third person, precise, no contractions)",
    "casual conversational (first person, contractions ok)",
    "terse bullet-style narrative (short sentences, minimal connective tissue)",
    "verbose academic (longer sentences, hedged language)",
    "non-native-speaker English (simpler grammar, occasional awkward phrasing)",
    "executive summary (lead with the bottom line, then details)",
    "engineer-writing-a-ticket (matter-of-fact, slightly impatient)",
    "consultant pitch (mild salesmanship, but factually identical)",
    "junior analyst confused by the jargon (asks the question more naively)",
    "operator on the shop floor (concrete, references the physical work)",
]


def _paraphrase_system_prompt(style: str, domain: str) -> str:
    domain_word = "transportation" if domain == "transport" else "scheduling"
    return (
        f"You rewrite operations-research {domain_word} problem statements.\n"
        f"You will receive a canonical problem statement and a target style.\n"
        f"\n"
        f"HARD REQUIREMENTS — do not violate any of these:\n"
        f"1. Preserve EVERY number from the input exactly (capacities, demands,\n"
        f"   costs, processing times, due dates). Do not round, scale, or omit.\n"
        f"2. Preserve EVERY proper noun (plant names, market names, order names,\n"
        f"   unit names) exactly as written.\n"
        f"3. Preserve the optimization objective verbatim in meaning.\n"
        f"4. Change only: tone, sentence structure, ordering, word choice.\n"
        f"5. The rewrite must read as natural prose from a human user, not as\n"
        f"   structured data.\n"
        f"\n"
        f"TARGET STYLE: {style}\n"
        f"\n"
        f"Output ONLY the rewritten problem statement. No preamble, no commentary."
    )


def paraphrase(
    canonical_text: str,
    llm_client,
    params: Dict[str, Any],
    domain: str,
    k: int = 5,
    cache_key: Optional[str] = None,
    styles: Optional[list] = None,
) -> list:
    """Return ``k`` paraphrases of ``canonical_text``.

    Each paraphrase is checked for the same coverage + leakage guards as the
    canonical verbalization, with one retry on miss. Anything still missing
    after the retry is returned as-is — the holdout runner reports it as a
    paraphrase-stage failure rather than aborting the batch.
    """
    if domain not in _DOMAINS:
        raise ValueError(f"Unknown domain {domain!r}; expected one of {list(_DOMAINS)}")
    spec = _DOMAINS[domain]

    if styles is None:
        styles = _PARAPHRASE_STYLES
    if k > len(styles):
        raise ValueError(
            f"Requested k={k} paraphrases but only {len(styles)} distinct styles "
            f"are defined; pass `styles=...` to extend."
        )
    chosen = styles[:k]

    results = []
    for idx, style in enumerate(chosen):
        sub_key = f"{cache_key}:paraphrase:{idx}" if cache_key else None
        if sub_key is not None:
            cpath = _cache_path(f"{domain}:{sub_key}")
            if cpath.exists():
                results.append(cpath.read_text())
                continue

        sys_prompt = _paraphrase_system_prompt(style, domain)
        user_msg = canonical_text + "\n\nRewrite this in the target style now."

        text = None
        for attempt in range(2):
            sp = sys_prompt
            if attempt > 0:
                sp += (
                    "\nYOUR PREVIOUS ATTEMPT DROPPED REQUIRED NUMBERS OR NAMES. "
                    "Repeat every number and every proper noun from the input."
                )
            raw = llm_client.reasoning_client._chat(sp, user_msg, json_mode=False)
            candidate = _strip_thinking(raw).strip()
            try:
                _assert_no_leakage(candidate, spec["leakage_patterns"])
            except ValueError:
                continue
            missing = spec["coverage_missing"](candidate, params)
            if not missing:
                text = candidate
                break
        if text is None:
            # Use the last candidate even if incomplete — holdout runner treats
            # this as a paraphrase-stage failure bucket, not a hard error.
            text = candidate

        if sub_key is not None:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            _cache_path(f"{domain}:{sub_key}").write_text(text)
        results.append(text)

    return results
