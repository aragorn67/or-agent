# Analysis Log

MAJOR results and design decisions not obvious from the code.
**Problem → Solution → Result.** Newest first. Minor follow-ups are folded
into their parent result — this is a log of conclusions, not a diary.

---

## 2026-05-19 — Chat round-trip stress harness (deterministic regression net)

**Problem.** The chat path — the integration surface every change flows
through — had only piecemeal coverage. The transport-only-degradation
class (scheduling silently mis-handled) had no net at the chat contract
level; the one repository test that exercises it end-to-end is
LLM-driven and flaky (`test_feasible_us_manufacturing`).

**Solution.** `tests/test_chat_roundtrip.py`: a contract-correct
`ScriptedLLM` (stubs the 4 agent-called LLM methods, routed on canonical
phrases) + scripted intent seam, driving the *exact* endpoints the UI
uses (`POST /jobs` → poll → `POST /chat/continue`) via `TestClient`. The
real solver, 3-layer gate, and `_with_options` chip chokepoint run.
Assertions target the **deterministic response envelope chat.html
branches on** (`success`, `status`, `solution`, `next_options`,
`reasons`/`suggestions`, `job_pending`, `response`) — not LLM prose, so
it is stable. 9 turns: smalltalk · help · transport solve · scheduling
solve · transport-infeasible · scheduling-infeasible · malformed ·
pending-job free-text (no dead-end) · pending-job optimize action. The
scheduling-infeasible turn asserts *scheduling* reasons, never
transport's "supply" — the transport-only-degradation guard.

**Result.** 9/9 pass; suite 217 passed, zero new regressions. Building
it surfaced two non-blocking notes (system correct, just imprecise/
noisy): the first-message path scripts `_llm_intent_detection`, not
`detect_intent`; and a feasible scheduling solve logs a caught pyomo
`ERROR: No eligible units` from an internal LP-bound build attempt —
result correct (Cmax 5.0), ERROR-level log is noise (→ quick win).

**Extension — routing matrix (answers "do we need another LLM?").**
Added a phrasing matrix over the two *deterministic* (LLM-free) routers
— `_check_deterministic_intent` (16 phrasings) and
`detect_analysis_type_keyword_based` (13) — asserting clear cases route
correctly and *cataloguing* the ones that legitimately punt to the LLM
(`ESCALATE`), with a tripwire test so the ratio can't drift silently.
**Finding:** the free keyword layer resolves ~75–80% of a realistic
phrasing set; misses are **keyword-coverage gaps, not reasoning gaps**
(e.g. "drop P2 capacity by 20%" has no trigger word; "how sensitive" ≠
substring "sensitivity"; "what changes if" ≠ "what if"). The matrix also
caught a wrong *catalogue* prediction — embedded greeting + optimization
keywords correctly routes `optimization` (router more robust than
assumed). **Decision: do NOT add a second model yet** — broaden the
keyword layer / few-shot the existing model and re-measure first; a new
model must beat this catalogue on the eval, same bar that killed RAG/ML.
Suite **246 passed**, zero new regressions.

---

## 2026-05-19 — Genuine Layer-2 feasibility for scheduling + curated infeasible corpus

**Problem.** After the fail-closed refactor, scheduling still had no
*real* Layer 2: `solver_based.py` required `solver.build_model()`, but
the scheduling solver built its Pyomo model inline inside `solve()` →
always `UNKNOWN` (resting on Layers 0/1 + the solver backstop). The
3-layer stack was architecturally both-domain but only transport had a
conclusive Layer 2. (The "solver_id mismatch" the backlog suspected was
a probe typo — `instance_builder` already used the correct id.)

