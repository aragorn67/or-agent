"""
Map a free-text user reply to a canonical /continue action.

Used by the chat-friendly `/chat/continue` endpoint: the user says "yeah make
it better" and we need that to become `action="optimize"`. Keyword matching
covers the common phrases unambiguously; an LLM fallback can be added later
if/when users stray off the script.

Why a separate file: keeping the keyword vocabulary in one place makes it easy
to extend without touching the agent or API surface. Same reason the existing
follow_up_handler keeps its detection in a dedicated module.
"""

import re
from typing import Optional


# Order matters: more-specific phrases first. Each entry is (regex, action).
# Regexes use word boundaries so "stop" doesn't match "stoppage".
_PATTERNS = [
    # "use the heuristic" / "keep heuristic" → use_heuristic
    (re.compile(r"\b(use|keep|stick\s+with|stay\s+on)\b[^.!?]*\bheuristic\b", re.I), "use_heuristic"),
    (re.compile(r"\bheuristic\s+is\s+(fine|good|enough|ok|okay)\b", re.I), "use_heuristic"),

    # Acceptance: "accept", "good enough", "this is fine", "done", "ok done"
    (re.compile(r"\b(accept|accepted|good\s+enough|this\s+is\s+fine|that'?s\s+fine|that\s+works|finalize|finalise|finish|that'?ll\s+do)\b", re.I), "accept"),
    (re.compile(r"\b(i'?m\s+done|i'?m\s+good|we'?re\s+good|stop|cancel|no\s+thanks|no\s+thank\s+you)\b", re.I), "accept"),

    # Optimize: "improve", "optimize", "keep going", "make it better", "to optimum", "yes"
    (re.compile(r"\b(optimize|optimise|optimal|to\s+optimum|exact|run\s+(the\s+)?solver|keep\s+going|continue|proceed)\b", re.I), "optimize"),
    (re.compile(r"\b(improve|make\s+it\s+better|do\s+better|better\s+answer|squeeze|close\s+the\s+gap|tighten)\b", re.I), "optimize"),
    (re.compile(r"^\s*(yes|yeah|yep|sure|ok|okay|go|please)\s*[.!]?\s*$", re.I), "optimize"),
]


def parse_continue_action(message: str) -> Optional[str]:
    """
    Best-effort parse of a free-text reply into an action.

    Returns one of "optimize" | "accept" | "use_heuristic", or None if no
    pattern matched. Callers should surface a clarification prompt on None
    rather than guessing.
    """
    if not message or not message.strip():
        return None
    for pattern, action in _PATTERNS:
        if pattern.search(message):
            return action
    return None
