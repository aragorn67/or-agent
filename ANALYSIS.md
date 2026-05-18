# Analysis Log

Experiment log for design decisions that aren't obvious from the code. Each
entry follows **Problem → Solution → Results**. Add new entries at the top.

---

## 2026-05-15 — Demo UI + fixed-charge NL extraction wiring

**Problem.** Needed a presentable UI for a live demo. The repo had only a
JSON API; the sole UI was an archived `chat.html` calling the dead
`/solve/natural` single-shot endpoint. Separately, the new fixed-charge
solver was unreachable from natural language — the transport extractor never
emitted `fixed_cost`, so a fixed-charge prompt silently solved as pure LP.

**Solution.** (1) `api.py` now serves a rewired single-file
`templates/chat.html` at `GET /` (JSON index moved to `/api/info`). The UI
drives the real two-call protocol: `POST /solve mode=heuristic_then_ask`,
then `POST /chat/continue`, with a live elapsed-seconds spinner (Ollama's
first parse is ~2 min) and a "New" button to reset the job. (2) Added a
`fixed_cost` field + extraction rules to `llm/transportation_specialist.py`,
mirroring the existing `arc_capacity` pattern; omitted when no fixed charge
is mentioned so pure-LP problems stay LP.

**Results.** End-to-end via the same endpoints the UI uses (Ollama
qwen3:14b): fixed-charge NL → extracted `fixed_cost` → heuristic_then_ask
returns VAM 160 (fixed-charge-blind) + LP bound 1660 → "yes optimize it" →
exact MIP OPTIMAL **1660**, gap 0, 3 routes opened (P1→M1, P1→M2, P2→M3),
`warm_started=True`. 134 tests pass; the 2 fails / 3 errors are pre-existing
and unrelated (real-LLM flakiness, stale deepseek config assertion,
collection fixture) — none touch the changed files.

**Diagnosis.** Demo path is solid. The VAM-vs-bound spread (160 vs 1660) is
the fixed-charge-blind heuristic from the entry below made visible in the UI
— honest, and a good talking point rather than a flaw to hide.

---

## 2026-05-15 — Fixed-charge transport MIP + honest warm-start result

**Problem.** The 6.6x warm-start spike cited below was an ad-hoc experiment;
there was no real fixed-charge solver in the codebase. Build one and verify
whether the VAM warm-start payoff actually holds.

**Solution.** Added optional fixed charges to `BipartiteTransportSolver`:
`fixed_cost[i,j]` param -> binary `y[i,j]` (route open?) + tight big-M link
`x[i,j] <= min(supply_i, demand_j, arc_cap) * y[i,j]`, objective gains
`sum(fc * y)`. Auto-trips `_model_has_integer_vars` so the existing
warm-start gate and `relax_integer_vars` LP-bound path engage with no other
changes. Warm-start now also seeds `y` (1 iff seeded flow > 0). 11 tests
pass (5 new + 6 transport regression).

**Results.** Solver correct: open-route consolidation, valid LP bound below
MIP optimum, warm == cold optimum. **But warm-start gives no speedup**: a
5-seed sweep (22x30, tight 1.12x supply slack, instances 1.4s–83s) shows
**1.00–1.02x** every time, objectives identical.

**Diagnosis.** VAM minimizes *transport cost only* — it is blind to fixed
charges. Once the solver adds `sum(fc*y)`, the VAM incumbent is no better
than what HiGHS's internal feasibility heuristics find on their own, so
seeding it changes nothing. The earlier "6.6x" was a non-representative
single instance, not a robust effect. **The real lever is a fixed-charge-
aware construction heuristic** (greedy that prices in fc when opening a
route) — logged as backlog, not built this session. Honest mixed result,
consistent with the scheduling/transport warm-start entries below.

---

## 2026-05-15 — End-to-end two-call protocol with real Ollama stack

**Problem.** The two-call `heuristic_then_ask` protocol (VAM/LPT + bound,
then free-text follow-up → exact solve) had only been exercised with stubbed
LLM calls. We needed to confirm it survives a real qwen3:14b run via Ollama
end to end, including free-text intent parsing.

**Solution.** Ran `demos/heuristic_two_call_demo.py` against a live
`LLM_BACKEND=ollama` API server (qwen3:14b for classify/extract/parse).
Classic GAMS `trnsport` instance, two HTTP turns.

