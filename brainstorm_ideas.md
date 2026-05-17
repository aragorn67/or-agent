# Optimization AI - Architectural Brainstorming

**Date**: 2025-11-29
**Status**: Analysis framework complete for transportation, ready for expansion

---

## 🎯 Current State Summary

### What's Working Well ✅
- **LLM Classification**: 100% accuracy on solvable problems (DeepSeek-R1)
- **3-Layer Feasibility Checking**: Production-ready (structural, aggregate, solver-based)
- **Analysis Framework**: Sensitivity, what-if, resolve - **4/4 tests passing**
- **Solver Coverage**: Transportation (bipartite), Single-stage scheduling (makespan)

### Current Limitations ⚠️
- Analysis framework hardcoded to transportation problems only
- No data layer (can't load CSV/Excel inputs)
- No model persistence (rebuild model every solve)
- No decomposition strategies (won't scale to large MILPs)
- No heuristics (exact solver only)

---

## 🔍 Critical Bottlenecks Identified

### 1. **No Data Layer** - MOST CRITICAL 🔴

**Problem**: Currently can only accept natural language input. Real OR problems use:
- CSV files with supply/demand/cost data
- Excel spreadsheets with multiple sheets (nodes, arcs, parameters)
- JSON/YAML configuration files
- Database queries

**Impact**:
- Can't integrate with real business systems
- Can't handle problems with 1000+ entities (typing them in text is impractical)
- No support for batch processing or automation
- Forces users to manually type problem data into text

**Example Use Case**:
```
User has: supply_chain_data.csv (500 plants × 2000 markets)
Currently: Must type "Plant 1 has capacity 500, Plant 2 has capacity 320..." (impossible)
Should be: "Load supply_chain_data.csv and optimize the distribution network"
```

**Solution Needed**:
- CSV/Excel loader that maps columns to problem parameters
- Schema inference (detect which columns are plants/markets/capacity/demand/cost)
- LLM-assisted mapping when ambiguous ("Is 'Factory' column the source or sink?")
- Support for multiple formats (wide vs long, nested vs flat)

**Files to Create**:
```
data/
  loaders/
    csv_loader.py         # CSV/TSV loading
    excel_loader.py       # Excel multi-sheet loading
    json_loader.py        # Structured JSON
  mappers/
    schema_detector.py    # Auto-detect parameter structure
    llm_mapper.py         # Use LLM to clarify ambiguous schemas
  validators/
    data_validator.py     # Check loaded data matches problem type
```

**Estimated Effort**: 2-3 days

---

### 2. **No Model Persistence** 🟠

**Problem**: Every time user runs analysis (sensitivity, what-if), we:
1. Rebuild the entire Pyomo model from scratch
2. Re-convert parameters to solver format
3. Re-create constraints and objective
4. Solve from scratch

**Impact**:
- Slow for interactive analysis (3-5 second delay per query)
- Wasteful for large models (rebuilding 10,000 variables each time)
- Can't do warm-starts (re-use previous solution as starting point)
- Memory inefficient (create/destroy model objects repeatedly)

**Solution Needed**:
- Cache compiled Pyomo model after first solve
- Only update changed parameters (capacity[i], demand[j], cost[i,j])
- Support warm-starts when solver allows it
- Invalidate cache when structure changes (new plants/markets added)

**Example**:
```python
# Current approach (SLOW):
for test_value in sensitivity_values:
    params['capacity']['Plant A'] = test_value
    model = build_model(params)  # ← Rebuild entire model
    solution = solver.solve(model)

# Better approach (FAST):
model = build_model(params)  # Build once
for test_value in sensitivity_values:
    model.capacity['Plant A'].value = test_value  # ← Just update parameter
    solution = solver.solve(model, warmstart=True)  # ← Re-use previous solution
```

**Files to Modify**:
- `solvers/transport/bipartite.py` - Add model caching
- `solvers/scheduling/single_stage_ipm.py` - Add model caching
- `analysis/sensitivity/engine.py` - Use cached model
- `analysis/scenarios/engine.py` - Use cached model

**Estimated Effort**: 1-2 days

---

### 3. **No Decomposition Strategy** 🟠

**Problem**: For large MILPs (100,000+ variables, 50,000+ constraints):
- Monolithic solve takes hours or runs out of memory
- GLPK/CBC can't handle industrial-scale problems
- No support for Benders decomposition, Dantzig-Wolfe, or column generation

**Impact**:
- Can't solve real-world problems (e.g., nationwide supply chain optimization)
- Locked into small-scale problems only
- Can't compete with commercial solvers (Gurobi/CPLEX have built-in decomposition)

**Solution Needed**:
- Auto-detect problem structure (is it decomposable?)
- Implement Benders decomposition for two-stage problems
- Implement Dantzig-Wolfe for block-diagonal structure
- Column generation for problems with exponential variables (VRP, cutting stock)

**Example Problems That Need Decomposition**:
- **Two-stage stochastic**: Decide plant locations (stage 1), then optimize flows (stage 2)
- **Multi-period planning**: Separate decisions by time period
- **Multi-commodity flow**: Decompose by commodity type
- **VRP with large fleet**: Generate routes on-demand (column generation)

**Files to Create**:
```
decomposition/
  structure_detector.py    # Detect if problem has decomposable structure
  benders.py               # Benders decomposition (master + subproblem)
  dantzig_wolfe.py         # Dantzig-Wolfe decomposition
  column_generation.py     # Column generation framework
```

**Estimated Effort**: 3-5 days (complex, but high impact)

---

### 4. **No Heuristics** 🟡

**Problem**: Only exact solvers available (GLPK, CBC). For large MILPs:
- Exact solve can take hours/days
- Often need "good enough" solution in minutes
- No support for metaheuristics (GA, SA, Tabu Search)
- No support for problem-specific heuristics (greedy, nearest neighbor)

**Impact**:
- Can't provide fast answers for time-sensitive decisions
- Can't handle very large problems (even with decomposition)
- No trade-off between solution quality and speed

**Solution Needed**:
- Implement metaheuristics framework
- Add greedy heuristics for common problems (transportation, assignment)
- LLM-based heuristic selection ("This is urgent, use fast heuristic")
- Hybrid approach: heuristic first for quick answer, exact solver in background

**Example Heuristics Needed**:
- **Transportation**: Vogel's approximation, Northwest corner rule
- **Scheduling**: Earliest Due Date (EDD), Shortest Processing Time (SPT)
- **VRP**: Clarke-Wright savings, sweep algorithm
- **General MILP**: Genetic Algorithm, Simulated Annealing

**Files to Create**:
```
heuristics/
  framework/
    base_heuristic.py       # Abstract base class
    metaheuristic.py        # GA, SA, Tabu Search
  transport/
    vogel.py                # Vogel's approximation method
    northwest_corner.py     # Northwest corner rule
  scheduling/
    priority_rules.py       # EDD, SPT, WSPT
  vrp/
    clarke_wright.py        # Savings algorithm
```

**Estimated Effort**: 2-4 days per heuristic family

---

### 5. **Hardcoded Analysis Framework** 🟡

**Problem**: Sensitivity/what-if/resolve only work for transportation problems
- Checks for 'plants', 'markets', 'capacity', 'demand'
- Won't work for scheduling (jobs, machines, processing_time)
- Won't work for knapsack, portfolio, facility location, VRP

**Impact**:
- Analysis features limited to transportation only
- Need to rewrite analysis code for each new problem type
- Not truly "problem-agnostic"

**Solution Needed**: (Already documented in diary as "Next Task")
- LLM-based parameter detection (detect which parameter to analyze from query)
- Generic instance creation (build ParsedInstance without hardcoding)
- Dynamic modification engine (apply changes to any parameter type)

**Status**: Detailed 5-phase plan already written in `Claude_Diary.md`

**Estimated Effort**: 5-7 hours (see diary for breakdown)

---

## 📊 Recommended Priority Order

### **Priority 1: Data Layer** (2-3 days) 🔴

**Why First?**
1. **Unblocks Real Usage**: Can't deploy to production without CSV/Excel support
2. **Foundation for Everything**: Decomposition/heuristics need data layer too
3. **High Visibility**: Users immediately see value ("I can load my spreadsheet!")
4. **Not Too Hard**: Mostly engineering, not research

**Implementation Steps**:
1. Create `data/loaders/csv_loader.py` with pandas-based CSV reading
2. Create `data/mappers/schema_detector.py` for auto-detecting parameter structure
3. Create `data/mappers/llm_mapper.py` for LLM-assisted ambiguous mapping
4. Update `agent/core.py` to accept file paths as input
5. Add tests with real CSV files (transportation, scheduling)

**Deliverables**:
- Users can run: `agent.solve_from_csv("supply_chain.csv", problem_type="TRANSPORTATION")`
- LLM asks: "Which column contains plant capacities?" if ambiguous
- Works with both wide format (plants × markets matrix) and long format (from, to, cost rows)

---

### **Priority 2: Model Persistence** (1-2 days) 🟠

**Why Second?**
1. **Immediate Performance Boost**: Sensitivity analysis 5-10x faster
2. **Easy to Implement**: Just cache the Pyomo model object
3. **Enables Interactive Analysis**: Users can iterate rapidly
4. **Foundation for Warm-Starts**: Needed for large problems

**Implementation Steps**:
1. Add `model_cache` dict to solver classes
2. Cache compiled model after first solve
3. Update only changed parameters instead of rebuilding
4. Add cache invalidation when structure changes
5. Benchmark performance improvement

**Deliverables**:
- Sensitivity analysis on 10 values: < 1 second (currently 5-10 seconds)
- What-if scenarios: instant feedback
- Memory efficient (only one model in memory)

---

### **Priority 3: Solver Strategy Selection** (2-3 days) 🟡

**Why Third?**
1. **Smart Routing**: Auto-choose exact vs heuristic vs decomposition
2. **User-Friendly**: "I need answer in 30 seconds" → automatically use heuristic
3. **Foundation for Heuristics**: Need strategy layer before implementing heuristics
4. **LLM Integration**: Use LLM to understand user's time/quality trade-offs

**Implementation Steps**:
1. Create `solvers/strategy/selector.py` for strategy selection
2. Add problem size estimator (variables, constraints, structure)
3. Implement decision rules (small → exact, large → heuristic, structured → decomposition)
4. LLM prompt to detect urgency ("I need this in 5 minutes" → heuristic)
5. Add strategy explanation ("Using greedy heuristic due to problem size")

**Deliverables**:
- Auto-detect: "This problem has 100,000 variables, using Benders decomposition"
- User control: "solve this quickly" vs "solve this optimally"
- Transparent: "Heuristic found solution in 30 seconds, exact solver would take 2 hours"

---

### **Priority 4: Decomposition** (3-5 days) 🟠

**Why Fourth?**
1. **Unlocks Large Problems**: Only way to solve industrial-scale MILPs
2. **Builds on Strategy Layer**: Need Priority 3 first to route problems correctly
3. **Differentiator**: Most open-source OR tools don't have decomposition
4. **Research Opportunity**: Can publish results, contribute to OR community

**Implementation Steps**:
1. Implement Benders decomposition for two-stage problems
2. Add structure detector (identify master/subproblem split)
3. Implement Dantzig-Wolfe for block-diagonal structure
4. Add column generation framework (for VRP, cutting stock)
5. Benchmark on large problems (10,000+ variables)

**Deliverables**:
- Solve two-stage stochastic problems with 100,000+ variables
- Multi-period planning with automatic time-period decomposition
- VRP with column generation (100+ vehicles, 1000+ customers)

---

## 🚀 Quick Wins (Do These Anytime)

### **Easy Improvements** (1-2 hours each):
1. **Add progress bars**: Show "Solving... 45% complete" for long solves
2. **Solution export**: Save solutions to CSV/Excel/JSON
3. **Visualization**: Plot flows, Gantt charts, network diagrams
4. **Better error messages**: "Plant 'Seattle' not found. Did you mean 'Seatle'?"
5. **Undo/Redo**: Track modification history, allow rollback
6. **Solution comparison**: "New solution is $500 cheaper (8% improvement)"
7. **2D parameter sensitivity**: Extend sensitivity to route costs, arc capacities, efficiency matrices (currently 1D only)

### **Nice-to-Haves** (1 day each):
1. **Web UI**: Flask/Streamlit interface for non-technical users
2. **Batch processing**: Solve multiple scenarios overnight
3. **Sensitivity reports**: Auto-generate PDF reports
4. **Constraint relaxation**: "Problem infeasible. Try relaxing demand by 10%?"
5. **Multi-objective**: Minimize cost AND minimize late deliveries

---

## 🎯 6-Month Roadmap

### **Month 1**: Data Layer + Model Persistence
- ✅ CSV/Excel loading
- ✅ Schema detection and LLM mapping
- ✅ Model caching for fast analysis
- ✅ Basic visualization

### **Month 2**: Solver Strategy + Greedy Heuristics
- ✅ Strategy selection framework
- ✅ Problem size estimator
- ✅ Greedy heuristics for transportation/scheduling
- ✅ Performance benchmarking

### **Month 3**: Decomposition (Benders)
- ✅ Benders decomposition implementation
- ✅ Structure detector for two-stage problems
- ✅ Benchmark on large problems

### **Month 4**: Decomposition (Dantzig-Wolfe + Column Gen)
- ✅ Dantzig-Wolfe for block-diagonal
- ✅ Column generation framework
- ✅ VRP solver with column generation

### **Month 5**: Metaheuristics
- ✅ Genetic Algorithm framework
- ✅ Simulated Annealing
- ✅ Tabu Search
- ✅ Hybrid exact+heuristic

### **Month 6**: Polish + Production
- ✅ Web UI
- ✅ Solution export and reporting
- ✅ Multi-objective optimization
- ✅ Documentation and examples

---

## 💡 Research Opportunities

### **Novel Contributions**:
1. **LLM-Driven Decomposition**: Use LLM to suggest decomposition strategy
2. **Adaptive Heuristics**: LLM learns which heuristics work best for user's problems
3. **Hybrid Solving**: Heuristic provides warm-start for exact solver
4. **Natural Language Constraints**: "Minimize cost BUT Plant A must serve at least 30% of Market X"

### **Potential Publications**:
- "LLM-Assisted Operations Research: From Natural Language to Optimal Solutions"
- "Adaptive Decomposition Strategies for Large-Scale MILPs"
- "Hybrid Heuristic-Exact Solving with Language Model Guidance"

---

## 🔑 Key Takeaways

### **Most Important Bottleneck**: Data Layer 🔴
- Blocks real-world usage
- Foundation for everything else
- High visibility, moderate effort
- **DO THIS FIRST**

### **Biggest Performance Win**: Model Persistence 🟠
- 5-10x faster analysis
- Easy to implement
- Immediate user impact
- **DO THIS SECOND**

### **Biggest Scale Unlock**: Decomposition 🟠
- Handle industrial-scale problems
- Differentiator from other tools
- Research opportunity
- **DO THIS AFTER DATA + PERSISTENCE**

### **Best Long-Term Investment**: Solver Strategy Layer 🟡
- Foundation for heuristics/decomposition
- Makes system truly adaptive
- LLM integration opportunity
- **DO THIS THIRD**

---

**Next Steps**: Start with Priority 1 (Data Layer) - create `data/loaders/csv_loader.py` and test with real supply chain CSV files.

---

# 🧪 Round-Trip Evaluation Plan (Added 2026-05-12)

## The wall we hit

The reason work paused on this project was not the data layer — it was **evaluation**. We could not measure whether a change to a prompt, model, or pipeline stage made the system better or worse. The only ground truth we had was 27 hand-curated problems in `tests/or_problem_repository.py`; that's too small to detect anything but huge regressions, and hand-writing more problems with full ground truth (classification + extracted params + optimal objective) does not scale.

## The idea: generate ground truth, don't curate it

Run the pipeline backwards. Start from params with a known optimum, verbalize them into natural language with an LLM, push the description through the agent, and check whether the agent recovers the same params (and same objective) we started with. No human labeling. Unlimited test cases. Closes the loop end-to-end.

```
generate_params(seed)
        │
        ▼
true_objective ◄─── solve(params)          ← ground truth, by construction
        │
        ▼
problem_text ◄────── verbalize(params)     ← LLM rephrases params as a problem
        │
        ▼
agent.solve_natural_language(problem_text)
        │
        ▼
{recovered_classification, recovered_params, recovered_objective}
        │
        ▼
compare ──► metrics: classification match, param recall, |Δ objective| / true_objective
```

## Scope (Phase 1 only — 1 day of work)

- **Transportation problems only** for the first cut. Scheduling extends naturally.
- **Bounded problem sizes**: 2–5 plants × 2–6 markets, capacities in [50, 1000], demands satisfying total ≤ total supply.
- **N = 100 generated problems** for the first run. Cheap enough to iterate, big enough to get sub-5% confidence intervals.

## Files to add (no edits to existing modules)

```
evals/
├── __init__.py
├── generators/
│   ├── __init__.py
│   ├── transport_generator.py    # produces feasible transportation param dicts
│   └── scheduling_generator.py   # Phase 2
├── verbalizer.py                 # params dict → natural-language problem text via LLM
├── round_trip.py                 # orchestrates one round-trip cycle
├── comparators.py                # param semantic-diff + objective-gap helpers
├── run_eval.py                   # CLI entry: `python -m evals.run_eval --n 100 --domain transport`
└── README.md                     # how to run, how to read results
```

## Component contracts

**`transport_generator.generate(seed) -> dict`**
- Returns a valid params dict the bipartite solver accepts (`plants`, `markets`, `capacity`, `demand`, `cost`).
- Guaranteed feasible (total supply ≥ total demand, all costs non-negative, every market reachable).
- Deterministic given seed (for reproducibility).

**`verbalizer.verbalize(params, style='neutral') -> str`**
- One LLM call (uses `EnhancedLLMClient` reasoning model).
- Returns a natural-language problem statement that *does not* leak structure (no JSON, no key names).
- `style` knob: `'neutral'`, `'formal'`, `'casual'`, `'noisy'` (with redundant info) — to test robustness later.

**`round_trip.run_one(seed, agent) -> RoundTripResult`**
- Returns dataclass with: `generated_params`, `true_objective`, `verbalized_text`, `recovered_classification`, `recovered_params`, `recovered_objective`, `param_recall`, `objective_gap`, `stage_latencies`, `error`.

**`comparators.param_recall(generated, recovered) -> float`**
- For each top-level key in generated (`plants`, `markets`, `capacity`, `demand`, `cost`), compute element-wise match within tolerance.
- Returns a single 0–1 score plus a per-key breakdown.

**`comparators.objective_gap(true_obj, recovered_obj) -> float`**
- `|true - recovered| / max(|true|, 1e-9)`. The headline metric.

## Reported metrics

- **Classification accuracy**: % of runs where `recovered_classification == 'TRANSPORTATION'`
- **Param recall**: mean per-key recall across runs, plus distribution
- **Objective gap**: median + 95th percentile of `|Δobj| / true_obj`
- **End-to-end pass rate**: % of runs where objective gap < 1%
- **Stage latency**: ms per (classify, extract, solve, explain)
- **Failure histogram**: counts of {JSON parse fail, classification miss, infeasibility, solver error, objective mismatch}

## Phase plan

- **Phase 1 — DONE (2026-05-13)** — transport generator + verbalizer + round-trip. Smoke (N=3): classification 100%, recall 1.0, objective gap 0.0. Caught a real `arc_capacity` bug in `feasibility/problem_specific/transport.py`. N=100 not yet run (qwen3:14b latency makes it a ~5 hr run; deferred until Phase 3 changes warrant it).
- **Phase 2 — DONE (2026-05-14)** — scheduling generator + classifier check via `--domain scheduling`. Smoke (N=3, seeds 1/2/3): classification 100%, recall 1.0, objective gap 0.0, agent latency ~200s/case on qwen3:14b. The scheduling generator stays minimal on purpose (full eligibility, no changeover, no time window) — extensions are Phase 3+ work. Phase 2 caught three real bugs:
    1. `llm/scheduling_specialist.py:60-63` — system prompt was an f-string with literal `{...}` JSON examples → `Invalid format specifier` at runtime.
    2. `feasibility/structural.py:150` — non-negative check didn't recurse into nested dicts, so `processing_time[order][unit]` was rejected as "not a finite number".
    3. `llm/enhanced_client.py:100` — extraction dispatch missed `PARALLEL_MACHINE_SCHEDULING` and `SINGLE_MACHINE_MAKESPAN` even though the classifier's fallback map routes both to the single-stage IPM solver. Agent classified correctly, then extraction returned "not yet supported".
- **Phase 3 (0.5 day)** — metamorphic transforms layered on the eval (`double all costs → objective doubles`, `permute plant order → objective unchanged`, `add unused plant → objective unchanged`). Adds invariant assertions without new ground truth.
- **Phase 4 (later)** — paraphrase the 27-problem seed set 10x via LLM, run pipeline on paraphrases, treat the original 27 as a human-curated holdout to spot the synthetic-vs-real gap.

## Known risks / open questions

- **LLM verbalization cost.** 100 round-trips ≈ 100 verbalize calls + 100 pipeline runs. With local Ollama at ~30s/pipeline, Phase 1 takes ~1 hr wall clock. Tolerable; cache verbalizations on disk by seed.
- **Generator realism.** Random uniform params produce toy problems that the system may handle better than real user inputs do. Mitigation: keep the 27-problem seed set as a held-out human benchmark. **Report both numbers — synthetic and seed — every time.**
- **Verbalizer leaking structure.** If the LLM verbalizer outputs JSON-like text, the extractor will look better than it actually is. Mitigation: assertion in `verbalizer.verbalize` that strips obvious structural cues (curly braces, key names, colons before numbers).
- **Feasibility-gated generation.** If a generated instance is infeasible at the solver step, drop it before round-tripping — those teach nothing about extraction quality.
- **Determinism vs. coverage.** Seeded RNG buys reproducibility but a fixed seed list will keep finding the same failure modes. Plan: 50% fixed seeds (regression set) + 50% rotating (exploration).

## What we are *not* doing yet

- Multi-stage / job-shop scheduling generation. Out of scope until the solver supports it.
- LLM-as-judge for explanation quality. Separate problem; not gated by this eval.
- Real CSV / Excel inputs (that's the Data Layer priority above, independent track).
- Fine-tuning anything. The point of the eval is to give us a number we can move; no model changes until we can measure.

## Definition of done for Phase 1

- `python -m evals.run_eval --n 100 --domain transport` runs end-to-end and produces a JSON report at `evals/results/transport_<timestamp>.json`.
- Report contains the six headline metrics listed above.
- At least one metric reveals a real issue (e.g., the JSON-parse-fail histogram bucket is non-zero) — i.e., the eval is sensitive enough to find bugs.

✅ Met on N=3 (3/3 pass; sensitivity demonstrated by the `arc_capacity` bug catch). N=100 deferred — cost outweighs marginal info until Phase 3 is in place.

## Definition of done for Phase 2

- `python -m evals.run_eval --domain scheduling --seeds 1,2,3` runs end-to-end on the local Ollama backend (qwen3:14b) and produces a JSON report at `evals/results/scheduling_<timestamp>.json`.
- Report shows non-zero classification accuracy and at least one seed passing end-to-end (recall = 1.0, objective gap < 0.01).
- Eval surfaces at least one real bug along the way.

✅ Met on 2026-05-14: 3/3 pass, three bugs caught (see Phase 2 list above).
- Result reproducible across runs given the same seed list.

---

# 📌 TODO (next after eval): Deploy a public REST API behind Cloudflare (Added 2026-05-13)

## Why this exists

The project needs to be visible at a URL for CV purposes. "Local GitHub repo" vs. "deployed REST API with N endpoints" is a meaningfully different signal for an AI-Specialist role; a reviewer with OR / ML hiring eyes will register the difference immediately. Goal is **a URL that exists**, not production-grade — weekend scope.

This goes ahead of the heuristic/warm-start TODO below. Heuristics are a research contribution; deployment is a recruiting artifact. Order: eval → deploy → heuristics.

## Scope (intentionally small)

- One public endpoint exposing the existing `OptimizationAgent.solve_natural_language` pipeline.
- One demo page / one curl example so the URL is meaningful when opened.
- Cloudflare in front for DNS + TLS + a free DDoS shield. No Cloudflare Workers (the pipeline needs Pyomo + GLPK + an LLM backend; Workers can't run any of that).
- Not in scope: auth, rate limiting beyond Cloudflare defaults, persistence, observability beyond basic logs.

## Architecture

```
user → Cloudflare DNS/TLS → VPS (small box) → FastAPI (api.py) → OptimizationAgent
                                              └─→ LLM backend  ← KEY DECISION
```

`api.py` and `fastapi` are already in the project; the pipeline can run inside an existing FastAPI app. The hard call is **how to serve the LLM** from a cheap host — see open questions.

## Concrete pieces to build

1. **Inventory and harden `api.py`.** Make sure `POST /solve` accepts `{"description": "..."}` and returns the same dict that `solve_natural_language` returns. Add `GET /health` and `GET /capabilities`. Trim anything that requires local files or shells out.
2. **Dockerfile.** Pyomo + GLPK + Python deps + the repo. Pin GLPK via apt. One container.
3. **LLM backend choice** (see open questions). Probably swap qwen3:14b for a cloud-hosted model the deployed instance can reach over the network. Add an `LLM_BACKEND=ollama|anthropic|openai|groq` env var; gate the existing `EnhancedLLMClient` factory on it.
4. **Host the container.** Cheap VPS (Hetzner CX22 €4/mo, Fly.io free tier with caveats, Railway, Render). Pick one — Hetzner is the lowest-friction for a Pyomo workload.
5. **Cloudflare wiring.** Point a subdomain at the host. Enable proxy ("orange cloud"). Use a Cloudflare-issued cert. Optional: Cloudflare Tunnel if you don't want to open ports on the box.
6. **Demo surface.** Either a tiny static HTML page calling the API from JS, or a one-line `curl` example in the README. The page version is more impressive at zero extra effort.

## Open questions

- **Which LLM backend?** qwen3:14b can't run on a €4 VPS. Realistic choices:
  - **Groq free tier** (Llama / Mixtral, fast, generous limits, no payment). Fits the budget; reliability over a CV-lifetime is the risk.
  - **Anthropic / OpenAI paid API** (~$2–10/mo at zero traffic). Most reliable; small monthly burn.
  - **Cloudflare Workers AI** (Llama, free quota). Ties nicely to the Cloudflare story but quality is lower than qwen3:14b.
  - **Self-host a 7B model on a beefier VPS** (€20–40/mo). Defeats the "weekend job" framing.
  - Recommended: Groq with an Anthropic fallback. Both behind a single `LLMClient` interface.
- **Cold start vs always-on.** Render/Fly free tiers sleep; Hetzner doesn't. Sleeping containers means a 30s first request, which looks broken in a demo. Pay €4 for always-on.
- **What happens when the LLM is the bottleneck.** Synchronous request takes 30–90s. Need either (a) a "this can take a minute" loading state in the demo page, or (b) async with a job ID. (a) is the weekend version.
- **Secrets.** API keys for the LLM provider must be env vars on the host, never in the repo. Standard, but worth stating.

## Definition of done

- A public URL (`https://<name>.<domain>`) responds 200 to `GET /health`.
- `POST /solve` with a natural-language transportation problem returns a valid solution dict.
- A linked demo page / curl one-liner exists in the repo README.
- Bullet on the CV stops being a lie.

---

# 📌 TODO (after deploy): Metaheuristic → MILP warm-start with interactive gap check

## The idea

For larger problem instances, exact MILP can be slow. A standard OR pattern is to run a fast metaheuristic first to get a good feasible solution, then hand it to the MILP solver as a **warm start (MIP start)** so the solver begins with a known upper bound and prunes the branch-and-bound tree aggressively.

Layer a user-facing checkpoint on top: tell the user the current optimality gap (best-found vs. LP relaxation lower bound) and let them decide whether to keep improving or accept the heuristic answer.

```
agent.solve_natural_language(text)
        │
        ▼
classify → extract → feasibility OK
        │
        ▼
metaheuristic.run(params) ──► heuristic_solution, heuristic_cost
        │
        ▼
solver.solve_with_warmstart(params, warm_start=heuristic_solution)
        │
        ▼
every K seconds / nodes:
  current_gap = (best_incumbent - best_bound) / best_incumbent
  if current_gap < target_gap (e.g. 1%):  done
  elif elapsed > soft_budget:
      → ask user:
        "Reached X% optimality gap in Y seconds.
         Heuristic baseline was Z% gap.
         (a) keep solving (estimated +T sec to close to 1%)
         (b) accept current solution (cost = $C)
         (c) accept heuristic baseline (cost = $H)"
```

## Why this is interesting for *this* project

- Already in roadmap: "Heuristics", "Decomposition", "Solver Strategy Selection" are all listed as future priorities (months 2–5). This TODO is the **glue** between them.
- Fits naturally into the existing follow-up handler — gap-check prompts are just another `follow_up_type` ("solver_progress_question").
- Forces the system to surface OR concepts (optimality gap, dual bound, incumbent) to a non-OR user in plain English — which is the entire project thesis.
- Plays well with the eval framework: round-trip eval can compare `heuristic_only` vs `heuristic+milp` vs `exact_milp_from_scratch` on the same instances. Three numbers, one chart.

## Concrete pieces to build

1. **`solvers/heuristics/`** — minimum viable: greedy + 2-opt local search for transportation, list-scheduling + swap moves for scheduling. ~150 lines each. No metaheuristic-framework dependency; hand-rolled is fine for Phase 1.
2. **`solvers/transport/bipartite.py`** — add `solve(params, warm_start=None)` so the MIP solver can accept a starting solution. For Pyomo+GLPK this means setting `model.x[i,j].value = warm_start[i,j]` before solve and passing `warmstart=True` to `SolverFactory.solve`. (GLPK warm-start support for MIPs is limited; may need to swap to HiGHS or CBC. Note this in the file.)
3. **`solvers/progress.py`** — wraps the solve call with a callback that records `(time, incumbent, bound, gap)` every K nodes. Pyomo callbacks are solver-specific; cleanest with HiGHS/Gurobi, hacky with GLPK.
4. **`agent/core.py`** — after `solver.solve(...)`, if elapsed > soft_budget and gap > target_gap, return a special status `"interim_solution"` with the gap data instead of a final result. The intent router treats user reply as `follow_up_type="solver_progress"`.
5. **`llm/follow_up_handler.py`** — new branch for `solver_progress`: surfaces gap numbers, asks the user (keep / accept / use heuristic), and routes back to `agent` with the decision.

## User-facing copy (draft)

> I've found a solution costing **$48,200**.
>
> The mathematical lower bound is **$45,800**, so this solution is at most **5.0% away from the theoretical optimum**.
> The heuristic baseline I started from was 11.2% away.
>
> Keep going to try to close the gap further? Each additional minute will shave roughly **0.5 percentage points** off the gap based on current progress.
>
> Reply: **continue**, **accept $48,200**, or **use the heuristic at $51,000**.

## Open questions

- **Target gap.** 1%? 5%? Should it be problem-type dependent? (Scheduling tolerates larger gaps than transportation in practice.)
- **Soft vs hard budget.** Soft = ask the user; hard = just stop. Plumbing both is cheap; UX of asking too often is real.
- **What if the heuristic is worse than nothing.** For tiny problems, MILP is faster than the heuristic. Need a problem-size threshold below which we skip the heuristic step entirely. The Solver Strategy Selector (Priority 3 in main roadmap) is the right place to gate this.
- **Solver swap.** GLPK has weak warm-start support for MIPs. HiGHS is the obvious upgrade and is open-source. Worth doing alongside this TODO.

## Definition of done

- For one solvable problem type (transport), the agent can: run heuristic → warm-start MILP → report incremental gap → accept user decision → return final answer.
- Eval framework can compare `heuristic_only`, `heuristic+milp`, `cold_milp` on the same 100 round-trip instances.
- README documents the new interactive checkpoint with one concrete example.

---

# 🔒 LOCKED PLAN (2026-05-14): Heuristic + warm-start, Phase 1 = transport

This is the consolidated plan after the design session on 2026-05-14. It supersedes
the open questions above. Implementation starts here.

## Goal

Give users a **fast feasible answer** quickly, then let them ask for the
**proven-optimal answer** via chat. Two-call protocol — no streaming.

## Why
- Exact MILP is slow on bigger instances → bad demo UX.
- Mirrors how a human OR consultant works: "here's a good plan now; if you want
  me to squeeze out the last 5%, I can run longer."
- Surfaces real OR concepts (gap, dual bound, incumbent) in plain English —
  that's the entire thesis of the project.

## Resolved design decisions

| Question | Decision | Why |
|---|---|---|
| Solver | **HiGHS everywhere** via Pyomo `appsi_highs`, drop GLPK | Proper MIP warm-start, faster on every benchmark, open-source |
| Interactive UX | **Two-call protocol** (`/solve` + `/continue`), no streaming | Simpler; live callbacks not needed |
| Progress callbacks | **Not used.** Pyomo post-solve metrics are enough | Two-call doesn't need mid-solve updates; avoids dropping to raw `highspy` |
| Heuristic algorithm (transport) | **Vogel's Approximation Method (VAM)** | Near-optimal on classic transport instances, well-known in OR, ~80 lines |
| LP relaxation | **Run on heuristic call** | Gives lower bound → "your quick answer is X% from optimum" framing |
| MILP time limit | **60s** | Phase 1 demo default |
| Gap target | **1%** | Industry standard "essentially optimal"; rarely matters below given noisy data |
| Job storage | **In-memory dict, UUID-keyed, 10-min TTL** | Phase 1 doesn't need durability; restart losing in-flight jobs is acceptable |
| Eval framework | **Untouched** — exact MILP only, no warm-start path | Ground-truth comparison must be deterministic; interim solutions would make `gap == 0.0` flaky |
| Heuristic tests | **New surface under `tests/`** (not `evals/`) | Separate concern from round-trip eval |
| Scope | **Transport first, scheduling reuses scaffolding** | De-risk on the easier domain (bipartite assignment) |

## Architecture

**Solver layer**
- `solvers/transport/bipartite.py` gains `solve(params, warm_start=None,
  time_limit=60, gap_target=0.01)`. When `warm_start` is given, populate
  `model.x[i,j].value` and call solve with `warmstart=True`.

**Heuristic layer (new)**
- `solvers/heuristics/transport_vam.py` — VAM implementation. Returns
  `(solution_dict, heuristic_cost)`.

**Bound layer**
- LP relaxation helper, solved on the heuristic call.

**API layer (`api.py`) — two-call protocol**
- `POST /solve` with `mode ∈ {heuristic, exact, heuristic_then_ask}`:
  - `heuristic`: VAM + LP bound → return solution + gap-vs-bound + `job_id`
  - `exact`: skip heuristic, run MILP to 1% gap or 60s
  - `heuristic_then_ask`: VAM result + chat prompt "improve / accept / stop?"
- `POST /continue` with `job_id` and `action ∈ {optimize, accept, use_heuristic}`:
  - `optimize`: warm-start MILP from stored heuristic, return final
  - `accept` / `use_heuristic`: terminal, return what we have

**Agent layer**
- `agent/core.py` `solve_natural_language` routes by mode.
- `IntentRouter` learns `follow_up_type="solver_progress"`.
- New reasoning prompt explains "1% optimality gap" to non-OR users.

## Implementation order (de-risked)

1. **Spike (1h)**: swap GLPK→HiGHS in existing transport solver, confirm
   warm-start round-trips end-to-end with a hand-crafted starting solution,
   confirm post-solve metrics report what we expect. **Gate**: if this fails,
   redesign before going further.
2. **VAM heuristic** in `solvers/heuristics/transport_vam.py` + unit tests on
   tiny instances with known optimum.
3. **`bipartite.py` warm-start parameter** + LP relaxation helper.
4. **Two-call API** in `api.py` + in-memory job store.
5. **Agent integration** in `agent/core.py` — mode routing + follow-up handler.
6. **LLM prompts** — intent classification for "improve/accept/stop", gap
   explanation in reasoning specialist.
7. **Heuristic test surface** under `tests/`.
8. **Demo pass** end-to-end: NL problem → heuristic → "improve" → optimum.

Then Phase 2 (scheduling) reuses the same scaffolding with LPT + swap moves.

## Explicitly NOT doing in Phase 1

- No streaming / SSE
- No live progress callbacks (no `solvers/progress.py`)
- No Redis / persistence
- No raw `highspy` calls
- No multi-objective, no constraint relaxation, no parallel runs
- No touching the eval framework's exact-MILP path

## Findings from spike + stress test (2026-05-14)

**Warm-start is gated on integer var presence.** Pure-LP transport (current
`bipartite.py`) does NOT benefit from primal warm-start — HiGHS dual simplex
from cold is consistently equal or faster than crashing a basis from a primal
solution. So `BipartiteTransportSolver.solve(warm_start=...)` auto-skips warm
seeding when no Integer/Binary vars are present.

**Where warm-start actually pays off:** MIPs. Spike on a fixed-charge transport
MIP showed 6.6× speedup (0.079s → 0.012s). Phase 2 scheduling (true MIP with
integer assignment vars) is where the warm-start narrative becomes the headline.

**VAM gap on random-cost instances is 10–45%, not the textbook "near-optimal."**
Random uniform costs have no exploitable structure. Real-world geographic
distance-based costs will produce tighter gaps. We surface the LP bound to the
user so the gap is always visible — no false claims.

**VAM perf:** numpy vectorized implementation runs at ~3s for 400×800 (was
~51s with pure-Python). On 800×1600 it's 28s — for very large pure-LP transport
HiGHS cold solve (24s) is actually slightly faster than VAM. This is expected
for pure LP; the two-call UX still has value (bound reporting, conversation
hook) but the *speedup* story belongs to Phase 2 MIP.

**Phase 1 transport story (refined):** the value isn't solver speedup. It's:
1. Interactive UX (heuristic answer → user reacts → optimize on demand).
2. LP bound visibility ("your quick answer is X% from optimum").
3. Plumbing that becomes load-bearing the moment we add fixed-charge transport
   or move to scheduling MIP.

## Phase 2 done (2026-05-14): scheduling heuristic + warm-start

Same scaffolding extended to single-stage IPM scheduling:

- `solvers/heuristics/scheduling_lpt.py` — LPT (Longest Processing Time)
  greedy assignment with eligibility + per-(order, unit) processing times +
  changeover-aware completion times. Produces a complete primal solution
  (assignment + sequence + completion + Cmax) suitable for warm-starting the
  MILP.
- `solvers/scheduling/single_stage_ipm.py` swapped from GLPK to HiGHS; accepts
  `warm_start`, `time_limit`, `gap_target`. Warm-start seeds every Y, XX, C,
  and Cmax. Same `_model_has_integer_vars` gate as transport — passes here
  because the scheduling model IS MIP.
- `agent/heuristic_handler.py` dispatches to scheduling when the classifier
  returns `SCHEDULING` / `SINGLE_STAGE_SCHEDULING` / `PARALLEL_MACHINE_SCHEDULING`
  / `SINGLE_MACHINE_MAKESPAN`.
- 6 new unit tests under `tests/test_heuristics_scheduling.py` cover
  feasibility, eligibility-respect, warm-start matching cold MILP, LPT as
  upper bound, and changeover handling.

**Scheduling warm-start payoff (random adversarial instances):**

| Size | Cold MILP | Warm MILP | LPT Cmax | Optimal Cmax |
|---|---|---|---|---|
| 6 orders × 3 units | 87ms | 63ms (1.38×) | 16.0 | 16.0 |
| 10 orders × 3 units | 1.2s | 1.2s (1.0×) | 18.0 | 15.0 |
| 12 orders × 4 units | >30s | >30s (1.0×) | 16.0 | 14.0 |

At 12×4 both runs hit the time limit without proving optimum. The IPM
formulation has O(n² × m) precedence variables so problems blow up quickly;
on adversarial random instances the warm-start doesn't reliably accelerate the
proof. Real structured scheduling instances (industrial workloads with
exploitable due-date / changeover patterns) typically benefit more.

**LP relaxation for scheduling is stubbed** — `solve_lp_relaxation` returns
`NOT_IMPLEMENTED`. Adding it requires factoring `build_model` out of `solve`.
For Phase 2 MVP we omit the bound from the chat response and rely on the
heuristic Cmax as the headline number plus the exact solver's
`best_objective_bound` after `/continue optimize`.

---

# 🔖 Picking up next session (2026-05-14 EOD)

## Where we are
Commit `3536a83` on `origin/main` (= `apostoliselekidis-star/Optimization-AI-`).
Old aragorn67 remote preserved as `aragorn`.

Phase 1 + Phase 2 of the locked plan are shipped. 83 tests passing. The
warm-start payoff finding turned out to be honest-but-mixed: real on
fixed-charge transport MIP (6.6×), absent on IPM scheduling (~1×). Both
documented in `ANALYSIS.md`.

## Chosen next step
**End-to-end demo with Ollama** — finish task #8 from the original plan.
Drive the full /solve mode=heuristic_then_ask → /chat/continue flow with
qwen3:14b classifying and extracting from a real NL transport problem.

## Demo plan (already prepared, just needs to run)

1. Verify Ollama up: `curl -sf http://localhost:11434/api/tags`
2. Start API with explicit backend (shell may still have `LLM_BACKEND=groq`
   exported — must override):
   ```bash
   LLM_BACKEND=ollama ./Tolis_Env/bin/uvicorn api:app \
       --host 127.0.0.1 --port 8765 --log-level warning &
   ```
3. Run the demo: `./Tolis_Env/bin/python demos/heuristic_two_call_demo.py`
4. Capture clean output, paste into README and/or ANALYSIS.md as the
   headline demo.
5. If the LLM stumbles on the NL prompt (qwen3:14b sometimes classifies oddly),
   tighten the prompt phrasing — the demo script's `PROBLEM` constant is a
   good starting point but may need tweaks.

## Options NOT taken this session — for the backlog

- **Fixed-charge transport MIP solver.** Add binary "use this arc" + Big-M
  to bipartite. Half-day. Makes the warm-start speedup story load-bearing
  (6.6× in the original spike). This is the strongest demo unlock.
- **Tighter scheduling formulation.** Replace IPM with positional or
  time-indexed. 1-2 days; rewrite of `solvers/scheduling/single_stage_ipm.py`.
  Would either rescue the scheduling warm-start story or confirm the
  finding is solver-agnostic.
- **Eval Phase 3 (metamorphic transforms).** Double costs → double
  objective, permute plants → same objective, etc. Half-day. Hardens the
  test surface; doesn't extend capabilities.
- **LP relaxation for scheduling** (stubbed today). Requires factoring
  build_model out of solve(). Small but useful — gives the user a bound
  on Cmax during the heuristic call.

## Open environmental note

The shell at session end had `LLM_BACKEND=groq` exported, which silently
broke the demo earlier. Permanent fix: `unset LLM_BACKEND` in the shell
profile so the in-code default (Ollama) wins. Per-command override works
in the meantime.

---

# 🔖 DEMO ROADMAP (approved 2026-05-15) — interactive demo, 1–2 day scope

User-approved plan. Demo in 1–2 days. **In scope:** conversational polish,
live progress, latency/structured input, graceful NL fallback.
**Deferred:** NL constraint editing (#1), artificial-problem testing (#3).

## Item list (user requests, this session)

1. (DEFERRED) Change constraints/objectives in NL after a solve — needs a
   re-extract/re-solve loop; too risky to land unstably 2 days pre-demo.
2. Excel / database as input.
3. (DEFERRED) Large-scale + artificial OR problems for classification.
4. Investigate time bottlenecks (the ~147s `/solve` blocking call).
5. After each solution, offer options to continue the discussion.
6. App exports the result as an Excel file.
7. App shows its progress live (esp. for the demo).
8. Better understand user language (e.g. "pareto front" currently
   dead-ends with a raw `CUSTOM_REVIEW` error).

## Key grounding discoveries (cheaper than feared)

- **#7 is not a refactor.** `agent/core.py` already emits stages via
  `update_progress("Analyzing problem type...", 15)` →
  `"Identified as X"` (25) → `"Extracting parameters..."` (40). The hooks
  exist; Phase 1 only surfaces them through the API/UI.
- **#8: Pareto already works — as a follow-up.** Full `analysis/` module
  (`analysis/router.py`) wired into `agent/core.py:628` handles
  `sensitivity / what_if / resolve / pareto` *after* a solve. The bug is a
  first-message routing gap: no solver → `solver_id == "none"` → hard
  dead-end at `core.py:145`. Fix = route/explain, not build a solver.

## Phases (each independently demoable; commit after each)

- **Phase 0 — prereqs (~15 min):** commit current uncommitted work
  (fixed-charge MIP, UI, `fixed_cost` extraction) on a branch; verify
  `openpyxl` / `pandas` in `Tolis_Env`, add if missing.
- **Phase 1 — live progress backbone (#7, #4 dead-air):** refactor
  `/solve` to job + poll; surface existing `update_progress` stages via
  `GET /jobs/{id}/status`; `chat.html` shows a live pipeline checklist
  instead of one spinner. Biggest single demo win; lands first because
  the rest rides on the job model.
- **Phase 2 — conversational polish (#5, #8, #6):** every response carries
  `next_options` → clickable chips. Replace dead-ends with a friendly
  explanation + supported-type chips; detect analysis-intent first
  messages via `analysis/router.py` and respond conversationally. Excel
  result export via `GET /jobs/{id}/export.xlsx` (openpyxl).
- **Phase 3 — latency + structured input (#4, #2):** profile classify vs
  extract vs solve (Phase 1 already exposes per-stage timing); log to
  ANALYSIS.md. `POST /solve/file` (multipart `.xlsx`) → pandas parser →
  params → solve, skipping both qwen3 calls (~147s → ~1s). The
  spreadsheet path is the "instant" demo lane.

## Cut order if time runs short

Phase 1 (must-have) → Phase 2 → Phase 3. Phase 1 alone transforms the demo.

## Status at log-off (2026-05-15)

Map approved and recorded. **Nothing built yet** — next session starts at
Phase 0. Session work prior to this (fixed-charge MIP + UI + extraction)
is still uncommitted; Phase 0 commits it first.

---

# 🔖 Status update (2026-05-16) — read this first next session

Significant progress since the 2026-05-15 roadmap. Updated map below.

## Shipped this session (2026-05-16)

- **Roadmap #8 — fully done.** Free-text what-if / sensitivity / resolve /
  pareto follow-ups now re-solve and answer. Highlights:
  - `follow_up_on_job()` answers what-ifs against a *pending*
    heuristic_then_ask job without consuming it; `/chat/continue` falls
    back to it instead of dead-ending on non-action messages.
  - Fixed a latent bug: `_handle_follow_up_analysis` used the problem-type
    *category* as a solver_id → always raised "Unsupported solver_id".
  - Infeasible what-ifs return plain-language "why + how to fix", not a
    cryptic "failed at layer N".
  - Perf: keyword-only analysis-type detection in the routing gate, type
    passed downstream — a what-if dropped from **3 qwen3 calls to 1**.
- **Fixed-charge heuristic gap bug fixed.** Heuristic cost now includes the
  fixed charge on every opened route (was variable-only → understated cost
  → negative gap surfaced as a garbage ~9% gap).
- **Demo deliverables built** (`deliverables/`): Overview PDF (exec summary
  **+ technical deep dive + assumptions + future work**), Windows run guide
  PDF, demo video (mp4 + webm source), HTML sources.
- **setup.bat fixed** (qwen3:14b, no GLPK, fixed step numbering/doc refs).
- Tests: `test_followup_whatif.py` (6) + fixed-charge heuristic regression
  in `test_heuristic_two_call.py`; suites green. ANALYSIS.md updated.
- **Commit message prepared but NOT committed** — work still uncommitted on
  `main` (feature + 3 fixes + deliverables + setup.bat + ANALYSIS.md).

## Roadmap status

| Phase | State |
|---|---|
| Phase 0 — commit + deps | Commit msg ready, **not committed**. `openpyxl`/`pandas` **still missing** in `Tolis_Env` |
| Phase 1 — live progress (job+poll UI) | **Not started.** Still the biggest demo win; everything rides on the job model |
| Phase 2 — conversational polish | #8 **done**; remaining: first-message analysis-intent dead-end (`core.py:145`), #5 continuation chips (`next_options`), #6 Excel export |
| Phase 3 — Excel fast path + latency profiling | Not started |

Cut order unchanged: **Phase 1 → Phase 2 → Phase 3**.

## Next session starts here (loose ends, in order)

1. **Commit** the uncommitted work (message ready; on `main` — consider a
   branch; decide on committing the `deliverables/` binaries vs gitignore).
2. **Phase 0 deps:** `pip install openpyxl pandas` into `Tolis_Env`
   (blocks all Excel work in Phase 2/3).
3. **Phase 1 (recommended primary):** refactor `/solve` → job + poll,
   surface existing `update_progress` stages via `GET /jobs/{id}/status`,
   live pipeline checklist in `chat.html`.
4. **Phase 2 remainder:** fix the first-message analysis-intent dead-end
   (`solver_id == "none"` → hard stop at `core.py:145`; route/explain
   instead); add #5 continuation chips; #6 `GET /jobs/{id}/export.xlsx`.
5. **Phase 3:** `POST /solve/file` (.xlsx → params → solve, skips both
   qwen3 calls) + per-stage latency profiling to ANALYSIS.md.

## Update — Phase 1 DONE (2026-05-16, later same day)

Phase 1 (live progress) shipped: `agent/progress_store.py`,
`POST /jobs` + `GET /jobs/{run_id}`, live pipeline checklist in
`chat.html`. `POST /solve` kept sync for back-compat. 5 tests in
`test_progress_jobs.py`; smoke-verified stages stream live. **Uncommitted.**

Revised loose-end order next session:
1. Commit (brainstorm status edits + Phase 1: progress_store/api/chat.html
   + test_progress_jobs.py + ANALYSIS.md).
2. **Phase 2 remainder** (now primary): first-message analysis-intent
   dead-end at `core.py:145` (route/explain instead of hard stop); #5
   continuation chips (`next_options`); #6 `GET /jobs/{id}/export.xlsx`
   (openpyxl/pandas now installed).
3. **Phase 3:** `POST /solve/file` (.xlsx → params → solve, skips both
   qwen3 calls) + per-stage latency profiling to ANALYSIS.md.

## Update — Phase 2 dead-end DONE (2026-05-16, later same day)

First-message analysis-intent dead-end fixed: new
`_analysis_needs_baseline` returns a conversational guide instead of the
`core.py` "not supported"/"extraction failed" hard stops; `chat.html`
renders no-solution responses plainly. 7 tests in
`test_first_message_analysis.py`; live smoke-verified. **Uncommitted**
(stacks on the still-uncommitted Phase 1 work).

## Update — Phase 1+2 + deliverables, COMMITTING (2026-05-16, end of session)

Done & being committed this session (one commit, code + docs + binary PDF):
Phase 1 live progress, Phase 2 first-message dead-end, deliverable PDF
overhaul (Tolaros removed; +feasibility-gate / three-approaches-classifier
/ warm-start sections), forgotten-subsystem audit (`ML_RAG_archive/`,
`or_classify/` → memory + ANALYSIS.md). 32/32 tests green.

## Update — Phase 2 #5 + interactivity pass DONE (2026-05-17)

#5 continuation chips done **and scope-expanded** (user: "make the chat
box more interactive", picked all 4 options):
- `build_next_options(result)` in `agent/core.py` — pure fn, result→chips;
  applied at one API chokepoint (`_with_options`) so every path
  (sync/async/continue/chat) carries `next_options`. 8 states verified.
- Persistent toolbar in `chat.html` (New / Help / 2 examples) — never
  stuck even with no chips.
- Client-derived chips: quick what-ifs synthesised from real
  `extracted_params` (e.g. "🔻 P1 capacity −20%"), Show table,
  Explain more.
- #6 folded forward as `POST /export/xlsx` (takes the payload the chat
  already holds → workbook; sidesteps the job-store TTL of the planned
  GET-by-id form). Summary + Flows/Schedule + Parameters sheets;
  TestClient-verified for transport & scheduling.
Zero regressions: new logic green; the only suite reds
(`test_default_config`, classification errors, full-run-ordering
`test_feasible_us_manufacturing`) all pre-exist on a clean tree.
**Uncommitted.**

**RESUME POINT — "lets continue" picks up here:**
1. Commit this interactivity pass (core.py/api.py/schemas/chat.html +
   ANALYSIS.md + brainstorm).
2. Live smoke in the browser (chips click-through, export download) —
   only static review done so far, no running-server check.
3. Phase 3: `POST /solve/file` (.xlsx → params → solve) + per-stage
   latency profiling to ANALYSIS.md.
4. *Optional micro-opt:* move keyword analysis check before
   `detect_intent` so the bare-what-if path is fully LLM-free.

## Agentic roadmap — on-thesis only (added 2026-05-17)

Governing constraint: the LLM **routes to published/validated OR models
and builds on them; it never invents the formulation**. Open-ended LLM
model-construction ("#1") is **rejected as off-thesis**, not deferred.
Endorsed agentic upgrades must stay inside the validated-model envelope.

**A2 — Multi-stage decomposition (composer over the solver registry).**
Decompose a compound request (e.g. "design my supply chain") into a
*per-request sequence of EXISTING registered solvers* (location →
transport → scheduling), wiring each stage's output into the next. The
LLM chooses which registered solvers and in what order — never writes
math. Agentic pattern: plan-and-execute over the registry; each node is
a provably-correct solver. *Off-thesis tripwire:* a stage needing a
model not in the registry → stop and tell the user, do not synthesise.

**A3 — Autonomous infeasibility repair (within a known formulation).**
Replace the capped 3 deterministic retries with an LLM reason→edit→
re-check→revise loop (Reflexion-style) that proposes edits to the
*parameters / toggleable constraints of the already-selected model*
(relax a bound, drop an optional constraint, flag a contradiction). Same
envelope as today's loop, better convergence. *Off-thesis tripwire:*
repair that requires a structurally different / unregistered model →
escalate to the user, do not reformulate.

Both are real "remove the hard ceiling" items and are the next agentic
direction after the deterministic backlog (Phase 3) is closed. See
memory `project_design_thesis` for the rationale and the tripwire rule.
