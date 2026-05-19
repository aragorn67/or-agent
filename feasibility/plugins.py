"""
FeasibilityPlugin — one bundle of (Layer-1 checker, suggestion generator)
per OR problem-type family, registered together so a domain can never be
*half-wired*.

This replaces the old split that let scheduling ship broken for a while:
- a `PROBLEM_TYPE_CHECKERS` registry (Layer-1 checker), and
- a separate, hardcoded `if "SCHEDUL" else transport` suggestion dispatch
  inside `feasibility/core.py`.

With that split a new domain could register a checker but no suggester (or
land before the `if`-ladder) and silently get transport's nonsensical
"increase supply" advice for, say, an infeasible schedule. Here a domain is
*one object* carrying both halves: forgetting either is a construction-time
TypeError, not a runtime fail-open. Adding a domain = add one plugin.

Layer 0 (structural) stays domain-agnostic and is intentionally NOT part of
a plugin. Layer-1 *math* is still domain-specific — this formalizes the
*contract*, not the conditions.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

# (ok, messages) — necessary-condition verdict + human-readable reasons.
Checker = Callable[[object], Tuple[bool, List[str]]]
# (instance, failed_reasons) -> plain-language fixes for THIS domain.
Suggester = Callable[[object, List[str]], List[str]]


@dataclass(frozen=True)
class FeasibilityPlugin:
    """A domain's Layer-1 contract: necessary-condition checker + its
    matching suggestion generator, bound together."""

    name: str                       # canonical domain label
    match_tokens: Tuple[str, ...]   # UPPERCASE problem_type tokens
    checker: Checker
    suggester: Suggester

    def __post_init__(self):
        if not callable(self.checker) or not callable(self.suggester):
            raise TypeError(
                f"FeasibilityPlugin '{self.name}' must bundle BOTH a "
                f"checker and a suggester — a domain cannot be half-wired."
            )
        if not self.match_tokens:
            raise TypeError(
                f"FeasibilityPlugin '{self.name}' needs at least one "
                f"problem_type match token."
            )


_REGISTRY: List[FeasibilityPlugin] = []


def register_plugin(plugin: FeasibilityPlugin) -> None:
    """Register a domain plugin. Idempotent by name so re-imports during
    tests don't stack duplicates."""
    global _REGISTRY
    _REGISTRY = [p for p in _REGISTRY if p.name != plugin.name]
    _REGISTRY.append(plugin)


def registered_plugins() -> List[FeasibilityPlugin]:
    return list(_REGISTRY)


def resolve_plugin(problem_type) -> Optional[FeasibilityPlugin]:
    """Resolve a domain plugin for ``problem_type`` (case-insensitive,
    exact token first then substring).

    Returns ``None`` when no domain plugin exists. Callers MUST treat
    ``None`` as *"Layer 1 did not validate this domain"* — never as
    *"Layer 1 passed"*. The absence of a necessary-condition check is not
    evidence of feasibility; that distinction is the whole point of this
    module (see `feasibility/core.py`, which refuses to assert FEASIBLE
    from Layer-2 ignorance when no plugin backed Layer 1)."""
    if not problem_type:
        return None
    key = str(problem_type).upper()
    for p in _REGISTRY:                       # exact token match
        if key in p.match_tokens:
            return p
    for p in _REGISTRY:                       # then substring
        if any(tok in key for tok in p.match_tokens):
            return p
    return None
