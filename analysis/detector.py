# analysis/detector.py
from typing import Dict, Any
from llm.client import LLMClient

class AnalysisDetector:
    """Uses LLM to intelligently detect analysis and plotting requests"""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def detect_analysis_requests(self, description: str) -> Dict[str, Any]:
        """Use LLM to understand what analyses/plots the user wants"""

        prompt = f"""
Analyze this optimization problem description and detect if the user wants any additional analysis, plots, or visualizations:

Problem Description: "{description}"

Please identify:
1. Does the user want plots, graphs, charts, or visualizations?
2. What type of analysis do they want?
   - Sensitivity analysis (how one variable affects outcomes)
   - Pareto analysis (trade-offs between objectives)
   - Scenario comparison (what-if analysis)
   - Variable relationships (connections between factors)
   - Other analysis types

3. Which specific variables or factors should be analyzed?
4. What relationships or effects do they want to explore?

Return ONLY valid JSON:
{{
  "wants_analysis": true/false,
  "analysis_types": ["sensitivity", "pareto", "scenario", "relationship"],
  "variables": ["seattle", "capacity", "cost", "demand"],
  "requests": [
    {{
      "type": "sensitivity",
      "description": "How Seattle capacity affects total cost",
      "x_variable": "seattle_capacity",
      "y_variable": "total_cost",
      "plot_type": "line"
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