"""
Dynamic Parameter Detection for Analysis Framework

Uses LLM to detect which parameter to analyze from user queries,
making the analysis framework problem-agnostic.

Supports multiple OR problem types:
- Transportation: plants/markets, capacity/demand/cost
- Scheduling: jobs/machines, processing_time/due_date/setup_time
- Knapsack: items, weights/values/volume
- Assignment: workers/tasks, efficiency/cost/time
- Facility Location: facilities/customers, fixed_cost/variable_cost/distance
- Network Flow: nodes/arcs, capacity/cost/flow
- Portfolio: assets, returns/risk/correlation
- Vehicle Routing: vehicles/locations, distance/time/capacity

NEW PROBLEM TYPES: To add a new problem type, simply ensure your params dict
follows OR conventions (lists for entity sets, dicts for parameters).
The LLM will naturally understand new parameter types without code changes.
"""

from typing import Dict, Any, Optional
import json


# Common parameter patterns across OR problem types
# This helps the LLM understand various problem domains
PARAMETER_PATTERNS = {
    "transportation": {
        "sets": ["plants", "factories", "sources", "markets", "warehouses", "customers", "destinations", "sinks"],
        "params": ["capacity", "supply", "demand", "cost", "distance", "time", "arc_capacity"]
    },
    "scheduling": {
        "sets": ["jobs", "tasks", "operations", "machines", "processors", "resources"],
        "params": ["processing_time", "duration", "due_date", "deadline", "setup_time", "release_time", "priority", "weight"]
    },
    "knapsack": {
        "sets": ["items", "objects", "products"],
        "params": ["weights", "values", "profit", "volume", "size", "quantity", "limit", "capacity"]
    },
    "assignment": {
        "sets": ["workers", "agents", "employees", "tasks", "jobs", "projects"],
        "params": ["efficiency", "cost", "time", "skill_level", "compatibility"]
    },
    "facility_location": {
        "sets": ["facilities", "sites", "locations", "customers", "demand_points"],
        "params": ["fixed_cost", "opening_cost", "variable_cost", "distance", "capacity"]
    },
    "network_flow": {
        "sets": ["nodes", "vertices", "arcs", "edges"],
        "params": ["capacity", "cost", "lower_bound", "upper_bound", "flow"]
    },
    "portfolio": {
        "sets": ["assets", "stocks", "bonds", "investments"],
        "params": ["returns", "expected_return", "risk", "volatility", "correlation", "weight"]
    },
    "vehicle_routing": {
        "sets": ["vehicles", "trucks", "locations", "customers", "depots"],
        "params": ["distance", "time", "capacity", "demand", "service_time", "time_window"]
    }
}


def detect_parameter_from_query(
    query: str,
    params: Dict[str, Any],
    llm_client
) -> Optional[Dict[str, Any]]:
    """
    Use LLM to detect which parameter to analyze from a user query.

    Works with ANY problem type (transportation, scheduling, knapsack, etc.)
    by dynamically analyzing the query and available parameters.

    Args:
        query: User's natural language query
        params: Current problem parameters
        llm_client: LLM client for intelligent parsing

    Returns:
        Dictionary with:
        - parameter_name: str  # Which dict/param to modify (e.g., 'capacity', 'processing_time')
        - entity: str          # Which specific entity (e.g., 'Plant North', 'Job 5')
        - entity_type: str     # Which set the entity belongs to (e.g., 'plants', 'jobs')
        - current_value: float # Current value of the parameter

        Returns None if detection fails.

    Examples:
        Transportation:
        >>> detect_parameter_from_query("sensitivity on Plant North capacity", params, llm)
        {'parameter_name': 'capacity', 'entity': 'Plant North', 'entity_type': 'plants', 'current_value': 80}

        Scheduling:
        >>> detect_parameter_from_query("sensitivity on Job 5 processing time", params, llm)
        {'parameter_name': 'processing_time', 'entity': 'Job 5', 'entity_type': 'jobs', 'current_value': 12}

        Knapsack:
        >>> detect_parameter_from_query("sensitivity on Item 3 weight", params, llm)
        {'parameter_name': 'weights', 'entity': 'Item 3', 'entity_type': 'items', 'current_value': 45}

        Assignment:
        >>> detect_parameter_from_query("sensitivity on Worker A efficiency for Task 2", params, llm)
        {'parameter_name': 'efficiency', 'entity': 'Worker A', 'entity_type': 'workers', 'current_value': 0.85}
    """

    # Analyze parameter structure to identify sets (lists) and parameters (dicts/numbers)
    available_sets = {}
    available_params = {}

    for key, value in params.items():
        if isinstance(value, list) and value:
            # This is a set of entities (plants, jobs, items, machines, etc.)
            available_sets[key] = value
        elif isinstance(value, dict):
            # This is a parameter dictionary (capacity, demand, cost, processing_time, etc.)
            available_params[key] = value
        elif isinstance(value, (int, float)):
            # This is a scalar parameter
            available_params[key] = value

    # Build LLM prompt with multi-domain examples
    system_prompt = f"""You are an expert at parsing operations research queries across multiple problem domains.

Given a user query and available problem parameters, identify:
1. Which parameter to analyze (e.g., capacity, processing_time, weight, efficiency, demand, cost, etc.)
2. Which entity is mentioned (e.g., Plant North, Job 5, Item 3, Berlin, Amsterdam, etc.)
3. Which set that entity belongs to (e.g., plants, jobs, items, markets, customers, etc.)

IMPORTANT: The query can be in different formats:
- Command format: "sensitivity on Plant North capacity"
- Question format: "How does Berlin demand affect the cost?"
- Impact format: "What's the impact of changing Market A demand?"

Extract the parameter and entity regardless of format.

AVAILABLE PROBLEM PARAMETERS:
Sets (entity collections): {json.dumps(list(available_sets.keys()))}
Parameters: {json.dumps(list(available_params.keys()))}

Entity examples from sets:
{_format_entity_examples(available_sets)}

COMMON PARAMETER PATTERNS BY PROBLEM TYPE:
{_format_parameter_patterns()}

RESPONSE FORMAT:
Respond with a JSON object in this exact format:
{{
  "parameter_name": "capacity",
  "entity": "Plant North",
  "entity_type": "plants"
}}

EXAMPLES:
Query: "sensitivity on Plant North capacity"
Response: {{"parameter_name": "capacity", "entity": "Plant North", "entity_type": "plants"}}

Query: "How does Berlin demand affect the cost?"
Response: {{"parameter_name": "demand", "entity": "Berlin", "entity_type": "markets"}}

Query: "What's the impact of changing Job 5 processing time?"
Response: {{"parameter_name": "processing_time", "entity": "Job 5", "entity_type": "jobs"}}

If you cannot determine the parameter, respond with:
{{
  "error": "Could not identify parameter or entity"
}}

IMPORTANT: Match the parameter_name and entity_type to the EXACT keys in the available parameters above.
"""

    user_prompt = f"Query: {query}"

    try:
        # Call LLM to parse the query using the reasoning client
        response_text = llm_client.reasoning_client._chat(
            system_prompt,
            user_prompt,
            json_mode=True
        ).strip()

        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        result = json.loads(response_text)

        # Check for error response
        if "error" in result:
            return None

        # Validate and enrich the result
        param_name = result.get("parameter_name")
        entity = result.get("entity")
        entity_type = result.get("entity_type")

        if not param_name or not entity or not entity_type:
            return None

        # Verify entity exists in the specified set
        if entity_type not in available_sets:
            return None

        # Use fuzzy matching to find the entity
        matched_entity = _fuzzy_match_entity(entity, available_sets[entity_type])
        if not matched_entity:
            return None

        # Get current value
        current_value = _get_parameter_value(param_name, matched_entity, params)
        if current_value is None:
            return None

        return {
            "parameter_name": param_name,
            "entity": matched_entity,
            "entity_type": entity_type,
            "current_value": current_value
        }

    except Exception as e:
        print(f"Error in parameter detection: {e}")
        return None


