# api.py
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path
from io import BytesIO
import base64
import json

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

# plotting (server-friendly)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from solvers.transportation_solver import solve_transport

# New agent system
from agent.core import OptimizationAgent
from conversation.agent import ConversationalAgent
from conversation.memory import conversation_memory
from config import config
from schemas.requests import NaturalLanguageRequest, FileInputRequest


# ---------- Pydantic Schemas ----------

class TransportRequest(BaseModel):
    plants: List[str] = Field(..., description="List of plant names")
    markets: List[str] = Field(..., description="List of market names")
    capacity: Dict[str, float] = Field(..., description="Capacity per plant (cases)")
    demand: Dict[str, float] = Field(..., description="Demand per market (cases)")
    # Nested dict: {plant: {market: distance_thousand_miles}}
    distance: Dict[str, Dict[str, float]] = Field(
        ..., description="Distances in thousand miles as nested dict"
    )
    freight: float = Field(..., description="Freight $ per case per thousand miles")


class SaveRequest(TransportRequest):
    scenario_name: Optional[str] = Field(
        default=None, description="Optional scenario name used in filename"
    )


class QARequest(BaseModel):
    question: str = Field(..., description="Natural language question")
    solution: Dict[str, Any] = Field(
        ..., description="Solution JSON returned by /solve/transport"
    )


# ---------- FastAPI App ----------

app = FastAPI(title="Optimization Agent API", version="1.0.0")

# Initialize the optimization agents
agent = OptimizationAgent(config.get_llm_client())
conversational_agent = ConversationalAgent(config.get_llm_client())

# Global variables to cache data for plot endpoints
_cached_solution = None
_cached_sensitivity_plot = None

# Mount static files for HTML frontend
app.mount("/static", StaticFiles(directory="static"), name="static")


# ---------- Utilities ----------

