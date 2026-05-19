# solvers/scheduling/single_stage_ipm.py
"""
Single-Stage Immediate-Precedence Scheduling Solver

Handles single-stage continuous process scheduling with:
- Multiple parallel units
- Order-unit eligibility restrictions
- Sequence-dependent changeovers
- Due date constraints
- Optional time windows
- Makespan or changeover minimization

Based on Immediate-Precedence MILP (IPM) formulation from Section 3.1
"""

from typing import Dict, List, Any, Optional, Tuple
from pyomo.environ import (
    ConcreteModel, Set, Param, Var, NonNegativeReals, Binary,
    Objective, Constraint, minimize, value, TransformationFactory,
    SolverFactory,
)
from pyomo.contrib.appsi.solvers.highs import Highs
from ..base import OptimizationSolver
from ..transport.bipartite import _model_has_integer_vars


class SingleStageIPMSolver(OptimizationSolver):
    """
    Single-stage immediate-precedence scheduling solver.

    Formulation:
        - Binary assignment variables Y[i,j]: order i assigned to unit j
        - Binary precedence variables XX[i,i',j]: order i immediately precedes i' on unit j
        - Continuous completion times C[i]
        - Makespan Cmax

    Constraints:
        - Each order assigned to exactly one eligible unit
        - At most one predecessor/successor per (order, unit) pair
        - Sequence count consistency
        - Time-window bounds (optional)
        - Precedence timing constraints
        - Due date constraints
        - Makespan definition
    """

    @property
    def solver_id(self) -> str:
        return "single_stage_ipm_scheduling"

    @property
    def problem_type(self) -> str:
        return "scheduling"

    @property
    def description(self) -> str:
        return "Single-stage immediate-precedence continuous process scheduling"

    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        """Validate scheduling problem parameters"""
        errors = []

        required = ["orders", "units", "eligible", "processing_time", "due_date"]
        missing = [k for k in required if k not in params]
        if missing:
            errors.append(f"Missing required keys: {missing}")
            return errors

        if not isinstance(params["orders"], list):
            errors.append("`orders` must be a list of order IDs")

        if not isinstance(params["units"], list):
            errors.append("`units` must be a list of unit IDs")

        if not isinstance(params["eligible"], dict):
            errors.append("`eligible` must be a dict mapping order -> list of eligible units")

        if not isinstance(params["processing_time"], dict):
            errors.append("`processing_time` must be a dict ((i,j)->val) or nested {i:{j:val}}")

        if not isinstance(params["due_date"], dict):
            errors.append("`due_date` must be a dict {order: due_date}")

        if "changeover" in params and not isinstance(params["changeover"], dict):
            errors.append("`changeover` must be a dict ((i,i',j)->val) or nested {j:{i:{i':val}}}")

        if "window" in params and not isinstance(params["window"], dict):
            errors.append("`window` must be a dict {order: 0/1}")

        if "lower" in params and not isinstance(params["lower"], dict):
            errors.append("`lower` must be a dict {order: lower_bound}")

        return errors

    def get_example_params(self) -> Dict[str, Any]:
        """Return example scheduling parameters"""
        return {
            "orders": ["O1", "O2", "O3"],
            "units": ["U1", "U2"],
            "eligible": {
                "O1": ["U1", "U2"],
                "O2": ["U1"],
                "O3": ["U1", "U2"]
            },
            "processing_time": {
                "O1": {"U1": 2.0, "U2": 3.0},
                "O2": {"U1": 1.5},
                "O3": {"U1": 2.5, "U2": 2.0}
            },
            "due_date": {
                "O1": 10.0,
                "O2": 8.0,
                "O3": 12.0
            },
            "changeover": {
                "U1": {
                    "O1": {"O2": 0.5, "O3": 0.3},
                    "O2": {"O1": 0.4, "O3": 0.6},
                    "O3": {"O1": 0.5, "O2": 0.4}
                },
                "U2": {
                    "O1": {"O3": 0.4},
                    "O3": {"O1": 0.3}
                }
            },
            "window": {},
            "lower": {},
            "objective": "makespan"
        }

    def build_model(self, params: Dict[str, Any]):
        """
        Construct the Immediate-Precedence Single-Stage MILP (no solve).

        Factored out of ``solve()`` so the same model can be (a) solved,
        (b) LP-relaxed for a bound, and (c) used by the Layer-2
        solver-based feasibility check — which only runs for solvers that
        expose ``build_model``. Returns the Pyomo ``ConcreteModel`` with
        its original objective intact.

        Raises ``ValueError`` on invalid params so direct callers (Layer 2)
        fail cleanly into UNKNOWN rather than crashing.
        """
        errors = self.validate_params(params)
        if errors:
            raise ValueError("; ".join(errors))

        I: List[str] = [str(x) for x in params["orders"]]
        J: List[str] = [str(x) for x in params["units"]]
        J_i: Dict[str, List[str]] = self._normalize_eligible(params["eligible"])

        T = self._normalize_matrix_ij(params["processing_time"])
        changeover = self._normalize_tensor_iip_j(params.get("changeover", {}))
        DDATE: Dict[str, float] = {str(k): float(v) for k, v in params["due_date"].items()}
        window: Dict[str, float] = {str(k): float(v) for k, v in params.get("window", {}).items()}
        lower: Dict[str, float] = {str(k): float(v) for k, v in params.get("lower", {}).items()}
        objective = params.get("objective", "makespan").lower().strip()

        # Orders with strict time window
        W = {i for i, w in window.items() if w >= 0.5}

        # Build Pyomo model
        m = ConcreteModel()

        # Sets
        m.I = Set(initialize=I)
        m.J = Set(initialize=J)

        def _J_i_init(m, i):
            return J_i.get(i, [])
        m.J_i = Set(m.I, initialize=_J_i_init, ordered=True)

        # Parameters
        def _T_init(m, i, j):
            return float(T.get((i, j), 0.0))
        m.T = Param(m.I, m.J, initialize=_T_init, within=NonNegativeReals, default=0.0)

        def _chg_init(m, i, ip, j):
            if i == ip:
                return 0.0
            return float(changeover.get((i, ip, j), 0.0))
        m.changeover = Param(m.I, m.I, m.J, initialize=_chg_init, within=NonNegativeReals, mutable=True)

        m.DDATE = Param(m.I, initialize=DDATE, within=NonNegativeReals)

        def _win_init(m, i):
            return float(window.get(i, 0.0))
        def _low_init(m, i):
            return float(lower.get(i, 0.0))
        m.window = Param(m.I, initialize=_win_init, within=NonNegativeReals, default=0.0, mutable=True)
        m.Lower = Param(m.I, initialize=_low_init, within=NonNegativeReals, default=0.0, mutable=True)

        # Tmin[i] = min_j T[i,j] for j in J_i[i]
        def _Tmin_init(m, i):
            elig = list(m.J_i[i])
            if not elig:
                raise ValueError(f"No eligible units for order '{i}'.")
            return min(m.T[i, j] for j in elig)
        m.Tmin = Param(m.I, initialize=_Tmin_init, within=NonNegativeReals)

        # Variables
        m.Y = Var(m.I, m.J, domain=Binary)  # assignment
        m.XX = Var(((i, ip, j) for i in I for ip in I if i != ip for j in J), domain=Binary)  # immediate precedence
        m.C = Var(m.I, domain=NonNegativeReals)  # completion time
        m.Cmax = Var(domain=NonNegativeReals)    # makespan

        # Constraints
        # (3.1.1) assignment: Σ_{j∈J_i} Y[i,j] = 1
        def _assign_rule(m, i):
            return sum(m.Y[i, j] for j in m.J_i[i]) == 1
        m.Assign = Constraint(m.I, rule=_assign_rule)

        # Zero-out non-eligible Y
        def _elig_rule(m, i, j):
            if j in m.J_i[i]:
                return Constraint.Skip
            return m.Y[i, j] == 0
        m.Eligibility = Constraint(m.I, m.J, rule=_elig_rule)

        # (3.1.2) at most one predecessor
        def _pred_rule(m, i, j):
            return sum(m.XX[i2, i, j] for i2 in m.I if i2 != i) <= m.Y[i, j]
        m.Pred = Constraint(m.I, m.J, rule=_pred_rule)

        # (3.1.3) at most one successor
        def _succ_rule(m, i, j):
            return sum(m.XX[i, i2, j] for i2 in m.I if i2 != i) <= m.Y[i, j]
        m.Succ = Constraint(m.I, m.J, rule=_succ_rule)

        # (3.1.4) sequence count on each unit j
        def _seqcount_rule(m, j):
            left = sum(m.XX[i, i2, j] for i in m.I for i2 in m.I if i != i2)
            right = sum(m.Y[i, j] for i in m.I) - 1
            return left == right if len(m.I) > 0 else left == 0
        m.SeqCount = Constraint(m.J, rule=_seqcount_rule)

        # (3.1.5) time-window lower bound only for i in W
        def _timewindow_rule(m, i):
            if i not in W:
                return Constraint.Skip
            return m.C[i] >= m.Lower[i] + sum(m.T[i, j] * m.Y[i, j] for j in m.J_i[i])
        m.TimeWindow = Constraint(m.I, rule=_timewindow_rule)

        # Base completion lower bound for first jobs
        def _base_completion_lb(m, i):
            return m.C[i] >= sum(m.T[i, j] * m.Y[i, j] for j in m.J_i[i])
        m.BaseCompletionLB = Constraint(m.I, rule=_base_completion_lb)

        # (3.1.6) lower timing with efficient M1 = DDATE[i]
        def _timing_lower_rule(m, i, ip, j):
            if i == ip:
                return Constraint.Skip
            M1 = m.DDATE[i]
            return m.C[ip] >= m.C[i] + m.T[ip, j] + m.changeover[i, ip, j] - M1 * (1 - m.XX[i, ip, j])
        m.TimingLower = Constraint(((i, ip, j) for i in I for ip in I if i != ip for j in J),
                                   rule=_timing_lower_rule)

        # (3.1.7) upper timing (exclude when predecessor i has window=1)
        def _timing_upper_rule(m, i, ip, j):
            if i == ip:
                return Constraint.Skip
            if i in W:
                return Constraint.Skip
            M2 = m.DDATE[ip] - m.Tmin[ip]
            return m.C[ip] <= m.C[i] + m.T[ip, j] + m.changeover[i, ip, j] + M2 * (1 - m.XX[i, ip, j])
        m.TimingUpper = Constraint(((i, ip, j) for i in I for ip in I if i != ip for j in J),
                                   rule=_timing_upper_rule)

        # (3.1.9) due dates
        def _due_rule(m, i):
            return m.C[i] <= m.DDATE[i]
        m.Due = Constraint(m.I, rule=_due_rule)

        # makespan link
        def _cmax_link_rule(m, i):
            return m.Cmax >= m.C[i]
        m.CmaxLink = Constraint(m.I, rule=_cmax_link_rule)

        # Objective
        if objective == "changeover":
            m.OBJ = Objective(
                expr=sum(m.changeover[i, ip, j] * m.XX[i, ip, j]
                         for i in I for ip in I if i != ip for j in J),
                sense=minimize
            )
        else:  # "makespan" default
            m.OBJ = Objective(expr=m.Cmax, sense=minimize)

        return m

    def solve(
        self,
        params: Dict[str, Any],
        warm_start: Optional[Dict[str, Any]] = None,
        time_limit: float = 60.0,
        gap_target: float = 0.01,
    ) -> Dict[str, Any]:
        """
        Build & solve the Immediate-Precedence Single-Stage MILP (IPM) with HiGHS.

        Args:
            params: scheduling parameters (orders, units, eligible,
                processing_time, due_date, optional changeover/window/lower/objective).
            warm_start: optional dict with keys
                - "assignment": {order -> unit}
                - "sequence": {unit -> [orders in order]}
                - "completion": {order -> float}
                - "cmax": float
                Used to seed Y, XX, C, Cmax variables. Gated on integer-var
                presence — this solver IS a MIP so the gate always passes.
            time_limit: hard time limit passed to HiGHS (seconds).
            gap_target: acceptable relative MIP gap (HiGHS mip_rel_gap).

        Returns:
            {
                "status": "OPTIMAL" | "INFEASIBLE" | ...,
                "solver_id": "single_stage_ipm_scheduling",
                "objective": float,
                "objective_value": float,
                "best_bound": float | None,
                "gap": float | None,
                "assignments": [{"order": str, "unit": str}, ...],
                "arcs": [{"pred": str, "succ": str, "unit": str}, ...],
                "completion": {order: float, ...},
                "Cmax": float,
                "objective_type": "makespan" | "changeover",
                "warm_started": bool,
            }
        """
        # Validate
        errors = self.validate_params(params)
        if errors:
            return {
                "status": "VALIDATION_ERROR",
                "solver_id": self.solver_id,
                "errors": errors
            }

        # Model construction lives in build_model() (shared with the LP
        # relaxation and the Layer-2 feasibility check).
        m = self.build_model(params)

        # solve() still needs these few scalars — cheap to re-derive, no
        # model side effects: warm-start seeding + result extraction.
        I: List[str] = [str(x) for x in params["orders"]]
        J: List[str] = [str(x) for x in params["units"]]
        objective = params.get("objective", "makespan").lower().strip()

        # Apply warm-start if provided AND the model is MIP (always true here).
        warm_start_applied = False
        if warm_start and _model_has_integer_vars(m):
            self._apply_warm_start(m, I, J, warm_start)
            warm_start_applied = True

        # Solve with HiGHS
        solver = Highs()
        solver.config.time_limit = time_limit
        solver.config.load_solution = True
        solver.highs_options = {"mip_rel_gap": gap_target}
        # appsi-HiGHS raises (rather than returning a status) when it can't
        # load a solution because the model is infeasible. The feasibility
        # gate should catch this first, but treat a raw solve failure as a
        # clean INFEASIBLE result instead of letting the exception surface
        # as "Analysis failed: <pyomo internals>".
        try:
            res = solver.solve(m)
            status = str(res.termination_condition).upper().split(".")[-1]
        except Exception as e:
            msg = str(e)
            status = ("INFEASIBLE"
                      if "feasible solution was not found" in msg
                      or "infeasible" in msg.lower()
                      else "ERROR")
            return {
                "status": status,
                "solver_id": self.solver_id,
                "objective": None,
                "objective_value": None,
                "best_bound": None,
                "gap": None,
                "assignments": [],
                "arcs": [],
                "completion": {},
                "Cmax": None,
                "objective_type": objective,
                "warm_started": warm_start_applied,
                "message": "No feasible schedule exists for these constraints.",
            }

        # If HiGHS aborted without a feasible solution, return early.
        if status not in {"OPTIMAL", "FEASIBLE", "MAXTIMELIMIT"}:
            return {
                "status": status,
                "solver_id": self.solver_id,
                "objective": None,
                "objective_value": None,
                "best_bound": None,
                "gap": None,
                "assignments": [],
                "arcs": [],
                "completion": {},
                "Cmax": None,
                "objective_type": objective,
                "warm_started": warm_start_applied,
                "message": f"Solver terminated with status: {status}",
            }

        # Extract results
        assignments = []
        for i in I:
            for j in J:
                v = value(m.Y[i, j])
                if v is not None and v > 0.5:
                    assignments.append({"order": str(i), "unit": str(j)})

        arcs = []
        for i in I:
            for ip in I:
                if i == ip:
                    continue
                for j in J:
                    v = value(m.XX[i, ip, j])
                    if v is not None and v > 0.5:
                        arcs.append({"pred": str(i), "succ": str(ip), "unit": str(j)})

        # Continuous vars carry solver float noise (e.g. 7.999999999998).
        # Round to 6 dp so completion times / makespan read cleanly
        # everywhere downstream (chat table, xlsx, narration).
        def _clean(x: float) -> float:
            return round(float(x), 6)

        completion = {str(i): _clean(value(m.C[i])) for i in I}
        cmax = _clean(value(m.Cmax))
        obj_val = _clean(value(m.OBJ))
        best_bound = (
            float(res.best_objective_bound)
            if res.best_objective_bound is not None else None
        )
        gap = (
            abs(obj_val - best_bound) / abs(obj_val)
            if best_bound is not None and obj_val != 0 else 0.0
        )

        return {
            "status": status,
            "solver_id": self.solver_id,
            "objective": obj_val,
            "objective_value": obj_val,
            "best_bound": best_bound,
            "gap": gap,
            "assignments": assignments,
            "arcs": arcs,
            "completion": completion,
            "Cmax": cmax,
            "objective_type": objective,
            "warm_started": warm_start_applied,
        }

    def _apply_warm_start(self, m, I: List[str], J: List[str],
                          warm_start: Dict[str, Any]) -> None:
        """
        Seed the MILP variables from a heuristic primal solution.

        Sets every Y, XX, C, and Cmax that we have an answer for. Variables we
        don't seed default to 0 / unset, which HiGHS handles correctly. Missing
        keys are tolerated so partial warm-starts still work.
        """
        assignment = warm_start.get("assignment", {}) or {}
        sequence = warm_start.get("sequence", {}) or {}
        completion = warm_start.get("completion", {}) or {}
        cmax = warm_start.get("cmax", None)

        # Assignment vars
        for i in I:
            for j in J:
                m.Y[i, j].value = 1.0 if assignment.get(i) == j else 0.0

        # Immediate-precedence vars: default 0, then set 1 for consecutive pairs.
        for i in I:
            for ip in I:
                if i == ip:
                    continue
                for j in J:
                    m.XX[i, ip, j].value = 0.0
        for j, seq in sequence.items():
            for prev, nxt in zip(seq, seq[1:]):
                if (prev, nxt, j) in {(a, b, c) for (a, b, c) in m.XX}:
                    m.XX[prev, nxt, j].value = 1.0

        # Completion times + Cmax.
        for i in I:
            if i in completion:
                m.C[i].value = float(completion[i])
        if cmax is not None:
            m.Cmax.value = float(cmax)

    def solve_lp_relaxation(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Solve the LP relaxation of the IPM model. Useful as a lower bound on
        the makespan reported to the user alongside the heuristic answer.

        Returns:
            {"status": str, "bound": float | None}
        """
        try:
            m = self.build_model(params)
        except ValueError as e:
            return {"status": "VALIDATION_ERROR", "bound": None, "errors": [str(e)]}

        # Relax every binary/integer var to continuous, then solve as an LP.
        # For the makespan objective the relaxed optimum is a valid LOWER
        # bound on the MILP makespan (now that build_model is factored out
        # this is exact, not the old NOT_IMPLEMENTED placeholder).
        TransformationFactory("core.relax_integer_vars").apply_to(m)

        solver = SolverFactory("glpk")
        try:
            res = solver.solve(m, tee=False, load_solutions=False)
        except Exception as e:
            return {"status": "ERROR", "bound": None, "message": str(e)}

        tc = str(res.solver.termination_condition).lower()
        if tc not in ("optimal", "feasible"):
            return {"status": tc.upper(), "bound": None}

        m.solutions.load_from(res)
        return {"status": "OPTIMAL", "bound": round(float(value(m.OBJ)), 6)}

    # Helper methods for normalization
    def _normalize_matrix_ij(self, d: Dict[str, Any]) -> Dict[Tuple[str, str], float]:
        """Normalize (i,j) matrices: {(i,j): val} OR {i: {j: val}} -> flat {(i,j): float}"""
        if all(isinstance(k, tuple) and len(k) == 2 for k in d.keys()):
            return {(str(i), str(j)): float(v) for (i, j), v in d.items()}

        flat: Dict[Tuple[str, str], float] = {}
        for i, inner in d.items():
            if not isinstance(inner, dict):
                raise ValueError("Nested matrix must be {i: {j: val}}.")
            for j, v in inner.items():
                flat[(str(i), str(j))] = float(v)
        return flat

    def _normalize_tensor_iip_j(self, d: Dict[str, Any]) -> Dict[Tuple[str, str, str], float]:
        """Normalize (i,i',j) changeover tensor: {(i,i',j): val} OR {j: {i: {i': val}}} -> flat"""
        if all(isinstance(k, tuple) and len(k) == 3 for k in d.keys()):
            return {(str(i), str(ip), str(j)): float(v) for (i, ip, j), v in d.items()}

        flat: Dict[Tuple[str, str, str], float] = {}
        for j, level2 in d.items():
            if not isinstance(level2, dict):
                raise ValueError("Nested changeover must be {j: {i: {i': val}}}.")
            for i, level3 in level2.items():
                if not isinstance(level3, dict):
                    raise ValueError("Nested changeover must be {j: {i: {i': val}}}.")
                for ip, v in level3.items():
                    flat[(str(i), str(ip), str(j))] = float(v)
        return flat

    def _normalize_eligible(self, eligible: Dict[str, Any]) -> Dict[str, List[str]]:
        """Ensure eligible[i] is a deterministic, sorted list of units."""
        norm: Dict[str, List[str]] = {}
        for i, units in eligible.items():
            if not isinstance(units, (list, tuple, set)):
                raise ValueError("`eligible[i]` must be a list/tuple/set of unit IDs.")
            norm[str(i)] = sorted([str(u) for u in units])
        return norm
