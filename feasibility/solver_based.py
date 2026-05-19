"""
Layer 2: Solver-based feasibility checking.

Uses LP relaxation with dummy objective:
1. Build model using solver's build_model()
2. Relax all integer/binary variables to continuous
3. Replace objective with dummy (0)
4. Solve for feasibility
5. If solver returns OPTIMAL/FEASIBLE → model is feasible
   If solver returns INFEASIBLE → model is infeasible
"""

from pyomo.environ import (
    Objective, SolverFactory, minimize, Var, NonNegativeReals, Constraint
)
from pyomo.opt import TerminationCondition as TC


def solver_feasibility_check(instance, solver_name="glpk"):
    """
    Solver-based feasibility check using LP relaxation with dummy objective.

    Strategy:
    1. Get solver and build model
    2. Relax integer/binary vars to continuous [0,1]
    3. Replace objective with dummy (0)
    4. Solve
    5. If OPTIMAL/FEASIBLE → constraints are feasible
       If INFEASIBLE → constraints are infeasible

    Args:
        instance: Problem instance
        solver_name: LP solver (default: glpk)

    Returns:
        tuple: (status, details)
    """
    from solvers import get_solver

    solver_id = instance.solver_id if hasattr(instance, 'solver_id') else instance.get('solver_id', '')

    if not solver_id or solver_id == "none":
        problem_type = instance.problem_type if hasattr(instance, 'problem_type') else instance.get('problem_type', '')
        return "UNKNOWN", {"reason": f"No solver available for {problem_type}"}

    try:
        # Get solver instance (get_solver returns an instance, not a class)
        solver_instance = get_solver(solver_id)
        if not solver_instance:
            return "UNKNOWN", {"reason": f"Solver '{solver_id}' not found"}

        # Check if solver has build_model()
        if not hasattr(solver_instance, 'build_model'):
            return "UNKNOWN", {"reason": f"Solver '{solver_id}' does not expose build_model()"}

        # Convert instance to solver params format
        params = _convert_instance_to_params(instance)

        # Build model
        model = solver_instance.build_model(params)

        # Relax integer/binary variables to continuous
        _relax_integer_variables(model)

        # Keep the original objective - don't replace it
        # The objective doesn't matter for feasibility, but keeping it
        # helps GLPK correctly detect infeasibility vs unboundedness

        # Solve
        # For GLPK, we need to capture output to detect infeasibility
        # because it returns "other" when infeasible due to presolver
        import io
        import sys

        pyomo_solver = SolverFactory(solver_name)

        # Capture solver output
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()

        result = pyomo_solver.solve(model, tee=True, load_solutions=False)

        sys.stdout = old_stdout
        solver_output = buffer.getvalue()

        tc = result.solver.termination_condition

        if tc == TC.optimal or tc == TC.feasible:
            # Solver found a feasible point
            return "FEASIBLE", {
                "solver": solver_name,
                "termination_condition": str(tc)
            }
        elif tc == TC.infeasible:
            # Solver proved infeasibility
            return "INFEASIBLE", {
                "solver": solver_name,
                "termination_condition": str(tc),
                "reason": "LP relaxation is infeasible - constraint pattern cannot be satisfied"
            }
        elif tc == TC.unbounded:
            # Unbounded means feasible (no upper bound on objective, but constraints satisfied)
            return "FEASIBLE", {
                "solver": solver_name,
                "termination_condition": str(tc)
            }
        elif str(tc) == "other":
            # GLPK sometimes returns "other" when infeasible due to presolver
            # Check the captured output for "NO PRIMAL FEASIBLE SOLUTION"
            if "NO PRIMAL FEASIBLE SOLUTION" in solver_output or "NO FEASIBLE SOLUTION" in solver_output:
                return "INFEASIBLE", {
                    "solver": solver_name,
                    "termination_condition": str(tc),
                    "reason": "LP relaxation is infeasible (detected from solver output)"
                }
            else:
                return "UNKNOWN", {
                    "solver": solver_name,
                    "termination_condition": str(tc),
                    "reason": f"Inconclusive: {str(tc)}"
                }
        else:
            return "UNKNOWN", {
                "solver": solver_name,
                "termination_condition": str(tc),
                "reason": f"Inconclusive: {str(tc)}"
            }

    except Exception as e:
        return "UNKNOWN", {
            "error": str(e),
            "reason": "Error during solver-based feasibility check"
        }