**Results.** Full pipeline green. Step 1 (NL → classify → extract → VAM +
LP bound): **146.8s**, dominated by qwen3 classify+extract. VAM cost
153675.00 == LP bound, gap 0.0000% → flagged provably optimal. Step 2 (free
text "yes can you make it better" → intent parse → exact solve): **22.3s**,
parsed action `optimize`, HiGHS confirms OPTIMAL 153675.00, gap 0.0. As
expected `warm_started=False` (pure LP, warm-start gate correctly skipped —
see scheduling/transport entries below).

**Diagnosis.** Protocol and free-text routing are sound with the real local
model. The ~147s step-1 latency is entirely LLM inference (two qwen3 calls),
not solver — relevant for live demo pacing: pre-warm or narrate the wait.

---

## 2026-05-14 — Warm-start on single-stage scheduling IPM

**Problem.** Phase 2 promised a dramatic warm-start payoff for scheduling
(true MIP) compared to transport (which is pure LP and not expected to
benefit). We needed to validate this before claiming the speedup in the
README or demo materials.

**Solution.** Built an LPT (Longest Processing Time) heuristic in
`solvers/heuristics/scheduling_lpt.py` — greedy assignment with eligibility,
per-(order, unit) processing times, and changeover-aware completion times.
The output is a complete primal solution (assignment + sequence + completion +
Cmax) used to seed every Y, XX, C, and Cmax in the IPM MILP before solving
with HiGHS via Pyomo APPSI.

**Results.** Across nine random instances (loose due dates, tight due dates,
restricted eligibility; sizes 6×3 through 12×5), **cold and warm finish within
milliseconds of each other** and reach identical gaps at identical times:

| Instance | Cold | Warm | Speedup |
|---|---|---|---|
| 6×3 loose | 361ms | 347ms | 1.04× |
| 8×3 loose | 1.76s | 1.76s | 1.00× |
| 10×3 loose | 19.4s | 19.5s | (both 0.76% gap) |
| 12×4 loose | 30s | 30s | (both 20% gap) |
| 6×3 tight | 552ms | 554ms | 1.00× |
| 10×3 tight | 20s | 20s | (both 0.92% gap) |
| 8×4 restricted | 185ms | 185ms | 1.00× |
| 10×4 restricted | 3.08s | 3.08s | 1.00× |
| 12×5 restricted | 166ms | 149ms | 1.11× |

**Diagnosis.** HiGHS's built-in MIP primal heuristics find LPT-quality
incumbents within the first second on the IPM formulation, so the warm-start
is redundant. On larger instances the time is spent **proving** optimality
(closing the gap from the LP relaxation), which warm-start doesn't accelerate
— it only improves the initial incumbent. The IPM formulation has a weak LP
relaxation (O(n²m) precedence variables with Big-M constraints), so closing
the proof gap is the bottleneck.

**Where warm-start WOULD pay off** (validated separately):
- Fixed-charge transport MIP (binary "use this arc" + Big-M) — measured 6.6×
  speedup in the original spike. HiGHS's primal heuristics struggle to find
  feasible solutions here; the warm-start provides one they wouldn't have
  found quickly.
- Likely candidates: VRP, job-shop scheduling, facility-location problems
  with combinatorial structure that defeats default primal heuristics.

**What this means for the product.** The two-call UX story (heuristic answer
→ user decides → optimize) still has value on scheduling — users get an
immediate feasible schedule instead of waiting 20s+ for the MILP. We just
shouldn't claim "warm-start makes the exact solve faster" for IPM scheduling.
The speedup narrative belongs to fixed-charge problems and harder formulations
we haven't built yet.

**Plumbing is correct.** All 6 scheduling heuristic tests pass; warm-started
solves return the same Cmax as cold solves; `warm_started=True` flag is
reported correctly. Future formulation upgrades (positional, time-indexed)
can plug into the same scaffolding without API changes.

---

## 2026-05-14 — Warm-start on pure-LP transport

**Problem.** The brainstorm originally assumed warm-start would help on all
problems including the current bipartite transport solver. Needed to verify
on realistic sizes.