def _format_parameter_patterns() -> str:
    """
    Format parameter patterns for LLM prompt.

    This helps the LLM understand common patterns across different OR problem types.
    """
    lines = []
    for problem_type, patterns in PARAMETER_PATTERNS.items():
        lines.append(f"  {problem_type.upper()}:")
        lines.append(f"    Sets: {', '.join(patterns['sets'])}")
        lines.append(f"    Parameters: {', '.join(patterns['params'])}")
    return "\n".join(lines)


def _format_entity_examples(available_sets: Dict[str, list]) -> str:
    """Format entity examples for LLM prompt."""
    lines = []
    for set_name, entities in available_sets.items():
        # Show first 3 entities as examples
        examples = entities[:3]
        lines.append(f"  {set_name}: {examples}")
    return "\n".join(lines)


def _fuzzy_match_entity(query_entity: str, entity_list: list) -> Optional[str]:
    """
    Fuzzy match an entity name against available entities.

    Handles case-insensitivity, extra spaces, and minor variations.
    """
    query_lower = query_entity.lower().strip()

    # Try exact match first
    for entity in entity_list:
        if entity.lower().strip() == query_lower:
            return entity

    # Try substring match
    for entity in entity_list:
        if query_lower in entity.lower() or entity.lower() in query_lower:
            return entity

    # Try token-based match (handles "Plant North" vs "North Plant")
    query_tokens = set(query_lower.split())
    for entity in entity_list:
        entity_tokens = set(entity.lower().split())
        if query_tokens == entity_tokens:
            return entity

    return None


def _get_parameter_value(param_name: str, entity: str, params: Dict[str, Any]) -> Optional[float]:
    """
    Extract the current value of a parameter for a given entity.

    Handles both simple dicts and nested dicts.
    """
    param_data = params.get(param_name)

    if param_data is None:
        return None

    # Simple dict: {entity: value}
    if isinstance(param_data, dict):
        if entity in param_data:
            return param_data[entity]

        # Try nested dict: {entity1: {entity2: value}}
        # For arc/edge parameters like cost[plant][market], efficiency[worker][task]
        for key, value in param_data.items():
            if isinstance(value, dict) and entity in value:
                # This is tricky - entity could be in either dimension
                # For now, return the first value found
                return value[entity]

    # Scalar parameter
    if isinstance(param_data, (int, float)):
        return param_data

    return None


def infer_entity_set_from_params(entity: str, params: Dict[str, Any]) -> Optional[str]:
    """
    Infer which set an entity belongs to by checking all available sets.

    Args:
        entity: Entity name to find
        params: Problem parameters

    Returns:
        Name of the set containing the entity, or None
    """
    for key, value in params.items():
        if isinstance(value, list) and entity in value:
            return key

    return None


# EXTENSION GUIDE:
# ================
# To add support for a new OR problem type:
#
# 1. Add a new entry to PARAMETER_PATTERNS dict above with common set/parameter names
#    Example for a new "bin_packing" problem:
#    "bin_packing": {
#        "sets": ["bins", "containers", "items", "objects"],
#        "params": ["bin_capacity", "item_size", "weight", "fragility"]
#    }
#
# 2. That's it! The LLM will automatically understand queries for the new problem type.
#    No code changes needed elsewhere.
#
# 3. Test with queries like:
#    "sensitivity on Bin 1 capacity"
#    "what if item 5 size increases by 10"