def _relax_integer_variables(model):
    """
    Relax all integer/binary variables to continuous.

    Binary → Continuous [0,1]
    Integer → Continuous [lb, ub]
    """
    from pyomo.environ import Binary, Integers, Reals

    for var in model.component_objects(Var, active=True):
        for index in var:
            if var[index].domain == Binary:
                # Relax binary to continuous [0,1]
                var[index].domain = Reals
                var[index].setlb(0)
                var[index].setub(1)
            elif var[index].domain == Integers:
                # Relax integer to continuous
                var[index].domain = Reals


def _set_dummy_objective(model):
    """
    Replace the objective with a constant objective = 1.

    This turns the optimization into a pure feasibility check.
    The solver will just try to find ANY feasible point.

    Using constant 1 instead of 0 to avoid potential solver issues.
    """
    # Delete existing objective
    model.del_component(model.OBJ)

    # Set constant objective = 1
    model.OBJ = Objective(expr=1.0, sense=minimize)


def _convert_instance_to_params(instance):
    """Convert a feasibility instance into the param shape its solver's
    ``build_model`` expects.

    Domain-aware (was transport-only): this is the per-domain "glue" that
    lets Layer 2 run for ANY solver exposing ``build_model``. Adding a new
    OR domain means: register its Layer-1 plugin AND add a branch here
    (or give the instance a shape this already recognises). Scheduling is
    detected by its params; transport by its I*/J* sets; anything else
    passes params through untouched (the solver/relaxation will error →
    UNKNOWN, which core.py now treats fail-closed).
    """
    sets = instance.sets if hasattr(instance, 'sets') else instance.get('sets', {})
    params = instance.params if hasattr(instance, 'params') else instance.get('params', {})

    # --- Single-stage scheduling -------------------------------------
    # The IPM solver's build_model wants lists `orders`/`units` plus
    # `eligible`/`processing_time`/`due_date` (processing_time may stay
    # tuple-keyed — _normalize_matrix_ij handles that). The feasibility
    # instance carries orders/units in sets (I_orders/I_units) and the
    # rest in params.
    if 'processing_time' in params and 'due_date' in params:
        def _set_like(*needles):
            for k, v in sets.items():
                kl = k.lower()
                if any(n in kl for n in needles):
                    return list(v)
            return None

        orders = _set_like('order', 'job', 'task')
        units = _set_like('unit', 'machine', 'resource')
        # Fall back to deriving the universes from the params themselves.
        if orders is None:
            orders = list(params['due_date'].keys())
        if units is None:
            units = sorted({
                k[1] for k in params['processing_time']
                if isinstance(k, tuple) and len(k) == 2
            } or {
                u for v in params['processing_time'].values()
                if isinstance(v, dict) for u in v
            })
        sched = {
            "orders": orders,
            "units": units,
            "eligible": params.get('eligible', {}),
            "processing_time": params['processing_time'],
            "due_date": params['due_date'],
        }
        for opt in ("changeover", "window", "lower", "objective"):
            if opt in params:
                sched[opt] = params[opt]
        return sched

    # --- Transportation ----------------------------------------------
    sources_key = None
    sinks_key = None

    for key in sets.keys():
        if key.startswith('I'):
            sources_key = key
        if key.startswith('J'):
            sinks_key = key

    if sources_key and sinks_key:
        result = {
            "plants": sets[sources_key],
            "markets": sets[sinks_key],
            "capacity": params.get('supply', params.get('capacity', {})),
            "demand": params.get('demand', {})
        }

        # Add cost (required for build_model, but will be replaced)
        if 'cost' in params:
            result['cost'] = params['cost']
        elif 'distance' in params and 'freight' in params:
            result['distance'] = params['distance']
            result['freight'] = params['freight']
        else:
            # Dummy cost
            result['cost'] = {(i, j): 1.0 for i in sets[sources_key] for j in sets[sinks_key]}

        # Add arc_capacity if present (THIS IS KEY FOR LAYER 2!)
        if 'arc_capacity' in params:
            result['arc_capacity'] = params['arc_capacity']

        return result

    return params