**Solution.** Stress-tested cold-vs-warm solve on random transport instances
from 10×20 up to 800×1600 plants/markets. VAM heuristic runs first; its flow
values seed the Pyomo `x[i,j].value` before HiGHS solves.

**Results.** Warm-start was **slower than cold** beyond 10×20:

| Size | VAM | VAM gap | Cold | Warm | Speedup |
|---|---|---|---|---|---|
| 10×20 | 0.6ms | 11.2% | 62ms | 22ms | 2.78× |
| 25×50 | 8ms | 34.8% | 17ms | 20ms | 0.84× |
| 50×100 | 48ms | 42.4% | 59ms | 131ms | 0.45× |
| 100×200 | 56ms | 31.7% | 260ms | 698ms | 0.35× |
| 400×800 | 2.9s | 5.9% | 5.0s | 46s* | * pre-perf-fix |

**Diagnosis.** HiGHS's dual simplex from scratch is faster than crashing a
basis from a primal solution. Pure LP has no benefit from a starting
incumbent — there's no branch-and-bound tree to prune.

**Solution adopted.** Added a `_model_has_integer_vars` gate in
`solvers/transport/bipartite.py`. If the model is pure LP, warm-start is
silently skipped (response has `warm_started=False`). When fixed-charge or
integer-shipment variants are added later the gate auto-enables warm-start.

**Result.** Stress test re-run with the gate confirms `warm_started=False`
across all sizes and pure-LP cold-solve performance restored.

---

## 2026-05-14 — VAM heuristic performance

**Problem.** Initial pure-Python VAM implementation took 51 seconds on a
400×800 instance — unusable for a "fast heuristic" pitch.

**Solution.** Rewrote VAM with numpy: cost matrix stored as `np.ndarray`,
row/column penalties computed via `np.partition` (O(n+m) per axis),
inactive rows/columns masked with `np.inf` so they're naturally ignored.

**Results.**

| Size | Pure Python | NumPy | Speedup |
|---|---|---|---|
| 100×200 | 383ms | 56ms | 6.8× |
| 200×400 | 3.8s | 379ms | 10.0× |
| 400×800 | 51s | 2.9s | 17.6× |
| 800×1600 | (n/a) | 28s | — |

At 800×1600 (1.28M variables) VAM is now 28s — comparable to HiGHS solving
the LP directly (24s). For pure LP at that scale, running VAM at all is
debatable, but we keep it because:
1. It provides the conversational hook (user gets an answer to react to)
2. Phase 2+ formulations (fixed-charge, scheduling MIP) will benefit
3. The cost of running VAM is dominated by the LP solve anyway

**Gap quality.** On random uniform-cost instances, VAM gap ranges 5%–45%.
On the textbook Seattle/SD example (geographic structure), VAM matches the
LP optimum exactly. Real-world data with structure will fall in between.

---

## 2026-05-14 — HiGHS warm-start spike (the gate decision)

**Problem.** Plan called for replacing GLPK with HiGHS. Before committing to
the rewrite we needed to confirm Pyomo's APPSI HiGHS interface
(a) accepts a warm-start, (b) exposes post-solve metrics
(`best_feasible_objective`, `best_objective_bound`, `termination_condition`),
and (c) honors `time_limit` and `mip_rel_gap`.

**Solution.** Built a fixed-charge transport MIP (binary "arc-used" indicators
+ Big-M linking, integer-only variables in the objective). Constructed a
greedy primal solution by hand. Solved twice: cold (no warm-start) and warm
(variables seeded).

**Results.**
- Cold solve: 79ms, optimal objective 970, gap 0.00%.
- Warm solve: 12ms, same optimal, same metrics — **6.6× speedup**.
- All three post-solve metrics accessible.
- `time_limit` config respected; `mip_rel_gap` configurable via
  `solver.highs_options = {"mip_rel_gap": 0.01}`.

**Decision.** Proceed with full GLPK → HiGHS swap. APPSI HiGHS is sufficient
— no need to drop to raw `highspy`. Warm-start uses the natural Pyomo
pattern: set `var.value = ...` before `solver.solve(model)`, APPSI picks it up
automatically.

---

## 2026-05-16 — Roadmap #8: what-if follow-ups on a pending job

