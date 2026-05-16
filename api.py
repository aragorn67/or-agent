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
import threading
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from agent.core import OptimizationAgent
from agent.progress_store import ProgressStore
from config import config
from llm.continue_intent import parse_continue_action
from schemas.requests import ChatContinueRequest, ContinueRequest, NaturalLanguageRequest


app = FastAPI(title="Optimization Agent API", version="1.1.0")

agent = OptimizationAgent(config.get_llm_client())
progress_store = ProgressStore()


_CHAT_HTML = Path(__file__).parent / "templates" / "chat.html"


@app.get("/", response_class=HTMLResponse)
def chat_ui():
    """Serve the conversational demo UI (two-call heuristic_then_ask flow)."""
    return _CHAT_HTML.read_text(encoding="utf-8")


@app.get("/api/info")
def api_info():
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
    """Synchronous solve (back-compat). For the live-progress UI use
    POST /jobs + GET /jobs/{run_id}."""
    return agent.solve_natural_language(req.description, mode=req.mode)


def _run_solve(run_id: str, description: str, mode: str) -> None:
    """Background worker: run the blocking solve, streaming its stages into
    the progress store, then store the final payload."""
    def on_progress(step: str, percent: int) -> None:
        progress_store.add_stage(run_id, step, percent)

    try:
        result = agent.solve_natural_language(
            description, progress_callback=on_progress, mode=mode
        )
        progress_store.finish(run_id, result)
    except Exception as exc:  # noqa: BLE001 — surface any failure to the poller
        progress_store.fail(run_id, f"{type(exc).__name__}: {exc}")


@app.post("/jobs")
def create_job(req: NaturalLanguageRequest):
    """Start a solve asynchronously and return a run_id to poll. The heavy
    ~2-3 min of local-LLM work runs in a background thread; the client polls
    GET /jobs/{run_id} to render live pipeline progress."""
    run = progress_store.create()
    threading.Thread(
        target=_run_solve,
        args=(run.run_id, req.description, req.mode),
        daemon=True,
    ).start()
    return {"run_id": run.run_id, "state": run.state}


@app.get("/jobs/{run_id}")
def get_job(run_id: str):
    """Poll a run: current pipeline stages, and the full solve payload once
    state is 'done' (or an error message if it failed)."""
    run = progress_store.get(run_id)
    if run is None:
        return {"success": False, "error": f"Run {run_id} not found or expired."}
    return {
        "run_id": run.run_id,
        "state": run.state,
        "stages": run.stages,
        "percent": run.stages[-1]["percent"] if run.stages else 0,
        "result": run.result,
        "error": run.error,
    }


@app.post("/continue")
def continue_job(req: ContinueRequest):
    return agent.continue_job(req.job_id, req.action)


@app.post("/chat/continue")
def chat_continue(req: ChatContinueRequest):
    """Free-text alternative to /continue. Parses the message into an action."""
    action = parse_continue_action(req.message)
    if action is None:
        # Not an optimize/accept/use_heuristic action. Treat it as a free-text
        # follow-up / what-if against the still-pending job instead of
        # dead-ending. The job stays alive so the user can still decide.
        return agent.follow_up_on_job(req.job_id, req.message)
    result = agent.continue_job(req.job_id, action)
    result["parsed_action"] = action
    return result


@app.post("/agent/classify")
def classify_problem_only(req: NaturalLanguageRequest):
    from solvers import list_problem_types
    classification = agent.llm.classify_problem(req.description, list_problem_types())
    return classification
