# Analysis Log

Experiment log for design decisions that aren't obvious from the code. Each
entry follows **Problem → Solution → Results**. Add new entries at the top.

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
