# llm/follow_up_handler.py
"""
Follow-up question handler with deterministic responses for common questions.
Reduces LLM calls and provides instant, accurate responses.
"""

import json
from typing import Dict, Any, Optional
from .json_utils import extract_json_from_text, safe_json_parse
from .schemas import FOLLOW_UP_SCHEMA, FOLLOW_UP_TYPES


class FollowUpHandler:
    """Handles follow-up questions with deterministic responses when possible"""

    def __init__(self, llm_client):
        self.llm = llm_client

    def detect_follow_up_intent(self, message: str, conversation_context: Dict) -> Dict[str, Any]:
        """
        Detect follow-up intent using tiny schema instead of mega-prompt.

        Returns a dict matching FOLLOW_UP_SCHEMA.
        """

        last_solution = conversation_context.get("last_solution")
        has_context = bool(last_solution)

        # Quick deterministic check
        deterministic_result = self._deterministic_follow_up_check(message, has_context)
        if deterministic_result:
            return deterministic_result

        # Use LLM with tiny schema
        return self._llm_follow_up_detection(message, conversation_context)

    def _deterministic_follow_up_check(self, message: str, has_context: bool) -> Optional[Dict[str, Any]]:
        """Fast deterministic follow-up detection"""

        if not has_context:
            return {
                "is_follow_up": False,
                "follow_up_type": "new_problem",
                "confidence": 0.95
            }

        msg_lower = message.lower().strip()
        words = msg_lower.split()

        # Very short questions are likely follow-ups
        if len(words) <= 8:
            # Question patterns
            question_starters = ["what", "which", "how", "why", "where", "when", "who"]
            if any(msg_lower.startswith(q) for q in question_starters):
                # Detect question category
                category = self._detect_question_category(msg_lower)
                return {
                    "is_follow_up": True,
                    "follow_up_type": "question",
                    "confidence": 0.90,
                    "question_category": category
                }

            # Modification patterns
            if any(word in msg_lower for word in ["change", "modify", "update", "double", "triple", "increase", "decrease"]):
                return {
                    "is_follow_up": True,
                    "follow_up_type": "modification",
                    "confidence": 0.85,
                    "modification_targets": []  # Will be filled by specific handler
                }

            # Analysis patterns
            analysis_keywords = ["sensitivity", "plot", "graph", "visualize", "chart", "analyze", "analysis"]
            if any(keyword in msg_lower for keyword in analysis_keywords):
                return {
                    "is_follow_up": True,
                    "follow_up_type": "analysis",
                    "confidence": 0.90,
                    "analysis_types": self._detect_analysis_types(msg_lower)
                }

        # Check for new problem indicators
        new_problem_indicators = [
            "new problem", "different problem", "another optimization",
            "instead", "forget that", "ignore previous"
        ]
        if any(indicator in msg_lower for indicator in new_problem_indicators):
            return {
                "is_follow_up": False,
                "follow_up_type": "new_problem",
                "confidence": 0.95
            }

        return None  # Can't determine, use LLM

    def _detect_question_category(self, msg_lower: str) -> str:
        """Detect the category of a question"""

        objective_keywords = ["objective", "goal", "minimize", "maximiz", "optimiz", "cost", "total"]
        if any(kw in msg_lower for kw in objective_keywords):
            return "objective"

        variable_keywords = ["variable", "how many", "number of", "count", "entities"]
        if any(kw in msg_lower for kw in variable_keywords):
            return "variables"

        constraint_keywords = ["constraint", "restriction", "limit", "rule", "condition"]
        if any(kw in msg_lower for kw in constraint_keywords):
            return "constraints"

        result_keywords = ["result", "solution", "outcome", "answer", "value"]
        if any(kw in msg_lower for kw in result_keywords):
            return "results"

        capability_keywords = ["can you", "able to", "capability", "what types", "what analyses"]
        if any(kw in msg_lower for kw in capability_keywords):
            return "capabilities"

        return "general"

    def _detect_analysis_types(self, msg_lower: str) -> list:
        """Detect what types of analysis are requested"""

        types = []

        if any(word in msg_lower for word in ["sensitivity", "affect", "impact", "effect"]):
            types.append("sensitivity")

        if any(word in msg_lower for word in ["plot", "graph", "chart", "visualize", "show"]):
            types.append("visualization")

        if any(word in msg_lower for word in ["scenario", "what if", "what-if", "compare"]):
            types.append("scenario")

        if any(word in msg_lower for word in ["tradeoff", "trade-off", "balance", "pareto"]):
            types.append("tradeoff")

        return types if types else ["visualization"]

    def _llm_follow_up_detection(self, message: str, context: Dict) -> Dict[str, Any]:
        """Use LLM with tiny schema for follow-up detection"""

        system = """Detect if this is a follow-up to a previous optimization problem.

Return ONLY JSON matching this schema:
{
  "is_follow_up": true/false,
  "follow_up_type": "question|modification|analysis|new_problem",
  "confidence": 0.0-1.0,
  "question_category": "objective|variables|constraints|results|capabilities|general" (if question),
  "modification_targets": ["param1", "param2"] (if modification),
  "analysis_types": ["sensitivity", "visualization", "scenario", "tradeoff"] (if analysis)
}

Types:
- "question": asking about the problem or solution (objective, variables, constraints, results)
- "modification": changing parameters ("double capacity", "what if demand increases")
- "analysis": requesting computations (sensitivity, plots, scenarios)
- "new_problem": completely different optimization problem
"""

        last_sol = context.get("last_solution", {})
        problem_type = last_sol.get("problem_type", "unknown")
        context_str = f"Previous {problem_type} problem solved." if last_sol else "No previous problem."

        user = f"""Message: "{message}"
Context: {context_str}

Classify as follow-up or new problem."""

        try:
            response = self.llm._chat(system, user, json_mode=True)
            result = safe_json_parse(response, {
                "is_follow_up": False,
                "follow_up_type": "new_problem",
                "confidence": 0.0
            })

            # Validate
            if result.get("follow_up_type") not in FOLLOW_UP_TYPES:
                result["follow_up_type"] = "new_problem"

            result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.5))))

            return result

        except Exception as e:
            return {
                "is_follow_up": False,
                "follow_up_type": "new_problem",
                "confidence": 0.0,
                "error": str(e)
            }

    def answer_deterministic_question(self, message: str, last_solution: Dict, question_category: str) -> Optional[str]:
        """
        Answer common questions deterministically without LLM.
        Returns None if question requires LLM.
        """

        if not last_solution:
            return None

        msg_lower = message.lower()
        params = last_solution.get("extracted_params", {})
        solution = last_solution.get("solution", {})
        problem_type = last_solution.get("problem_type", "unknown")

        # Objective questions
        if question_category == "objective" or any(kw in msg_lower for kw in ["what are we", "what's the goal", "what is the objective"]):
            objective_value = solution.get("objective_value") or solution.get("objective_thousand_usd")
            if objective_value:
                return f"The objective of this {problem_type} problem is to minimize the total cost. The optimal cost achieved is ${objective_value}."
            return f"This is a {problem_type} optimization problem aimed at minimizing cost."

        # Variable/size questions
        if question_category == "variables" or any(kw in msg_lower for kw in ["how many", "number of"]):
            # Transportation-specific
            if problem_type == "TRANSPORTATION":
                plants = params.get("plants", [])
                markets = params.get("markets", [])
                if plants and markets:
                    num_vars = len(plants) * len(markets)
                    return f"This transportation problem has {len(plants)} plants/sources and {len(markets)} markets/destinations, creating {num_vars} decision variables (shipment quantities for each plant-market pair)."

            # Generic
            flows = solution.get("flows", [])
            if flows:
                return f"This {problem_type} problem has {len(flows)} decision variables."

        # Constraint questions
        if question_category == "constraints":
            if problem_type == "TRANSPORTATION":
                plants = params.get("plants", [])
                markets = params.get("markets", [])
                if plants and markets:
                    num_constraints = len(plants) + len(markets)
                    return f"The problem has {num_constraints} main constraints: {len(plants)} capacity constraints (one per plant) and {len(markets)} demand constraints (one per market)."

        # Result questions
        if question_category == "results":
            obj_val = solution.get("objective_value") or solution.get("objective_thousand_usd")
            status = solution.get("status", "UNKNOWN")
            if obj_val and status == "OPTIMAL":
                return f"The optimization was successful with status '{status}'. The optimal total cost is ${obj_val}."

        # Capabilities questions
        if question_category == "capabilities" or "what can you" in msg_lower or "what types of analy" in msg_lower:
            return """I can provide several types of analysis on this solution:

1. **Sensitivity Analysis**: How changes in parameters (capacity, demand, costs) affect the optimal solution
2. **Visualizations**: Plots showing shipment flows, cost breakdowns, and capacity utilization
3. **What-If Scenarios**: Compare different parameter configurations
4. **Detailed Explanations**: Break down the solution by routes, plants, or markets

Just ask! For example: "Show me how changing capacity affects cost" or "Plot the shipments"."""

        # Couldn't answer deterministically
        return None
