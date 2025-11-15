# llm/schemas.py
"""
Classification schemas for OR problem identification.

Includes:
- CLASS_ENUM: Valid OR problem types (taxonomy)
- SOLVER_ID_ENUM: Valid solver IDs (what we can actually solve)
- CLASSIFICATION_SCHEMA: JSON schema for LLM classification output
"""

# ============================================================================
# OR PROBLEM TYPES (Taxonomy)
# ============================================================================
CLASS_ENUM = [
    # Transportation family
    "transportation",              # Bipartite plant→market
    "min_cost_flow",              # General network flow with transshipment

    # Scheduling family
    "single_stage_scheduling",     # Single processing step (solvable)
    "single_machine_tardiness",    # Single machine with tardiness objective
    "job_shop",                    # Multi-stage with operation sequences
    "flow_shop",                   # Fixed machine sequence
    "shift_rostering",             # Employee/nurse scheduling
    "project_scheduling",          # PERT/CPM with precedence

    # Assignment
    "assignment",

    # Knapsack
    "knapsack",

    # Network problems
    "shortest_path",
    "max_flow",

    # Location
    "facility_location",

    # Other
    "set_cover",
    "lot_sizing",
    "portfolio",
    "custom_review"               # Use when uncertain
]

# ============================================================================
# SOLVER IDs (What we can actually solve)
# ============================================================================
SOLVER_ID_ENUM = [
    "transport_basic_bipartite",       # Bipartite plant→market transportation
    "single_stage_ipm_scheduling",     # Single-stage immediate-precedence scheduling
    "none",                            # Problem recognized but no solver available
]

# ============================================================================
# CLASSIFICATION SCHEMA
# ============================================================================
CLASSIFICATION_SCHEMA = {
    "type": "object",
    "required": ["problem_type", "solver_id", "confidence", "signals", "evidence", "why_short", "objective"],
    "properties": {
        "problem_type": {
            "type": "string",
            "enum": CLASS_ENUM,
            "description": "OR problem type (taxonomy classification)"
        },
        "solver_id": {
            "type": "string",
            "enum": SOLVER_ID_ENUM,
            "description": "Specific solver that can handle this problem. Use 'none' if no solver available."
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
            "description": "Confidence in classification (0.0 to 1.0)"
        },
        "signals": {
            "type": "object",
            "description": "Structural signals detected (e.g., bipartite_structure, num_stages, etc.)",
            "additionalProperties": {"type": ["boolean", "number", "string"]}
        },
        "evidence": {
            "type": "array",
            "description": "Direct quotes from text supporting classification",
            "items": {
                "type": "object",
                "required": ["field", "quote"],
                "properties": {
                    "field": {"type": "string"},
                    "quote": {"type": "string"}
                }
            }
        },
        "why_short": {
            "type": "string",
            "description": "One short sentence explaining classification (no definitions)"
        },
        "objective": {
            "type": "object",
            "required": ["sense", "target"],
            "properties": {
                "sense": {
                    "type": "string",
                    "enum": ["minimize", "maximize", "unknown"]
                },
                "target": {
                    "type": "string",
                    "description": "What is being optimized (e.g., 'total_cost', 'makespan', 'tardiness')"
                }
            }
        }
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