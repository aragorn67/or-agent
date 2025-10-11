# llm/schemas.py
CLASS_ENUM = [
    "transportation", "assignment", "knapsack",
    "shortest_path", "max_flow", "facility_location",
    "job_shop", "set_cover", "lot_sizing", "portfolio",
    "custom_review"  # use when uncertain
]

CLASSIFICATION_SCHEMA = {
  "type": "object",
  "required": ["problem_type","confidence","signals","evidence","why_short"],
  "properties": {
    "problem_type": {"type":"string","enum": CLASS_ENUM},
    "confidence": {"type":"number","minimum":0,"maximum":1},
    "signals": {"type":"object","additionalProperties":{"type":["boolean","number","string"]}},
    "evidence": {"type":"array","items": {
        "type":"object","required":["field","quote"],
        "properties":{"field":{"type":"string"},"quote":{"type":"string"}}
    }},
    "why_short": {"type":"string"}  # 1-liner, no definitions
  },
  "additionalProperties": False
}

# Tiny schema for follow-up detection (replaces the mega-prompt in ollama_client.py)
FOLLOW_UP_TYPES = ["question", "modification", "analysis", "new_problem"]

FOLLOW_UP_SCHEMA = {
  "type": "object",
  "required": ["is_follow_up", "follow_up_type", "confidence"],
  "properties": {
    "is_follow_up": {"type": "boolean"},
    "follow_up_type": {"type": "string", "enum": FOLLOW_UP_TYPES},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    "question_category": {
      "type": "string",
      "enum": ["objective", "variables", "constraints", "results", "capabilities", "general"],
      "description": "Only for 'question' type"
    },
    "modification_targets": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Only for 'modification' type: what parameters to change"
    },
    "analysis_types": {
      "type": "array",
      "items": {"type": "string", "enum": ["sensitivity", "visualization", "scenario", "tradeoff"]},
      "description": "Only for 'analysis' type"
    }
  },
  "additionalProperties": False
}