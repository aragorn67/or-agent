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
    "min_cost_flow": "none",  # Refuse: bipartite transport can't model transshipment/hub conservation — solving it there gives a confidently-wrong answer. Wait for a real min-cost-flow solver.

    # Scheduling family - single stage
    "single_stage_scheduling": "single_stage_ipm_scheduling",
    "single_machine_makespan": "single_stage_ipm_scheduling",      # ✅ Has makespan objective
    "parallel_machine_scheduling": "single_stage_ipm_scheduling",  # ✅ Multi-unit support

    # Scheduling family - NOT solvable (missing objective functions)
    "single_machine_tardiness": "none",  # ❌ Solver lacks tardiness objective (only has makespan/changeover)
}

# ============================================================================
# PROMPTS
# ============================================================================
SYSTEM = """You are an Operations Research problem classifier.

CRITICAL RULES:
1. Classify by STRUCTURE, not keywords.
2. Base your reasoning on sets, decision variables, constraints, and objective.
3. Use the canonical mathematical formulation that best matches the structure.
4. Keywords like "transportation", "scheduling" can be misleading - verify structure!

═══════════════════════════════════════════════════════════════════════════════
TRANSPORTATION vs MIN-COST FLOW
═══════════════════════════════════════════════════════════════════════════════

TRANSPORTATION (bipartite network):
  Structure:
    • Exactly TWO node sets: sources I and sinks J
    • Variables: x[i,j] ≥ 0 (flow from source i to sink j)
    • Flow ONLY from I → J (no I→I, no J→J, no intermediate nodes)
    • Constraints: supply[i] limits and demand[j] requirements

  MUST HAVE:
    ✓ Two distinct sets (sources and sinks)
    ✓ Direct shipping from sources to sinks
    ✓ No flow conservation at intermediate nodes

  MUST NOT HAVE:
    ✗ Intermediate/transshipment nodes with flow conservation
    ✗ "Through hubs", "via distribution centers"

  Positive signals: "bipartite", "direct shipping", "no intermediate nodes"
  Example: "3 factories ship directly to 4 customers"

MIN-COST FLOW (general network):
  Structure:
    • General node set N (sources, sinks, AND intermediate nodes)
    • Variables: flow[a] ≥ 0 for each arc a
    • Flow conservation at INTERNAL nodes: in_flow = out_flow
    • Arc capacity constraints

  MUST HAVE:
    ✓ Intermediate/transshipment nodes
    ✓ Flow conservation equations at internal nodes
    ✓ Network structure (not just bipartite)

  MUST NOT BE:
    ✗ Only two node sets (sources and sinks)

  Positive signals: "through", "via", "hubs", "transshipment", "flow conservation"
  Example: "depot → through 2 hubs → to hospitals"

═══════════════════════════════════════════════════════════════════════════════
SINGLE-STAGE vs JOB-SHOP SCHEDULING
═══════════════════════════════════════════════════════════════════════════════

SINGLE-STAGE SCHEDULING:
  Structure:
    • Each job j has ONE operation
    • Variables: assign[j,m] ∈ {0,1}, start[j] ≥ 0
    • Constraints: one assignment per job, no overlap, due dates
    • May have "eligible machines" (subset of machines per job)

  MUST HAVE:
    ✓ Exactly ONE operation per job
    ✓ Decision: which machine + when to start
    ✓ No operation precedence/sequence

  MUST NOT HAVE:
    ✗ Multiple operations per job with sequencing
    ✗ "First operation then second operation"

  Positive signals: "one operation per job", "parallel machines", "single stage"
  Example: "5 orders on 3 machines, each order processed once"

JOB-SHOP / FLOW-SHOP (multi-stage):
  Structure:
    • Each job has MULTIPLE operations with precedence
    • Variables: start[j,o] for job j, operation o
    • Precedence: operation k+1 starts after operation k finishes
    • Routing: different machine for each operation

  MUST HAVE:
    ✓ Multiple operations per job
    ✓ Operation sequences with precedence
    ✓ "Operation 1 then operation 2"

  Positive signals: "operation sequence", "routing", "multi-stage", "job shop"
  Example: "each job: M1 → M2 → M3"

═══════════════════════════════════════════════════════════════════════════════
DECISION PROCESS
═══════════════════════════════════════════════════════════════════════════════

Step 1: Count structural elements
  - How many node types? (2 sets = bipartite, 3+ = network)
  - How many operations per job? (1 = single-stage, 2+ = multi-stage)

Step 2: Look for explicit structural hints
  - "This is a bipartite problem" → transportation
  - "through intermediate nodes" → min_cost_flow
  - "one operation per job" → single_stage_scheduling
  - "operation sequence" → job_shop

Step 3: Ignore misleading keywords
  - The word "transportation" can appear in min-cost-flow problems
  - Focus on structure: bipartite vs network, single-stage vs multi-stage

Output ONLY JSON compliant with the given schema.
"""

