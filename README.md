# OR Agent

An LLM-driven operations-research agent. Takes a natural-language description of an optimization problem, classifies the problem family, extracts parameters into a structured schema, runs a deterministic solver, and explains the result.

## What it does

Given a prose problem statement such as:

> *"Boston can supply up to 1200 units and Phoenix can supply 700 units. Rome needs 350 units, Berlin needs 400 units, and Tokyo needs 250 units. Shipping from Boston to Rome costs $2.50 per unit, ..."*

the agent:

1. Detects intent (new problem vs. follow-up vs. small talk).
2. Classifies the problem family (transportation, scheduling, ...) using a JSON-schema-bound classifier with majority voting.
3. Routes to the matching specialist extractor, which converts prose to a typed parameter dict.
4. Runs a three-layer feasibility check (structural → problem-specific necessary conditions → solver-based LP relaxation) before invoking the solver, so hallucinated parameters do not silently corrupt the result. The gate is **fail-closed** — an inconclusive layer returns `UNKNOWN`, never a guessed "feasible" — and **domain-general**: each problem family registers one `FeasibilityPlugin` bundling its checker and repair-suggestion generator, so a domain cannot be half-wired and Layer 2 is conclusive for both transportation and scheduling.
5. Solves with Pyomo + HiGHS and returns the objective value, flows, and KPIs.
6. Generates a plain-language explanation of the solution.

Follow-up questions ("what if Boston's capacity drops by 30%?", "show me a sensitivity analysis on freight cost") are handled in-context against the previous solution.

## Architecture

```
natural language input
        │
        ▼
┌──────────────────────────┐
│  IntentRouter            │ smalltalk / help / follow-up / new
└──────────────────────────┘
        │ (new problem)
        ▼
┌──────────────────────────┐
│  ProblemClassifier       │ N-vote majority, JSON-schema bound
└──────────────────────────┘
        │
        ▼
┌──────────────────────────┐
│  Specialist extractor    │ TransportationSpecialist | SchedulingSpecialist
└──────────────────────────┘
        │
        ▼
┌──────────────────────────┐
│  Feasibility (3 layers)  │ structural → per-domain plugin → LP relaxation (fail-closed)
└──────────────────────────┘
        │ (feasible)
        ▼
┌──────────────────────────┐
│  Solver (Pyomo + HiGHS)  │ bipartite transport | single-stage scheduling
└──────────────────────────┘
        │
        ▼
┌──────────────────────────┐
│  Explanation (LLM)       │ summary + grounded units + chart hooks
└──────────────────────────┘
```

The LLM layer uses an abstract `LLMClient` interface so providers are swappable. The current backend is local Ollama with `qwen3:8b` across all stages (selected over `qwen3:14b` by the model sweep — see *Baseline vs. system* below); the same interface is designed to accept Anthropic, OpenAI, or other remote-API backends.

## Quickstart