**Problem.** In the chat demo, asking "what if P2 capacity drops to 50?" while
a heuristic_then_ask job was pending returned the dead-end "I didn't catch
what you'd like to do" message. The capability to re-solve under a what-if
appeared missing.

**Root cause — three layered defects, found by an offline repro:**
1. **UI/API funnel.** While a job is pending, `chat.html` sends *every*
   message to `/chat/continue`, which only ran `parse_continue_action`
   (optimize/accept/use_heuristic). Anything else dead-ended; the agent's
   follow-up machinery was never reached.
2. **Latent analysis-path bug.** `_handle_follow_up_analysis` built the solver
   via `get_solver(problem_type.lower())` → `get_solver("transportation")`,
   but the registry keys on solver_id. Every analysis follow-up would have
   raised `Unsupported solver_id: 'transportation'` — the path was simply
   never exercised before.
3. **Mis-routing.** `_handle_follow_up` sent "modification" follow-ups to
   canned text, and the lightweight keyword classifier labels "what if X…"
   as a plain *question* (starts with "what"), so it fell through to a
   generic reply instead of the (working) what-if engine.

**Fixes.**
- `follow_up_on_job(job_id, message)` (agent/core.py): synthesises a baseline
  by exactly solving the job's params, routes through `_handle_follow_up`,
  and **does not consume the job** (user can still optimize/accept).
- `/chat/continue`: non-action message → `follow_up_on_job` instead of the
  dead-end. `chat.html`: render the follow-up answer and keep `jobId` set
  when `job_pending` is returned.
- `_handle_follow_up_analysis`: resolve solver from
  `solution["solver_id"]` (fallback: category default), never the category.
- `_handle_follow_up`: modification/analysis and any LLM-detected
  what-if/sensitivity/resolve/pareto intent → `_handle_follow_up_analysis`.

**Verification.**
- Offline repro with the real qwen3:14b: "what if P2 capacity drops to 50?"
  on the fixed-charge example now returns FEASIBLE/OPTIMAL. Answer is
  *correctly* unchanged (1660): P2 only ships 40 to M3, so a cap of 50 is
  not binding — the engine genuinely re-solved, it did not echo.
- 5 deterministic regression tests (`tests/test_followup_whatif.py`), LLM
  stubbed. Full suite: 139 passed; the 2 fails / 3 errors are pre-existing
  and unrelated (Groq 429 rate-limit, stale config-default test, ML import
  collection errors).

