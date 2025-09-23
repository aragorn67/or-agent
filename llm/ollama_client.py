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

    def _generate(self, prompt: str) -> str:
        """Generate text using Ollama API"""
        response = requests.post(
            f"{self.host}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
        )
        response.raise_for_status()
        return response.json()["response"]

    def classify_problem(self, description: str, problem_types: List[str]) -> Dict[str, Any]:
        """Classify optimization problem type"""
        prompt = f"""
You are an optimization expert. Analyze this problem description and classify it ONLY if it's a clear optimization problem.

Problem: "{description}"

Available problem types:
- TRANSPORTATION: Moving goods/resources from sources to destinations (mentions plants, factories, warehouses, customers, shipping, delivery)

Rules:
1. If the description is too vague, unclear, or just random text, return confidence 0.0 and type "UNKNOWN"
2. Only classify as TRANSPORTATION if it clearly mentions moving things from sources to destinations
3. Be strict - require clear optimization context

Return ONLY valid JSON:
{{"type": "TRANSPORTATION", "confidence": 0.95}}

If unclear or not an optimization problem:
{{"type": "UNKNOWN", "confidence": 0.0}}
"""
        response = self._generate(prompt)

        try:
            # Extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx == -1 or end_idx == 0:
                return {"type": "UNKNOWN", "confidence": 0.0}

            json_str = response[start_idx:end_idx]
            result = json.loads(json_str)

            # Validate the result
            if result.get("confidence", 0) < 0.3:
                return {"type": "UNKNOWN", "confidence": 0.0}

            return result
        except:
            # Fallback for unclear problems
            return {"type": "UNKNOWN", "confidence": 0.0}

    def extract_parameters(self, description: str, problem_type: str, example: Dict) -> Dict[str, Any]:
        """Extract structured parameters from natural language"""
        prompt = f"""
Extract {problem_type} optimization parameters from this description:

Problem: {description}

Expected format (example):
{json.dumps(example, indent=2)}

Return only valid JSON with the extracted parameters:
"""
        response = self._generate(prompt)

        try:
            # Extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            json_str = response[start_idx:end_idx]
            return json.loads(json_str)
        except:
            # Return example as fallback
            return example

    def explain_solution(self, solution: Dict, problem_type: str) -> str:
        """Generate natural language explanation of solution"""
        prompt = f"""
Explain this {problem_type} optimization solution in simple terms:

Solution: {json.dumps(solution, indent=2)}

Provide a clear, concise explanation focusing on:
- What was optimized
- Key results and costs
- Main shipping routes or decisions
"""
        return self._generate(prompt)