Requirements: Python 3.10+, a running [Ollama](https://ollama.com) instance with a chat model available. The solver (HiGHS) is pulled in via the `highspy` wheel — no external binary required.

```bash
# 1. clone and set up the environment
git clone https://github.com/aragorn67/or-agent.git
cd or-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. pull the LLM (default model across all stages)
ollama pull qwen3:8b

# 3. one-shot solve from Python
python -c "
from llm.enhanced_client import EnhancedLLMClient
from agent.core import OptimizationAgent

text = '''
Plant A can supply 500 units and Plant B can supply 600 units.
Customer X needs 300 units and Customer Y needs 400 units.
Shipping A to X costs 2 per unit, A to Y costs 3, B to X costs 4, B to Y costs 1.
Minimise total shipping cost.
'''
agent = OptimizationAgent(EnhancedLLMClient())
result = agent.solve_natural_language(text)
print(result['solution']['objective_value'])
print(result['summary'])
"
```

Per-stage models can be overridden via env vars:

```bash
CLASSIFICATION_MODEL=qwen3:8b EXTRACTION_MODEL=qwen3:14b REASONING_MODEL=qwen3:14b python ...
```

### REST API

A FastAPI server is included. Primary endpoints:

- `POST /solve` (alias `POST /solve/natural`) — accepts `{"description": "...", "mode": "exact|heuristic|heuristic_then_ask"}`. Default mode is `exact`.
- `POST /continue` — `{"job_id": "...", "action": "optimize|accept|use_heuristic"}` resumes a job started in heuristic mode.
- `POST /chat/continue` — same as `/continue` but accepts a free-text `message` ("make it better", "good enough") that is mapped to an action.

Auxiliary: `GET /health`, `GET /capabilities`, `POST /agent/classify`. A solved payload can be exported via `POST /export/csv` (flat decision table — flows or schedule), `POST /export/json` (lossless), or `POST /export/xlsx`.

```bash
uvicorn api:app --host 0.0.0.0 --port 8000

# Then, from another shell:
curl -s -X POST http://localhost:8000/solve \
  -H "Content-Type: application/json" \
  -d '{"description": "Two plants Seattle (cap 350) and San Diego (cap 600) ship to New York (demand 325), Chicago (demand 300), Topeka (demand 275). Distances in thousand miles — Seattle: NY=2.5, Chicago=1.7, Topeka=1.8. San Diego: NY=2.5, Chicago=1.8, Topeka=1.4. Freight $90 per case per thousand miles. Minimise total shipping cost."}'
```

The LLM backend is local **Ollama** (qwen3:8b across stages by default). Override per-stage models via `CLASSIFICATION_MODEL` / `EXTRACTION_MODEL` / `REASONING_MODEL`, and the Ollama host via `OLLAMA_HOST`.

A `Dockerfile` is included for hosted deployment (still backed by Ollama). For a zero-cost demo the API can be exposed publicly with [`cloudflared`](https://github.com/cloudflare/cloudflared) without any VPS:

```bash
cloudflared tunnel --url http://localhost:8000   # yields an ephemeral https://*.trycloudflare.com URL
```

### Interactive heuristic + warm-start

Larger optimization instances can be slow if the exact MILP runs to optimality. The two-call protocol gives the user a fast feasible answer first, then lets them opt in to the proven-optimal answer:

```bash
# 1. Quick answer: VAM heuristic + LP relaxation bound + prompt
curl -s -X POST http://localhost:8000/solve -H 'content-type: application/json' \
  -d '{"description": "...transport problem...", "mode": "heuristic_then_ask"}'
# → returns {job_id, solution (heuristic), best_bound, gap, follow_up_prompt}

# 2. Free-text reply maps to action (parser handles "make it better", "good enough", etc.)
curl -s -X POST http://localhost:8000/chat/continue -H 'content-type: application/json' \
  -d '{"job_id": "<UUID from step 1>", "message": "can you make it better"}'
# → warm-starts the exact solver from the heuristic; returns proven-optimal answer.
```

Heuristic mode is currently supported for transportation (Vogel's Approximation Method). The warm-start path is gated on integer variables — pure-LP transport just solves cold; the speedup payoff lands on MIP problems such as scheduling.

## Evaluation

Evaluating an LLM pipeline against a small hand-curated test set only catches large regressions. This repository ships a round-trip evaluation framework under [`evals/`](evals/) that generates ground truth synthetically:

```
generate_params(seed)
        │
        ▼
true_objective ◄── solver.solve(params)         (ground truth, by construction)
        │
        ▼
problem_text ◄── verbalize(params, llm)         (LLM rephrases params as prose;
        │                                        leakage + coverage checks gate output)
        ▼
agent.solve_natural_language(problem_text)
        │
        ▼
{recovered_classification, recovered_params, recovered_objective}
        │
        ▼
compare → classification accuracy
        → per-key param recall
        → |Δobjective| / true_objective
        → end-to-end pass rate
        → stage latency
        → failure histogram
```

Run it:

```bash
python -m evals.run_eval --domain transport  --seeds 1,2,3   # transportation
python -m evals.run_eval --domain scheduling --seeds 1,2,3   # single-stage scheduling
python -m evals.run_eval --n 20                              # 20 fresh seeds, transport
```

The framework writes a timestamped JSON report under `evals/results/` containing the six headline metrics.

**System results (default `qwen3:8b`, local Ollama, n=3 seeds):**
- *Transportation* — classification accuracy 1.00, mean parameter recall 1.00, median objective gap 0.00, end-to-end pass rate 1.00.
- *Single-stage scheduling* — classification accuracy 1.00, mean parameter recall 1.00, median objective gap 0.00, end-to-end pass rate 1.00.

The framework has already paid for itself during development by surfacing four real bugs the existing hand-curated test set had missed: one feasibility-checker bug on the transport side, plus three on the scheduling side (an f-string format-spec crash in the scheduling extractor's system prompt, a non-recursive non-negativity check that rejected nested `processing_time` dicts, and an extraction-dispatch list that lagged behind the classifier's solver mapping).

Caveat: synthetic random problems with feasibility margins built in are the easy end of the input distribution. The harder end is covered by a **real-data correctness gate** (`evals/smoke_real_data_benchmark.py`) that runs the full NL pipeline over 57 hand-curated problems in `tests/or_problem_repository.py` — published textbook instances (Winston, Hillier, Wolsey) alongside out-of-scope and infeasible cases. It is a *gate*, not a smoke test: every solvable problem must classify to the right solver family, solve, and match its **independently-published optimum at 0.00% gap** (Powerco $1{,}020$, P&T $\$152{,}535$, Hillier 12.6-8 setup $36$); every out-of-scope problem must be refused for the right reason; the harness halts on any violation. Latest run: **57/57**.

## Baseline vs. system

Design decisions here were made by evaluation, not intuition — including rejecting things that did not earn their complexity. Every number below comes from a run recorded in `ANALYSIS.md`.

| Question | Baseline | This system | Decision |
|---|---|---|---|
| Parameter extraction: retrieval-augmented vs. direct | RAG ≈ **50%** accuracy (+ higher latency) | JSON-schema-bound LLM, no RAG ≈ **70%** | RAG **rejected** on evidence |
| Classification: learned vs. LLM | RandomForest on real OR ≈ **44%** | JSON-schema LLM + N-vote majority ≈ **70%** | Learned classifier **rejected** |
| Default model | `qwen3:14b` | `qwen3:8b` — identical accuracy at n=3 both domains, **~2× faster** | Default **flipped** to 8b; `qwen2.5:7b` rejected (transport recall 0.90 → fails) |
| Heuristic→MILP warm-start | cold solve | warm solve | **Honest negative**: ~1.00–1.02× on pure-LP and IPM (the headline "6.6×" was one non-representative instance) — kept for the interactive UX + LP bound, *not* claimed as a speedup |
| Feasibility before solve | solver raises on infeasible | 3-layer fail-closed gate | Plain-language reasons + suggestions; no false-feasible |

## Failure analysis

Where the system has broken, why, and what fixed it (full detail in `ANALYSIS.md`):

- **Silent transport-only degradation.** The post-solve stack (modification parse/apply, feasibility, suggestions) was written for transport and *silently* mis-handled scheduling — at worst returning a confidently-wrong *feasible* answer (€8) for an infeasible schedule. Fix pattern throughout: explicit per-domain dispatch + "unhandled ⇒ surface it, never silently pass".
- **Fail-open feasibility default.** Layer-2 `UNKNOWN` was mapped to `FEASIBLE` "if Layers 0–1 pass" — a latent false-feasible for any domain without a Layer-1 check. Now fail-closed (`UNKNOWN`), with the hardened solver as backstop.
- **LLM structured-output footguns.** `qwen3`/`deepseek-r1` emit `{}` instantly under Ollama `format=json` (never set it for those). Documented as a guardrail, not a one-off patch.
- **Expected-but-absent speedup.** Warm-start was assumed to accelerate every solve; measured null on the current formulations. Reported honestly rather than cherry-picked.
- **Two silent correctness bugs, caught by the gate not by hand-testing.** Hardening the real-data benchmark from "a number came out" into an *enforced* correctness gate immediately surfaced (a) a transshipment network being *solved* as bipartite transport — a model that cannot represent it — returning a confidently-wrong answer instead of refusing, and (b) the scheduling NL path unable to solve its own published anchor (the pure sequence-dependent-setup data had no extraction route). Both fixed. The lesson: make the eval *enforce* the answer, not just check that one exists.

## Project status

**Works today:**
- Bipartite single-commodity transportation (Pyomo + HiGHS)
- Single-stage scheduling (IPM-based makespan)
- Three-layer feasibility gate — fail-closed and domain-general (`FeasibilityPlugin` per family; Layer 2 conclusive for both transportation and scheduling), with plain-language reasons + repair suggestions and a curated per-layer infeasible corpus (`tests/test_infeasible_corpus.py`)
- Sensitivity / what-if / re-solve follow-up analysis on transportation
- Round-trip eval framework for both transportation and single-stage scheduling
- Interactive heuristic + warm-start (VAM for transport) with LP bound reporting and a two-call API protocol (`/solve mode=heuristic_then_ask` → `/chat/continue`)
- Solution export to CSV / JSON / xlsx (REST endpoints + chat-UI chips)

**On the roadmap** (see [`agenda.md`](agenda.md) for detail):
- Metamorphic transforms layered on the eval (double-costs → double-objective, permute plants → same objective, etc.)
- Scheduling heuristic + warm-start (LPT for makespan) — same scaffolding as transport, where MIP warm-start delivers real speedup
- CSV/Excel data loaders
- Decomposition strategies (Benders, Dantzig-Wolfe) for large MILPs

**Investigated and not adopted:**
- Retrieval-augmented generation for parameter extraction. Evaluated against the baseline on a 10-problem held-out set; accuracy regressed (≈70% → 50%) and latency increased. Experiments archived under `ML_RAG_archive/`.
- A learned classifier (rule-based labeling functions + supervised model) underperformed the JSON-schema-bound LLM classifier with majority voting. Archived under `ML_RAG_archive/`.

## Repository layout

```
agent/                    Top-level orchestrator (OptimizationAgent.solve_natural_language)
llm/                      LLMClient interface + EnhancedLLMClient multi-stage pipeline
                          and per-domain specialists for extraction
solvers/                  Solvers registered against a common OptimizationSolver base
   transport/             Bipartite transportation
   scheduling/            Single-stage scheduling
feasibility/              Three-layer feasibility checker
   problem_specific/      Necessary-condition checks per problem family
analysis/                 Sensitivity, what-if, and re-solve engines
evals/                    Round-trip evaluation framework (see Evaluation above)
tests/                    pytest suite covering classification, feasibility,
                          infeasibility handling, and normalizer
api.py                    FastAPI server exposing the agent over HTTP
agenda.md                 Forward plan / TODO list (priority + details)
archive/ ML_RAG_archive/  Prior approaches kept for reference (see "not adopted")
```

## License

MIT — see [`LICENSE`](LICENSE).
