# llm/ollama_client.py
import json
import requests
from typing import Dict, Any, List
from .client import LLMClient

class OllamaClient(LLMClient):
    """Ollama LLM client implementation"""

    def __init__(self, host: str = "http://localhost:11434", model: str = "qwen2:7b"):
        self.host = host.rstrip('/')
        self.model = model

    def _chat(self, system: str, user: str, json_mode: bool = False) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system.strip()},
                {"role": "user", "content": user.strip()},
            ],
            "stream": False,
            "options": {"temperature": 0}
        }
        if json_mode:
            # Force well-formed JSON content from the model
            payload["format"] = "json"

        resp = requests.post(f"{self.host}/api/chat", json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        # '/api/chat' returns {"message": {"role":"assistant","content":"..."}}
        return data["message"]["content"]

    def classify_problem(self, description: str, problem_types: List[str]) -> Dict[str, Any]:
        # Allow any subset: e.g., ["TRANSPORTATION","ASSIGNMENT","SINGLE_MACHINE"]
        allowed = [t.upper() for t in problem_types] if problem_types else []
        if not allowed:
            allowed = ["TRANSPORTATION"]

        # Brief, schema-bound instruction
        system = """
    You are a strict optimizer. Classify the problem into one of the provided families.
    If uncertain, return type "UNKNOWN" with confidence 0.0.
    Return ONLY this JSON:
    {"type": "<one of ALLOWED or UNKNOWN>", "confidence": <0..1>}
    """
        user = f"""ALLOWED: {allowed}
    TEXT: {description}"""

        try:
            content = self._chat(system, user, json_mode=True)
            result = json.loads(content)
            t = result.get("type", "UNKNOWN").upper()
            if t not in allowed and t != "UNKNOWN":
                result = {"type": "UNKNOWN", "confidence": 0.0}
            # Be strict about low confidence
            if float(result.get("confidence", 0)) < 0.3:
                return {"type": "UNKNOWN", "confidence": 0.0}
            return result
        except Exception:
            return {"type": "UNKNOWN", "confidence": 0.0}

    def extract_parameters(self, description: str, problem_type: str, example: Dict) -> Dict[str, Any]:
        problem_type = (problem_type or "").upper()

        if problem_type == "TRANSPORTATION":
            system = """
    Extract parameters for a Transportation LP. Output STRICT JSON with keys:
    - plants: string[]
    - markets: string[]
    - capacity: {plant: number}
    - demand: {market: number}
    - cost: {plant: {market: number}}  # per-unit shipping cost matrix
    - integer_shipments: boolean (optional, default false)
    - allow_unbalanced: boolean (optional, default false)

    Rules:
    - Use ONLY entities & numbers explicitly present in the text.
    - If ANY required piece is missing, return: {"error": "<what's missing, be specific>"}.
    - No extra keys. All numbers must be numbers, not strings.
    """
            user = f"TEXT:\n{description}\n\nReturn ONLY the JSON."

            try:
                content = self._chat(system, user, json_mode=True)
                result = json.loads(content)

                if "error" in result:
                    return result

                # Validate in-code before returning
                validation_error = self._validate_transportation_extraction(description, result)
                if validation_error:
                    return {"error": validation_error}

                return result

            except json.JSONDecodeError as e:
                return {"error": f"Invalid JSON response from LLM: {str(e)}"}
            except Exception as e:
                return {"error": f"Extraction error: {e}"}

        # Fallback for other families until you add their schemas
        return {"error": f"Unsupported problem_type for extraction: {problem_type}"}

    def _validate_transportation_extraction(self, description: str, p: Dict) -> str:
        # Required fields present?
        required = ["plants", "markets", "capacity", "demand", "cost"]
        missing = [k for k in required if k not in p or not p[k]]
        if missing:
            return f"Missing required information: {', '.join(missing)}."

        plants = p["plants"]
        markets = p["markets"]
        cap = p["capacity"]
        dem = p["demand"]
        cost = p["cost"]

        # Keys align?
        if set(cap.keys()) != set(plants):
            return "Each plant in 'plants' must appear in 'capacity' (keys must match)."
        if set(dem.keys()) != set(markets):
            return "Each market in 'markets' must appear in 'demand' (keys must match)."

        # Cost matrix completeness
        for i in plants:
            row = cost.get(i)
            if not isinstance(row, dict):
                return f"Cost row for plant '{i}' is missing or malformed."
            missing_cols = [j for j in markets if j not in row]
            if missing_cols:
                return f"Missing costs from plant '{i}' to markets: {', '.join(missing_cols)}."

        # Optional: numerical sanity checks
        if any(v < 0 for v in cap.values()):
            return "Capacity values must be non-negative."
        if any(v < 0 for v in dem.values()):
            return "Demand values must be non-negative."
        for i in plants:
            for j in markets:
                if cost[i][j] < 0:
                    return f"Cost {i}->{j} must be non-negative."

        # (Optional) check stated counts in prose vs extracted
        import re
        text = description.lower()
        mplant = re.search(r'(\d+)\s+(?:plants?|factories|sources)', text)
        if mplant and int(mplant.group(1)) != len(plants):
            return f"You mentioned {mplant.group(1)} plants/sources but extracted {len(plants)} names. Please list all."

        mmarket = re.search(r'(\d+)\s+(?:markets|customers|destinations|sinks)', text)
        if mmarket and int(mmarket.group(1)) != len(markets):
            return f"You mentioned {mmarket.group(1)} customers/destinations but extracted {len(markets)} names. Please list all."

        return None  # OK

    def explain_solution(self, solution: Dict, problem_type: str, original_description: str = "") -> str:
        system = "Explain the solution briefly, focusing on objective value and the key chosen decisions."
        user = f"Problem type: {problem_type}\nSolution JSON: {json.dumps(solution)}\nReturn 2-3 sentences."
        try:
            return self._chat(system, user, json_mode=False)
        except Exception:
            return "Solution obtained. Objective and key routes chosen are shown above."


    def detect_follow_up_intent(self, new_message: str, conversation_context: Dict) -> Dict[str, Any]:
        """Detect if message is a follow-up request and what type"""

        last_solution = conversation_context.get("last_solution")
        previous_messages = conversation_context.get("messages", [])

        # Build context summary
        context_summary = ""
        if last_solution:
            context_summary += f"Previous solution: {last_solution.get('problem_type', 'Unknown')} optimization with cost ${last_solution.get('solution', {}).get('objective_thousand_usd', 'N/A')}k\n"

        if previous_messages:
            recent_messages = previous_messages[-3:]  # Last 3 messages for context
            context_summary += "Recent conversation:\n"
            for msg in recent_messages:
                context_summary += f"- {msg.get('role', 'unknown')}: {msg.get('content', '')[:100]}...\n"

        prompt = f"""
Analyze this message to determine if it's a follow-up request about a previous optimization:

Current message: "{new_message}"

Context: {context_summary}

Determine:
1. Is this a follow-up request (references previous solution) or a new optimization problem?
2. If follow-up, what type of analysis is requested?

IMPORTANT: If there is a previous optimization solution in the context, almost ALL questions should be considered follow-ups unless they clearly describe a completely NEW optimization problem with different entities.

Questions like "what types of analyses?", "what can you do?", "how many variables?", "what's the goal?" are ALWAYS follow-ups when there's a previous solution.

CRITICAL: Distinguish between "question" and "analysis":

Use "question" for ANY informational request including:
- Problem structure: "what are we optimizing?", "what's the goal?", "what are we trying to maximize/minimize?"
- Capabilities: "what can you do?", "what analyses?", "mathematical analysis"
- Constraints/limitations: "what constraints?", "what limitations?", "what restrictions?"
- Insights/information: "what insights?", "tell me about this", "insights about this problem"
- Problem size: "how many variables/locations/entities?"

Use "analysis" ONLY for explicit computational requests:
- Sensitivity analysis: "how does X affect Y?", "impact of changing X"
- Plots/visualizations: "show me graphs", "create charts"
- Calculations: "compute the effect", "calculate sensitivity"
- Comparisons: "compare scenarios", "what-if analysis with specific changes"

When in doubt, choose "question" over "analysis".

Return JSON:
{{
  "is_follow_up": true/false,
  "follow_up_type": "analysis|modification|question|new_problem",
  "analysis_requested": ["sensitivity", "pareto", "scenario", "visualization", "explanation"],
  "confidence": 0.85,
  "reasoning": "Brief explanation of decision"
}}

Follow-up types:
- "analysis": Advanced analysis requests like "how does X affect Y", sensitivity analysis, plots, visualizations
- "modification": Changing parameters ("what if we change X?", "double the Y")
- "question": Basic questions about problem structure, capabilities, or simple facts (prefer this for informational questions)
- "new_problem": Completely new optimization problem

IMPORTANT: Use "question" for informational requests about the problem or capabilities:
- Questions about objective function ("what are we minimizing?", "what's the goal?", "what are we trying to maximize?")
- Questions about problem size ("how many variables?", "how many locations?", "how many cities?")
- Questions about constraints ("what rules?", "what restrictions?", "what limitations?")
- Questions about capabilities ("what types of analyses?", "what can you do?", "analysis options", "mathematical analysis")
- General informational questions ("what insights?", "tell me about this problem")

Only use "analysis" for requests that explicitly ask for:
- Computations or calculations
- Plots, charts, graphs, visualizations
- "How does X affect Y" type sensitivity analysis
- Performance comparisons or trade-offs

Analysis types:
- "sensitivity": Questions like "how does X affect Y", "impact of", "effect of"
- "pareto": Trade-offs between objectives
- "scenario": What-if analysis with parameter changes
- "visualization": Plots, charts, diagrams
- "explanation": Clarification about solution

Question types (basic problem info):
- Problem structure: "what is the objective function?", "what are the constraints?", "how many variables?"
- Capabilities: "what types of analyses can you provide?", "what can you do with this problem?"
- Solution facts: "what was the total cost?", "which routes were used?", "what is being optimized?"
"""

        try:
            response = self._chat("", prompt, json_mode=True)

            # Extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx == -1 or end_idx == 0:
                return {"is_follow_up": False, "follow_up_type": "new_problem", "confidence": 0.0}

            json_str = response[start_idx:end_idx]
            result = json.loads(json_str)

            return result

        except Exception as e:
            print(f"Follow-up detection error: {e}")
            return {"is_follow_up": False, "follow_up_type": "new_problem", "confidence": 0.0}

    def generate_follow_up_response(self, user_request: str, context: Dict, analysis_type: str) -> str:
        """Generate appropriate response for follow-up requests"""

        last_solution = context.get("last_solution", {})

        if analysis_type == "sensitivity":
            return f"I'll analyze how different variables affect your optimization solution. Let me run a sensitivity analysis..."

        elif analysis_type == "pareto":
            return f"I'll generate a Pareto front showing the trade-offs between different objectives for your problem..."

        elif analysis_type == "scenario":
            return f"I'll create what-if scenarios based on your request: '{user_request}'"

        elif analysis_type == "visualization":
            return f"I'll create visualizations to better illustrate your optimization results..."

        elif analysis_type == "explanation":
            return f"Let me explain the solution in more detail..."

        else:
            return f"I'll help you with that request about your previous optimization..."

    def extract_modification_parameters(self, user_request: str, original_params: Dict) -> Dict[str, Any]:
        """Extract what parameters user wants to modify"""

        prompt = f"""
The user wants to modify their optimization problem. Extract what changes they want:

Original parameters: {json.dumps(original_params, indent=2)}
User request: "{user_request}"

Identify what the user wants to change and return JSON:
{{
  "modifications": {{
    "capacity": {{"seattle": 500}},  // if capacity changes
    "demand": {{"chicago": 400}},    // if demand changes
    "freight": 180,                  // if freight cost changes
    "new_constraints": ["seattle cannot ship to chicago"],  // new restrictions
    "other_changes": ["add third factory in denver"]        // other modifications
  }},
  "change_description": "Brief description of what's being changed",
  "confidence": 0.90
}}

Focus on:
- Capacity changes ("increase Seattle to 500")
- Demand changes ("Chicago now needs 400")
- Cost changes ("double freight costs")
- New constraints ("Seattle can't ship to Chicago")
- New entities ("add factory in Denver")
"""

        try:
            response = self._chat("", prompt, json_mode=True)

            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx == -1 or end_idx == 0:
                return {"modifications": {}, "change_description": "Could not parse changes", "confidence": 0.0}

            json_str = response[start_idx:end_idx]
            result = json.loads(json_str)

            return result

        except Exception as e:
            print(f"Parameter extraction error: {e}")
            return {"modifications": {}, "change_description": f"Error: {e}", "confidence": 0.0}