**Solution.** (a) Factored `build_model(params) -> ConcreteModel` out of
the scheduling solver's `solve()` (additive-first then deduped so a
mismatch couldn't break the file); `solve()` delegates, zero behaviour
change. This also let the `solve_lp_relaxation` **NOT_IMPLEMENTED stub**
become a real LP relaxation (relax integers + glpk) — a separate backlog
item closed for free. (b) Made `_convert_instance_to_params`
domain-aware: a scheduling instance now yields buildable solver params,
so Layer 2 runs for **any** solver exposing `build_model` (the
generalization — a new domain needs only its Layer-1 plugin). (c)
Curated infeasible corpus: `or_problem_repository.py` had 3 infeasible
cases, all transport, zero scheduling. Added 6 (transport L0/L1 +
scheduling L0/L1/L1/L2) and backfilled the existing transport-L2 entry,
each with structured `params` + `expected_infeasible_layer`; new
`get_infeasible_problems(machine_checkable=True)` + a deterministic
LLM-free test (`test_infeasible_corpus.py`) asserting each instance is
rejected at exactly its tagged layer, both domains × Layers 0/1/2.

**Result.** Feasible scheduling now → `FEASIBLE` at **layer 2** (was
UNKNOWN); a schedule that passes Layer 1 but is jointly infeasible
(two 3 h orders, each due 4, one unit) → `INFEASIBLE` at layer 2. LP
relaxation returns a valid lower bound (≤ exact Cmax). Full suite **208
passed** (+16 across `test_scheduling_layer2.py` +
`test_infeasible_corpus.py`), same documented pre-existing 2 fails / 3
errors — zero new regressions; 16 scheduling regression tests confirm
`solve()` output unchanged. Transport Layer-2 untouched; the
fail-closed seam (KNAPSACK → UNKNOWN) still holds.

