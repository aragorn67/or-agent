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
import csv
import io
import json
import threading
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse

from agent import spreadsheet_input as sheet_input
from agent.core import OptimizationAgent, build_next_options
from agent.progress_store import ProgressStore
from config import config
from llm.continue_intent import parse_continue_action
from schemas.requests import (
    ChatContinueRequest,
    ContinueRequest,
    ExportRequest,
    NaturalLanguageRequest,
)


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
    return _with_options(agent.solve_natural_language(req.description, mode=req.mode))


def _with_options(result: dict) -> dict:
    """Attach continuation chips (Phase 2 #5) to any payload before it leaves
    the API. Single chokepoint so every code path gets next_options."""
    result["next_options"] = build_next_options(result)
    return result


def _run_solve(run_id: str, description: str, mode: str) -> None:
    """Background worker: run the blocking solve, streaming its stages into
    the progress store, then store the final payload."""
    def on_progress(step: str, percent: int) -> None:
        progress_store.add_stage(run_id, step, percent)

    try:
        result = agent.solve_natural_language(
            description, progress_callback=on_progress, mode=mode
        )
        progress_store.finish(run_id, _with_options(result))
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
    return _with_options(agent.continue_job(req.job_id, req.action))


@app.post("/chat/continue")
def chat_continue(req: ChatContinueRequest):
    """Free-text alternative to /continue. Parses the message into an action."""
    action = parse_continue_action(req.message)
    if action is None:
        # Not an optimize/accept/use_heuristic action. Treat it as a free-text
        # follow-up / what-if against the still-pending job instead of
        # dead-ending. The job stays alive so the user can still decide.
        return _with_options(agent.follow_up_on_job(req.job_id, req.message))
    result = agent.continue_job(req.job_id, action)
    result["parsed_action"] = action
    return _with_options(result)