def generate_solver_suggestions(instance, solver_result: dict) -> list[str]:
    """
    Generate actionable suggestions based on solver-based infeasibility.

    Layer 2 infeasibility means the constraint pattern is unsatisfiable,
    even though individual checks (Layer 0, 1) passed.

    Args:
        instance: The problem instance
        solver_result: Details from solver_feasibility_check

    Returns:
        List of actionable suggestions for the user
    """
    suggestions = []
    params = instance.params if hasattr(instance, 'params') else instance.get('params', {})
    sets = instance.sets if hasattr(instance, 'sets') else instance.get('sets', {})

    # Check if arc capacities are involved (common cause of Layer 2 infeasibility)
    has_arc_capacity = 'arc_capacity' in params

    if has_arc_capacity:
        arc_capacity = params['arc_capacity']
        demand = params.get('demand', {})
        supply = params.get('supply', params.get('capacity', {}))

        suggestions.append(
            "The problem passed supply/demand balance checks but the arc capacity constraints "
            "create an infeasible pattern. This means the specific routing constraints cannot all be satisfied simultaneously."
        )

        # Find potential bottlenecks
        sources = None
        sinks = None
        for name in ['I', 'I_sources', 'I_plants', 'I_factories']:
            if name in sets:
                sources = sets[name]
                break
        for name in ['J', 'J_sinks', 'J_markets', 'J_warehouses']:
            if name in sets:
                sinks = sets[name]
                break

        if sources and sinks:
            # Identify sinks with tight capacity
            tight_sinks = []
            for sink in sinks:
                total_incoming = sum(arc_capacity.get((src, sink), 0) for src in sources)
                sink_demand = demand.get(sink, 0)
                if total_incoming < sink_demand * 1.2:  # Less than 20% buffer
                    tight_sinks.append((sink, sink_demand, total_incoming))

            if tight_sinks:
                suggestions.append(
                    "Sinks with tight arc capacity constraints (potential bottlenecks):"
                )
                for sink, demand_val, total_cap in tight_sinks:
                    suggestions.append(
                        f"  - '{sink}': demand={demand_val:.2f}, total incoming capacity={total_cap:.2f}"
                    )
                suggestions.append(
                    "Try increasing arc capacities to these sinks, or add alternative routes."
                )

            # Suggest specific actions
            suggestions.append(
                "Possible fixes:"
            )
            suggestions.append(
                "1. Increase individual arc capacities to relieve bottlenecks"
            )
            suggestions.append(
                "2. Add new routes (arcs) between sources and sinks"
            )
            suggestions.append(
                "3. Redistribute demand across sinks to better match available capacity"
            )

            # Give specific example
            if tight_sinks:
                sink, demand_val, total_cap in tight_sinks[0]
                shortfall = demand_val - total_cap
                if shortfall > 0:
                    # Find best arc to increase
                    best_arc = max(
                        [(src, arc_capacity.get((src, sink), 0)) for src in sources],
                        key=lambda x: x[1]
                    )
                    suggestions.append(
                        f"Example: Increase capacity of route '{best_arc[0]}→{sink}' "
                        f"from {best_arc[1]:.2f} to {best_arc[1] + shortfall:.2f}"
                    )
    else:
        # Generic solver infeasibility (no arc capacities)
        suggestions.append(
            "The solver determined the constraint system is infeasible. "
            "This means even with relaxed integer constraints, no solution exists."
        )
        suggestions.append(
            "This could indicate:"
        )
        suggestions.append(
            "1. Conflicting constraints that cannot be satisfied together"
        )
        suggestions.append(
            "2. Insufficient capacity or resources to meet all requirements"
        )
        suggestions.append(
            "3. Routing or connectivity issues not detected by simpler checks"
        )
        suggestions.append(
            "Try relaxing some constraints or increasing capacities."
        )

    return suggestions