**Follow-up (same day).** Infeasible what-ifs ("what if P1 capacity drops to
5?") were surfacing as a cryptic error: `_handle_follow_up_analysis` treated
any `success=False` result as an `analysis_error` and returned the internal
`"Scenario is infeasible (failed at layer 1)"` string, discarding the
feasibility engine's plain-language reasons/suggestions. Fixed: a structured
`feasible=False` result is now a valid `follow_up_analysis` answer (formatted,
success=True, job stays pending); `format_scenario_results` rewritten to drop
all "Layer N" jargon for the non-OR audience. +1 regression test (6 total in
test_followup_whatif.py).

**Follow-up (same day) — perf + fixed-charge gap.**
(1) Perf: a "what if" follow-up was making 3 sequential qwen3:14b calls
(detect_analysis_type in the routing gate + again inside the handler + the
what-if parse). The routing gate now uses keyword-only detection (no LLM)
and passes the type down so the handler skips re-detecting → 3 LLM calls
→ 1 (only the unavoidable modification parse).
(2) Fixed-charge gap bug: `run_heuristic_for_transport` reported
`vam.cost` (variable cost only) for fixed-charge problems while the LP
bound included fixed costs, so the heuristic cost was understated (160 vs
true 1660) and gap-vs-bound went to ~-937% (surfaced to the user as a
"9-10%" gap). Fix: new `_fixed_charge_total()` adds the fixed charge for
every opened route to the reported/stored heuristic cost. The fixed-charge
demo now reports cost 1660, gap 0.0 ("provably optimal"), consistent
through the optimize/accept paths. +1 regression test in
test_heuristic_two_call.py (10 there; full follow-up/heuristic suites green).

---

## 2026-05-16 — Phase 1: live progress (job + poll)

**Problem.** A blocking `POST /solve` hid ~2-3 min of local-LLM work behind
one spinner — the single worst thing in the demo.

**Solution.** The agent already emitted stages via its
`update_progress(step, percent)` callback (never surfaced — `/solve` passed
no callback). Added a thread-safe `ProgressStore` (UUID runs, stages, result,
15-min TTL); `POST /jobs` runs `solve_natural_language` in a daemon thread
feeding the callback into the store and returns a `run_id` immediately;
`GET /jobs/{run_id}` returns live stages + the full payload once done.
`chat.html` polls (900 ms) and renders a ✓/⏳ pipeline checklist, then runs
the existing result rendering — the heuristic continuation `job_id` survives
the async round-trip untouched. `POST /solve` kept synchronous for
back-compat.

**Verification.** 5 tests in `test_progress_jobs.py` (store lifecycle/error/
TTL + end-to-end TestClient flow with solve stubbed); 26 across the Phase-1
+ related suites green. Live smoke: stages stream in real time
(`Detecting intent...` → `Analyzing problem type...` → …) while running.

## 2026-05-16 — Phase 2: first-message analysis-intent dead-end

**Problem.** A what-if / sensitivity / resolve / pareto request as the
*first* message has no solved baseline. The follow-up branch is skipped
(no `last_solution`), so it was misrouted into the solver pipeline and
dead-ended with a cryptic "not supported by our solvers" (`core.py`
`solver_id == "none"`) or "Parameter extraction failed" — unactionable.

**Solution.** New `OptimizationAgent._analysis_needs_baseline(desc, ctx,
allow_data_rich)`: keyword-only `detect_analysis_type` (no LLM), gated on
no `last_solution`/`last_infeasibility`. Returns a conversational guide
(`type: "analysis_no_baseline"`) that explains a what-if needs a baseline
and shows a concrete example. Wired in three places:
(1) early gate before the optimization pipeline with
`allow_data_rich=False` — only short-circuits the *bare* case (number/
length heuristic lets a full problem stated as a what-if through),
saving ~2 LLM calls; (2) + (3) post-failure net at the `solver_id ==
"none"` and extraction-failure returns with `allow_data_rich=True`,
converting both dead-ends to the guide. `chat.html`: first-message
success branch now renders `d.response` when there's no `d.solution`
(also fixes a pre-existing smalltalk/help-as-first-message NaN-card bug).

**Verification.** 7 tests in `test_first_message_analysis.py` (helper in
isolation: bare what-if/sensitivity/pareto, baseline-present pass-through,
non-analysis pass-through, data-rich early/late behaviour; + integration
through `solve_natural_language` with intent stubbed). 32 across related
suites green. Live smoke: first-message "what if I increase plant
capacity by 20%?" returns the guide in ~12s (one `detect_intent` LLM
call) instead of the full pipeline + cryptic error.

**Possible follow-up.** Early gate runs *after* `detect_intent`'s LLM
call; moving the keyword check ahead of it would make this path fully
LLM-free (~0s). Deferred — micro-opt on an error path, not the happy path.

## 2026-05-16 — Deliverable overhaul + forgotten-subsystem audit

**Doc.** `Optimization-AI_Overview` repurposed for interview/management
reuse: removed the only Tolaros reference (footer → "system overview");
added three Part II sections — the 3-layer feasibility gate (Structural
→ problem-specific → LP-relaxation, with the fail-fast/fail-actionable
rationale), Classification: three approaches evaluated, and Warm-start:
an honest negative result. HTML edited, PDF regenerated (6 → 9 pp,
visually verified). Part I (pp.1–2) stands alone as the exec/FYI piece
(page-break + bridge line); no separate brief created, per user.

**Audit.** "What did we miss" sweep found two substantial, dormant
subsystems absent from memory/docs (root cause of an earlier wrong
"no RAG" claim):
- `ML_RAG_archive/` — real RAG (LangChain+Chroma, 20,399 chunks /
  5,008 pp, all-MiniLM-L6-v2) + RandomForest, both benchmarked then
  rejected: RAG 50% vs 70% no-RAG (+ extraction timeouts); ML 44% on
  real OR vs LLM 70%. Archived 2025-11-19.
- `or_classify/` — versioned 9-family OR taxonomy + 7 Snorkel-style
  labeling functions + hybrid TF-IDF/LF feature pipeline; built,
  not wired to production.
