# ipm_model.py
# Immediate-Precedence Single-Stage MILP (IPM) — Section 3.1
# - GLPK-based solver workflow
# - Efficient big-M choices
# - Deterministic eligible sets
# - No formula-card constraint (3.1.8)
# - Fix: Base completion lower bound to avoid C[i]=0 for first jobs
#
# API: result = solve_ipm(params)
# params schema at _validate_ipm_params()

from typing import Dict, List, Any, Tuple
from pyomo.environ import (
    ConcreteModel, Set, Param, Var, NonNegativeReals, Binary,
    Objective, Constraint, minimize, value, SolverFactory
)

# -----------------------------
# Validation & normalization
# -----------------------------
def _validate_ipm_params(p: Dict[str, Any]) -> None:
    """
    Required keys:
      - orders: List[str]
      - units: List[str]
      - eligible: Dict[order -> List[unit]]
      - processing_time: {(i,j): val} or {i: {j: val}}
      - due_date: Dict[i -> val]
    Optional:
      - changeover: {(i,i',j): val} or {j: {i: {i': val}}}
      - window: Dict[i -> 0/1]
      - lower: Dict[i -> lower_start_time]
      - objective: "makespan" or "changeover" (default "makespan")
    """
    req = ["orders", "units", "eligible", "processing_time", "due_date"]
    missing = [k for k in req if k not in p]
    if missing:
        raise ValueError(f"Missing required keys: {missing}")

    if not isinstance(p["orders"], list) or not isinstance(p["units"], list):
        raise ValueError("`orders` and `units` must be lists of strings.")

    if not isinstance(p["eligible"], dict):
        raise ValueError("`eligible` must be a dict mapping order -> list of eligible units.")

    if not isinstance(p["processing_time"], dict):
        raise ValueError("`processing_time` must be a dict ((i,j)->val) or nested {i:{j:val}}.")

    if not isinstance(p["due_date"], dict):
        raise ValueError("`due_date` must be a dict {i: DDATE_i}.")

    if "changeover" in p and not isinstance(p["changeover"], dict):
        raise ValueError("`changeover` must be a dict ((i,i',j)->val) or nested {j:{i:{i':val}}}.")

    if "window" in p and not isinstance(p["window"], dict):
        raise ValueError("`window` must be a dict {i:0/1}.")

    if "lower" in p and not isinstance(p["lower"], dict):
        raise ValueError("`lower` must be a dict {i: lower_bound}.")


def _normalize_matrix_ij(d: Dict[str, Any]) -> Dict[Tuple[str, str], float]:
    """
    Normalize (i,j) matrices:
      - accepts {(i,j): val}  OR  {i: {j: val}}
      - returns flat {(i,j): float(val)}
    """
    # flat form?
    if all(isinstance(k, tuple) and len(k) == 2 for k in d.keys()):
        return {(str(i), str(j)): float(v) for (i, j), v in d.items()}

    # nested form {i:{j:val}}
    flat: Dict[Tuple[str, str], float] = {}
    for i, inner in d.items():
        if not isinstance(inner, dict):
            raise ValueError("Nested matrix must be {i: {j: val}}.")
        for j, v in inner.items():
            flat[(str(i), str(j))] = float(v)
    return flat


def _normalize_tensor_iip_j(d: Dict[str, Any]) -> Dict[Tuple[str, str, str], float]:
    """
    Normalize (i,i',j) changeover tensor:
      - accepts {(i,i',j): val} OR {j: {i: {i': val}}}
      - returns flat {(i,i',j): float(val)}
    """
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


