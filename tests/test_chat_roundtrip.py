"""
Chat round-trip stress harness (backlog #2).

A deterministic golden-envelope net over the *exact endpoints the chat UI
uses* — `POST /jobs` → poll `GET /jobs/{id}` → `POST /chat/continue` —
across every branch the UI switches on. The LLM is stubbed (a contract-
correct `ScriptedLLM`); the real solver, the 3-layer feasibility gate,
and the `_with_options` chip chokepoint all run for real.

Why envelope, not prose: chat.html branches on a fixed response contract
(`success`, `status`, `solution`, `next_options`, `reasons`/
`suggestions`, `job_pending`, `response`). That contract is exactly what
silently broke for scheduling before the parity work (transport-only
degradation). Pinning it here makes any future "works for transport,
silently wrong for scheduling" regression fail loudly and fast — and
unlike the live-LLM repository tests this is stable (no model in loop).
"""

import time

import pytest
from fastapi.testclient import TestClient


# --- canonical inputs (the ScriptedLLM routes on these) -------------------

T_OK = "transport-ok: 2 plants to 2 markets, plenty of supply"
T_INFEAS = "transport-infeasible: supply strictly less than demand"
S_OK = "scheduling-ok: 2 orders one unit, loose deadlines"
S_INFEAS = "scheduling-infeasible: an order due before its work is done"
MALFORMED = "asdf qwerty zzz not an optimization problem at all"

_TRANSPORT_OK = {
    "plants": ["P1", "P2"], "markets": ["M1", "M2"],
    "capacity": {"P1": 100, "P2": 100},
    "demand": {"M1": 60, "M2": 60},
    "cost": {"P1": {"M1": 2, "M2": 3}, "P2": {"M1": 4, "M2": 1}},
}
_TRANSPORT_INFEAS = {  # total supply 70 < total demand 80 -> Layer 1
    "plants": ["P1", "P2"], "markets": ["M1", "M2", "M3"],
    "capacity": {"P1": 40, "P2": 30},
    "demand": {"M1": 35, "M2": 25, "M3": 20},
    "cost": {"P1": {"M1": 1, "M2": 1, "M3": 1},
             "P2": {"M1": 1, "M2": 1, "M3": 1}},
}
_SCHED_OK = {
    "orders": ["A", "B"], "units": ["U1"],
    "processing_time": {"A": {"U1": 2.0}, "B": {"U1": 3.0}},
    "due_date": {"A": 10.0, "B": 10.0},
    "eligible": {"A": ["U1"], "B": ["U1"]},
}
_SCHED_INFEAS = {  # C needs 5 h on its only unit, due hour 4 -> Layer 1
    "orders": ["A", "B", "C"], "units": ["U1"],
    "processing_time": {"A": {"U1": 2.0}, "B": {"U1": 2.0}, "C": {"U1": 5.0}},
    "due_date": {"A": 10.0, "B": 10.0, "C": 4.0},
    "eligible": {"A": ["U1"], "B": ["U1"], "C": ["U1"]},
}


class ScriptedLLM:
    """Contract-correct stand-in for EnhancedLLMClient — routes on the
    canonical phrases above. Shapes mirror the real client exactly so the
    harness exercises the system, not the stub."""

    def classify_problem(self, description, problem_types=None):
        d = description
        if T_OK in d or T_INFEAS in d:
            pt, sid = "TRANSPORTATION", "transport_basic_bipartite"
        elif S_OK in d or S_INFEAS in d:
            pt, sid = "SINGLE_STAGE_SCHEDULING", "single_stage_ipm_scheduling"
        else:  # malformed / unrecognised
            return {"type": "UNKNOWN", "problem_type": "unknown",
                    "solver_id": "none", "confidence": 0.0,
                    "signals": {}, "evidence": [], "reasoning": "",
                    "objective": {}, "votes": []}
        return {"type": pt, "problem_type": pt.lower(), "solver_id": sid,
                "confidence": 0.99, "signals": {}, "evidence": [],
                "reasoning": "scripted", "objective": {}, "votes": []}

    def extract_parameters(self, description, problem_type, example):
        d = description
        if T_OK in d:
            return dict(_TRANSPORT_OK)
        if T_INFEAS in d:
            return dict(_TRANSPORT_INFEAS)
        if S_OK in d:
            return dict(_SCHED_OK)
        if S_INFEAS in d:
            return dict(_SCHED_INFEAS)
        return {"error": "scripted: nothing to extract"}

    def explain_solution(self, solution, problem_type, original_description=""):
        return {"summary": "scripted summary", "explanation": "scripted",
                "units_info": {}, "grounding_check": "deterministic_fallback"}

    def parse_infeasibility_fix(self, user_message, current_params, ctx):
        return {"is_complete_redescription": False, "modifications": [],
                "applied_params": dict(current_params)}