**Docs applied (backlog #1 Part C + #2-B, 2026-05-19).** README: 3-layer
description + diagram now say fail-closed / per-domain plugin /
both-domain; stale "qwen3:14b across all stages" → qwen3:8b; new
*Baseline vs. system* table and *Failure analysis* section (pure
surfacing of existing ANALYSIS numbers — RAG 50/70, ML 44/70, sweep,
warm-start honest-negative, fail-open default). Overview HTML §7
rewritten to current reality (was still documenting the fail-open
"defer to feasible" default + transport-only Layer 1); Part-I
limitation bullet corrected (warm-start). PDF regenerated via
libreoffice headless (11 pp, content verified). Backlog #1 fully done;
#2-D (consolidated formulation) still open.

---

## 2026-05-19 — Feasibility stack made fail-closed & domain-general

**Problem.** Two fail-*open* seams (root cause of the scheduling bug
class): (1) `core.py` mapped Layer-2 `UNKNOWN` → **FEASIBLE** "if Layer
0+1 pass" — a latent false-feasible for *every* domain whose Layer-2 LP
path is inconclusive (e.g. scheduling: no glpk-buildable model →
exception → UNKNOWN → silently FEASIBLE); (2) the Layer-1 checker
(`PROBLEM_TYPE_CHECKERS`) and its suggester (a hardcoded
`if "SCHEDUL" else transport` ladder in `core.py`) were *separately*
wired, so a domain could register a checker yet hand transport's
"increase supply" advice to an infeasible schedule.

**Solution.** New `feasibility/plugins.py`: a `FeasibilityPlugin`
bundles `(checker, suggester)` + match tokens per domain; a half-wired
plugin is a construction-time `TypeError`, not a runtime fail-open.
`core.py` now resolves one plugin and takes *both* halves from it (the
`if "SCHEDUL"` ladder is gone). Layer-2 `UNKNOWN` returns
`FeasStatus.UNKNOWN` (never asserts FEASIBLE from ignorance) and leans on
the now-hardened fail-soft solver as the real backstop. The one caller
that gated on `== FEASIBLE` (sensitivity sweep) was loosened to
`!= INFEASIBLE` so the honest UNKNOWN doesn't silently drop scheduling
points — its `status == 'OPTIMAL'` post-solve check is the true gate.
Layer 0 stays domain-agnostic and deliberately outside the plugin model.

**Result.** Full suite **192 passed** (+13, incl. new
`tests/test_feasibility_plugins.py` covering the contract +
fail-closed); same 2 fails / 3 errors as the documented pre-existing
baseline — **zero new regressions**. Transport's Layer-2-conclusive
happy path is untouched (still FEASIBLE); an unknown domain with no
solver now honestly returns UNKNOWN instead of a confident wrong
FEASIBLE. Adding a 3rd OR domain is now safe: forget either half and it
won't build, and absence of a Layer-1 check can no longer masquerade as
feasibility. (Was open backlog #1.)

---

## 2026-05-18/19 — Scheduling reaches interaction parity with transport

**Problem.** The scheduling chat demo (initial → modify → modify →
infeasible) exposed that the *entire post-solve interaction stack was
transport-only*, degrading silently on scheduling: (1) modification parse —
`parse_infeasibility_fix` schema enumerated only transport params, so
qwen3:8b returned zero mods for any scheduling what-if; (2) modification
apply — `_apply_modifications` had no scheduling branch, so a parsed
`set due_date=4` was *dropped* and the engine solved the unchanged problem
and reported a confidently-wrong FEASIBLE €8 (false-feasible — the most
dangerous bug); (3) feasibility gate — no Layer-1 scheduling checker, so a
genuinely-infeasible scenario hit HiGHS and surfaced a raw pyomo exception.

**Solution.** Prompt/schema gained `due_date|processing_time|eligible` +
the `entity="ALL"` convention; `_apply_modifications` returns
`(modified, applied_count)` and both scenario+modification engines reject
`applied_count==0`; new `feasibility/problem_specific/scheduling.py`
(necessary condition `min(processing over eligible) ≤ due_date` +
no-eligible-unit) registered with case-insensitive/substring routing;
`feasibility/core.py` dispatches Layer-1 suggestions by problem type;
`SingleStageIPMSolver.solve` wraps the solve → clean `INFEASIBLE` dict.
Output: makespan in hours (not €), 6dp rounding, schedule table
auto-renders. Backlog #3 (multi-line render) verified a non-issue
(`.bubble` is `white-space:pre-wrap`, `addMsg` uses `textContent`) but
fixed an adjacent same-class bug: a *first-message* infeasible payload
(`success:false`, no `error`) was `JSON.stringify`-dumped in chat.html —
added an `errText(d)` helper formatting message/Why/💡 multi-line.

**Result.** Suite 179 passed (+10 tests), zero regressions vs the
documented pre-existing baseline. Live qwen3:8b: "every order within 4
hours" → gate returns *"Order 'OrderC' needs ≥5 h on its fastest eligible
unit, but its deadline is hour 4"* + relax suggestion. New deliverable
`Project_Demo_Sceuduling.{webm,mp4}`. **Root shape of every defect:**
subsystems built for transport with no domain dispatch, failing silently
instead of loudly. Fix pattern: explicit per-domain branch + "unhandled ⇒
surface it, never silently pass". Generalizing this is open backlog #1.

---

## 2026-05-18 — Default LLM flipped qwen3:14b → qwen3:8b (model sweep)

**Problem.** No way to know if a cheaper/faster model regresses accuracy.
Curated ground truth doesn't scale (the original eval-wall problem).

**Solution.** `evals/model_sweep.py` — subprocess-per-config sweep over the
round-trip eval (clean config re-import + Ollama model reset per run),
tabulating the 6 metrics + per-stage latency, auto-appending here. A config
is `{backend, 3 model names}`; adding a model is a table row, no code. This
also closed the Phase-3 latency-profiling item.

**Result (seeds 1,2,3, both domains).** **Default flipped to `qwen3:8b`:**
vs the qwen3:14b baseline it is bit-identical on every accuracy metric
(recall 1.000/1.000, pass 0.667/1.000, gap_med 0.000) at **~2× speed**
(agent ≈95k/80k ms vs 197k/159k). The n=3 match is exact and the change is
a reversible 3-line env default, so the n=10 confirm was deliberately
skipped. The transport `pass 0.667` is one `agent_infeasible` seed present
on *both* baseline and qwen3:8b → a model-independent transport-formulation
edge case, not a regression.
- **Rejected on evidence:** `qwen2.5:7b-instruct` — ~7–10× faster but
  transport recall 0.90 / pass 0.333 / gap_med 0.50; the tiered variant
  isolates the qwen2.5 *extractor* as the param-dropping culprit.
  Scheduling was fine, transport disqualifying.
- **Not a verdict (untested, ignore):** `groq-70b` class_acc 0.333/0.000 at
  ~300 ms = instant API reject from a stale Groq model ID, never validly
  exercised. `mistral-7b` class_acc 0.000 at ~13 s = output-format/parse
  mismatch with the classifier, same family as the qwen3/Groq-Llama JSON
  footgun. Both inconclusive re: actual capability.

---

## 2026-05-18 — xlsx structured-input fast path (the "instant demo lane")

**Problem.** The NL path is ~80–95 s (qwen3:8b), almost all LLM inference —
bad live-demo pacing when the user already has structured data.

**Solution.** `POST /solve/file` takes a purpose-built `.xlsx` and skips
*both* qwen3 calls (classify+extract) and, with `explain=false`, the
narration call too. Factored the post-extraction tail of
`solve_natural_language` into a reusable
`OptimizationAgent.solve_with_params(...)` + shared `_friendly_error` —
one source of truth for the feasibility gate / heuristic routing /
`next_options`; the NL path now delegates (zero behaviour change). Input
contract is deliberately NOT the lossy `/export/xlsx` shape; every
malformed input is a `ValueError` → HTTP 422, never a 500.
`GET /solve/file/template` serves a blank correctly-shaped workbook.

**Result.** ~80–95 s → **sub-second**. Both domains round-trip
template→parse→solve to OPTIMAL (transport $153,675 = EX0 baseline;
scheduling Cmax 3.5). Suite 169 passed incl. 17 new (running in 0.81 s —
itself proof the lane touches no LLM). Refactor introduced zero regressions.

---

## 2026-05-16/17 — Demo interactivity: live progress, fallback, chips, follow-ups

**Problem.** A blocking `POST /solve` hid ~2–3 min of LLM work behind one
spinner (worst thing in the demo). Separately, the post-solve conversation
dead-ended: "what if P2 capacity drops to 50?" on a pending job, any
analysis-intent *first* message, and infeasible what-ifs all returned
cryptic errors instead of answers.

**Solution (aggregated — Phases 1+2, roadmap #5/#6/#8).**
- **Live progress:** thread-safe `ProgressStore` + `POST /jobs` /
  `GET /jobs/{id}` surface the agent's existing `update_progress` stages;
  `chat.html` polls and renders a ✓/⏳ pipeline checklist. `POST /solve`
  kept sync for back-compat.
- **What-if follow-ups (#8):** `follow_up_on_job` synthesises a baseline by
  exactly solving the job's params and routes through `_handle_follow_up`
  *without consuming the job*; fixed a latent bug (analysis path resolved
  the solver by problem-type *category* not solver_id → would always have
  raised `Unsupported solver_id`); infeasible what-ifs now return
  plain-language why+fix (all "Layer N" jargon stripped) as a valid
  `success=True` answer; routing-gate analysis detection made keyword-only
  → a what-if dropped from **3 qwen3 calls to 1**.
- **First-message guard:** `_analysis_needs_baseline` returns a
  conversational guide instead of the `solver_id=="none"` /
  extraction-failure hard stops.
- **Chips/export (#5/#6):** `build_next_options(result)` is a pure fn
  applied at one API chokepoint (`_with_options`) so every path carries
  `next_options`; params-derived chips synthesised client-side. #6 shipped
  as stateless `POST /export/xlsx` (the GET-by-id form was hostage to the
  job-store TTL). Fixed a fixed-charge gap bug (heuristic reported
  variable-cost only vs fixed-cost-inclusive LP bound → garbage gap).

**Result.** Stages stream in real time; pending-job what-ifs genuinely
re-solve (verified: cap 50 correctly leaves the 1660 optimum unchanged
because P2 only ships 40 — engine re-solved, didn't echo). Suites green
across the work; the recurring 2 fails / 3 errors are the documented
pre-existing baseline (us_manufacturing ordering, stale `LLMConfig`
deepseek assert, Groq-429 / ML import) — unrelated to any change here.

---

## 2026-05-16 — Deliverables + forgotten-subsystem audit (RAG/ML rejected)

**Result (interview-critical, kept verbatim).** A "what did we miss" sweep
found two substantial dormant subsystems, the root cause of an earlier
wrong "no RAG" claim — say "tested and rejected on evidence", never "no
RAG":
- `ML_RAG_archive/` — real RAG (LangChain+Chroma, 20,399 chunks / 5,008 pp,
  all-MiniLM-L6-v2) + RandomForest, both benchmarked then rejected:
  **RAG 50% vs 70% no-RAG** (+ extraction timeouts); **ML 44% vs LLM 70%**
  on real OR. Archived 2025-11-19.
- `or_classify/` — versioned 9-family OR taxonomy + 7 Snorkel-style
  labeling functions + hybrid TF-IDF/LF pipeline; built, not wired to prod.

`Optimization-AI_Overview` deliverable repurposed for interview reuse
(Tolaros refs removed; added the 3-layer feasibility gate, the
three-approaches-classifier story, and warm-start as an honest negative).

---

## 2026-05-15 — Demo UI + fixed-charge NL; two-call protocol e2e on Ollama

**Problem.** Only a JSON API existed; the fixed-charge solver was
unreachable from NL (extractor never emitted `fixed_cost`). And the
two-call `heuristic_then_ask` protocol had only run with stubbed LLMs.

**Solution.** `api.py` serves a single-file `templates/chat.html` driving
the real two-call protocol with a live elapsed spinner; added `fixed_cost`
extraction (mirrors `arc_capacity`, omitted when absent so pure-LP stays
LP). Ran `demos/heuristic_two_call_demo.py` against a live `LLM_BACKEND=
ollama` server (qwen3:14b), classic GAMS `trnsport`, two HTTP turns.

**Result.** Full pipeline green end-to-end on the real local model.
Fixed-charge NL → `fixed_cost` extracted → VAM 160 (fixed-charge-blind) +
LP bound 1660 → "optimize" → exact MIP OPTIMAL **1660**, gap 0. Pure-LP
trnsport: VAM 153675 == LP bound, flagged provably optimal. **Key pacing
fact:** step-1 ~147 s is *entirely* LLM inference (two qwen3 calls), not
solver — pre-warm or narrate the wait in a live demo.

---

## 2026-05-14 — Warm-start: honest negative result + the integer-var gate

*(The big OR finding — aggregates the HiGHS spike, pure-LP transport,
IPM scheduling, fixed-charge MIP, and VAM-perf experiments.)*

**Problem.** The plan assumed a metaheuristic→MILP warm-start would broadly
accelerate solves. Validate before claiming it anywhere.

**Solution / decision.** Confirmed Pyomo APPSI HiGHS accepts warm-starts,
exposes post-solve metrics, and honors `time_limit`/`mip_rel_gap` →
**full GLPK → HiGHS swap, no raw highspy needed**. Pattern: set
`var.value=…` before `solver.solve(model)`. VAM rewritten with numpy
(O(n+m) penalties via `np.partition`): **17× faster** at 400×800 (51 s →
2.9 s). Added a `_model_has_integer_vars` gate: pure-LP models silently
skip warm-seeding (`warm_started=False`); MIP variants auto-enable it.

**Result — warm-start is mostly a null effect, honestly:**
- **Pure-LP transport:** warm-start *slower* than cold beyond 10×20
  (0.35–0.84× at scale). Dual simplex from scratch beats crashing a basis;
  no B&B tree to prune.
- **IPM scheduling (true MIP):** cold ≈ warm within ms across 9 instances
  (sizes 6×3–12×5). HiGHS's primal heuristics find LPT-quality incumbents
  in <1 s; the bottleneck is *proving* optimality (weak LP relaxation,
  O(n²m) Big-M precedence vars), which warm-start doesn't accelerate.
- **Fixed-charge transport MIP:** the headline "6.6×" was a
  non-representative single instance; a 5-seed sweep shows **1.00–1.02×**.
  VAM minimizes transport cost only — it is blind to fixed charges, so its
  incumbent is no better than HiGHS's own. **The real lever is a
  fixed-charge-aware construction heuristic** (prices in `fc` when opening
  a route) — open backlog, not built.

**What this means.** The two-call UX (immediate heuristic answer → user
decides → optimize, with LP-bound visibility) still has product value; the
*solver-speedup* claim does not hold for current formulations and we don't
make it. Plumbing is correct (`warm_started` reported accurately, warm ==
cold optimum everywhere); future combinatorial formulations (VRP, job-shop,
fixed-charge-aware) can plug into the same scaffolding. Consistent honest
negative across all four experiments.
