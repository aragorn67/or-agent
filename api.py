# api.py — public REST API for the optimization agent.
#
# Surface (intentionally small, see brainstorm_ideas.md "Deploy a public REST API"):
#   GET  /            — service index
#   GET  /health      — liveness probe
#   GET  /capabilities — supported problem types
#   POST /solve       — natural-language problem → solution dict
#   POST /agent/classify — classify problem type without solving
from fastapi import FastAPI

from agent.core import OptimizationAgent
from config import config
from schemas.requests import NaturalLanguageRequest


app = FastAPI(title="Optimization Agent API", version="1.0.0")

agent = OptimizationAgent(config.get_llm_client())


@app.get("/")
def root():
    return {
        "service": "Optimization Agent API",
        "docs": "/docs",
        "health": "/health",
        "capabilities": "/capabilities",
        "solve": "POST /solve with {\"description\": \"...\"}",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/capabilities")
def get_capabilities():
    return agent.get_capabilities()


@app.get("/agent/capabilities")
def get_agent_capabilities():
    return agent.get_capabilities()


@app.post("/solve")
@app.post("/solve/natural")
def solve_natural_language(req: NaturalLanguageRequest):
    return agent.solve_natural_language(req.description)


@app.post("/agent/classify")
def classify_problem_only(req: NaturalLanguageRequest):
    from solvers import list_problem_types
    classification = agent.llm.classify_problem(req.description, list_problem_types())
    return classification