def save_solution_to_file(solution: Dict[str, Any], scenario_name: Optional[str] = None) -> str:
    """Save solution JSON into ./solutions/ with timestamp. Returns absolute filepath."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = scenario_name or "transport"
    fname = f"{name}_{ts}.json"
    outdir = Path("solutions")
    outdir.mkdir(parents=True, exist_ok=True)
    fpath = outdir / fname
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump(solution, f, indent=2)
    return str(fpath.resolve())


def _png_bytes_from_fig(fig) -> bytes:
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _b64(img_bytes: bytes) -> str:
    return base64.b64encode(img_bytes).decode("utf-8")


def _plot_shipments_by_plant(solution: Dict[str, Any]) -> bytes:
    totals = solution.get("kpis", {}).get("total_by_plant", {})
    plants = list(totals.keys())
    values = [totals[p] for p in plants]

    fig = plt.figure()
    plt.bar(plants, values)
    plt.title("Total shipments per Plant (cases)")
    plt.xlabel("Plant")
    plt.ylabel("Cases")
    return _png_bytes_from_fig(fig)


def _plot_shipments_matrix(solution: Dict[str, Any]) -> bytes:
    # stacked bars per plant by market
    flows = solution.get("flows", [])
    plants = sorted({rec["plant"] for rec in flows})
    markets = sorted({rec["market"] for rec in flows})

    # build matrix: market -> list per plant
    data = {m: [0.0 for _ in plants] for m in markets}
    pidx = {p: i for i, p in enumerate(plants)}
    for rec in flows:
        i = pidx[rec["plant"]]
        data[rec["market"]][i] += float(rec["value"])

    fig = plt.figure()
    bottom = [0.0 for _ in plants]
    for m in markets:
        vals = data[m]
        plt.bar(plants, vals, bottom=bottom, label=m)
        bottom = [b + v for b, v in zip(bottom, vals)]
    plt.title("Shipments per Plant by Market (stacked)")
    plt.xlabel("Plant")
    plt.ylabel("Cases")
    plt.legend(title="Market")
    return _png_bytes_from_fig(fig)


def _sum_by_plant(solution: Dict[str, Any], plant: str) -> float:
    return float(sum(rec["value"] for rec in solution.get("flows", []) if rec["plant"].lower() == plant.lower()))


def _sum_by_market(solution: Dict[str, Any], market: str) -> float:
    return float(sum(rec["value"] for rec in solution.get("flows", []) if rec["market"].lower() == market.lower()))


def _flow_plant_market(solution: Dict[str, Any], plant: str, market: str) -> float:
    return float(sum(
        rec["value"]
        for rec in solution.get("flows", [])
        if rec["plant"].lower() == plant.lower() and rec["market"].lower() == market.lower()
    ))


def _which_plants_supply_market(solution: Dict[str, Any], market: str) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for rec in solution.get("flows", []):
        if rec["market"].lower() == market.lower() and rec["value"] > 1e-12:
            p = rec["plant"]
            totals[p] = totals.get(p, 0.0) + float(rec["value"])
    return totals


def _which_markets_served_by_plant(solution: Dict[str, Any], plant: str) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for rec in solution.get("flows", []):
        if rec["plant"].lower() == plant.lower() and rec["value"] > 1e-12:
            m = rec["market"]
            totals[m] = totals.get(m, 0.0) + float(rec["value"])
    return totals


# ---------- Endpoints ----------

@app.post("/solve/transport")
def solve_transport(req: TransportRequest):
    """
    Solve the transport model and return the solution (JSON-safe).
    """
    params = req.dict()
    result = solve_transport(params)
    return result


@app.post("/solve/transport/save")
def solve_transport_and_save(req: SaveRequest):
    """
    Solve and also persist the solution to ./solutions/<scenario>_<timestamp>.json
    """
    params = req.dict()
    scenario_name = params.pop("scenario_name", None)
    result = solve_transport(params)
    saved_path = save_solution_to_file(result, scenario_name=scenario_name)
    return {"saved_to": saved_path, "solution": result}


@app.post("/qa/transport")
def qa_transport(req: QARequest):
    """
    Very simple deterministic Q&A over the solution JSON (no LLM).
    Supported intents (case-insensitive):
      - total cost
      - total by plant <X>
      - total to market <Y>
      - flow from <plant> to <market>
      - which plants supplied <market>
      - which markets were served by <plant>
    """
    q = req.question.strip().lower()
    sol = req.solution

    # 1) total cost
    if "total cost" in q or "objective" in q:
        cost = sol.get("objective_thousand_usd")
        return {"answer": f"Total cost = {cost} thousand USD.", "evidence": ["objective_thousand_usd"]}

    # 2) total by plant
    if "by plant" in q or "from plant" in q or "plant" in q:
        tokens = q.replace("?", "").split()
        if "plant" in tokens:
            idx = tokens.index("plant")
            if idx + 1 < len(tokens):
                plant = tokens[idx + 1]
                total = _sum_by_plant(sol, plant)
                return {"answer": f"Total shipped by plant '{plant}' = {total} cases.", "evidence": ["flows"]}
        for p in [rec["plant"] for rec in sol.get("flows", [])]:
            if p.lower() in q:
                total = _sum_by_plant(sol, p)
                return {"answer": f"Total shipped by plant '{p}' = {total} cases.", "evidence": ["flows"]}

    # 3) total to market
    if "to market" in q or "market" in q:
        for m in [rec["market"] for rec in sol.get("flows", [])]:
            if m.lower() in q:
                total = _sum_by_market(sol, m)
                return {"answer": f"Total shipped to market '{m}' = {total} cases.", "evidence": ["flows"]}

    # 4) flow from plant to market
    if "flow from" in q or ("from" in q and "to" in q):
        plants = {rec["plant"].lower() for rec in sol.get("flows", [])}
        markets = {rec["market"].lower() for rec in sol.get("flows", [])}
        chosen_p = next((p for p in plants if f"from {p}" in q), None)
        chosen_m = next((m for m in markets if f"to {m}" in q), None)
        if chosen_p and chosen_m:
            val = _flow_plant_market(sol, chosen_p, chosen_m)
            return {"answer": f"Flow from '{chosen_p}' to '{chosen_m}' = {val} cases.", "evidence": ["flows"]}

    # 5) which plants supplied <market>
    if "which plants" in q and ("supplied" in q or "supply" in q or "to" in q):
        for m in {rec["market"] for rec in sol.get("flows", [])}:
            if m.lower() in q:
                breakdown = _which_plants_supply_market(sol, m)
                if breakdown:
                    return {"answer": f"Plants supplying '{m}': {breakdown}", "evidence": ["flows"]}
                return {"answer": f"No shipments to '{m}'.", "evidence": ["flows"]}

    # 6) which markets were served by <plant>
    if "which markets" in q and ("served" in q or "from" in q):
        for p in {rec["plant"] for rec in sol.get("flows", [])}:
            if p.lower() in q:
                breakdown = _which_markets_served_by_plant(sol, p)
                if breakdown:
                    return {"answer": f"Markets served by '{p}': {breakdown}", "evidence": ["flows"]}
                return {"answer": f"No shipments from '{p}'.", "evidence": ["flows"]}

    # Fallback help
    return {
        "answer": "I could not parse the question. Try one of:\n"
                  "- 'total cost'\n"
                  "- 'total by plant seattle'\n"
                  "- 'total to market chicago'\n"
                  "- 'flow from seattle to topeka'\n"
                  "- 'which plants supplied chicago'\n"
                  "- 'which markets were served by seattle'",
        "evidence": []
    }


@app.post("/plots/transport")
def plots_transport(req: QARequest):
    """
    Returns base64 PNG plots for a given solution JSON:
      - shipments_by_plant_png_b64
      - shipments_matrix_png_b64
    """
    sol = req.solution
    img1 = _plot_shipments_by_plant(sol)
    img2 = _plot_shipments_matrix(sol)
    return {
        "plots": {
            "shipments_by_plant_png_b64": _b64(img1),
            "shipments_matrix_png_b64": _b64(img2)
        }
    }


@app.post("/solve/transport/with_plots")
def solve_transport_with_plots(req: TransportRequest):
    """
    Solve the model and return solution + plot URLs for display.
    """
    params = req.dict()
    result = solve_transport(params)

    # Store solution globally for plot endpoints to access
    global _cached_solution
    _cached_solution = result

    return {
        "solution": result,
        "plot_urls": {
            "shipments_by_plant": "/plots/shipments_by_plant.png",
            "shipments_matrix": "/plots/shipments_matrix.png"
        }
    }

@app.get("/plots/shipments_by_plant.png")
def get_shipments_by_plant_plot():
    """Return the shipments by plant plot as a PNG image."""
    global _cached_solution
    if not _cached_solution:
        raise HTTPException(status_code=404, detail="No solution data available. Run /solve/transport/with_plots first.")

    img_bytes = _plot_shipments_by_plant(_cached_solution)
    return StreamingResponse(BytesIO(img_bytes), media_type="image/png")

@app.get("/plots/shipments_matrix.png")
def get_shipments_matrix_plot():
    """Return the shipments matrix plot as a PNG image."""
    global _cached_solution
    if not _cached_solution:
        raise HTTPException(status_code=404, detail="No solution data available. Run /solve/transport/with_plots first.")

    img_bytes = _plot_shipments_matrix(_cached_solution)
    return StreamingResponse(BytesIO(img_bytes), media_type="image/png")


@app.get("/plots/sensitivity.png")
def get_sensitivity_plot():
    """Return the sensitivity analysis plot as a PNG image."""
    global _cached_sensitivity_plot
    if not _cached_sensitivity_plot:
        raise HTTPException(status_code=404, detail="No sensitivity analysis data available. Request a sensitivity analysis first.")

    # The cached plot is already in base64 format, so we need to decode it
    import base64
    img_bytes = base64.b64decode(_cached_sensitivity_plot)
    return StreamingResponse(BytesIO(img_bytes), media_type="image/png")


# ---------- New Agent Endpoints ----------

@app.get("/", response_class=HTMLResponse)
def get_homepage():
    """Serve the conversational chat interface"""
    html_path = Path("templates/chat.html")
    if html_path.exists():
        return html_path.read_text()
    return "<h1>Optimization Agent</h1><p>Chat interface not found. Use /docs for API.</p>"

@app.get("/chat", response_class=HTMLResponse)
def get_chat_interface():
    """Serve the conversational chat interface"""
    html_path = Path("templates/chat.html")
    if html_path.exists():
        return html_path.read_text()
    return "<h1>Chat Interface</h1><p>Chat interface not found.</p>"

@app.post("/solve/natural")
def solve_natural_language(req: NaturalLanguageRequest):
    """Solve optimization problem from natural language description"""
    return agent.solve_natural_language(req.description)

@app.post("/solve/file")
def solve_from_file(req: FileInputRequest):
    """Solve optimization problem from text file"""
    try:
        file_path = Path(req.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")

        description = file_path.read_text(encoding='utf-8')
        return agent.solve_natural_language(description)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

@app.get("/agent/capabilities")
def get_agent_capabilities():
    """Get agent capabilities and supported problem types"""
    return agent.get_capabilities()

@app.post("/agent/classify")
def classify_problem_only(req: NaturalLanguageRequest):
    """Just classify problem type without solving"""
    from solvers import list_problem_types
    classification = agent.llm.classify_problem(req.description, list_problem_types())
    return classification


# ---------- Conversation Endpoints ----------

@app.post("/conversation/start")
def start_conversation():
    """Start a new conversation session"""
    session_id = conversation_memory.create_conversation()
    welcome_message = "Hello! I'm your optimization agent. What problem can I help you solve today?"

    conversation_memory.add_message(session_id, "assistant", welcome_message)

    return {
        "session_id": session_id,
        "message": welcome_message,
        "status": "started"
    }

@app.post("/conversation/{session_id}/message")
def send_message(session_id: str, message: dict):
    """Send message in conversation"""
    user_message = message.get("content", "").strip()

    if not user_message:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    if session_id not in conversation_memory.conversations:
        raise HTTPException(status_code=404, detail="Conversation not found")

    try:
        # Process message with conversational agent
        result = conversational_agent.process_message(session_id, user_message)

        return {
            "session_id": session_id,
            "response": result,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@app.get("/conversation/{session_id}")
def get_conversation(session_id: str):
    """Get conversation history"""
    conversation = conversation_memory.get_conversation(session_id)

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return conversation

@app.get("/conversations")
def list_conversations():
    """List all conversation sessions"""
    sessions = conversation_memory.list_conversations()
    return {
        "sessions": sessions,
        "count": len(sessions)
    }