def _scripted_intent(message, conversation_context=None):
    m = message.lower()
    if any(g in m for g in ("hello", "hi ", "hey")):
        return {"intent": "smalltalk", "confidence": 1.0}
    if m.strip() == "help" or "what can you do" in m:
        return {"intent": "help", "confidence": 1.0}
    return {"intent": "optimization", "confidence": 1.0}


@pytest.fixture
def client(monkeypatch):
    import api
    from agent.core import OptimizationAgent

    agent = OptimizationAgent(ScriptedLLM())
    # The first-message path calls _check_deterministic_intent (keyword, no
    # LLM — catches "hello") then _llm_intent_detection only if that is
    # inconclusive. Script the latter (the real LLM seam) so ambiguous
    # cases like bare "help" resolve deterministically.
    monkeypatch.setattr(agent.intent_router, "_llm_intent_detection",
                        _scripted_intent)
    monkeypatch.setattr(agent.intent_router, "detect_intent", _scripted_intent)
    monkeypatch.setattr(api, "agent", agent)
    return TestClient(api.app)


# In the two-call `heuristic_then_ask` protocol the first card shows the
# *heuristic* answer; the proven-optimal one comes after "optimize".
_SOLVED_STATUSES = {"OPTIMAL", "FEASIBLE", "HEURISTIC_FEASIBLE"}


def _solve(client, description):
    """Drive the chat UI's first-message path: POST /jobs then poll."""
    run_id = client.post(
        "/jobs", json={"description": description, "mode": "heuristic_then_ask"}
    ).json()["run_id"]
    deadline = time.time() + 30
    while time.time() < deadline:
        body = client.get(f"/jobs/{run_id}").json()
        if body["state"] in ("done", "error"):
            return body.get("result") or {"success": False, "error": body.get("error")}
        time.sleep(0.05)
    raise AssertionError(f"job {run_id} did not finish in time")


# ---- envelope contract, per chat-UI branch -------------------------------

def test_smalltalk_returns_conversational_no_solution(client):
    d = _solve(client, "hello there")
    assert d.get("success") is not False
    assert not d.get("solution")
    assert (d.get("response") or d.get("summary"))          # bubble text
    assert "next_options" in d                                # chips chokepoint


def test_help_returns_guidance_no_solution(client):
    d = _solve(client, "help")
    assert not d.get("solution")
    assert (d.get("response") or d.get("summary"))
    assert "next_options" in d


def test_transport_solve_envelope(client):
    d = _solve(client, T_OK)
    assert d["success"] is True
    assert d["problem_type"].upper().startswith("TRANSPORT")
    assert d["solution"]["status"] in _SOLVED_STATUSES
    assert d["solution"].get("objective_value") is not None
    assert "next_options" in d


def test_scheduling_solve_envelope(client):
    d = _solve(client, S_OK)
    assert d["success"] is True
    assert "SCHEDUL" in d["problem_type"].upper()
    assert d["solution"]["status"] in _SOLVED_STATUSES
    assert (d["solution"].get("Cmax") is not None
            or d["solution"].get("objective_value") is not None)
    assert "next_options" in d


def test_transport_infeasible_envelope(client):
    d = _solve(client, T_INFEAS)
    assert d.get("success") is False
    assert d.get("status") == "infeasible"
    blob = " ".join(d.get("reasons", []) + d.get("suggestions", [])).lower()
    assert "supply" in blob or "demand" in blob          # transport reason
    assert "next_options" in d


