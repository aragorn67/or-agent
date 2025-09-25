# analysis/detector.py
from typing import Dict, Any
from llm.client import LLMClient

class AnalysisDetector:
    """Uses LLM to intelligently detect analysis and plotting requests"""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def detect_analysis_requests(self, description: str) -> Dict[str, Any]:
        """Detect if user wants specific analysis OR if they explicitly don't want plots"""

        prompt = f"""
Analyze this optimization problem description and detect if the user wants any additional analysis, plots, or visualizations:

Problem Description: "{description}"

Look for requests like:
- "show me plots/graphs/charts"
- "sensitivity analysis"
- "what-if analysis"
- "visualize the results"
- "how does X affect Y"

Return ONLY valid JSON:
{{
  "wants_analysis": true/false,
  "requests": [
    {{
      "type": "sensitivity",
      "description": "How capacity affects total cost",
      "x_variable": "capacity",
      "y_variable": "total_cost"
    }}
  ]
}}

If no analysis requested, return: {{"wants_analysis": false}}
"""

        try:
            response = self.llm._generate(prompt)

            # Extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1

            if start_idx == -1 or end_idx == 0:
                return {"wants_analysis": False}

            json_str = response[start_idx:end_idx]
            import json
            result = json.loads(json_str)

            return result

        except Exception as e:
            # Fallback if LLM fails
            return {"wants_analysis": False, "error": str(e)}