USER_TMPL = """Schema (for validation reference):
{schema}

Text to classify:
\"\"\"{text}\"\"\"

═══════════════════════════════════════════════════════════════════════════════
CLASSIFICATION CHECKLIST
═══════════════════════════════════════════════════════════════════════════════

STEP 1: IDENTIFY NODE/JOB STRUCTURE

For TRANSPORTATION-like problems:
  □ Count node types:
    - Only sources + sinks (2 types)? → Likely TRANSPORTATION
    - Sources + intermediate + sinks (3+ types)? → Likely MIN-COST FLOW

  □ Check for explicit hints:
    - "bipartite", "direct shipping", "no intermediate"? → TRANSPORTATION
    - "through", "via", "hubs", "flow conservation"? → MIN-COST FLOW

  □ Look for transshipment:
    - NO intermediate nodes mentioned? → TRANSPORTATION
    - YES intermediate nodes with flow conservation? → MIN-COST FLOW

  Decision:
    → If bipartite: problem_type="transportation", solver_id="transport_basic_bipartite"
    → If network: problem_type="min_cost_flow", solver_id="none"

For SCHEDULING-like problems:
  □ Count operations per job:
    - Each job has ONE operation? → Likely SINGLE-STAGE
    - Jobs have MULTIPLE operations? → Likely JOB-SHOP/FLOW-SHOP

  □ Check for explicit hints:
    - "one operation per job", "parallel machines", "single stage"? → SINGLE-STAGE
    - "operation sequence", "multi-stage", "routing"? → JOB-SHOP

  □ Look for precedence:
    - NO "first...then", no operation sequences? → SINGLE-STAGE
    - YES "operation 1 then operation 2"? → JOB-SHOP

  Decision:
    → If single-stage: problem_type="single_stage_scheduling", solver_id="single_stage_ipm_scheduling"
    → If multi-stage: problem_type="job_shop" (or "flow_shop"), solver_id="none"

STEP 2: EXTRACT EVIDENCE

Gather direct quotes that support your classification:
  - Structural hints (e.g., "This is a bipartite problem")
  - Node/operation counts (e.g., "3 sources, 4 sinks", "one operation per job")
  - Keywords (e.g., "through hubs", "operation sequence")

STEP 3: ASSIGN CONFIDENCE

High confidence (0.9-1.0):
  - Text explicitly states structure ("This is a bipartite...")
  - Clear structural signals align with one type
  - No ambiguity

Medium confidence (0.7-0.9):
  - Structure is clear but not explicitly stated
  - Some keywords but structure is evident

Low confidence (0.5-0.7):
  - Ambiguous wording
  - Could be interpreted multiple ways

═══════════════════════════════════════════════════════════════════════════════
RETURN JSON WITH THESE FIELDS:
═══════════════════════════════════════════════════════════════════════════════

- problem_type: one of {enum}
- confidence: 0.0 to 1.0 (your epistemic confidence)
- solver_id: one of {solver_enum}
- signals: dict of structural cues detected
    Example: {{"bipartite_structure": true, "num_node_types": 2, "num_ops_per_job": 1}}
- evidence: list of short direct quotes from text
    Example: ["no intermediate nodes", "3 sources, 4 sinks"]
- why_short: one sentence explaining your classification
    Example: "Bipartite with 3 sources shipping directly to 4 sinks"
- objective: {{"sense": "minimize"/"maximize", "target": "cost"/"time"/etc}}
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