# OR Agent

An LLM-driven operations-research agent. Takes a natural-language description of an optimization problem, classifies the problem family, extracts parameters into a structured schema, runs a deterministic solver, and explains the result.

## What it does

Given a prose problem statement such as:

> *"Boston can supply up to 1200 units and Phoenix can supply 700 units. Rome needs 350 units, Berlin needs 400 units, and Tokyo needs 250 units. Shipping from Boston to Rome costs $2.50 per unit, ..."*

the agent:

1. Detects intent (new problem vs. follow-up vs. small talk).
2. Classifies the problem family (transportation, scheduling, ...) using a JSON-schema-bound classifier with majority voting.
3. Routes to the matching specialist extractor, which converts prose to a typed parameter dict.
4. Runs a three-layer feasibility check (structural → problem-specific necessary conditions → solver-based) before invoking the solver, so hallucinated parameters do not silently corrupt the result.
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
│  Feasibility (3 layers)  │ structural → problem-specific → LP relaxation
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

The LLM layer uses an abstract `LLMClient` interface so providers are swappable. The current backend is local Ollama with `qwen3:14b` across all stages; the same interface is designed to accept Anthropic, OpenAI, or other remote-API backends.

## Quickstart

Requirements: Python 3.10+, a running [Ollama](https://ollama.com) instance with a chat model available. The solver (HiGHS) is pulled in via the `highspy` wheel — no external binary required.

```bash
# 1. clone and set up the environment
git clone https://github.com/aragorn67/or-agent.git
cd or-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. pull the LLM
ollama pull qwen3:14b

# 4. one-shot solve from Python
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

Auxiliary: `GET /health`, `GET /capabilities`, `POST /agent/classify`.

```bash
uvicorn api:app --host 0.0.0.0 --port 8000

# Then, from another shell:
curl -s -X POST http://localhost:8000/solve \
  -H "Content-Type: application/json" \
  -d '{"description": "Two plants Seattle (cap 350) and San Diego (cap 600) ship to New York (demand 325), Chicago (demand 300), Topeka (demand 275). Distances in thousand miles — Seattle: NY=2.5, Chicago=1.7, Topeka=1.8. San Diego: NY=2.5, Chicago=1.8, Topeka=1.4. Freight $90 per case per thousand miles. Minimise total shipping cost."}'
```

The LLM backend is selected by the `LLM_BACKEND` env var: `ollama` (default; uses the local qwen3:14b stack) or `groq` (uses Groq's hosted Llama models, set `GROQ_API_KEY`). The latter is intended for hosted deployments that cannot keep a 9 GB local model resident.

```bash
LLM_BACKEND=groq GROQ_API_KEY=$GROQ_API_KEY \
  GROQ_CLASSIFICATION_MODEL=llama-3.1-8b-instant \
  uvicorn api:app --host 0.0.0.0 --port 8000
```

A `Dockerfile` is included for hosted deployment. For a zero-cost demo the API can be exposed publicly with [`cloudflared`](https://github.com/cloudflare/cloudflared) without any VPS:

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

The CLI defaults to local Ollama (`--backend ollama`); pass `--backend groq` to opt into the hosted backend. The framework writes a timestamped JSON report under `evals/results/` containing the six headline metrics.

**Baseline results (qwen3:14b, local Ollama):**
- *Transportation* — classification accuracy 1.00, mean parameter recall 1.00, median objective gap 0.00, end-to-end pass rate 1.00.
- *Single-stage scheduling* — classification accuracy 1.00, mean parameter recall 1.00, median objective gap 0.00, end-to-end pass rate 1.00 (3/3 seeds).

The framework has already paid for itself during development by surfacing four real bugs the existing hand-curated test set had missed: one feasibility-checker bug on the transport side, plus three on the scheduling side (an f-string format-spec crash in the scheduling extractor's system prompt, a non-recursive non-negativity check that rejected nested `processing_time` dicts, and an extraction-dispatch list that lagged behind the classifier's solver mapping).

Caveat: synthetic random problems with feasibility margins built in are the easy end of the input distribution. The 27-problem hand-curated set under `tests/or_problem_repository.py` is held out as a realism benchmark.

## Project status

**Works today:**
- Bipartite single-commodity transportation (Pyomo + HiGHS)
- Single-stage scheduling (IPM-based makespan)
- Three-layer feasibility checking with diagnostic suggestions
- Sensitivity / what-if / re-solve follow-up analysis on transportation
- Round-trip eval framework for both transportation and single-stage scheduling
- Interactive heuristic + warm-start (VAM for transport) with LP bound reporting and a two-call API protocol (`/solve mode=heuristic_then_ask` → `/chat/continue`)

**On the roadmap** (see [`brainstorm_ideas.md`](brainstorm_ideas.md) for detail):
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
brainstorm_ideas.md       Architecture notes, current bottlenecks, and roadmap
archive/ ML_RAG_archive/  Prior approaches kept for reference (see "not adopted")
```

## License

MIT — see [`LICENSE`](LICENSE).
