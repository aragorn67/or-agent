# Agenda — TODO

Forward plan for Optimization-AI. **Tasks only — no results, no analysis, no
"shipped" log.** Completed work lives in `git log` and `ANALYSIS.md`.

**Governing thesis (constrains every task below):** the LLM routes to
*published / validated* OR models and builds on them; it never invents the
formulation. Tripwire: any task that needs a model not in the solver
registry → stop and tell the user, do not synthesise.

---

## Priority list

1. Large-scale OR problems via xlsx
2. Third problem family (multi-period or multi-commodity flow)
3. Consolidated problem formulation in Overview PDF
4. Confidence / disagreement surfacing in UI
5. Web UI (clean front-end)
6. Persistent REST deployment
7. Cost / ROI framing in-app
8. Pick one vertical and go deep (strategic gate before #5/#6/#7)
9. Agentic frontier — multi-stage decomposition + autonomous infeasibility repair
10. VNS heuristic layer + whitelist constraint-template translation *(blocked on real-data benchmark)*

### Quick wins (anytime, low-risk)

- Flow / Gantt / network visualisation
- Fuzzy-match entity-name errors ("did you mean 'Seattle'?")
- 2-D parameter sensitivity (currently 1-D)
- Constraint-relaxation suggestion on infeasible ("relax demand by 10%?")
- Move keyword-analysis check ahead of `detect_intent` (bare what-if becomes fully LLM-free)
- Quiet the caught Pyomo "No eligible units" log emitted during a *successful* scheduling solve
- **Prompt for missing numeric parameters instead of failing extraction.** When a problem text describes the *schema* (warehouses/stores/cost matrix) but supplies no actual numbers, the extractor currently returns "Parameter validation failed." Better: the agent should detect "schema described, values missing" and ask the user to supply them (e.g. "I see 3 warehouses and 5 stores — what are the daily capacities, demands, and unit costs?"). Surfaced by smoke benchmark 2026-05-24 (fresh_food_distribution / steel_supply_construction / wafer_processing_single_stage all match this pattern).
- **Anchor scheduling's parallel / due-date / makespan features.** Hillier
  12.6-8 only exercises the single-machine changeover objective. The
  parallel-assignment, due-date, and makespan paths have no published-optimum
  anchor — either find a tiny published instance or enumeration-verify one.
  Surfaced 2026-06-06.
- **Smoke benchmark progress visibility — terminal-side.** `evals/smoke_real_data_benchmark.py` now prints a compact `[PROGRESS] N/55 …` line per problem (done 2026-05-24), but it goes to stdout, which is typically redirected to a log file (`> /tmp/smoke_full.log 2>&1`) → terminal stays blank during the 30–60 min run. Fix: write the progress line to `/dev/tty` (or stderr, if user prefers) in addition to stdout, so the terminal shows live status regardless of redirection. Detailed per-problem output stays on stdout (log only). Surfaced 2026-05-24.

---

## Details

### 1. Large-scale OR problems via xlsx

Industry-scale instances (hundreds of plants/customers, multi-period, real
cost matrices) fed in as `.xlsx` rather than NL prose — the xlsx fast-path
already exists and bypasses LLM extraction, so this exercises the *solver*
side at realistic scale instead of the parser. Pair each with a published
optimum or a reference solution so `objective_gap` stays meaningful. Good
sources: public utility / logistics RFPs, INFORMS case-study supplements,
academic datasets with sheets (e.g. UFLP / CVRP benchmark instances reshaped
into the `data/examples/` schema).

### 2. Third problem family

Multi-period or multi-commodity flow (or a third single-stage variant if
those are too heavy). Tests generalisation of the `FeasibilityPlugin`
contract and the registry/composer wiring. Gives a concrete "here's how I
extended the architecture" story; doubles as a stress test of the
domain-general fail-closed gate.

### 3. Consolidated problem formulation (Overview-PDF expansion)

Objective / constraints / assumptions / failure-cases for the transport
LP-MIP and the scheduling IPM in one place (code already has the numbered
constraints; §4 covers transport, §7 the gate).

### 4. Confidence / disagreement surfacing

When the voting classifier splits, show it in-UI. Turns ambiguity into a
feature, not a hidden failure. Cheap to ship — the voter already returns
per-voter labels; just expose the disagreement when it's non-unanimous.

### 5. Web UI (clean front-end)

Replace the terminal-first interaction with a real web front-end on top of
the existing job/poll pipeline UI. The pipeline streams stage events
already; this is presentation, not new backend.

### 6. Persistent REST deployment

Previous cloudflared quick tunnel was ephemeral. Persistent REST API +
stable URL → "try it here" works without a co-located laptop. Pair with #5
(Web UI) for full external access.

### 7. Cost / ROI framing in-app

Surface "this solve would take a consultant ~X hours / ~$Y" next to each
result, parameterized by problem size. Pure UX/marketing layer over numbers
the solver already produces.

### 8. Pick one vertical and go deep

Strategic, not engineering: choose a concrete buyer (logistics? supply
chain?) and make *one* end-to-end workflow excellent (data ingest →
formulation → solve → explanation → export) rather than many shallow.
Decision gate before #5/#6/#7 (Web UI / Persistent REST / Cost-ROI) turn
into generic effort.

### 9. Agentic frontier — on-thesis only

Both items stay inside the validated-model envelope.

- **A2 — Multi-stage decomposition (composer over the registry).** Decompose
  a compound request ("design my supply chain") into a sequence of *existing
  registered solvers* (location → transport → scheduling), wiring each
  stage's output into the next. The LLM chooses which/what order — never
  writes math. Tripwire: a stage needing an unregistered model → stop, don't
  synthesise.
- **A3 — Autonomous infeasibility repair (within a known formulation).**
  Replace the capped 3 deterministic retries with an LLM
  reason→edit→re-check→revise loop proposing edits to the *parameters /
  toggleable constraints of the already-selected model*. Tripwire: repair
  needing a structurally different model → escalate, don't reformulate.

### 10. VNS + constraint-template whitelist

**Both blocked on real-data benchmark results** — the benchmark will tell us
*which* constraint templates users actually want and *whether* the IPM proof
gap is the real bottleneck VNS would address. Building these speculatively
risks designing templates / neighborhoods for problems nobody has.

- **A. VNS (Variable Neighborhood Search) as the heuristic layer.**
  Mladenović & Hansen 1997 — published, validated metaheuristic, on-thesis.
  Replaces or augments VAM/LPT where the current heuristics under-perform:
  primarily fixed-charge transport (VAM is fixed-charge-blind) and
  scheduling IPM (LPT gives a feasible primal but doesn't search around it).
  Neighborhood ladders are problem-specific (transport: close open route /
  open closed route / swap pair; scheduling: job-swap-same-machine /
  move-between-machines / block-reverse / eligible-swap). Local search
  inside the ladder is deterministic descent; outer loop shakes + restarts.
  Two-call `heuristic_then_ask` UX stays — VNS gives the immediate feasible
  answer; HiGHS still proves the bound on the exact solve. Honest caveat:
  still a heuristic, no optimality proof. Effort: ~1 week per domain.

- **B. Whitelist-based constraint translation (NL → MILP template).**
  Each registered solver declares a small set of *toggleable constraint
  templates* (`forbid_arc`, `force_arc_open`, `max_open_routes`,
  `implication`, etc.). User says "Seattle cannot serve Topeka"; LLM picks
  the template + params from a fixed list; deterministic linearizer
  instantiates the constraint and rebuilds the model. On-thesis tripwire: if
  the LLM can't match a registered template, stop and tell the user — never
  synthesise a new constraint. Boolean-algebra encoding zoo (Williams ch. 9)
  for any binary-based pattern: indicator → linear, implication → ≤,
  exactly-one → =1, etc. Compound expressions (LLM emits a constraint tree,
  deterministic code linearizes) is the optional second layer — same
  posture, LLM picks structure, code controls math. Effort: ~2 days per
  solver + ~1 week for compound expressions.

The two stack: constraint translation tightens the model; VNS searches the
tightened model heuristically; HiGHS proves the bound. Together they're the
natural "remove the hard ceiling" pair without violating the thesis.

### 11. Longer-term architecture (aspirational)

- **Data layer beyond the xlsx fast path:** general CSV/Excel/long-vs-wide
  loaders + schema inference + LLM-assisted ambiguous-column mapping.
- **Model persistence / warm caching:** cache the compiled Pyomo model,
  update only changed params for interactive analysis (5–10× on sensitivity
  sweeps).
- **Decomposition for industrial scale:** Benders (two-stage), Dantzig-Wolfe
  (block-diagonal), column generation (VRP / cutting stock). Requires the
  solver-strategy selector to route by problem size/structure first.
- **Fixed-charge-aware construction heuristic:** the actual lever the
  warm-start work identified (VAM is fixed-charge-blind). Also: tighter
  scheduling formulation (positional/time-indexed) if the IPM proof gap
  becomes the bottleneck.

---

## Research framing (CV / publication angle)

LLM-assisted OR (NL → optimal solution with the OR concepts surfaced in
plain English), adaptive heuristic/decomposition selection, hybrid
heuristic-exact solving — all consistent with the governing thesis (the LLM
orchestrates validated solvers; it does not do the math).
