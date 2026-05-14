# api.py — public REST API for the optimization agent.
#
# Surface:
#   GET  /             — service index
#   GET  /health       — liveness probe
#   GET  /capabilities — supported problem types
#   POST /solve        — natural-language problem → solution dict
#                        Accepts mode={exact|heuristic|heuristic_then_ask}
#   POST /continue     — resume a heuristic-mode job by job_id + action
#   POST /agent/classify — classify problem type without solving
from fastapi import FastAPI

from agent.core import OptimizationAgent
from config import config
from llm.continue_intent import parse_continue_action
from schemas.requests import ChatContinueRequest, ContinueRequest, NaturalLanguageRequest


app = FastAPI(title="Optimization Agent API", version="1.1.0")

agent = OptimizationAgent(config.get_llm_client())


@app.get("/")
def root():
    return {
        "service": "Optimization Agent API",
        "docs": "/docs",
        "health": "/health",
        "capabilities": "/capabilities",
        "solve": "POST /solve with {\"description\": \"...\", \"mode\": \"exact|heuristic|heuristic_then_ask\"}",
        "continue": "POST /continue with {\"job_id\": \"...\", \"action\": \"optimize|accept|use_heuristic\"}",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/capabilities")
def get_capabilities():
    caps = agent.get_capabilities()
    caps["modes"] = ["exact", "heuristic", "heuristic_then_ask"]
    caps["continue_actions"] = ["optimize", "accept", "use_heuristic"]
    caps["heuristic_supported_problem_types"] = ["TRANSPORTATION"]
    return caps


@app.get("/agent/capabilities")
def get_agent_capabilities():
    return get_capabilities()


@app.post("/solve")
@app.post("/solve/natural")
def solve_natural_language(req: NaturalLanguageRequest):
    return agent.solve_natural_language(req.description, mode=req.mode)


@app.post("/continue")
def continue_job(req: ContinueRequest):
    return agent.continue_job(req.job_id, req.action)


@app.post("/chat/continue")
def chat_continue(req: ChatContinueRequest):
    """Free-text alternative to /continue. Parses the message into an action."""
    action = parse_continue_action(req.message)
    if action is None:
        return {
            "success": False,
            "error": (
                "I didn't catch what you'd like to do. Try one of: "
                "'optimize' / 'make it better' to run the exact solver, "
                "'accept' / 'good enough' to keep this answer, or "
                "'use heuristic' to stick with the heuristic."
            ),
            "available_actions": ["optimize", "accept", "use_heuristic"],
        }
    result = agent.continue_job(req.job_id, action)
    result["parsed_action"] = action
    return result


@app.post("/agent/classify")
def classify_problem_only(req: NaturalLanguageRequest):
    from solvers import list_problem_types
    classification = agent.llm.classify_problem(req.description, list_problem_types())
    return classification
