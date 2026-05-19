"""
Layer 1: Problem-specific necessary-condition checks.

Every domain registers ONE :class:`FeasibilityPlugin` bundling its checker
and its suggestion generator (see ``feasibility/plugins.py``) — they can no
longer drift apart or be half-wired. ``core.py`` resolves the plugin
directly; ``problem_specific_checks`` is kept as a thin, plugin-routed
back-compat entry for callers/tests that only want the Layer-1 verdict.
"""

from ..plugins import (
    FeasibilityPlugin,
    register_plugin,
    resolve_plugin,
    registered_plugins,
)
from .transport import transport_checks, generate_transport_suggestions
from .scheduling import scheduling_checks, generate_scheduling_suggestions

register_plugin(FeasibilityPlugin(
    name="transportation",
    match_tokens=("TRANSPORTATION", "TRANSPORT"),
    checker=transport_checks,
    suggester=generate_transport_suggestions,
))

register_plugin(FeasibilityPlugin(
    name="single_stage_scheduling",
    # Covers SCHEDULING / SINGLE_STAGE_SCHEDULING / SINGLE_MACHINE_*; the
    # short tokens make the substring pass forgiving of LLM variants.
    match_tokens=("SCHEDULING", "SCHEDUL", "SINGLE_STAGE", "SINGLE_MACHINE"),
    checker=scheduling_checks,
    suggester=generate_scheduling_suggestions,
))


def problem_specific_checks(instance) -> tuple[bool, list[str]]:
    """Run the resolved domain's Layer-1 checks.

    Returns ``(ok, messages)``. When NO domain plugin matches this is
    ``(True, ["No Layer 1 plugin …"])`` — Layer 0 alone shouldn't block —
    but note this is *"not validated"*, not *"validated feasible"*.
    ``core.py`` resolves the plugin itself and uses that distinction to
    stay fail-closed; this shim is only for the Layer-1-verdict callers.
    """
    problem_type = None
    if hasattr(instance, 'problem_type'):
        problem_type = instance.problem_type
    elif isinstance(instance, dict):
        problem_type = instance.get('problem_type', '')

    if not problem_type:
        return True, ["No problem_type specified, skipping problem-specific checks"]

    plugin = resolve_plugin(problem_type)
    if plugin is None:
        return True, [
            f"No Layer 1 plugin for problem type '{problem_type}' "
            f"(necessary conditions NOT validated for this domain)"
        ]
    return plugin.checker(instance)


__all__ = [
    "FeasibilityPlugin",
    "register_plugin",
    "resolve_plugin",
    "registered_plugins",
    "problem_specific_checks",
]
