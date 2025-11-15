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

from typing import Dict, List, Any, Tuple
from pyomo.environ import (
    ConcreteModel, Set, Param, Var, NonNegativeReals, Binary,
    Objective, Constraint, minimize, value, SolverFactory
)
from ..base import OptimizationSolver


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

    def solve(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build & solve the Immediate-Precedence Single-Stage MILP (IPM) with GLPK.

        Returns:
            {
                "status": "OPTIMAL" | "INFEASIBLE" | ...,
                "solver_id": "single_stage_ipm_scheduling",
                "objective": float,
                "assignments": [{"order": str, "unit": str}, ...],
                "arcs": [{"pred": str, "succ": str, "unit": str}, ...],
                "completion": {order: float, ...},
                "Cmax": float,
                "objective_type": "makespan" | "changeover"
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

        # Solve
        solver = SolverFactory("glpk")
        res = solver.solve(m, tee=False)
        status = str(res.solver.termination_condition).upper()

        # Extract results
        assignments = []
        for i in I:
            for j in J:
                if value(m.Y[i, j]) > 0.5:
                    assignments.append({"order": str(i), "unit": str(j)})

        arcs = []
        for i in I:
            for ip in I:
                if i == ip:
                    continue
                for j in J:
                    if value(m.XX[i, ip, j]) > 0.5:
                        arcs.append({"pred": str(i), "succ": str(ip), "unit": str(j)})

        completion = {str(i): float(value(m.C[i])) for i in I}
        cmax = float(value(m.Cmax))

        return {
            "status": status,
            "solver_id": self.solver_id,
            "objective": float(value(m.OBJ)),
            "assignments": assignments,
            "arcs": arcs,
            "completion": completion,
            "Cmax": cmax,
            "objective_type": objective
        }

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
