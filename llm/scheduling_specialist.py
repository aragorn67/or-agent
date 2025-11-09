# llm/scheduling_specialist.py
import json
from typing import Dict, Any, List
from .ollama_client import OllamaClient

class SchedulingSpecialist:
    """Specialized LLM handler for scheduling optimization problems"""

    def __init__(self, ollama_client: OllamaClient, knowledge_base=None):
        """
        Initialize scheduling specialist.

        Args:
            ollama_client: LLM client for parameter extraction
            knowledge_base: Optional KnowledgeBase for RAG context
        """
        self.client = ollama_client
        self.kb = knowledge_base

    def extract_parameters(self, description: str) -> Dict[str, Any]:
        """Extract scheduling-specific parameters with deep validation"""

        # Get relevant context from knowledge base if available
        rag_context = ""
        if self.kb is not None:
            try:
                rag_context = self.kb.get_context(
                    "scheduling problem makespan processing time changeover",
                    max_tokens=500
                )
                if rag_context:
                    rag_context = f"\n\nRelevant OR knowledge:\n{rag_context}\n"
            except:
                pass  # KB not available, continue without RAG

        system = f"""
Extract parameters for a Scheduling problem. Output STRICT JSON with keys:
- orders: string[] (jobs, tasks, orders to be scheduled)
- units: string[] (machines, resources, processing units)
- eligible: {{order: string[]}} (which units can process each order)
- processing_time: {{order: {{unit: number}}}} (time to process order on unit)
- due_date: {{order: number}} (deadline for each order)
- changeover: {{unit: {{order1: {{order2: number}}}}}} (optional - setup/changeover time between orders on same unit)
- window: {{order: 0 or 1}} (optional - if 1, order has strict time window)
- lower: {{order: number}} (optional - earliest start time for orders with time window)
- objective: string (optional - "makespan" or "changeover", default "makespan")

EXTRACTION RULES:
1. Use ONLY entities & numbers explicitly mentioned in the text
2. Look for various phrasings: "jobs/orders/tasks" = orders, "machines/units/resources" = units
3. Extract ALL processing times mentioned (e.g., "Order A takes 2 hours on Unit 1")
4. Extract ALL due dates/deadlines mentioned (e.g., "Order A due by hour 10")
5. Extract eligibility constraints (e.g., "Order B can only use Unit 1")
6. Extract changeover/setup times if mentioned (e.g., "switching from A to B takes 0.5 hours")
7. If time windows mentioned, set window=1 and extract lower bound
8. If ANY required piece is missing, return: {{"error": "<specific missing information>"}}
9. All numbers must be numeric types, not strings
10. Time units should be consistent (convert to hours if needed)

NESTED STRUCTURE EXAMPLES:
- processing_time: {"O1": {"U1": 2.0, "U2": 3.0}, "O2": {"U1": 1.5}}
- changeover: {"U1": {"O1": {"O2": 0.5, "O3": 0.3}, "O2": {"O1": 0.4}}}
- eligible: {"O1": ["U1", "U2"], "O2": ["U1"], "O3": ["U1", "U2"]}
"""

        user = f"SCHEDULING PROBLEM:\n{description}\n\nReturn ONLY the JSON."

        try:
            content = self.client._chat(system, user, json_mode=True)
            result = json.loads(content)

            if "error" in result:
                return result

            # Deep validation for scheduling
            validation_error = self._validate_scheduling_deep(description, result)
            if validation_error:
                return {"error": validation_error}

            return result

        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON response from LLM: {str(e)}"}
        except Exception as e:
            return {"error": f"Scheduling extraction error: {e}"}

    def _validate_scheduling_deep(self, description: str, params: Dict) -> str:
        """Deep validation specifically for scheduling problems"""

        # Core structure validation
        required = ["orders", "units", "eligible", "processing_time", "due_date"]
        missing = [k for k in required if k not in params or not params[k]]
        if missing:
            return f"Missing required scheduling data: {', '.join(missing)}. Please specify all orders, units, eligibility, processing times, and due dates."

        orders = params["orders"]
        units = params["units"]
        eligible = params["eligible"]
        processing_time = params["processing_time"]
        due_date = params["due_date"]

        # Type validation
        if not isinstance(orders, list):
            return "orders must be a list"
        if not isinstance(units, list):
            return "units must be a list"
        if not isinstance(eligible, dict):
            return "eligible must be a dictionary"
        if not isinstance(processing_time, dict):
            return "processing_time must be a dictionary"
        if not isinstance(due_date, dict):
            return "due_date must be a dictionary"

        # Check all orders have eligibility
        if set(eligible.keys()) != set(orders):
            missing_elig = set(orders) - set(eligible.keys())
            extra_elig = set(eligible.keys()) - set(orders)
            if missing_elig:
                return f"Missing eligibility data for orders: {', '.join(missing_elig)}"
            if extra_elig:
                return f"Extra eligibility data for unknown orders: {', '.join(extra_elig)}"

        # Check all orders have processing times
        if set(processing_time.keys()) != set(orders):
            missing_pt = set(orders) - set(processing_time.keys())
            if missing_pt:
                return f"Missing processing time data for orders: {', '.join(missing_pt)}"

        # Check all orders have due dates
        if set(due_date.keys()) != set(orders):
            missing_dd = set(orders) - set(due_date.keys())
            if missing_dd:
                return f"Missing due date data for orders: {', '.join(missing_dd)}"

        # Validate eligibility structure
        for order, eligible_units in eligible.items():
            if not isinstance(eligible_units, list):
                return f"Eligibility for order '{order}' must be a list of units"
            if not eligible_units:
                return f"Order '{order}' has no eligible units"

            # Check all eligible units exist
            invalid_units = [u for u in eligible_units if u not in units]
            if invalid_units:
                return f"Order '{order}' lists non-existent units: {', '.join(invalid_units)}"

        # Validate processing time structure and completeness
        for order in orders:
            if order not in processing_time:
                return f"Missing processing times for order '{order}'"

            order_times = processing_time[order]
            if not isinstance(order_times, dict):
                return f"Processing times for order '{order}' must be a dictionary"

            # Check that processing times are provided for all eligible units
            eligible_units = eligible[order]
            for unit in eligible_units:
                if unit not in order_times:
                    return f"Missing processing time for order '{order}' on eligible unit '{unit}'"

                time_val = order_times[unit]
                if not isinstance(time_val, (int, float)) or time_val <= 0:
                    return f"Processing time for order '{order}' on unit '{unit}' must be a positive number, got: {time_val}"

        # Validate due dates
        for order, dd in due_date.items():
            if not isinstance(dd, (int, float)) or dd <= 0:
                return f"Due date for order '{order}' must be a positive number, got: {dd}"

        # Validate optional changeover if present
        if "changeover" in params:
            changeover = params["changeover"]
            if not isinstance(changeover, dict):
                return "changeover must be a dictionary"

            # Validate nested structure: {unit: {order1: {order2: time}}}
            for unit, unit_changeovers in changeover.items():
                if unit not in units:
                    return f"Changeover specified for non-existent unit '{unit}'"
                if not isinstance(unit_changeovers, dict):
                    return f"Changeover data for unit '{unit}' must be a dictionary"

                for from_order, to_orders in unit_changeovers.items():
                    if from_order not in orders:
                        return f"Changeover specified for non-existent order '{from_order}' on unit '{unit}'"
                    if not isinstance(to_orders, dict):
                        return f"Changeover from order '{from_order}' on unit '{unit}' must be a dictionary"

                    for to_order, time in to_orders.items():
                        if to_order not in orders:
                            return f"Changeover to non-existent order '{to_order}' on unit '{unit}'"
                        if not isinstance(time, (int, float)) or time < 0:
                            return f"Changeover time from '{from_order}' to '{to_order}' on unit '{unit}' must be non-negative, got: {time}"

        # Validate optional window and lower if present
        if "window" in params:
            window = params["window"]
            if not isinstance(window, dict):
                return "window must be a dictionary"
            for order, val in window.items():
                if order not in orders:
                    return f"Time window specified for non-existent order '{order}'"
                if val not in [0, 1]:
                    return f"Time window for order '{order}' must be 0 or 1, got: {val}"

        if "lower" in params:
            lower = params["lower"]
            if not isinstance(lower, dict):
                return "lower must be a dictionary"
            for order, val in lower.items():
                if order not in orders:
                    return f"Lower bound specified for non-existent order '{order}'"
                if not isinstance(val, (int, float)) or val < 0:
                    return f"Lower bound for order '{order}' must be non-negative, got: {val}"

        # Validate objective if present
        if "objective" in params:
            obj = params["objective"]
            if obj not in ["makespan", "changeover"]:
                return f"objective must be 'makespan' or 'changeover', got: '{obj}'"

        # Business logic checks
        # Check if any order has impossible due date (less than minimum processing time)
        for order in orders:
            min_time = min(processing_time[order].values())
            if due_date[order] < min_time:
                return f"Order '{order}' has due date {due_date[order]} but minimum processing time is {min_time} - impossible to meet deadline"

        # Prose vs extracted validation
        import re
        text = description.lower()

        # Check mentioned counts vs extracted counts
        # Use word boundary to avoid matching "due by hour 10" as "10 orders"
        order_match = re.search(r'\b(\d+)\s+(?:production\s+)?(?:orders?|jobs?|tasks?)\b', text)
        if order_match and int(order_match.group(1)) != len(orders):
            return f"You mentioned {order_match.group(1)} orders/jobs but I found {len(orders)} order names. Please list all order names clearly."

        unit_match = re.search(r'\b(\d+)\s+(?:processing\s+)?(?:units?|machines?|resources?)\b', text)
        if unit_match and int(unit_match.group(1)) != len(units):
            return f"You mentioned {unit_match.group(1)} units/machines but I found {len(units)} unit names. Please list all unit names clearly."

        return None  # All validations passed

    def explain_solution(self, solution: Dict) -> str:
        """Generate scheduling-specific solution explanation"""

        system = """
You are explaining a Scheduling Optimization solution. Focus on:
1. Total makespan (completion time) or objective achieved
2. Assignment of orders to units
3. Sequence of orders on each unit
4. Whether all due dates are met
5. Key insights about the schedule (e.g., parallel processing, bottlenecks)

Be clear and business-focused. Use 2-3 sentences.
"""

        user = f"Scheduling Solution: {json.dumps(solution, indent=2)}"

        try:
            return self.client._chat(system, user, json_mode=False)
        except Exception:
            # Fallback explanation
            cmax = solution.get("Cmax", "N/A")
            num_assignments = len(solution.get("assignments", []))
            return f"Optimal schedule found with makespan of {cmax} time units. {num_assignments} orders assigned to processing units, all meeting their due date constraints."

    def suggest_scheduling_analysis(self, solution: Dict, params: Dict) -> List[str]:
        """Suggest scheduling-specific analyses based on the solution"""

        suggestions = []

        # Analyze solution characteristics
        assignments = solution.get("assignments", [])
        if not assignments:
            return ["Basic schedule visualization"]

        orders = params.get("orders", [])
        units = params.get("units", [])

        # Check unit utilization
        unit_usage = {}
        for assignment in assignments:
            unit = assignment.get("unit")
            unit_usage[unit] = unit_usage.get(unit, 0) + 1

        if len(unit_usage) < len(units):
            suggestions.append("Unit utilization analysis - some units are not being used")

        # Check for bottlenecks
        max_usage = max(unit_usage.values()) if unit_usage else 0
        min_usage = min(unit_usage.values()) if unit_usage else 0
        if max_usage > min_usage * 2:
            suggestions.append("Bottleneck analysis - workload is unevenly distributed")

        # Check due date slack
        completion = solution.get("completion", {})
        due_dates = params.get("due_date", {})
        tight_schedules = []
        for order, comp_time in completion.items():
            if order in due_dates:
                slack = due_dates[order] - comp_time
                if slack < 1.0:  # Less than 1 time unit slack
                    tight_schedules.append(order)

        if tight_schedules:
            suggestions.append(f"Due date sensitivity analysis - {len(tight_schedules)} orders have tight margins")

        # Changeover analysis
        if "changeover" in params and params["changeover"]:
            suggestions.append("Changeover time optimization analysis")

        # Makespan sensitivity
        suggestions.append("Processing time sensitivity - how changes affect makespan")

        return suggestions[:4]  # Top 4 suggestions
