"""
Layer 1: Single-stage scheduling necessary-condition checks.

The dominant necessary condition for makespan / due-date scheduling: an
order cannot complete before it has run for its processing time on *some*
eligible unit. So for every order, the minimum processing time over its
eligible units must not exceed its due date — otherwise no schedule, on
any number of units, can meet the deadline. This is exactly the case the
demo hits ("every order due by hour 4" while OrderC needs >= 5 h), and
catching it here yields a plain-language explanation instead of the
solver raising a raw HiGHS "no feasible solution" exception.
"""


def _get_params(instance) -> dict:
    return instance.params if hasattr(instance, 'params') else instance.get('params', {})


def _processing_lookup(processing_time, order, unit):
    """processing_time may be flattened to {(order, unit): v} (the instance
    builder path) or stay nested {order: {unit: v}}. Support both."""
    if (order, unit) in processing_time:
        return processing_time[(order, unit)]
    nested = processing_time.get(order)
    if isinstance(nested, dict):
        return nested.get(unit)
    return None


def check_due_date_vs_processing(instance) -> tuple[bool, list[str]]:
    params = _get_params(instance)
    processing_time = params.get('processing_time', {})
    due_date = params.get('due_date', {})
    eligible = params.get('eligible', {})

    if not processing_time or not due_date:
        # Nothing to check (e.g. pure changeover objective, no deadlines)
        return True, []

    # Derive the unit universe from whatever keys we have.
    all_units = set()
    for k in processing_time:
        if isinstance(k, tuple) and len(k) == 2:
            all_units.add(k[1])
        elif isinstance(processing_time[k], dict):
            all_units.update(processing_time[k].keys())

    for order, deadline in due_date.items():
        if deadline is None:
            continue

        # An order *explicitly* present in the eligibility map uses that
        # list verbatim — an empty list means "no eligible unit" and is
        # infeasible, NOT "fall back to all units". Only an absent/empty
        # eligibility map at all defaults to every unit.
        if isinstance(eligible, dict) and order in eligible:
            elig_units = eligible[order] or []
        else:
            elig_units = sorted(all_units)

        if not elig_units:
            return False, [
                f"Order '{order}' has no eligible unit, so it can never "
                f"be scheduled."
            ]

        times = [
            t for t in (_processing_lookup(processing_time, order, u) for u in elig_units)
            if t is not None
        ]

        if not times:
            return False, [
                f"Order '{order}' has no eligible unit with a defined "
                f"processing time, so it can never be scheduled."
            ]

        fastest = min(times)
        if fastest > deadline:
            return False, [
                f"Order '{order}' needs at least {fastest:g} h on its "
                f"fastest eligible unit, but its deadline is hour "
                f"{deadline:g}. No schedule on any number of units can "
                f"meet that — the deadline is shorter than the work itself."
            ]

    return True, ["Every order can meet its deadline on at least one eligible unit"]


def scheduling_checks(instance) -> tuple[bool, list[str]]:
    """Run all single-stage scheduling Layer 1 checks."""
    all_checks = [check_due_date_vs_processing]

    reasons = []
    for check in all_checks:
        ok, msgs = check(instance)
        if not ok:
            return False, msgs
        reasons.extend(msgs)
    return True, reasons


def generate_scheduling_suggestions(instance, error_messages: list[str]) -> list[str]:
    """Plain-language fixes for an infeasible scheduling instance."""
    suggestions = []
    for msg in error_messages:
        if "deadline" in msg or "shorter than the work" in msg:
            suggestions.append(
                "Relax the deadline(s) to at least the order's fastest "
                "processing time, or add a faster eligible unit."
            )
        elif "no eligible unit" in msg:
            suggestions.append(
                "Make at least one unit eligible for that order, or add a "
                "processing time for it on an existing unit."
            )
    if not suggestions:
        suggestions.append(
            "Loosen the binding deadline or add processing capacity."
        )
    # De-duplicate while preserving order.
    seen, out = set(), []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out