Both captured to memory as interview material. The three-approaches
classifier section in the doc is grounded in this audit.

## Phase 2 #5 — continuation chips + chat interactivity pass (2026-05-17)

**What.** Closed Phase 2 #5 and, on user request, expanded it into a
full chat-interactivity pass (all 4 scoped options).

**Design choice — single chokepoint.** `build_next_options(result)` is a
*pure* function of the response dict (no agent state), applied once at the
API boundary via `_with_options(...)` rather than at ~12 `core.py` return
sites. Every path (sync `/solve`, async `/jobs`, `/continue`,
`/chat/continue`) gets `next_options` for free; routing-state chips stay
server-authored, while params-derived chips (quick what-ifs, Show table,
Export) are synthesised client-side from the payload the chat already
holds — no extra round-trips.

**#6 evolved, not deferred.** Planned as `GET /jobs/{id}/export.xlsx`;
shipped as `POST /export/xlsx` taking the client-held payload. Rationale:
the GET-by-id form is hostage to the 10-min heuristic job-store TTL and
breaks after an exact solve (jobId cleared). Posting the payload back is
stateless and works in every post-solve state. Workbook = Summary +
Flows/Schedule + Parameters; openpyxl/pandas; TestClient-verified for
transportation and single-stage scheduling.

**Validation.** 8 routing states → expected chip sets; export 200 +
valid workbook (both domains); `api` imports clean; full suite shows no
new reds (`test_default_config`, `test_classification` errors, and
full-run-ordering `test_feasible_us_manufacturing` all reproduce on a
clean tree — pre-existing, unrelated). Browser click-through still
pending (static review only).

## Model-sweep harness added (2026-05-17)

`evals/model_sweep.py` — subprocess-per-config sweep over the existing
round-trip eval; varies LLM backend + per-stage models via env
(isolation = clean config.py re-import + Ollama model reset), tabulates
the 6 metrics + per-stage latency, auto-appends results here. Model-
agnostic: a config is `{backend, 3 model names}`; add a row, no code.
Closes the Phase 3 "per-stage latency profiling" item (eval already
captured `stage_latency`; the sweep aggregates it across models).

Harness validated end-to-end (dry-run + 1 real run). **Non-conclusive
early signal** (`qwen2.5:7b-instruct`, transport, n=1): class_acc 1.0,
param recall 0.80, end-to-end FAIL (objective_mismatch), agent ≈20 s
vs qwen3:14b ≈150 s. ~7× faster but lost ~20% of params on the seed —
the speed/accuracy tradeoff the real sweep must quantify (n≥3, both
domains). Full sweep is the user's to launch (long on qwen3:14b);
results land here automatically.

## Model sweep — 20260517_110157 (seeds=1,2,3, gap_threshold=0.01)

| config | domain | n | class_acc | recall | pass | gap_med | agent_ms | wall_s | notes |
|---|---|---|---|---|---|---|---|---|---|
| baseline | transport | 3 | 1.000 | 1.000 | 0.667 | 0.000 | 196685 | 643 | agent_infeasible:1 |
| baseline | scheduling | 3 | 1.000 | 1.000 | 1.000 | 0.000 | 158856 | 476 | ok |
| qwen3-8b | transport | 3 | 1.000 | 1.000 | 0.667 | 0.000 | 95306 | 240 | agent_infeasible:1 |
| qwen3-8b | scheduling | 3 | 1.000 | 1.000 | 1.000 | 0.000 | 80074 | 241 | ok |
| qwen2.5-7b | transport | 3 | 1.000 | 0.900 | 0.333 | 0.500 | 20853 | 67 | objective_mismatch:1, agent_infeasible:1 |
| qwen2.5-7b | scheduling | 3 | 1.000 | 1.000 | 1.000 | 0.000 | 15489 | 46 | ok |
| qwen2.5-extract | transport | 3 | 1.000 | 0.900 | 0.333 | 0.500 | 54689 | 182 | objective_mismatch:1, agent_infeasible:1 |
| qwen2.5-extract | scheduling | 3 | 1.000 | 1.000 | 0.667 | 0.000 | 63106 | 200 | agent_infeasible:1 |
| mistral-7b | transport | 3 | 0.000 | — | 0.000 | — | 13398 | 42 | classification_miss:3 |
| mistral-7b | scheduling | 3 | 0.000 | — | 0.000 | — | 14403 | 52 | classification_miss:3 |
| groq-70b | transport | 3 | 0.333 | — | 0.000 | — | 324 | 2 | agent_infeasible:1, classification_miss:2 |
| groq-70b | scheduling | 3 | 0.000 | — | 0.000 | — | 315 | 1 | classification_miss:3 |

