# llm/problem_classifier.py
import json
from collections import Counter
from typing import Dict, Any, Tuple, List
try:
    from jsonschema import Draft2020Validator
    _HAVE_JSONSCHEMA = True
except Exception:
    _HAVE_JSONSCHEMA = False

from .schemas import CLASS_ENUM, CLASSIFICATION_SCHEMA

SYSTEM = """You are an Operations Research problem classifier.
Infer the problem TYPE from structure, not from keywords.
- Rely on detected sets, decision domains (binary/integer/continuous), and constraint patterns.
- Ignore literal mentions like "assignment", "transportation", etc. They may be red herrings.
Output ONLY JSON compliant with the given schema.
"""

USER_TMPL = """Schema (for validation reference):
{schema}

Text to classify:
\"\"\"{text}\"\"\"

Return fields:
- problem_type: one of {enum}
- confidence: 0..1 (epistemic confidence in your classification)
- signals: a few booleans/numbers/strings capturing structural cues you used
  e.g., has_one_to_one_assignment, flow_conservation, capacity_limit, selection_under_budget, path_optimality, binary_decisions, continuous_flow, cost_matrix_present, supply_vector_present, demand_vector_present, facility_opening_costs, time_indexing, precedence_constraints, etc.
- evidence: list of short direct quotes from the text (no paraphrase) tied to the signals
- why_short: one short sentence (no definitions, no background)
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
                                enum=CLASS_ENUM, text=text)
        out = self.llm._chat(SYSTEM, user, json_mode=True)   # Ollama client must support format=json
        obj = json.loads(out)
        return obj

    def classify(self, text: str, n: int = 3) -> Tuple[Dict[str,Any], List[Dict[str,Any]]]:
        """Run n votes (low temperature) and return the consensus object + all raw votes."""
        votes = []
        for _ in range(n):
            try:
                v = self._classify_once(text)
            except Exception:
                continue
            v["_errors"] = _validate(v)
            votes.append(v)
        if not votes:
            return {"problem_type":"custom_review","confidence":0.0,
                    "signals":{}, "evidence":[], "why_short":"No valid vote."}, []

        # Majority vote on problem_type among VALID votes; tie-break by mean confidence
        valid = [v for v in votes if not v["_errors"]]
        pool = valid or votes
        counts = Counter(v.get("problem_type","custom_review") for v in pool)
        top_type, _ = counts.most_common(1)[0]
        # pick best representative of that type
        same = [v for v in pool if v.get("problem_type")==top_type]
        best = max(same, key=lambda v: float(v.get("confidence",0)))
        # clamp and clean
        best["confidence"] = float(min(1.0, max(0.0, best.get("confidence",0))))
        best.pop("_errors", None)
        return best, votes