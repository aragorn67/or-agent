# llm/problem_classifier.py
import json
from collections import Counter
from typing import Dict, Any, Tuple, List
try:
    from jsonschema import Draft2020Validator
    _HAVE_JSONSCHEMA = True
except Exception:
    _HAVE_JSONSCHEMA = False

from .schemas import CLASS_ENUM, SOLVER_ID_ENUM, CLASSIFICATION_SCHEMA

# ============================================================================
# CONFIGURATION PARAMETERS
# ============================================================================
DEFAULT_VOTING_ROUNDS = 5  # Number of classification votes for consensus (higher = more accurate but slower)

# ============================================================================
# FALLBACK MAPPING: problem_type → solver_id
# ============================================================================
# Maps fine-grained problem_type to default solver_id when LLM doesn't provide one
DEFAULT_SOLVER_BY_TYPE = {
    # Transportation family
    "transportation": "transport_basic_bipartite",
    "min_cost_flow": "transport_basic_bipartite",  # Fallback until we add true min-cost-flow solver

    # Scheduling family
    "single_stage_scheduling": "single_stage_ipm_scheduling",
    "single_machine_tardiness": "single_stage_ipm_scheduling",
}

# ============================================================================
# PROMPTS
# ============================================================================
SYSTEM = """You are an Operations Research problem classifier.

CRITICAL RULES:
1. Classify by STRUCTURE, not keywords.
2. Base your reasoning on sets, decision variables (binary/integer/continuous),
   constraints, and the objective.
3. Prefer the problem type whose canonical mathematical formulation best matches
   the described structure, even if the text uses misleading words.

KEY DISTINCTIONS:

TRANSPORTATION vs MIN-COST FLOW:
  * Transportation is a BIPARTITE network: flows only from supply nodes (plants,
    warehouses, origins) to demand nodes (markets, customers, sinks).
    There are NO intermediate/transshipment nodes.
  * Min-cost flow uses a GENERAL NETWORK: directed arcs, possible intermediate/
    transshipment nodes with flow conservation, sometimes arc capacities, possibly
    multiple commodities. If the description mentions flow conservation at many
    internal nodes, treat it as min-cost flow (even if it says "transportation").

SINGLE-STAGE vs JOB-SHOP SCHEDULING:
  * Single-stage (including single-machine or parallel-machine) scheduling:
    each job has ONE processing step; decisions are about assignment to machines
    and sequencing on that stage, with capacity and timing constraints.
  * Job-shop/multi-stage scheduling:
    each job has a SEQUENCE of operations on different machines, with
    precedence constraints between operations and machine-specific routing.

GENERAL GUIDELINES:
- Ignore literal mentions like "assignment", "transportation", "scheduling" etc.
  They can be red herrings. Use the underlying mathematical structure instead.
- If the structure does not clearly match any known type, choose the closest one
  and set solver_id="none".

Output ONLY JSON compliant with the given schema.
"""

USER_TMPL = """Schema (for validation reference):
{schema}

Text to classify:
\"\"\"{text}\"\"\"

CLASSIFICATION CHECKLIST:

For TRANSPORTATION problems, check:
- Is it BIPARTITE (sources→destinations only)? → problem_type: "transportation", solver_id: "transport_basic_bipartite"
- Does it have INTERMEDIATE NODES or HUBS? → problem_type: "min_cost_flow", solver_id: "none"
- Example bipartite: "factories ship to customers", "plants supply markets"
- Example network: "through distribution centers", "via hubs", "multi-stage"

For SCHEDULING problems, check:
- How many PROCESSING STAGES per job?
  * ONE stage (e.g., "process on one of several machines") → problem_type: "single_stage_scheduling", solver_id: "single_stage_ipm_scheduling"
  * MULTIPLE stages (e.g., "operation 1 then operation 2", "machine sequence") → problem_type: "job_shop", solver_id: "none"
- Look for: "single stage", "parallel machines", "one operation per job" → single_stage
- Look for: "operation sequence", "routing", "multi-stage", "precedence between operations" → job_shop

Return fields:
- problem_type: one of {enum}
- confidence: 0..1 (epistemic confidence in your classification)
- solver_id: which specific solver can handle this problem (one of {solver_enum})
- signals: structural cues you detected (bipartite_structure, transshipment_nodes, num_processing_stages, operation_sequences, etc.)
- evidence: list of short direct quotes from the text supporting your classification
- why_short: one short sentence explaining your choice
- objective: sense (minimize/maximize) and target (what's being optimized)
"""

