# llm/intent_router.py
"""
Intent router - first-stage classifier to detect:
- smalltalk (greetings, "who are you", casual conversation)
- help requests (capabilities, how-to questions)
- optimization problems (the main use case)
- follow-up requests (questions about previous solutions)
"""

import json
from typing import Dict, Any, Optional
from .client import LLMClient

# Tiny schema for intent detection
INTENT_SCHEMA = {
    "type": "object",
    "required": ["intent", "confidence"],
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["smalltalk", "help", "optimization", "follow_up"]
        },
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reasoning": {"type": "string"}
    }
}


class IntentRouter:
    """Routes user messages to appropriate handlers"""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def detect_intent(self, message: str, conversation_context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Detect the intent of a user message.

        Returns:
            {
                "intent": "smalltalk" | "help" | "optimization" | "follow_up",
                "confidence": 0.0-1.0,
                "reasoning": "brief explanation"
            }
        """

        # Quick deterministic checks first (no LLM needed)
        deterministic_intent = self._check_deterministic_intent(message, conversation_context)
        if deterministic_intent:
            return deterministic_intent

        # Use LLM for ambiguous cases
        return self._llm_intent_detection(message, conversation_context)

    def _check_deterministic_intent(self, message: str, context: Optional[Dict]) -> Optional[Dict[str, Any]]:
        """Fast deterministic intent detection for obvious cases"""

        msg_lower = message.lower().strip()

        # Smalltalk patterns (greetings, identity questions)
        smalltalk_patterns = [
            "hello", "hi ", "hey", "greetings",
            "who are you", "what are you", "your name",
            "good morning", "good afternoon", "good evening",
            "how are you", "nice to meet you"
        ]

        if any(pattern in msg_lower for pattern in smalltalk_patterns):
            # But check if it's part of an optimization problem
            if not any(opt_word in msg_lower for opt_word in ["optimize", "minimize", "maximize", "cost", "capacity", "demand", "ship"]):
                return {
                    "intent": "smalltalk",
                    "confidence": 0.95,
                    "reasoning": "Greeting or identity question detected"
                }

        # Help requests
        help_patterns = [
            "what can you do", "your capabilities", "help me",
            "how do i", "how to", "can you help", "show me how",
            "what types", "what kinds", "available options"
        ]

        if any(pattern in msg_lower for pattern in help_patterns):
            return {
                "intent": "help",
                "confidence": 0.95,
                "reasoning": "Help request detected"
            }

        # Follow-up detection (requires context)
        if context and context.get("last_solution"):
            word_count = len(msg_lower.split())

            # Very short messages (1-3 words) with context are almost always follow-ups
            if word_count <= 3:
                return {
                    "intent": "follow_up",
                    "confidence": 0.95,
                    "reasoning": "Very short message with previous solution context"
                }

            # Check for follow-up indicators
            follow_up_patterns = [
                "what about", "how many", "which", "why", "what",
                "can you explain", "tell me more", "what if",
                "change", "modify", "update", "adjust", "increase", "decrease",
                "sensitivity", "analysis", "plot", "graph", "visualize", "chart", "create",
                "objective", "goal", "variables", "constraints"
            ]

            # If message is short (< 20 words) and has follow-up words, likely follow-up
            if word_count < 20 and any(pattern in msg_lower for pattern in follow_up_patterns):
                # But make sure it's not a new optimization problem
                # Strong indicators that it's a NEW problem (needs multiple of these)
                strong_new_problem_indicators = [
                    "new problem", "different problem", "another problem",
                    "solve", "optimize", "minimize", "maximize", "find the", "calculate"
                ]

                # Weak indicators - just mentioning entities doesn't mean new problem
                # These are OK in follow-up questions (e.g., "how many plants?")
                weak_new_problem_indicators = [
                    "factories", "warehouses", "supply", "demand",
                    "capacity", "cost"
                ]

                # Count indicators
                strong_count = sum(1 for ind in strong_new_problem_indicators if ind in msg_lower)
                weak_count = sum(1 for ind in weak_new_problem_indicators if ind in msg_lower)

                # Asking ABOUT entities (e.g., "how many plants?") is a follow-up
                # Describing entities (e.g., "plants A and B with capacity X") is new problem
                question_words = ["how many", "what", "which", "tell me", "show me"]
                is_question = any(q in msg_lower for q in question_words)

                # If very short (< 10 words) and asking a question, it's a follow-up
                if word_count < 10 and is_question:
                    return {
                        "intent": "follow_up",
                        "confidence": 0.90,
                        "reasoning": "Very short question with previous solution context"
                    }

                # If no strong indicators and is a question, it's a follow-up
                if strong_count == 0 and is_question:
                    return {
                        "intent": "follow_up",
                        "confidence": 0.85,
                        "reasoning": "Question about previous solution"
                    }

                # If has strong indicators (like "solve", "optimize"), likely new problem
                if strong_count >= 1:
                    # Let it fall through to optimization detection
                    pass
                else:
                    # Default to follow-up if no strong new problem indicators
                    return {
                        "intent": "follow_up",
                        "confidence": 0.80,
                        "reasoning": "Short message with context, no new problem indicators"
                    }

        # Optimization problem indicators
        optimization_indicators = [
            "optimize", "minimize", "maximize", "cost", "profit",
            "capacity", "demand", "supply", "ship", "transport",
            "factories", "warehouses", "plants", "customers", "markets",
            "assign", "allocate", "schedule", "route"
        ]

        indicator_count = sum(1 for ind in optimization_indicators if ind in msg_lower)

        if indicator_count >= 3:
            return {
                "intent": "optimization",
                "confidence": 0.90,
                "reasoning": f"Multiple optimization keywords detected ({indicator_count})"
            }

        # If message is very long (>50 words) and has optimization words, likely optimization
        word_count = len(msg_lower.split())
        if word_count > 50 and indicator_count >= 2:
            return {
                "intent": "optimization",
                "confidence": 0.85,
                "reasoning": "Long message with optimization context"
            }

        return None  # Couldn't determine deterministically

    def _llm_intent_detection(self, message: str, context: Optional[Dict]) -> Dict[str, Any]:
        """Use LLM for ambiguous intent detection"""

        has_previous_solution = bool(context and context.get("last_solution"))

        system = """You are an intent classifier for an optimization assistant.
Classify the user's message into ONE of these intents:
- "smalltalk": greetings, chitchat, "who are you", casual conversation
- "help": asking what the system can do, requesting capabilities
- "optimization": describing a new optimization problem to solve
- "follow_up": question or modification about a previous solution

Output ONLY valid JSON matching this schema:
{"intent": "smalltalk|help|optimization|follow_up", "confidence": 0.0-1.0, "reasoning": "brief explanation"}
"""

        context_str = ""
        if has_previous_solution:
            last_sol = context.get("last_solution", {})
            problem_type = last_sol.get("problem_type", "unknown")
            context_str = f"\n\nCONTEXT: User has a previous {problem_type} optimization solution."

        user = f"""Message: "{message}"{context_str}

Classify the intent."""

        try:
            response = self.llm._chat(system, user, json_mode=True)
            result = json.loads(response)

            # Validate
            if result.get("intent") not in ["smalltalk", "help", "optimization", "follow_up"]:
                raise ValueError("Invalid intent")

            if not isinstance(result.get("confidence"), (int, float)):
                raise ValueError("Invalid confidence")

            result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))

            return result

        except Exception as e:
            # Fallback: assume optimization if we can't determine
            return {
                "intent": "optimization",
                "confidence": 0.3,
                "reasoning": f"Fallback due to error: {e}"
            }

    def handle_smalltalk(self, message: str) -> Dict[str, Any]:
        """Handle smalltalk/greetings without using LLM pipeline"""

        msg_lower = message.lower().strip()

        # Predefined responses for common greetings
        if any(word in msg_lower for word in ["hello", "hi ", "hey", "greetings"]):
            return {
                "type": "smalltalk",
                "response": "Hello! I'm an AI assistant specialized in solving optimization problems. I can help you with transportation, assignment, scheduling, and other operations research problems. How can I help you today?"
            }

        if "who are you" in msg_lower or "what are you" in msg_lower:
            return {
                "type": "smalltalk",
                "response": "I'm an AI-powered optimization assistant. I help solve complex operations research problems using linear programming and other optimization techniques. You can describe problems in natural language, and I'll extract the parameters, solve them, and explain the results."
            }

        if "your name" in msg_lower:
            return {
                "type": "smalltalk",
                "response": "I'm an Optimization AI assistant, powered by LLM technology and mathematical solvers. I don't have a personal name, but you can call me Optimus if you'd like!"
            }

        if any(word in msg_lower for word in ["how are you", "how's it going"]):
            return {
                "type": "smalltalk",
                "response": "I'm functioning well and ready to help you solve optimization problems! What challenge can I assist you with?"
            }

        # Generic smalltalk response
        return {
            "type": "smalltalk",
            "response": "I'm an optimization assistant here to help you solve operations research problems. Feel free to describe an optimization challenge you're facing!"
        }

    def handle_help_request(self, message: str) -> Dict[str, Any]:
        """Handle help requests without heavy LLM use"""

        return {
            "type": "help",
            "response": """I can help you solve various optimization problems:

**Problem Types:**
- Transportation: Minimize shipping costs from factories to customers
- Assignment: Assign workers to tasks optimally
- Scheduling: Optimize production schedules
- Facility Location: Choose optimal facility locations
- And more...

**How to use me:**
1. Describe your problem in natural language
2. Include all relevant data (capacities, demands, costs, distances)
3. I'll extract parameters, solve, and explain the solution

**Follow-up analyses:**
- Sensitivity analysis: "How does changing X affect the cost?"
- What-if scenarios: "What if we double the capacity?"
- Visualizations: "Show me a plot of the solution"

**Example:** "I have 2 factories (Seattle: 350 units, San Diego: 600 units) and 3 customers (New York: 325 units, Chicago: 300 units, Topeka: 275 units). Shipping costs are: Seattle→NY: $0.225/unit, Seattle→Chicago: $0.153/unit, Seattle→Topeka: $0.162/unit, San Diego→NY: $0.225/unit, San Diego→Chicago: $0.162/unit, San Diego→Topeka: $0.126/unit. Minimize total shipping cost."

What would you like to optimize?"""
        }
