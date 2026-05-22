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
- **Chat round-trip stress harness** (`tests/test_chat_roundtrip.py`):
  deterministic golden-envelope net over the real chat endpoints
  (`/jobs`→poll→`/chat/continue`), LLM stubbed, 9 branches incl. the
  transport-only-degradation guard. Plus a **routing matrix** (29
  phrasings over the two keyword routers) that catalogued LLM-escalation
  rate → decided *not* to add a second model (misses are keyword-coverage
  gaps, not reasoning gaps). (ANALYSIS 2026-05-19.)
- **Eval hardening block — DONE 2026-05-21.** Phase 3 metamorphic
  invariants (50 tests), Phase 4 paraphrase holdout (10-style runner +
  agreement metric), Metric C named reliability rates (4 rates + `noisy`
  verbalizer style), and adversarial extraction characterisation (8
  transforms × should_solve/graceful_degrade × 4-way outcome classifier).
  Live validation surfaced a real bug (transport coverage-gate
  asymmetry — capacity/demand weren't number-checked, fixed; cache
  bumped v5→v6) and a structural finding (single-stage IPM SeqCount
  can't represent an unused unit; test uses the dual). Adversarial run
  on 12 transport cases: zero hallucinations, zero hard failures;
  silent-contradiction-handling flagged as a future feature. Suite
  248→329. (ANALYSIS 2026-05-21.)

---

## Open backlog (priority order)

### 1. Real-data benchmark 🟠 ◀ active

20–30 hand-curated real OR problems (transport + scheduling), run through
the pipeline, report parameter-recall / objective-gap / failure-modes
alongside the synthetic round-trip numbers. Directly answers the "n=10
is small / synthetic-only" critique. Biggest credibility win after the
eval-hardening block.

**Concrete plan (decided 2026-05-21):**

- **Where they live:** add to the existing `tests/or_problem_repository.py`
  (41 problems already there with full schema + helpers + test integration).
  Don't create a parallel structure.
- **Mix:** ~5 textbook (Winston / Hillier-Lieberman / Wolsey — published
  optima, easy to score) + ~5 case-study (INFORMS Edelman abstracts /
  OR-Society writeups / public RFPs — high realism, often no
  machine-checkable optimum, score on what's available). Defer
  OR-Library/NETLIB (numeric-only, no real prose — defeats the point).
- **Per-problem extras the runner needs** (on top of the existing
  fields — text, expected_type, expected_schema, feasible, solvable):
  - `metadata.tags`: include `"real_data_benchmark"` so the runner can
    filter on this without touching the existing 41 problems.
  - `metadata.source`: citation string ("Winston OR, Ch.7, Example 1").
  - `ground_truth_params`: the numeric instance we expect the extractor
    to recover (for `param_recall`). Optional — leave out if a case
    study doesn't have machine-checkable numerics; runner reports recall
    N/A for that problem.
  - `published_optimum`: float — what we score `objective_gap` against.
    Optional for the same reason.
- **Workflow:** user sources + pastes problems into the repo file.
  Once 3–5 are in, build a runner under `evals/` that loads
  tag=`real_data_benchmark`, pipes each through the agent, and produces
  the same reliability metrics + bucket histogram + gap stats the
  synthetic round-trip already emits — so the two reports are
  side-by-side comparable.
- **Expected numbers:** *not* 3/3 / recall 1.0 / gap 0.0. Real instances
  are bigger and messier — expect "recall ~0.8, obj-gap median ~5%" and
  a non-trivial failure histogram. That's the interview answer.

### 2. Third problem family 🟠

Multi-period or multi-commodity flow (or a third single-stage variant if
those are too heavy). Tests generalisation of the `FeasibilityPlugin`
contract and the registry/composer wiring. Gives a concrete "here's how
I extended the architecture" story; doubles as a stress test of the
domain-general fail-closed gate.

### 3. Consolidated problem formulation (Overview-PDF expansion)

Objective / constraints / assumptions / failure-cases for the transport
LP-MIP and the scheduling IPM in one place (code already has the
numbered constraints; §4 covers transport, §7 the gate). Items A
(curated infeasible corpus) and B (Baseline-vs-system +
Failure-analysis surfacing) of this checklist are DONE (see Shipped).

### 4. Confidence / disagreement surfacing

When the voting classifier splits, show it in-UI. Turns ambiguity into
a feature, not a hidden failure. Cheap to ship — the voter already
returns per-voter labels; just expose the disagreement when it's
non-unanimous.

### 5. Web UI (clean front-end)

Replace the terminal-first interaction with a real web front-end on top
of the existing job/poll pipeline UI. The pipeline streams stage events
already; this is presentation, not new backend.

### 6. Persistent REST deployment

The previous cloudflared quick tunnel is shipped but de-prioritized
and ephemeral. Persistent REST API + stable URL → "try it here" works
without a co-located laptop. Pair with #5 (Web UI) for full external access.

### 7. Cost / ROI framing in-app

Surface "this solve would take a consultant ~X hours / ~$Y" next to
each result, parameterized by problem size. Pure UX/marketing layer
over numbers the solver already produces.

### 8. Pick one vertical and go deep

Strategic, not engineering: choose a concrete buyer (logistics? supply
chain?) and make *one* end-to-end workflow excellent (data ingest →
formulation → solve → explanation → export) rather than many shallow.
Decision gate before #5/#6/#7 (Web UI / Persistent REST / Cost-ROI)
turn into generic effort.

### 9. Agentic frontier — on-thesis only

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

### 10. Longer-term architecture (aspirational, unblocked but not urgent)

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
of `detect_intent` so the bare-what-if first-message path is fully LLM-free;
quiet a caught pyomo `ERROR: No eligible units` logged during a *successful*
scheduling solve (internal LP-bound build attempt — result is correct, the
ERROR-level log is misleading noise; surfaced by the chat harness).

---

## Audience-targeted feature backlog (interview vs. investor)

Brainstorm 2026-05-21. Cross-cuts the priority list above; items here may
duplicate or extend earlier entries — kept as a separate lens for quick
audience-driven triage.

### For interviews (BoA-type — engineering depth)

- **Streaming pipeline output** — show classify → extract → validate →
  solve stages live (roadmap item #1 of original demo plan). Kills the
  "spinner = dead air" problem; visually demonstrates the architecture.
- **Confidence / disagreement surfacing** — when the voting classifier
  splits, show it. Turns ambiguity into a feature, not a hidden failure.
- **Expand eval harness** — more synthetic families, adversarial
  extraction tests (malformed/ambiguous prose), report parameter-recall +
  objective-gap per stage. Strongest interview asset; make it richer.
  (Overlaps with Open backlog #3.)
- **A third problem family** — multi-period or multi-commodity flow.
  Tests generalisation of the feasibility gate; gives a "here's how I
  extended it" story.
- **Real-data benchmark** — even 20–30 hand-curated real OR problems.
  Directly answers the "n=10 is small" critique.

### For investors (product, not demo)

- **Excel / CSV fast-path** — upload a sheet, skip the LLM calls, get a
  solve + Excel export. Killer enterprise feature: most real OR users
  live in spreadsheets. (Partial xlsx fast path already shipped — extend
  to CSV + general schemas.)
- **Web UI** — clean front-end, not a terminal. Investors need to see it
  work in 30 seconds.
- **Live deployment** — the Cloudflare REST API previously deferred.
  "Try it here" beats any slide.
- **One vertical, deep** — pick a concrete buyer (logistics? supply
  chain?) and make one workflow excellent rather than many shallow.
- **Cost / ROI framing in-app** — "this solve would take a consultant
  X hours." Quantify the bottleneck removed.

### Priority order (limited time)

1. **Streaming output** — high value both audiences, fast win.
2. **Excel fast-path** — biggest investor signal.
3. **Live deployment** — unblocks "try it" for everyone.
4. **Real-data benchmark** — biggest interview-credibility win.
5. **Third problem family / web UI** — later.

---

## Research framing (CV / publication angle)

LLM-assisted OR (NL → optimal solution with the OR concepts surfaced in
plain English), adaptive heuristic/decomposition selection, hybrid
heuristic-exact solving — all consistent with the governing thesis (the LLM
orchestrates validated solvers; it does not do the math).
