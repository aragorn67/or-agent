# Optimization AI — Plan & Backlog

LLM-driven OR agent: NL → classify → extract → 3-layer feasibility → solve
→ explain. Domains live: bipartite transportation, single-stage scheduling.
This file = the **forward plan**. Done work is one-lined under "Shipped";
the *why* of each result lives in `ANALYSIS.md`.

---

## Governing design thesis (read before adding capability)

The LLM **routes to published / validated OR models and builds on them; it
never invents the formulation.** Open-ended LLM model-construction is
*rejected as off-thesis*, not deferred. **Off-thesis tripwire:** anything
that needs a model not in the solver registry → stop and tell the user, do
not synthesise. (memory: `project_design_thesis`)

---

## Shipped (milestones — detail in ANALYSIS.md / memory)

- **Round-trip eval framework** (the answer to the eval-wall that paused the
  project): generate params with known optimum → LLM verbalizes → agent
  recovers → compare. Phase 1 (transport) + Phase 2 (scheduling) done —
  3/3 pass, recall 1.0, objective gap 0.0; caught 4 real bugs.
- **Heuristic + warm-start path**: GLPK→HiGHS swap, VAM/LPT heuristics,
  two-call `heuristic_then_ask` protocol. Warm-start is an **honest
  negative** (null on pure-LP and IPM; the "6.6×" was non-representative) —
  the value is the interactive UX + LP-bound visibility, not solver speedup.
- **Fixed-charge transport MIP** + NL `fixed_cost` extraction.
- **Public deployment** via cloudflared quick tunnel — done, then
  de-prioritized by the user (focus moved to modelling/heuristics).
- **Demo roadmap Phases 0–3**: live progress (job+poll pipeline UI),
  conversational chips + graceful NL fallback, what-if/sensitivity/resolve/
  pareto follow-ups, first-message analysis guard, xlsx structured-input
  fast path (~80–95 s → sub-second), per-stage latency profiling.
- **Model sweep** → default flipped **qwen3:14b → qwen3:8b** (==accuracy
  n=3 both domains, ~2× faster). qwen2.5:7b rejected (transport
  regression); groq/mistral untested (config/format bugs, not verdicts).
- **Scheduling interaction parity**: modification parse/apply, Layer-1
  scheduling feasibility checker, fail-soft solver, hours-not-€ output,
  auto-rendered schedule table; killed a false-feasible bug class. Plus the
  multi-line infeasible-render fix (old backlog #3).
- **Feasibility stack fail-closed & domain-general**:
  `FeasibilityPlugin` bundles checker+suggester per domain (half-wiring is
  a construction error); Layer-2 `UNKNOWN` no longer asserts FEASIBLE.
- **Genuine Layer-2 for scheduling**: `build_model` factored out (LP
  relaxation un-stubbed too), domain-aware converter → Layer 2 conclusive
  for both domains, automatic for any solver exposing `build_model`.
  Curated machine-checkable infeasible corpus (both domains × Layers
  0/1/2); README *Baseline vs. system* + *Failure analysis*; Overview §7
  rewritten + PDF regenerated. (ANALYSIS 2026-05-19.)

---

## Open backlog (priority order)

### 1. Consolidated problem formulation (interview-grade item D) 🟠

Objective / constraints / assumptions / failure-cases for the transport
LP-MIP and the scheduling IPM in one place — an Overview-PDF expansion
(code already has the numbered constraints; §4 covers transport, §7 the
gate). Items A (curated infeasible corpus) and B (Baseline-vs-system +
Failure-analysis surfacing) of this checklist are DONE (see Shipped).

### 2. UI-chat stress harness 🟠

Scripted `TestClient` sequence + golden outputs driving the chat
round-trip across *every* branch — smalltalk, help, classify
(transport/scheduling), what-if (delta + ALL), infeasible, follow-up,
malformed. The chat path only has piecemeal coverage; this is the
regression net for exactly the transport-only-silent-degradation class the
scheduling-parity work just fixed.

### 3. Agentic frontier — on-thesis only 🟠

Both are real "remove the hard ceiling" items; both stay inside the
validated-model envelope.
- **A2 — Multi-stage decomposition (composer over the registry).**
  Decompose a compound request ("design my supply chain") into a sequence
  of *existing registered solvers* (location → transport → scheduling),
  wiring each stage's output into the next. The LLM chooses which/what
  order — never writes math. Tripwire: a stage needing an unregistered
  model → stop, don't synthesise.
- **A3 — Autonomous infeasibility repair (within a known formulation).**
  Replace the capped 3 deterministic retries with an LLM
  reason→edit→re-check→revise loop proposing edits to the *parameters /
  toggleable constraints of the already-selected model*. Tripwire: repair
  needing a structurally different model → escalate, don't reformulate.

### 4. Eval hardening

- **Phase 3 — metamorphic transforms:** double all costs → objective
  doubles; permute plant order → objective unchanged; add unused plant →
  unchanged. Invariant assertions, no new ground truth (~0.5 day).
- **Phase 4 — paraphrase holdout:** LLM-paraphrase the 27-problem seed set
  10×, run the pipeline, treat the original 27 as a human-curated holdout
  to measure the synthetic-vs-real gap.
- **C. Named reliability metrics:** structured-output-validity rate (LLM
  JSON parse success), constraint-violation rate, and robustness-to-noise
  (activate the verbalizer's existing unused `'noisy'` style knob). High
  signal for Applied-Scientist framing; the harness already aggregates
  per-stage data, these are mostly new aggregations.

### 5. Longer-term architecture (aspirational, unblocked but not urgent)

- **Data layer beyond the xlsx fast path:** general CSV/Excel/long-vs-wide
  loaders + schema inference + LLM-assisted ambiguous-column mapping.
- **Model persistence / warm caching:** cache the compiled Pyomo model,
  update only changed params for interactive analysis (5–10× on
  sensitivity sweeps).
- **Decomposition for industrial scale:** Benders (two-stage), Dantzig-Wolfe
  (block-diagonal), column generation (VRP / cutting stock). Requires the
  solver-strategy selector to route by problem size/structure first.
- **Fixed-charge-aware construction heuristic:** the actual lever the
  warm-start work identified (VAM is fixed-charge-blind). Also: tighter
  scheduling formulation (positional/time-indexed) if the IPM proof gap
  becomes the bottleneck (the scheduling LP relaxation is now implemented).

---

## Quick wins (anytime, low-risk)

Solution export to CSV/JSON; flow / Gantt / network visualisation;
fuzzy-match entity-name errors ("did you mean 'Seattle'?"); 2-D parameter
sensitivity (currently 1-D); constraint-relaxation suggestion on infeasible
("relax demand by 10%?"); micro-opt: move the keyword analysis check ahead
of `detect_intent` so the bare-what-if first-message path is fully LLM-free.

---

## Research framing (CV / publication angle)

LLM-assisted OR (NL → optimal solution with the OR concepts surfaced in
plain English), adaptive heuristic/decomposition selection, hybrid
heuristic-exact solving — all consistent with the governing thesis (the LLM
orchestrates validated solvers; it does not do the math).
