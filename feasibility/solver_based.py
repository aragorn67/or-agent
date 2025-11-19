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
    """Convert feasibility instance format to solver params format."""
    sets = instance.sets if hasattr(instance, 'sets') else instance.get('sets', {})
    params = instance.params if hasattr(instance, 'params') else instance.get('params', {})

    # For transportation problems
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
