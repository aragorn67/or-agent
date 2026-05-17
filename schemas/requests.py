# schemas/requests.py
from pydantic import BaseModel, Field
from typing import Any, Dict, Literal, Optional


SolveMode = Literal["heuristic", "exact", "heuristic_then_ask"]
ContinueAction = Literal["optimize", "accept", "use_heuristic"]


class NaturalLanguageRequest(BaseModel):
    description: str = Field(..., description="Natural language description of optimization problem")
    explain_solution: bool = Field(default=True, description="Generate explanation of solution")
    mode: SolveMode = Field(
        default="exact",
        description=(
            "Solve mode. `exact` runs the MILP/LP solver to proven optimum or "
            "time limit. `heuristic` returns a fast feasible answer plus the LP "
            "lower bound. `heuristic_then_ask` returns the heuristic answer with "
            "a prompt asking whether to run the exact solver next."
        ),
    )


class ContinueRequest(BaseModel):
    job_id: str = Field(..., description="UUID returned by a prior heuristic-mode /solve call")
    action: ContinueAction = Field(
        ...,
        description=(
            "What to do next. `optimize` warm-starts the exact solver from the "
            "heuristic solution. `accept` and `use_heuristic` finalize with the "
            "heuristic answer (both are terminal)."
        ),
    )


class ChatContinueRequest(BaseModel):
    job_id: str = Field(..., description="UUID returned by a prior heuristic-mode /solve call")
    message: str = Field(
        ...,
        description=(
            "Free-text reply (e.g. 'make it better', 'good enough', 'use the heuristic'). "
            "Parsed into one of optimize / accept / use_heuristic before dispatch."
        ),
    )


class ExportRequest(BaseModel):
    """Export a solved payload to .xlsx. The chat holds the full solve result
    client-side, so it posts that back rather than re-solving by id (avoids
    the heuristic job-store TTL entirely)."""
    problem_type: Optional[str] = Field(default=None)
    extracted_params: Dict[str, Any] = Field(default_factory=dict)
    solution: Dict[str, Any] = Field(default_factory=dict)


class FileInputRequest(BaseModel):
    file_path: str = Field(..., description="Path to text file containing problem description")
    explain_solution: bool = Field(default=True, description="Generate explanation of solution")