Raw JSON: `/tmp/sweep_20260517_110157_2itgvcq1` (lost — machine rebooted,
`/tmp` cleared; interpretation below is from the table + harness code).

**Verdict — default flipped to `qwen3:8b`.** vs the `qwen3:14b` baseline,
qwen3-8b is **bit-identical on every accuracy metric** (recall 1.000/1.000,
pass 0.667/1.000, gap_med 0.000) across **both** domains at n=3, at **~2x
speed** (agent_ms 95k/80k vs 197k/159k). Meets the pre-set guardrail
(n≥3, both domains, no regression). n=10 confirm deliberately skipped:
the n=3 match is exact (not approximate) and the change is a reversible
3-line env default — not worth ~1h of qwen3:14b compute to gate. The
transport `pass 0.667` is one `agent_infeasible` seed present on baseline
*and* qwen3-8b → a model-independent transport-formulation edge case,
not a regression. `OLLAMA_MODEL` legacy alias unchanged (tracks
`CLASSIFICATION_MODEL`).

**Rejected on evidence:** `qwen2.5:7b-instruct` (and the
qwen2.5-extract tiered variant) — ~7-10x faster but transport recall
0.90, pass 0.333, gap_med 0.50 (`objective_mismatch`); the tiered row
isolates the qwen2.5 *extractor* as the param-dropping culprit.
Scheduling was fine but transport is disqualifying.

**Not a verdict — untested, ignore these rows:**
- `groq-70b` — class_acc 0.333/0.000 at ~300 ms is an *instant API
  reject*, not 70b reasoning. Root cause: stale Groq model ID
  (`config.py` default `llama-3.3-70b-versatile`; Groq retires IDs
  aggressively). The harness never validly exercised Groq. Fix is to
  refresh the three `GROQ_*_MODEL` defaults before any future Groq run;
  deliberately deferred.
- `mistral-7b` — class_acc 0.000 both domains but ~13 s latency (real
  inference, not an API reject) → output-format/parse mismatch with the
  classifier, same family of footgun as the qwen3/Groq-Llama JSON
  issues. Inconclusive re: mistral's actual capability.

## Phase 3 #2 — xlsx structured-input fast path (2026-05-18)

The "instant demo lane": `POST /solve/file` takes a structured `.xlsx`
and skips **both** qwen3 calls (classify + extract); with
`explain=false` (default) it also skips the third (narration) — solve
goes from ~80–95 s (qwen3:8b) to **sub-second**.

**Refactor (no behaviour change).** Factored the post-extraction tail
of `solve_natural_language` (validate → 3-layer feasibility → mode
routing → solve → explain → assemble) into a reusable
`OptimizationAgent.solve_with_params(...)`, plus a shared
`_friendly_error`. The NL path calls it after classify+extract; the
file path calls it directly. One source of truth for the feasibility
gate / heuristic routing / `next_options`. Full suite: **169 passed**
(incl. 17 new), the 2 fails + 3 errors are the documented pre-existing
baseline (`test_feasible_us_manufacturing`, the legacy
`LLMConfig.model=='deepseek-r1:latest'` stale assert — *not* the
qwen3:8b change, it's a different config object — and the Groq-429 / ML
classification errors). Refactor introduced **zero** regressions.

**Input contract.** A purpose-built input workbook, deliberately NOT
the `/export/xlsx` shape (its `Parameters` sheet is `str(v)`-lossy,
`Flows` is output). Transport: `Supply`/`Demand`/`Cost` (+ optional
`FixedCost`→MIP / `ArcCapacity`); Scheduling: `Processing` (blank cell
= not eligible) / `DueDate`. Parser targets the *extractor's* output
shape (`cost` nested map, etc.), not the solver's alternate
`distance`+`freight` form — verified by feeding it through the real
feasibility gate. Every malformed input is a `ValueError` → HTTP 422,
never a 500. `GET /solve/file/template?problem_type=…` serves a
correctly-shaped blank workbook.