def _validate(obj: Dict[str,Any]) -> List[str]:
    if not _HAVE_JSONSCHEMA:
        # Minimal sanity checks if jsonschema isn't installed
        errs = []
        if "problem_type" not in obj: errs.append("missing problem_type")
        if "confidence" not in obj: errs.append("missing confidence")
        if obj.get("problem_type") not in CLASS_ENUM: errs.append("invalid problem_type")
        return errs
    v = Draft2020Validator(CLASSIFICATION_SCHEMA)
    return [f"{'/'.join(map(str,e.path))}: {e.message}" for e in v.iter_errors(obj)]

class ProblemClassifier:
    def __init__(self, llm_client):
        self.llm = llm_client

    def _classify_once(self, text: str) -> Dict[str,Any]:
        user = USER_TMPL.format(schema=json.dumps(CLASSIFICATION_SCHEMA),
                                enum=CLASS_ENUM,
                                solver_enum=SOLVER_ID_ENUM,
                                text=text)
        out = self.llm._chat(SYSTEM, user, json_mode=True)   # Ollama client must support format=json
        obj = json.loads(out)
        return obj

    def classify(self, text: str, n: int = None) -> Tuple[Dict[str,Any], List[Dict[str,Any]]]:
        """
        Run n votes (low temperature) and return the consensus object + all raw votes.

        Uses majority voting on both problem_type AND solver_id, with fallback mapping.
        """
        if n is None:
            n = DEFAULT_VOTING_ROUNDS
        votes: List[Dict[str, Any]] = []
        for _ in range(n):
            try:
                v = self._classify_once(text)
            except Exception:
                continue
            v["_errors"] = _validate(v)
            votes.append(v)

        if not votes:
            return {
                "problem_type": "custom_review",
                "solver_id": "none",
                "confidence": 0.0,
                "signals": {},
                "evidence": [],
                "why_short": "No valid vote.",
                "objective": {"sense": "unknown", "target": ""},
            }, []

        # Prefer fully valid votes, but fall back to all
        valid = [v for v in votes if not v["_errors"]]
        pool = valid or votes

        # ---------------------------------------------------------------------
        # 1) Majority vote on problem_type
        # ---------------------------------------------------------------------
        type_counts = Counter(v.get("problem_type", "custom_review") for v in pool)
        top_type, _ = type_counts.most_common(1)[0]

        # All votes that picked that type
        same_type = [v for v in pool if v.get("problem_type") == top_type]
        if not same_type:
            same_type = pool  # Extreme fallback

        # Pick representative by highest confidence
        best = max(same_type, key=lambda v: float(v.get("confidence", 0.0)))

        # ---------------------------------------------------------------------
        # 2) Majority vote on solver_id among the winning type
        # ---------------------------------------------------------------------
        solver_counts = Counter(v.get("solver_id", "none") for v in same_type)
        top_solver, _ = solver_counts.most_common(1)[0]

        # Basic sanity for solver_id
        if top_solver not in SOLVER_ID_ENUM:
            top_solver = "none"

        # ---------------------------------------------------------------------
        # 3) Fallback: if solver_id is 'none', infer from problem_type mapping
        # ---------------------------------------------------------------------
        if top_solver == "none":
            mapped = DEFAULT_SOLVER_BY_TYPE.get(top_type, "none")
            top_solver = mapped

        # ---------------------------------------------------------------------
        # 4) Clean + clamp
        # ---------------------------------------------------------------------
        best["problem_type"] = top_type
        best["solver_id"] = top_solver
        best["confidence"] = float(min(1.0, max(0.0, best.get("confidence", 0.0))))
        best.pop("_errors", None)

        # Ensure objective present
        if "objective" not in best:
            best["objective"] = {"sense": "unknown", "target": ""}

        return best, votes