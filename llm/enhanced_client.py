# llm/enhanced_client.py
from typing import Dict, Any, List, Optional
from .client import LLMClient
from .ollama_client import OllamaClient
from .transportation_specialist import TransportationSpecialist
from .scheduling_specialist import SchedulingSpecialist
from .problem_classifier import ProblemClassifier
from config import Config

class EnhancedLLMClient(LLMClient):
    """
    Enhanced LLM client with multi-model pipeline.

    Uses different specialized models for different stages:
    - Classification: qwen2:7b-instruct (fast, accurate)
    - Extraction: llama3.1:8b-instruct-q8_0 (structured JSON)
    - Reasoning: deepseek-r1:latest (explanations, what-ifs)
    """

    def __init__(
        self,
        host: str = None,
        model: str = None,  # Deprecated: kept for backward compatibility
        knowledge_base=None
    ):
        """
        Initialize enhanced LLM client with multi-model pipeline.

        Args:
            host: Ollama host URL (default from Config)
            model: Deprecated - models now auto-selected per stage
            knowledge_base: Optional KnowledgeBase for RAG
        """
        if host is None:
            host = Config.OLLAMA_HOST

        self.host = host
        self.kb = knowledge_base

        # Stage A: Classification (qwen2:7b-instruct)
        self.classification_client = OllamaClient(host, Config.CLASSIFICATION_MODEL)
        self.classifier = ProblemClassifier(self.classification_client)

        # Stage B: Parameter Extraction (llama3.1:8b-instruct-q8_0)
        self.extraction_client = OllamaClient(host, Config.EXTRACTION_MODEL)
        self.transportation = TransportationSpecialist(self.extraction_client, knowledge_base)
        self.scheduling = SchedulingSpecialist(self.extraction_client, knowledge_base)

        # Stage E: Reasoning & Explanations (deepseek-r1:latest)
        self.reasoning_client = OllamaClient(host, Config.REASONING_MODEL)

        # Legacy: base_client points to classification for backward compatibility
        self.base_client = self.classification_client

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
            "signals": classification["signals"],
            "evidence": classification["evidence"],
            "reasoning": classification["why_short"],
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

        # Scheduling family
        elif problem_type in ["SCHEDULING", "SINGLE_STAGE_SCHEDULING", "SINGLE_MACHINE_TARDINESS", "JOB_SHOP"]:
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

    # Future helper methods for other problem types:

    # def _is_assignment_params(self, params: Dict) -> bool:
    #     required_keys = {"agents", "tasks", "costs"}
    #     return required_keys.issubset(set(params.keys()))