@app.post("/export/xlsx")
def export_xlsx(req: ExportRequest):
    """Phase 2 #6: turn a solved payload into a downloadable .xlsx workbook.

    Always writes a Summary sheet plus a domain detail sheet — shipment flows
    for transportation, the order→unit schedule for scheduling.
    """
    import pandas as pd

    sol = req.solution or {}
    params = req.extracted_params or {}

    summary = [
        ("Problem type", req.problem_type or "—"),
        ("Status", sol.get("status", "—")),
        ("Objective", sol.get("objective_value", sol.get("objective", "—"))),
        ("Best bound", sol.get("best_bound", "—")),
        ("Gap", sol.get("gap", "—")),
        ("Heuristic", sol.get("is_heuristic", False)),
        ("Warm-started", sol.get("warm_started", "—")),
    ]

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame(summary, columns=["Metric", "Value"]).to_excel(
            xw, sheet_name="Summary", index=False
        )
        if sol.get("flows"):
            pd.DataFrame(sol["flows"]).to_excel(
                xw, sheet_name="Flows", index=False
            )
        if sol.get("assignments"):
            df = pd.DataFrame(sol["assignments"])
            comp = sol.get("completion") or {}
            if comp:
                df["completion"] = df.get("order", df.iloc[:, 0]).map(comp)
            df.to_excel(xw, sheet_name="Schedule", index=False)
        if params:
            flat = {k: str(v) for k, v in params.items()}
            pd.DataFrame(
                list(flat.items()), columns=["Parameter", "Value"]
            ).to_excel(xw, sheet_name="Parameters", index=False)
    buf.seek(0)

    fname = f"{(req.problem_type or 'solution').lower()}_result.xlsx"
    return StreamingResponse(
        buf,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


def _primary_solution_table(sol: dict) -> tuple[str, list[dict]]:
    """Pick the flat decision table to export: shipment flows for
    transportation, the order->unit schedule for scheduling. Returns
    (table_name, rows); rows is empty when neither is present."""
    if sol.get("flows"):
        return ("flows", list(sol["flows"]))
    if sol.get("assignments"):
        rows = [dict(r) for r in sol["assignments"]]
        comp = sol.get("completion") or {}
        if comp:
            for r in rows:
                key = r.get("order", next(iter(r.values()), None))
                if key in comp:
                    r["completion"] = comp[key]
        return ("schedule", rows)
    return ("", [])


@app.post("/export/json")
def export_json(req: ExportRequest):
    """Download the full solved payload as JSON — lossless: objective, status,
    bound/gap, the decision variables, and the extracted parameters."""
    payload = {
        "problem_type": req.problem_type,
        "solution": req.solution or {},
        "extracted_params": req.extracted_params or {},
    }
    buf = io.BytesIO(json.dumps(payload, indent=2, default=str).encode("utf-8"))
    fname = f"{(req.problem_type or 'solution').lower()}_result.json"
    return StreamingResponse(
        buf,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.post("/export/csv")
def export_csv(req: ExportRequest):
    """Download the decision table as CSV — shipment flows for transportation,
    the order->unit schedule for scheduling. Falls back to a Metric/Value
    summary when there is no tabular solution (use /export/json for the full
    lossless payload)."""
    sol = req.solution or {}
    _, rows = _primary_solution_table(sol)

    sbuf = io.StringIO()
    if rows:
        fieldnames = list(dict.fromkeys(k for r in rows for k in r.keys()))
        writer = csv.DictWriter(sbuf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    else:
        writer = csv.writer(sbuf)
        writer.writerow(["Metric", "Value"])
        for label, key in (
            ("Problem type", None), ("Status", "status"),
            ("Objective", "objective_value"), ("Best bound", "best_bound"),
            ("Gap", "gap"),
        ):
            val = req.problem_type if key is None else sol.get(
                key, sol.get("objective") if key == "objective_value" else "—"
            )
            writer.writerow([label, val])

    buf = io.BytesIO(sbuf.getvalue().encode("utf-8"))
    fname = f"{(req.problem_type or 'solution').lower()}_result.csv"
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.get("/solve/file/template")
def solve_file_template(problem_type: str = Query(...)):
    """Download a blank, correctly-shaped input workbook for a domain so
    the user can see the exact sheet layout the fast path expects."""
    try:
        data = sheet_input.build_template(problem_type)
        dom = sheet_input.domain_of(problem_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    fname = f"{dom}_input_template.xlsx"
    return StreamingResponse(
        io.BytesIO(data),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.post("/solve/file")
async def solve_file(
    problem_type: str | None = Form(None),
    mode: str = Form("exact"),
    explain: bool = Form(False),
    file: UploadFile = File(...),
):
    """Phase 3 #2: structured .xlsx upload -> solve, skipping BOTH qwen3
    calls (classify + extract). The "instant demo lane".

    ``problem_type`` is optional — when omitted, the domain is inferred
    from the workbook's sheet names (Supply/Demand/Cost -> transport;
    Processing/DueDate -> scheduling). Everything after
    (validate -> feasibility -> mode-route -> solve) is the exact shared
    pipeline the NL path uses. ``explain=False`` (default) also skips the
    third qwen3 call, using a deterministic summary instead.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")
    try:
        sheets = sheet_input._read_book(io.BytesIO(raw))
        domain = (sheet_input.domain_of(problem_type) if problem_type
                  else sheet_input.infer_domain(sheets))
        params = (sheet_input._parse_transport(sheets) if domain == "transport"
                  else sheet_input._parse_scheduling(sheets))
        resolved_type, solver_id = sheet_input.resolved_ids_from_domain(domain)
    except ValueError as exc:
        # Malformed workbook / unsupported domain / ambiguous — never a 500.
        raise HTTPException(status_code=422, detail=str(exc))

    result = agent.solve_with_params(
        params=params,
        problem_type=resolved_type,
        solver_id=solver_id,
        description=f"Structured spreadsheet input ({file.filename})",
        mode=mode,
        explain=explain,
    )
    result["input"] = "spreadsheet"
    result["skipped_stages"] = (
        ["classify", "extract", "explain"] if not explain
        else ["classify", "extract"]
    )
    return _with_options(result)


@app.post("/agent/classify")
def classify_problem_only(req: NaturalLanguageRequest):
    from solvers import list_problem_types
    classification = agent.llm.classify_problem(req.description, list_problem_types())
    return classification