def test_scheduling_infeasible_uses_scheduling_reasons(client):
    """The transport-only-degradation guard: a scheduling infeasibility
    must surface a scheduling explanation, never transport's
    'increase supply' advice."""
    d = _solve(client, S_INFEAS)
    assert d.get("success") is False
    assert d.get("status") == "infeasible"
    blob = " ".join(d.get("reasons", []) + d.get("suggestions", [])).lower()
    assert any(k in blob for k in ("deadline", "due", "eligible", "processing"))
    assert "supply" not in blob and "demand" not in blob
    assert "next_options" in d


def test_malformed_input_fails_gracefully_not_500(client):
    d = _solve(client, MALFORMED)
    # Never an unhandled crash: a clean, conversational refusal.
    assert d.get("success") is False
    assert (d.get("error") or d.get("response"))
    assert "next_options" in d


def test_pending_job_freetext_does_not_dead_end(client):
    """A non-action free-text message on a pending job must be answered
    (job_pending) — the #8 dead-end class — and still carry chips."""
    run_id = client.post(
        "/jobs", json={"description": T_OK, "mode": "heuristic_then_ask"}
    ).json()["run_id"]
    deadline = time.time() + 30
    while time.time() < deadline:
        body = client.get(f"/jobs/{run_id}").json()
        if body["state"] == "done":
            break
        time.sleep(0.05)
    job_id = body["result"].get("job_id")
    assert job_id, "feasible solve should yield a continuation job_id"

    r = client.post("/chat/continue",
                     json={"job_id": job_id, "message": "what does this mean?"})
    d = r.json()
    assert r.status_code == 200
    assert d.get("job_pending") is True
    assert (d.get("response") or d.get("summary") or d.get("error"))
    assert "next_options" in d


def test_pending_job_optimize_action_consumes_job(client):
    run_id = client.post(
        "/jobs", json={"description": T_OK, "mode": "heuristic_then_ask"}
    ).json()["run_id"]
    deadline = time.time() + 30
    while time.time() < deadline:
        body = client.get(f"/jobs/{run_id}").json()
        if body["state"] == "done":
            break
        time.sleep(0.05)
    job_id = body["result"]["job_id"]

    d = client.post("/chat/continue",
                     json={"job_id": job_id, "message": "optimize it"}).json()
    assert d.get("parsed_action") == "optimize"
    assert d.get("success") is True
    assert d["solution"]["status"] in ("OPTIMAL", "FEASIBLE")
    assert "next_options" in d


# ===========================================================================
# Routing matrix — the *deterministic* layers, many phrasings.
#
# Both routers below are keyword-only (no LLM): IntentRouter
# ._check_deterministic_intent and detect_analysis_type_keyword_based.
# This is a living catalogue of what the cheap layer covers vs. what it
# punts to the LLM. "ESCALATE" rows are not failures — they are the
# evidence for whether the model layer needs reinforcing: a phrasing that
# falls through here is one the big model has to handle. If a future
# change moves a row in or out of ESCALATE, this test makes it visible.
# ===========================================================================

ESCALATE = "ESCALATE"  # deterministic layer punts -> LLM decides


def _router():
    from llm.intent_router import IntentRouter
    return IntentRouter(ScriptedLLM())  # ._check_deterministic_intent ignores llm


_CTX = {"last_solution": {"problem_type": "TRANSPORTATION"}}

# (message, context, expected intent or ESCALATE)
INTENT_MATRIX = [
    # --- clear: the keyword layer SHOULD nail these (hard contract) ---
    ("hello", None, "smalltalk"),
    ("hi there", None, "smalltalk"),
    ("good morning", None, "smalltalk"),
    ("who are you?", None, "smalltalk"),
    ("what can you do?", None, "help"),
    ("can you help me", None, "help"),
    ("what types of problems do you handle", None, "help"),
    ("minimize shipping cost from 2 plants to 3 markets given capacity and demand",
     None, "optimization"),
    ("why?", _CTX, "follow_up"),
    ("how many plants?", _CTX, "follow_up"),
    ("tell me more", _CTX, "follow_up"),
    # broadened follow-up patterns (context-gated) — these resolved to
    # ESCALATE before the routing fix, now deterministic:
    ("suppose P2 drops to 50", _CTX, "follow_up"),
    ("rerun with that change", _CTX, "follow_up"),
    # --- legitimately ambiguous: documented to need the LLM ---
    # bare imperative modification, no question word / "what if" / context kw
    ("suppose Boston drops to 50", None, ESCALATE),
    ("drop the second plant by a fifth", None, ESCALATE),
    ("bump freight up and rerun", None, ESCALATE),
    # greeting embedded in a real problem: the smalltalk patterns are
    # correctly gated off by the optimization words, so this resolves to
    # optimization (robust — NOT a routing weakness, kept as a guard).
    ("hi, I need to minimize cost shipping from A to B", None, "optimization"),
]

