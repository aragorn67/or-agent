# llm/enhanced_client.py
from typing import Dict, Any, List, Optional, Tuple
from .client import LLMClient
from .ollama_client import OllamaClient
from .transportation_specialist import TransportationSpecialist
from .scheduling_specialist import SchedulingSpecialist
from .problem_classifier import ProblemClassifier
from config import Config


def _make_stage_client(stage: str):
    """Return a per-stage Ollama chat client.

    stage ∈ {"classification", "extraction", "reasoning"}.
    """
    model = {
        "classification": Config.CLASSIFICATION_MODEL,
        "extraction": Config.EXTRACTION_MODEL,
        "reasoning": Config.REASONING_MODEL,
    }[stage]
    return OllamaClient(Config.OLLAMA_HOST, model)


class EnhancedLLMClient(LLMClient):
    """
    Enhanced LLM client with multi-model pipeline.

    Stage clients (classification / extraction / reasoning) are all Ollama-backed.
    """

    def __init__(self, host: str = None, model: str = None, knowledge_base=None):
        # host/model kwargs are accepted for backward compatibility but ignored —
        # configuration flows entirely through Config (Ollama host + per-stage models).
        self.kb = knowledge_base

        # Stage A: Classification
        self.classification_client = _make_stage_client("classification")
        self.classifier = ProblemClassifier(self.classification_client)

        # Stage B: Parameter Extraction
        self.extraction_client = _make_stage_client("extraction")
        self.transportation = TransportationSpecialist(self.extraction_client, knowledge_base)
        self.scheduling = SchedulingSpecialist(self.extraction_client, knowledge_base)

        # Stage E: Reasoning & Explanations
        self.reasoning_client = _make_stage_client("reasoning")

        # Legacy: base_client points to classification for backward compatibility
        self.base_client = self.classification_client
        self.host = getattr(self.base_client, "host", None)

        # Future specialists can be added here:
        # self.assignment = AssignmentSpecialist(self.base_client, knowledge_base)
        # self.knapsack = KnapsackSpecialist(self.base_client, knowledge_base)

    def classify_problem(self, description: str, problem_types: List[str] = None) -> Dict[str, Any]:
        """Classify problem type using structured schema-based classifier"""
        classification, votes = self.classifier.classify(description)

        # Convert to format with both legacy fields and new solver_id
        result = {
            "type": classification["problem_type"].upper(),  # legacy field
            "problem_type": classification["problem_type"],  # new field
            "solver_id": classification.get("solver_id", "none"),  # NEW: specific solver
            "confidence": classification["confidence"],
            "signals": classification.get("signals", {}),
            "evidence": classification.get("evidence", []),
            "reasoning": classification.get("why_short", ""),
            "objective": classification.get("objective", {}),
            "votes": votes  # Include all votes for debugging
        }

        return result

    def extract_parameters(self, description: str, problem_type: str, example: Dict) -> Dict[str, Any]:
        """Route to appropriate specialist based on problem type"""

        problem_type = (problem_type or "").upper()

        # Transportation family (includes min_cost_flow if bipartite)
        if problem_type in ["TRANSPORTATION", "MIN_COST_FLOW"]:
            return self.transportation.extract_parameters(description)

        # Scheduling family — every label the classifier maps to the single-stage
        # IPM solver in llm/problem_classifier.py must also route here. Otherwise
        # the agent classifies correctly but extraction rejects the same label.
        elif problem_type in [
            "SCHEDULING",
            "SINGLE_STAGE_SCHEDULING",
            "SINGLE_MACHINE_MAKESPAN",
            "SINGLE_MACHINE_TARDINESS",
            "PARALLEL_MACHINE_SCHEDULING",
            "JOB_SHOP",
        ]:
            return self.scheduling.extract_parameters(description)

        # Future problem types:
        # elif problem_type == "ASSIGNMENT":
        #     return self.assignment.extract_parameters(description)

        else:
            # Fallback to base client for unsupported types
            return {"error": f"Problem type '{problem_type}' not yet supported by specialist handlers"}

    def explain_solution(self, solution: Dict, problem_type: str, original_description: str = "") -> Dict[str, Any]:
        """
        Generate clean, factual explanation with proper units using REASONING model.

        Uses deepseek-r1:latest for intelligent explanations and analysis.

        Returns:
            {
                'summary': brief summary with units,
                'explanation': detailed explanation,
                'units_info': detected units (currency, distance, etc.),
                'grounding_check': 'passed' or 'deterministic_fallback'
            }
        """

        from .solution_formatter import SolutionFormatter

        # Use reasoning client (deepseek-r1) for intelligent explanations
        formatter = SolutionFormatter(self.reasoning_client)
        result = formatter.format_solution(solution, problem_type, original_description)

        # Return full dict instead of just explanation string
        return {
            'summary': result.get('formatted_summary', ''),
            'explanation': result.get('explanation', ''),
            'units_info': result.get('units_info', {}),
            'grounding_check': result.get('grounding_check', 'deterministic_fallback')
        }

    def detect_follow_up_intent(self, new_message: str, conversation_context: Dict) -> Dict[str, Any]:
        """Detect follow-up intent using base client"""
        return self.base_client.detect_follow_up_intent(new_message, conversation_context)

    def _chat(self, system: str, user: str, json_mode: bool = False) -> str:
        """Delegate core chat functionality to base client"""
        return self.base_client._chat(system, user, json_mode)

    def extract_modification_parameters(self, user_request: str, original_params: Dict) -> Dict[str, Any]:
        """Route modification detection to appropriate specialist"""

        # Try to detect problem type from params structure
        if self._is_transportation_params(original_params):
            return self.transportation.detect_transportation_modifications(user_request, original_params)

        # Future problem types:
        # elif self._is_scheduling_params(original_params):
        #     return self.scheduling.detect_scheduling_modifications(user_request, original_params)

        else:
            # Fallback to base client
            return self.base_client.extract_modification_parameters(user_request, original_params)

    def parse_infeasibility_fix(self, user_message: str, current_params: Dict, infeasibility_context: Dict) -> Dict[str, Any]:
        """
        Parse user's response to infeasibility report.

        Args:
            user_message: User's modification message
            current_params: Current problem parameters
            infeasibility_context: Context about the infeasibility (layer, reasons, suggestions)

        Returns:
            {
                "is_complete_redescription": bool,  # True if user provided complete new problem
                "modifications": [
                    {"type": "increase|decrease|set|add", "entity": "name", "parameter": "capacity", "value": float},
                    ...
                ],
                "applied_params": Dict  # Modified parameters (if modifications parsed)
            }
        """
        from .json_utils import safe_json_parse

        # Use reasoning model for intelligent parsing
        system = """You are parsing user modifications to fix an infeasible optimization problem.

The user was told their problem is infeasible and given suggestions. They're now responding with either:
1. A complete new problem description (redescription)
2. Specific modifications like "increase capacity of A by 50" or "set demand for B to 100"

Return JSON matching this schema:
{
  "is_complete_redescription": true/false,
  "modifications": [
    {
      "type": "increase|decrease|set|add|remove",
      "entity": "entity name (e.g., Factory1, Market2, route from A to B, OrderC, ALL)",
      "parameter": "capacity|demand|cost|arc_capacity|supply|due_date|processing_time|eligible",
      "value": numeric value (for increase/decrease, this is the delta; for set, this is the new value)
    }
  ]
}

There are two problem families. Transportation params use plants/markets with
capacity, demand, cost, arc_capacity, supply. Scheduling params use orders/units
with due_date (deadline per order), processing_time (hours for an order on a
unit), and eligible (which units an order may run on).

Rules:
- If the message looks like a complete new problem description, set is_complete_redescription=true and leave modifications empty
- For modifications like "increase X by Y", type="increase", value=Y (POSITIVE number)
- For modifications like "decrease X by Y", type="decrease", value=Y (POSITIVE number - the amount to decrease)
- For modifications like "set X to Y", type="set", value=Y
- For modifications like "add route from A to B with cost C", type="add"
- Extract ALL modifications mentioned in the message
- CRITICAL: For "decrease" operations, value should be POSITIVE (the magnitude of decrease), NOT negative

Scheduling-specific rules:
- A deadline / due date change uses parameter="due_date". The entity is the
  order name (e.g. "OrderC"). "OrderC's deadline moves up to hour 9" →
  {"type":"set","entity":"OrderC","parameter":"due_date","value":9}.
- When a deadline applies to EVERY order ("every order must be completed
  within 4 hours", "all orders due by hour 6"), use entity="ALL":
  {"type":"set","entity":"ALL","parameter":"due_date","value":4}.
- A processing-time change uses parameter="processing_time" with the entity
  naming both order and unit, "OrderA on Unit1": "OrderA now takes 7 hours on
  Unit1" → {"type":"set","entity":"OrderA on Unit1","parameter":"processing_time","value":7}.
- "tighter / sooner / move up / must finish within" a deadline means a SMALLER
  due_date number; prefer type="set" with the absolute hour when one is given.
"""

        layer_info = infeasibility_context.get('layer_failed', 'unknown')
        reasons = infeasibility_context.get('reasons', [])
        suggestions = infeasibility_context.get('suggestions', [])

        user = f"""User message: "{user_message}"

Context:
- Infeasibility detected at Layer {layer_info}
- Reasons: {reasons[:2] if reasons else 'unknown'}
- Suggestions given: {suggestions[:2] if suggestions else 'none'}

Current parameters (for reference):
{str(current_params)[:500]}

Parse the user's response and return modifications."""

        try:
            response = self.reasoning_client._chat(system, user, json_mode=True)
            result = safe_json_parse(response, {
                "is_complete_redescription": False,
                "modifications": []
            })

            # If complete redescription, return as-is
            if result.get("is_complete_redescription", False):
                return {
                    "is_complete_redescription": True,
                    "modifications": [],
                    "applied_params": None  # Will be re-extracted
                }

            # Fix modification values (ensure decrease/increase have correct signs)
            modifications = result.get("modifications", [])
            for mod in modifications:
                if mod.get("type") in ["decrease", "increase"]:
                    # Value should always be positive (magnitude)
                    mod["value"] = abs(mod.get("value", 0))

            # Apply modifications to params
            modified_params, applied_count = self._apply_modifications(
                current_params, modifications
            )

            return {
                "is_complete_redescription": False,
                "modifications": modifications,  # Return the fixed modifications
                "applied_count": applied_count,  # 0 => nothing actually changed
                "applied_params": modified_params
            }

        except Exception as e:
            return {
                "is_complete_redescription": False,
                "modifications": [],
                "error": str(e),
                "applied_params": current_params  # Return unchanged
            }

    def suggest_analysis(self, solution: Dict, params: Dict, problem_type: str) -> List[str]:
        """Get problem-specific analysis suggestions"""

        problem_type = (problem_type or "").upper()

        if problem_type == "TRANSPORTATION":
            return self.transportation.suggest_transportation_analysis(solution, params)

        elif problem_type == "SCHEDULING":
            return self.scheduling.suggest_scheduling_analysis(solution, params)

        # Future problem types will have their own suggestions

        else:
            return ["Basic solution analysis", "Parameter sensitivity analysis"]

    def _is_transportation_params(self, params: Dict) -> bool:
        """Check if parameters match transportation problem structure"""
        required_keys = {"plants", "markets", "capacity", "demand"}
        return required_keys.issubset(set(params.keys()))

    def _is_scheduling_params(self, params: Dict) -> bool:
        """Check if parameters match scheduling problem structure"""
        required_keys = {"orders", "units", "processing_time", "due_date"}
        return required_keys.issubset(set(params.keys()))

    def _apply_modifications(self, params: Dict, modifications: List[Dict]) -> Tuple[Dict, int]:
        """
        Apply parsed modifications to parameters.

        Args:
            params: Current parameters
            modifications: List of modification dicts

        Returns:
            (modified params deep copy, count of modifications actually applied).
            A zero count means nothing changed — callers must NOT treat the
            unchanged params as a valid scenario (that was the silent
            false-feasible bug for scheduling deadlines).
        """
        import copy

        # Deep copy to avoid modifying original
        modified = copy.deepcopy(params)
        applied_count = 0

        def _num(cur, new_v, kind):
            """Apply set/increase/decrease to a scalar, clamped at 0."""
            if kind == "increase":
                return cur + new_v
            if kind == "decrease":
                return max(0, cur - new_v)
            return new_v  # set

        def find_entity_fuzzy(entity: str, entity_list: list) -> str:
            """Find entity in list using fuzzy matching (case-insensitive, handles center/centre)"""
            entity_lower = entity.lower().strip()

            # Try exact match first
            for e in entity_list:
                if e == entity:
                    return e

            # Try case-insensitive match
            for e in entity_list:
                if e.lower() == entity_lower:
                    return e

            # Try with center/centre normalization
            entity_normalized = entity_lower.replace('center', 'centre')
            for e in entity_list:
                if e.lower().replace('center', 'centre') == entity_normalized:
                    return e

            # No match found
            return None

        for mod in modifications:
            mod_type = mod.get("type", "")
            entity = mod.get("entity", "")
            parameter = mod.get("parameter", "")
            value = mod.get("value", 0)

            _before = copy.deepcopy(modified)
            try:
                # Check if this is an arc capacity modification
                # Entity like "arc from F1 to C" should be treated as arc_capacity
                is_arc = "arc" in entity.lower() or " to " in entity.lower() or "→" in entity

                if parameter in ["capacity", "supply"] and not is_arc:
                    # Modify source/plant capacity (not arc capacity)
                    if "capacity" in modified:
                        # Use fuzzy matching to find entity
                        matched_entity = find_entity_fuzzy(entity, list(modified["capacity"].keys()))
                        if matched_entity:
                            if mod_type == "increase":
                                modified["capacity"][matched_entity] += value
                            elif mod_type == "decrease":
                                modified["capacity"][matched_entity] = max(0, modified["capacity"][matched_entity] - value)
                            elif mod_type == "set":
                                modified["capacity"][matched_entity] = value

                elif (parameter in ["capacity", "supply"] and is_arc) or parameter == "arc_capacity":
                    # Modify arc capacity - treat nested dict {i: {j: cap}} and flat dict {(i,j): cap}
                    if "arc_capacity" not in modified:
                        modified["arc_capacity"] = {}

                    route = self._parse_route(entity, modified.get("plants", []), modified.get("markets", []))
                    if route:
                        source, sink = route

                        # Ensure nested structure exists
                        if source not in modified["arc_capacity"]:
                            modified["arc_capacity"][source] = {}

                        current_value = modified["arc_capacity"][source].get(sink, 0)

                        if mod_type == "increase":
                            modified["arc_capacity"][source][sink] = current_value + value
                        elif mod_type == "decrease":
                            modified["arc_capacity"][source][sink] = max(0, current_value - value)
                        elif mod_type == "set":
                            modified["arc_capacity"][source][sink] = value

                elif parameter == "demand":
                    # Modify sink/market demand
                    if "demand" in modified:
                        # Use fuzzy matching to find entity
                        matched_entity = find_entity_fuzzy(entity, list(modified["demand"].keys()))
                        if matched_entity:
                            if mod_type == "increase":
                                modified["demand"][matched_entity] += value
                            elif mod_type == "decrease":
                                modified["demand"][matched_entity] = max(0, modified["demand"][matched_entity] - value)
                            elif mod_type == "set":
                                modified["demand"][matched_entity] = value

                elif parameter in ["cost", "distance"]:
                    # Modify cost/distance for a route
                    # Entity format: "A to B" or "A→B" or "route from A to B"
                    if parameter in modified and isinstance(modified[parameter], dict):
                        # Try to parse entity as route
                        route = self._parse_route(entity, modified.get("plants", []), modified.get("markets", []))
                        if route:
                            source, sink = route

                            # Handle BOTH nested dict {i: {j: cost}} AND flat dict {(i,j): cost}
                            # Check if nested format
                            if source in modified[parameter] and isinstance(modified[parameter][source], dict):
                                # Nested format: modified["cost"]["Bordeaux"]["Amsterdam"]
                                if sink in modified[parameter][source]:
                                    current_value = modified[parameter][source][sink]
                                    if mod_type == "increase":
                                        modified[parameter][source][sink] = current_value + value
                                    elif mod_type == "decrease":
                                        modified[parameter][source][sink] = max(0, current_value - value)
                                    elif mod_type == "set":
                                        modified[parameter][source][sink] = value
                                elif mod_type in ["add", "set"]:
                                    # Add new route in nested format
                                    modified[parameter][source][sink] = value

                            # Check if flat format
                            elif route in modified[parameter]:
                                # Flat format: modified["cost"][("Bordeaux", "Amsterdam")]
                                if mod_type == "increase":
                                    modified[parameter][route] += value
                                elif mod_type == "decrease":
                                    modified[parameter][route] = max(0, modified[parameter][route] - value)
                                elif mod_type == "set":
                                    modified[parameter][route] = value

                            elif mod_type in ["add", "set"]:
                                # Add new route - try nested format first
                                if source in modified[parameter]:
                                    if not isinstance(modified[parameter][source], dict):
                                        # Convert to nested if needed
                                        modified[parameter][source] = {}
                                    modified[parameter][source][sink] = value
                                else:
                                    # Create nested structure
                                    modified[parameter][source] = {sink: value}

                elif parameter in ["due_date", "deadline", "due"] and "due_date" in modified:
                    # Scheduling deadline. Entity is an order name, or "ALL"
                    # / "all orders" / "every order" when it applies to all.
                    ent = entity.lower().strip()
                    if ent in ("all", "all orders", "every order", "orders", "") \
                            or "all order" in ent or "every order" in ent:
                        targets = list(modified["due_date"].keys())
                    else:
                        m = find_entity_fuzzy(entity, list(modified["due_date"].keys()))
                        targets = [m] if m else []
                    for o in targets:
                        modified["due_date"][o] = _num(
                            modified["due_date"][o], value, mod_type
                        )

                elif parameter in ["processing_time", "proc_time", "processing"] \
                        and "processing_time" in modified:
                    # Entity names both order and unit: "OrderA on Unit1".
                    orders = list(modified["processing_time"].keys())
                    units = sorted({u for o in orders
                                    for u in modified["processing_time"][o]})
                    o = find_entity_fuzzy(
                        entity, orders) or next(
                        (x for x in orders if x.lower() in entity.lower()), None)
                    u = find_entity_fuzzy(
                        entity, units) or next(
                        (x for x in units if x.lower() in entity.lower()), None)
                    if o and u and u in modified["processing_time"].get(o, {}):
                        modified["processing_time"][o][u] = _num(
                            modified["processing_time"][o][u], value, mod_type
                        )

            except Exception as e:
                # If modification fails, skip it silently
                print(f"Warning: Could not apply modification {mod}: {e}")

            if modified != _before:
                applied_count += 1

        return modified, applied_count

    def _parse_route(self, entity_str: str, sources: List[str], sinks: List[str]) -> Optional[tuple]:
        """
        Parse route entity string like "A to B" or "F1→M2" or "arc from F1 to C" into tuple (source, sink).

        Args:
            entity_str: String describing the route
            sources: List of valid source names
            sinks: List of valid sink names

        Returns:
            (source, sink) tuple or None if can't parse
        """
        entity_lower = entity_str.lower()

        # Special case: "arc from X to Y" or "route from X to Y"
        if " from " in entity_lower and " to " in entity_lower:
            # Extract X and Y from "arc from X to Y"
            from_idx = entity_lower.find(" from ")
            to_idx = entity_lower.find(" to ", from_idx)

            src_candidate = entity_str[from_idx + 6:to_idx].strip()  # 6 = len(" from ")
            sink_candidate = entity_str[to_idx + 4:].strip()  # 4 = len(" to ")

            # Try to match to actual source/sink names (case-insensitive, fuzzy)
            for src in sources:
                if src.lower() == src_candidate.lower():
                    for sink in sinks:
                        if sink.lower() == sink_candidate.lower():
                            return (src, sink)

        # Try different separators
        separators = [" to ", "→", " -> ", "->"]

        for sep in separators:
            if sep in entity_lower or sep.strip() in entity_str:
                parts = entity_str.split(sep) if sep in entity_str else entity_str.lower().split(sep)
                if len(parts) >= 2:
                    src_candidate = parts[0].strip()
                    sink_candidate = parts[1].strip()

                    # Try to match to actual source/sink names
                    for src in sources:
                        if src.lower() == src_candidate.lower() or src_candidate.lower() in src.lower():
                            for sink in sinks:
                                if sink.lower() == sink_candidate.lower() or sink_candidate.lower() in sink.lower():
                                    return (src, sink)

        # Try parsing as direct mention
        for src in sources:
            for sink in sinks:
                if src.lower() in entity_lower and sink.lower() in entity_lower:
                    return (src, sink)

        return None

    # Future helper methods for other problem types:

    # def _is_assignment_params(self, params: Dict) -> bool:
    #     required_keys = {"agents", "tasks", "costs"}
    #     return required_keys.issubset(set(params.keys()))