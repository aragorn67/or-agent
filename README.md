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
5. Solves with Pyomo + GLPK and returns the objective value, flows, and KPIs.
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
│  Solver (Pyomo + GLPK)   │ bipartite transport | single-stage scheduling
└──────────────────────────┘
        │
        ▼
┌──────────────────────────┐
│  Explanation (LLM)       │ summary + grounded units + chart hooks
└──────────────────────────┘
```

The LLM layer uses an abstract `LLMClient` interface so providers are swappable. The current backend is local Ollama with `qwen3:14b` across all stages; the same interface is designed to accept Anthropic, OpenAI, or other remote-API backends.

## Quickstart

Requirements: Python 3.10+, a running [Ollama](https://ollama.com) instance with a chat model available, and the `glpsol` binary on PATH.

```bash
# 1. clone and set up the environment
git clone https://github.com/aragorn67/or-agent.git
cd or-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. install GLPK (Ubuntu/Debian)
sudo apt install glpk-utils

# 3. pull the LLM
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

A FastAPI server is included; the primary endpoint is `POST /solve/natural` which accepts `{"description": "..."}` and returns the same dict the Python entry point returns. The remaining endpoints (capabilities, sensitivity plots, conversation sessions) are exercised by the test suite.

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Public deployment behind Cloudflare is on the roadmap — see [`brainstorm_ideas.md`](brainstorm_ideas.md).

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
python -m evals.run_eval --n 20             # 20 fresh seeds
python -m evals.run_eval --seeds 1,2,3      # specific seeds
```

The framework writes a timestamped JSON report under `evals/results/` containing the six headline metrics.

**Baseline result (transportation, qwen3:14b, N=20):** classification accuracy 1.00, mean parameter recall 1.00, median objective gap 0.00, end-to-end pass rate 1.00. The framework already paid for itself during development by surfacing a latent feasibility-checker bug that the existing hand-curated test set had missed.

Caveat: synthetic random problems with feasibility margins built in are the easy end of the input distribution. The 27-problem hand-curated set under `tests/or_problem_repository.py` is held out as a realism benchmark.

## Project status

**Works today:**
- Bipartite single-commodity transportation (Pyomo + GLPK)
- Single-stage scheduling (IPM-based makespan)
- Three-layer feasibility checking with diagnostic suggestions
- Sensitivity / what-if / re-solve follow-up analysis on transportation
- Round-trip eval framework (transportation; scheduling generator is next)

**On the roadmap** (see [`brainstorm_ideas.md`](brainstorm_ideas.md) for detail):
- Scheduling generator for the eval framework
- Public REST API deployment behind Cloudflare
- Metaheuristic warm-start with interactive optimality-gap checkpoint
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
