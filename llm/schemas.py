# llm/schemas.py
"""
Classification schemas for OR problem identification.

Includes:
- CLASS_ENUM: Valid OR problem types (taxonomy)
- SOLVER_ID_ENUM: Valid solver IDs (what we can actually solve)
- CLASSIFICATION_SCHEMA: JSON schema for LLM classification output
"""

# ============================================================================
# OR PROBLEM TYPES (Taxonomy with Subtypes)
# ============================================================================
# Hierarchy: Some types are subtypes of others, both valid for classification
# Example: "single_machine_tardiness" is a SUBTYPE of "single_stage_scheduling"
# When both apply, prefer the more specific subtype for better precision
#
# Notation: [SOLVABLE] = we have a solver, [→ parent] = subtype of parent
# ============================================================================

CLASS_ENUM = [
    # ═══════════════════════════════════════════════════════════════════════
    # TRANSPORTATION FAMILY
    # ═══════════════════════════════════════════════════════════════════════
    "transportation",              # [SOLVABLE] Bipartite: sources → sinks only
    "min_cost_flow",              # Network with intermediate/transshipment nodes
    "max_flow",                   # Network: maximize flow from source to sink
    "shortest_path",              # Network: find minimum cost path

    # ═══════════════════════════════════════════════════════════════════════
    # SCHEDULING FAMILY - SINGLE STAGE (one operation per job)
    # ═══════════════════════════════════════════════════════════════════════
    "single_stage_scheduling",     # [SOLVABLE] Generic: parallel machines, one op per job

    # Subtypes of single_stage_scheduling (more specific):
    "single_machine_tardiness",    # [SOLVABLE] [→ single_stage] One machine, minimize Σ tardiness
    "single_machine_makespan",     # [SOLVABLE] [→ single_stage] One machine, minimize completion time
    "parallel_machine_scheduling", # [SOLVABLE] [→ single_stage] Multiple identical machines

    # ═══════════════════════════════════════════════════════════════════════
    # SCHEDULING FAMILY - MULTI STAGE (multiple operations per job)
    # ═══════════════════════════════════════════════════════════════════════
    "job_shop",                    # Jobs with operation sequences, flexible routing
    "flow_shop",                   # All jobs follow same machine sequence
    "open_shop",                   # Jobs with operations, any order allowed

    # ═══════════════════════════════════════════════════════════════════════
    # SCHEDULING FAMILY - OTHER
    # ═══════════════════════════════════════════════════════════════════════
    "shift_rostering",             # Employee/nurse shift scheduling
    "project_scheduling",          # PERT/CPM with task precedence
    "batch_scheduling",            # Chemical/pharma batch processing

    # ═══════════════════════════════════════════════════════════════════════
    # ASSIGNMENT FAMILY
    # ═══════════════════════════════════════════════════════════════════════
    "assignment",                  # Generic: workers to tasks, one-to-one
    "bipartite_matching",          # [→ assignment] Maximum matching in bipartite graph
    "generalized_assignment",      # [→ assignment] With capacity/resource constraints

    # ═══════════════════════════════════════════════════════════════════════
    # KNAPSACK FAMILY
    # ═══════════════════════════════════════════════════════════════════════
    "knapsack",                    # Generic: 0-1 or bounded knapsack
    "zero_one_knapsack",           # [→ knapsack] Binary selection only
    "bounded_knapsack",            # [→ knapsack] Limited quantities per item
    "unbounded_knapsack",          # [→ knapsack] Unlimited quantities
    "multidimensional_knapsack",   # [→ knapsack] Multiple resource constraints

    # ═══════════════════════════════════════════════════════════════════════
    # LOCATION FAMILY
    # ═══════════════════════════════════════════════════════════════════════
    "facility_location",           # Generic: where to locate facilities
    "uncapacitated_facility_location",  # [→ facility_location] No capacity limits
    "capacitated_facility_location",    # [→ facility_location] With capacity constraints

    # ═══════════════════════════════════════════════════════════════════════
    # VEHICLE ROUTING FAMILY
    # ═══════════════════════════════════════════════════════════════════════
    "vehicle_routing",             # Generic: routes for vehicles
    "cvrp",                        # [→ vehicle_routing] Capacitated VRP
    "vrptw",                       # [→ vehicle_routing] VRP with time windows
    "tsp",                         # [→ vehicle_routing] Traveling salesman

    # ═══════════════════════════════════════════════════════════════════════
    # PRODUCTION PLANNING FAMILY
    # ═══════════════════════════════════════════════════════════════════════
    "lot_sizing",                  # Production quantities over time periods
    "production_planning",         # Multi-product aggregate planning

    # ═══════════════════════════════════════════════════════════════════════
    # OTHER
    # ═══════════════════════════════════════════════════════════════════════
    "set_cover",                   # Cover elements with minimum cost sets
    "bin_packing",                 # Pack items into minimum bins
    "cutting_stock",               # Minimize waste when cutting materials
    "portfolio",                   # Financial portfolio optimization
    "custom_review"                # Use when structure doesn't match any type
]

# ============================================================================
# SOLVER IDs (What we can actually solve)
# ============================================================================
SOLVER_ID_ENUM = [
    "transport_basic_bipartite",       # Bipartite plant→market transportation
    "single_stage_ipm_scheduling",     # Single-stage immediate-precedence scheduling (makespan/changeover)
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