**Verified.** Both domains round-trip template→parse→solve to OPTIMAL
(transport = $153,675, the EX0 baseline; scheduling Cmax 3.5).
Endpoint TestClient-checked: solve 200 + `input=spreadsheet` +
`skipped_stages` + `next_options` intact; malformed/empty/unsupported
→ clean 422. The 17-test suite runs in **0.81 s** — itself proof the
lane touches no LLM (tests use a method-less dummy client).

## 2026-05-18 — Scheduling parity: what-if + feasibility + demo polish

**Problem.** Building the scheduling chat demo (initial → modify →
modify → infeasible) exposed that the entire post-solve interaction
stack was **transport-only**. Three compounding defects, surfaced in
order by the demo:
1. *Modification parse* — `parse_infeasibility_fix`'s schema enumerated
   only `capacity|demand|cost|arc_capacity|supply`; qwen3:8b returned
   zero mods for any scheduling what-if → "Could not parse".
2. *Modification apply* — `_apply_modifications` had no scheduling
   branch, so a *parsed* `set due_date=4` was silently dropped; the
   scenario engine then solved the **unchanged** problem and reported
   FEASIBLE €8 — a confidently-wrong false-feasible.
3. *Feasibility gate* — once apply worked, the genuinely-infeasible
   scenario had no Layer-1 scheduling checker (registry transport-only);
   it passed the gate, hit HiGHS, and raised a raw appsi
   "no feasible solution" exception surfaced as "Analysis failed:
   <pyomo internals>" — still no explanation.

**Solution.**
- Prompt/schema gained `due_date|processing_time|eligible` + the
  `entity="ALL"` convention; scheduling rules/examples added.
- `_apply_modifications`: due_date (per-order + ALL) and
  processing_time branches; now returns `(modified, applied_count)` via
  before/after snapshot. Both scenario + modification engines reject
  `applied_count == 0` instead of solving the unchanged problem.
- New `feasibility/problem_specific/scheduling.py`: necessary condition
  `min(processing over eligible units) ≤ due_date` + "no eligible
  unit", plain-language reason + suggestion. Registered SCHEDULING /
  SINGLE_STAGE / SINGLE_MACHINE with case-insensitive + substring
  routing. `feasibility/core.py` Layer-1 suggestion gen dispatched by
  problem type (was hardcoded transport). `SingleStageIPMSolver.solve`
  wraps the solve → clean `INFEASIBLE` dict, never a raw exception.
- Output: scheduling objective rendered as **makespan in hours** (not
  `€`); solver rounds completion/Cmax to 6 dp (kills `7.999…998`
  noise). Chat: schedule/flow table now **auto-renders after every
  result card**; new scheduling view reconstructs each unit's
  back-to-back timeline (Unit | Order | Start | End | Duration) with a
  makespan header + per-unit sequence string.

**Results.** Full suite **179 passed**, same 2 fails + 3 errors as the
documented pre-existing baseline (us_manufacturing, stale `LLMConfig`
deepseek assert, Groq-429/ML) — **zero regressions**; +10 new tests
(`test_scheduling_modifications.py`, `test_scheduling_feasibility.py`).
Live qwen3:8b: "OrderC's deadline moves up to hour 9" → `set OrderC=9`
(applied=1, OrderC only); "every order within 4 hours" → `set ALL=4`
(applied=1, all four) → gate now returns *"Order 'OrderC' needs at
least 5 h on its fastest eligible unit, but its deadline is hour 4…"*
+ a relax-deadline suggestion. JS validated via `node --check`. New
deliverable `Project_Demo_Sceuduling.{webm,mp4}` (gst-launch VP8→H.264,
no ffmpeg on box; padded 1107→1106 for even-dim x264).

**Diagnosis.** Every defect was the same root shape: subsystems built
for transport with no domain dispatch, silently degrading on scheduling
(empty parse, dropped apply, missing checker) rather than failing
loudly. The false-feasible (#2) was the most dangerous — a wrong answer,
not an error. Fix pattern throughout: explicit per-domain branch +
"unhandled ⇒ surface it, never silently pass".
