"""
Layer 1: Transportation-specific feasibility checks.

Implements necessary conditions that must hold for transportation problems:
- Supply/demand balance
- Sink reachability
- Capacity constraints vs demand
"""


def check_supply_demand_balance(instance) -> tuple[bool, list[str]]:
    """
    Check that total supply >= total demand.

    For a transportation problem to be feasible, we need enough total supply
    to meet total demand. This is a necessary (but not sufficient) condition.
    """
    params = instance.params if hasattr(instance, 'params') else instance.get('params', {})

    # Extract supply and demand
    supply = params.get('supply', params.get('capacity', {}))
    demand = params.get('demand', {})

    if not supply or not demand:
        # If no supply/demand specified, skip this check
        return True, []

    total_supply = sum(supply.values())
    total_demand = sum(demand.values())

    if total_supply < total_demand - 1e-6:  # Small tolerance for floating point
        shortfall = total_demand - total_supply
        return False, [
            f"Total supply ({total_supply:.2f}) is less than total demand ({total_demand:.2f}). "
            f"Shortfall: {shortfall:.2f}. "
            f"This problem is provably infeasible - you need to either increase supply or reduce demand."
        ]

    # Success message (for diagnostic purposes)
    if total_supply > total_demand + 1e-6:
        surplus = total_supply - total_demand
        return True, [f"Supply/demand balance OK (surplus: {surplus:.2f})"]
    else:
        return True, ["Supply/demand balance OK (perfectly balanced)"]


def check_sink_reachability(instance) -> tuple[bool, list[str]]:
    """
    Check that each sink can be reached from at least one source.

    For each sink j, there must exist at least one source i with:
    - A defined cost c[i,j]
    - Sufficient capacity (if arc capacities are specified)

    This is a basic connectivity check.
    """
    sets = instance.sets if hasattr(instance, 'sets') else instance.get('sets', {})
    params = instance.params if hasattr(instance, 'params') else instance.get('params', {})

    # Get source and sink sets
    sources = None
    sinks = None

    for name in ['I', 'I_sources', 'I_plants', 'I_factories', 'I_mills', 'I_warehouses']:
        if name in sets:
            sources = sets[name]
            break

    for name in ['J', 'J_sinks', 'J_markets', 'J_warehouses', 'J_stores', 'J_projects', 'J_centres', 'J_plants']:
        if name in sets:
            sinks = sets[name]
            break

    if not sources or not sinks:
        return True, []  # Skip if can't identify sets

    # Get cost matrix and arc capacities
    cost = params.get('cost', {})
    arc_capacity = params.get('arc_capacity', None)
    demand = params.get('demand', {})

    # For each sink, check if it can be reached
    unreachable_sinks = []

    for sink in sinks:
        incoming_arcs = []

        for source in sources:
            arc = (source, sink)

            # Check if arc exists (has a cost)
            if arc in cost:
                # Check if arc has sufficient capacity (if capacities specified)
                if arc_capacity is not None:
                    cap = arc_capacity.get(arc, 0)
                    if cap > 1e-6:  # Arc has positive capacity
                        incoming_arcs.append((source, cap))
                else:
                    # No arc capacities specified, assume unlimited
                    incoming_arcs.append((source, float('inf')))

        if not incoming_arcs:
            unreachable_sinks.append(sink)

    if unreachable_sinks:
        return False, [
            f"Sinks {unreachable_sinks} cannot be reached from any source. "
            f"These sinks have no incoming arcs with defined costs or positive capacity."
        ]

    return True, ["All sinks are reachable from at least one source"]


def check_individual_sink_capacity(instance) -> tuple[bool, list[str]]:
    """
    Check that each sink's demand can be met by its incoming arc capacities.

    If arc capacities are specified, for each sink j:
        sum of incoming arc capacities >= demand[j]

    This is a stronger check than just total balance.
    """
    sets = instance.sets if hasattr(instance, 'sets') else instance.get('sets', {})
    params = instance.params if hasattr(instance, 'params') else instance.get('params', {})

    # Get arc capacities - if not specified, skip this check
    arc_capacity = params.get('arc_capacity', None)
    if arc_capacity is None:
        return True, []  # No arc capacities, skip

    # Get sources and sinks
    sources = None
    sinks = None

    for name in ['I', 'I_sources', 'I_plants', 'I_factories', 'I_mills', 'I_warehouses']:
        if name in sets:
            sources = sets[name]
            break

    for name in ['J', 'J_sinks', 'J_markets', 'J_warehouses', 'J_stores', 'J_projects', 'J_centres', 'J_plants']:
        if name in sets:
            sinks = sets[name]
            break

    if not sources or not sinks:
        return True, []

    demand = params.get('demand', {})
    if not demand:
        return True, []

    # Check each sink
    insufficient_sinks = []

    for sink in sinks:
        total_incoming_capacity = 0

        for source in sources:
            arc = (source, sink)
            cap = arc_capacity.get(arc, 0)
            total_incoming_capacity += cap

        sink_demand = demand.get(sink, 0)

        if total_incoming_capacity < sink_demand - 1e-6:
            insufficient_sinks.append({
                'sink': sink,
                'demand': sink_demand,
                'capacity': total_incoming_capacity,
                'shortfall': sink_demand - total_incoming_capacity
            })

    if insufficient_sinks:
        details = [
            f"{s['sink']}: needs {s['demand']}, can receive max {s['capacity']} (shortfall: {s['shortfall']:.2f})"
            for s in insufficient_sinks
        ]
        return False, [
            f"Some sinks cannot receive enough flow due to arc capacity limits:\n" +
            "\n".join(f"  - {d}" for d in details)
        ]

    return True, ["All sinks have sufficient incoming arc capacity"]


def transport_checks(instance) -> tuple[bool, list[str]]:
    """
    Run all transportation-specific Layer 1 checks.

    Returns:
        (ok, messages) where ok=True if all checks pass
    """
    all_checks = [
        check_supply_demand_balance,
        check_sink_reachability,
        check_individual_sink_capacity
    ]

    reasons = []
    for check in all_checks:
        ok, msgs = check(instance)
        if not ok:
            return False, msgs
        reasons.extend(msgs)

    return True, reasons