# (query, expected analysis type or ESCALATE) — detect_analysis_type keyword
ANALYSIS_MATRIX = [
    ("sensitivity on Plant North capacity", "sensitivity"),
    ("what is the impact of freight on cost", "sensitivity"),
    ("what if demand increases by 20", "what_if"),
    ("suppose demand rises 10%", "what_if"),
    ("what happens if P2 capacity is 50", "what_if"),
    ("resolve with capacity = 100", "resolve"),
    ("reoptimize after the change", "resolve"),
    ("pareto front of cost vs distance", "pareto"),
    ("show the cost and distance tradeoff", "pareto"),
    # closed by the routing fix (safe, phrase-based — no first-message
    # misroute risk): 'sensitiv' now covers "sensitive"; "what changes
    # if" is an explicit what_if phrasing.
    ("how sensitive is the plan to freight", "sensitivity"),
    ("what changes if I add a plant", "what_if"),
    # --- DELIBERATELY left to the LLM (not a gap to close with keywords).
    #     Bare modification imperatives are genuinely ambiguous as a
    #     *first* message; keyword-forcing them would misroute partial
    #     new-problem inputs into the no-baseline guide
    #     (_analysis_needs_baseline, core.py). Correct to defer. ---
    ("drop P2 capacity by 20%", ESCALATE),
    ("bump Boston up to 1500", ESCALATE),
]


@pytest.mark.parametrize("msg,ctx,expected", INTENT_MATRIX,
                         ids=[m for m, _, _ in INTENT_MATRIX])
def test_intent_routing_matrix(msg, ctx, expected):
    res = _router()._check_deterministic_intent(msg, ctx)
    got = ESCALATE if res is None else res.get("intent")
    assert got == expected, (
        f"{msg!r} -> {got!r}, catalogued as {expected!r}. If this is an "
        f"intended routing change, update INTENT_MATRIX (it is the contract)."
    )


@pytest.mark.parametrize("query,expected", ANALYSIS_MATRIX,
                         ids=[q for q, _ in ANALYSIS_MATRIX])
def test_analysis_type_routing_matrix(query, expected):
    from analysis.router import detect_analysis_type_keyword_based
    res = detect_analysis_type_keyword_based(query)
    got = ESCALATE if res == "unknown" else res
    assert got == expected, (
        f"{query!r} -> {got!r}, catalogued as {expected!r}. Update "
        f"ANALYSIS_MATRIX if this routing change is intended."
    )


def test_keyword_layer_coverage_is_tracked():
    """Decision metric for the 'add another model?' question: how much of
    a realistic phrasing set the *free* keyword layer resolves vs. punts
    to the LLM. Not a pass/fail threshold — a tripwire so the ratio can't
    silently drift without us noticing."""
    intent_escalate = sum(1 for _, _, e in INTENT_MATRIX if e == ESCALATE)
    analysis_escalate = sum(1 for _, e in ANALYSIS_MATRIX if e == ESCALATE)
    # Post routing-fix catalogue: the free keyword layer now resolves all
    # but the genuinely-ambiguous cases. The 3 remaining intent escalations
    # are first-message-no-context (correctly deferred); the 2 analysis
    # escalations are bare modification imperatives DELIBERATELY left to
    # the LLM (keyword-forcing them risks first-message misroute). That
    # this floor is small + principled — not "we need a bigger model" —
    # is the answer to the model question, kept as a drift tripwire.
    assert intent_escalate == 3
    assert analysis_escalate == 2