def _normalize_eligible(eligible: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Ensure eligible[i] is a deterministic, sorted list of units.
    """
    norm: Dict[str, List[str]] = {}
    for i, units in eligible.items():
        if not isinstance(units, (list, tuple, set)):
            raise ValueError("`eligible[i]` must be a list/tuple/set of unit IDs.")
        norm[str(i)] = sorted([str(u) for u in units])
    return norm


# --------------------------------
# Build & solve the IPM Scheduling
# --------------------------------
def solve_ipm(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build & solve the 3.1 Immediate-Precedence Single-Stage MILP (IPM) with GLPK.
    Returns JSON-serializable dict (status, objective, assignments, arcs, completion times, Cmax).
    """
    _validate_ipm_params(params)

    I: List[str] = [str(x) for x in params["orders"]]
    J: List[str] = [str(x) for x in params["units"]]
    J_i: Dict[str, List[str]] = _normalize_eligible(params["eligible"])

    T = _normalize_matrix_ij(params["processing_time"])
    changeover = _normalize_tensor_iip_j(params.get("changeover", {}))
    DDATE: Dict[str, float] = {str(k): float(v) for k, v in params["due_date"].items()}
    window: Dict[str, float] = {str(k): float(v) for k, v in params.get("window", {}).items()}
    lower: Dict[str, float] = {str(k): float(v) for k, v in params.get("lower", {}).items()}
    objective = params.get("objective", "makespan").lower().strip()

    # --- Python set με orders που έχουν strict time window ---
    W = {i for i, w in window.items() if w >= 0.5}

    # ---- Pyomo model ----
    m = ConcreteModel()

    # Sets
    m.I = Set(initialize=I)
    m.J = Set(initialize=J)

    def _J_i_init(m, i):
        return J_i.get(i, [])
    m.J_i = Set(m.I, initialize=_J_i_init, ordered=True)  # ordered = deterministic

    # Parameters
    def _T_init(m, i, j):
        return float(T[(i, j)])
    m.T = Param(m.I, m.J, initialize=_T_init, within=NonNegativeReals)

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

    # Tmin[i] = min_j T[i,j] for j ∈ J_i[i]
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

    # (3.1.5) time-window lower bound only for i ∈ W:
    # C[i] ≥ Lower[i] + Σ_j T[i,j]Y[i,j]
    def _timewindow_rule(m, i):
        if i not in W:
            return Constraint.Skip
        return m.C[i] >= m.Lower[i] + sum(m.T[i, j] * m.Y[i, j] for j in m.J_i[i])
    m.TimeWindow = Constraint(m.I, rule=_timewindow_rule)

    # Base completion lower bound for first jobs
    # C[i] ≥ Σ_j T[i,j]Y[i,j]
    def _base_completion_lb(m, i):
        return m.C[i] >= sum(m.T[i, j] * m.Y[i, j] for j in m.J_i[i])
    m.BaseCompletionLB = Constraint(m.I, rule=_base_completion_lb)

    # (3.1.6) lower timing with efficient M1 = DDATE[i]
    # C[ip] ≥ C[i] + T[ip,j] + changeover[i,ip,j] − M1*(1−XX[i,ip,j])
    def _timing_lower_rule(m, i, ip, j):
        if i == ip:
            return Constraint.Skip
        M1 = m.DDATE[i]
        return m.C[ip] >= m.C[i] + m.T[ip, j] + m.changeover[i, ip, j] - M1 * (1 - m.XX[i, ip, j])
    m.TimingLower = Constraint(((i, ip, j) for i in I for ip in I if i != ip for j in J),
                               rule=_timing_lower_rule)

    # (3.1.7) upper timing (exclude when predecessor i has window=1)
    # C[ip] ≤ C[i] + T[ip,j] + changeover[i,ip,j] + M2*(1−XX[i,ip,j]),
    # where M2 = DDATE[ip] − Tmin[ip]
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
    else:  # "makespan" default (3.1.10)
        m.OBJ = Objective(expr=m.Cmax, sense=minimize)

    # ---- Solve ----
    solver = SolverFactory("glpk")
    res = solver.solve(m, tee=False)
    status = str(res.solver.termination_condition).upper()

    # ---- Extract results ----
    assignments = []
    for i in I:
        for j in J:
            if value(m.Y[i, j]) > 0.5:
                assignments.append({"order": i, "unit": j})

    arcs = []
    for i in I:
        for ip in I:
            if i == ip:
                continue
            for j in J:
                if value(m.XX[i, ip, j]) > 0.5:
                    arcs.append({"pred": i, "succ": ip, "unit": j})

    completion = {i: float(value(m.C[i])) for i in I}
    cmax = float(value(m.Cmax))

    return {
        "status": status,                   # e.g., "OPTIMAL"
        "objective": float(value(m.OBJ)),   # makespan or changeover total
        "assignments": assignments,         # [{order, unit}]
        "arcs": arcs,                       # [{pred, succ, unit}]
        "completion": completion,           # {order: C_i}
        "Cmax": cmax
    }