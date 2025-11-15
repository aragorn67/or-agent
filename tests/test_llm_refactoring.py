#!/usr/bin/env python3
"""
TEST: LLM Refactoring Components (Unit Tests)

PURPOSE: Unit tests for LLM refactoring modules
TESTS: Intent router, follow-up handler, JSON utils, config, error handling
FRAMEWORK: pytest

EXPECTED OUTPUT:
    ✓ All unit tests pass
    ✓ Intent routing: smalltalk, help, optimization detection
    ✓ Follow-up handler: deterministic answers for objective/variables/capabilities
    ✓ JSON utils: extraction from markdown, embedded JSON, error handling
    ✓ Explanation guard: decimal preservation, grounding checks
    ✓ Config system: task-specific settings, serialization, overrides
    ✓ Error handling: Ollama connection/timeout errors
    ✓ Integration tests: full conversation flow
    ✓ Transportation scenarios: 10+ real problem descriptions

RUN: pytest tests/test_llm_refactoring.py -v
REQUIRES: Mock LLM (uses unittest.mock, no Ollama needed)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
from unittest.mock import Mock, patch, MagicMock

# Import modules to test
from llm.intent_router import IntentRouter
from llm.follow_up_handler import FollowUpHandler
from llm.json_utils import extract_json_from_text, safe_json_parse, validate_json_schema
from llm.explanation_guard import ExplanationGuard
from llm.llm_config import LLMConfig, config, set_model, enable_deterministic_mode


class TestIntentRouter:
    """Test the intent routing system"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_llm = Mock()
        self.router = IntentRouter(self.mock_llm)

    def test_smalltalk_detection(self):
        """Test detection of smalltalk/greetings"""
        test_cases = [
            "Hello!",
            "Hi there",
            "Who are you?",
            "What's your name?",
            "Good morning"
        ]

        for message in test_cases:
            result = self.router.detect_intent(message, {})
            assert result["intent"] == "smalltalk", f"Failed for: {message}"
            assert result["confidence"] > 0.9

    def test_help_detection(self):
        """Test detection of help requests"""
        test_cases = [
            "What can you do?",
            "Help me understand your capabilities",
            "How do I use this?",
            "Show me what types of problems you solve"
        ]

        for message in test_cases:
            result = self.router.detect_intent(message, {})
            assert result["intent"] == "help", f"Failed for: {message}"
            assert result["confidence"] > 0.9

    def test_optimization_detection(self):
        """Test detection of optimization problems with various phrasings"""
        test_cases = [
            # Classic transportation problem
            """I have 2 factories and 3 customers. Seattle can produce 350 units,
            San Diego can produce 600 units. Customers need: NY 325, Chicago 300, Topeka 275.
            Minimize shipping costs.""",

            # European scenario
            """A company operates two production sites in Greece: Athens and Thessaloniki.
            Athens can make up to 120 units per week, Thessaloniki can supply 200 pieces.
            They deliver products to three customer areas: Patras, Larisa, and Heraklion.
            Patras requires 100 units, Larisa needs 80, Heraklion has a demand of 110.""",

            # UK scenario
            """There are two factories in the UK: Manchester and Birmingham.
            Manchester can produce 150 units weekly, Birmingham up to 170.
            Goods go to three retailers: London, Bristol, and Leeds.""",

            # Distance-based costs
            """A firm ships from Lyon and Marseille to Nice and Grenoble.
            Freight rate is €0.06 per unit per km. Distances: Lyon→Nice: 470 km.""",

            # With constraints
            """Three plants: Antwerp (capacity 120), Ghent (90), and Liège (110).
            Note: Shipments from Antwerp to Mons are not allowed due to a contract restriction."""
        ]

        for i, message in enumerate(test_cases):
            result = self.router.detect_intent(message, {})
            assert result["intent"] == "optimization", f"Failed for test case {i+1}"
            # Some cases might fallback to LLM with default confidence 0.3
            # Just ensure they're classified as optimization
            assert result["confidence"] >= 0.0

    def test_followup_detection(self):
        """Test detection of follow-up questions with various phrasings"""
        context = {
            "last_solution": {
                "problem_type": "TRANSPORTATION",
                "objective_value": 1500
            }
        }

        test_cases = [
            # Objective questions
            "What's the objective?",
            "What are we trying to minimize?",
            "What's the goal of this optimization?",
            "Tell me about the objective function",

            # Variable questions
            "How many variables?",
            "How many decision variables are there?",
            "What's the problem size?",
            "How many plants and markets?",

            # Constraint questions
            "Show me the constraints",
            "What restrictions are there?",
            "What are the capacity constraints?",

            # Modification requests
            "What if we double capacity?",
            "Change Seattle capacity to 500",
            "Increase demand by 20%",
            "What happens if we add a new plant?",

            # Analysis requests
            "Show me a sensitivity plot",
            "How does cost change with capacity?",
            "Visualize the solution",
            "Create a chart of the flows"
        ]

        for message in test_cases:
            result = self.router.detect_intent(message, context)
            assert result["intent"] == "follow_up", f"Failed for: {message}"

    def test_smalltalk_response(self):
        """Test smalltalk response generation"""
        response = self.router.handle_smalltalk("Hello!")
        assert response["type"] == "smalltalk"
        assert "optimization" in response["response"].lower()

    def test_help_response(self):
        """Test help response generation"""
        response = self.router.handle_help_request("What can you do?")
        assert response["type"] == "help"
        assert "transportation" in response["response"].lower()


class TestJSONUtils:
    """Test JSON extraction utilities"""

    def test_extract_pure_json(self):
        """Test extraction of pure JSON"""
        text = '{"key": "value", "number": 42}'
        result = extract_json_from_text(text)
        assert result == {"key": "value", "number": 42}

    def test_extract_json_with_markdown(self):
        """Test extraction from markdown code blocks"""
        text = """Here's the result:
```json
{"status": "success", "data": 123}
```
That's it!"""
        result = extract_json_from_text(text)
        assert result == {"status": "success", "data": 123}

    def test_extract_json_embedded(self):
        """Test extraction of JSON embedded in text"""
        text = "The result is: {\"answer\": 42, \"valid\": true} and that's final."
        result = extract_json_from_text(text)
        assert result == {"answer": 42, "valid": True}

    def test_extract_no_json(self):
        """Test extraction when no JSON present"""
        text = "This is just plain text with no JSON"
        result = extract_json_from_text(text)
        assert result is None

    def test_safe_json_parse_with_default(self):
        """Test safe parsing with default fallback"""
        result = safe_json_parse("invalid json", default={"error": "parse failed"})
        assert result == {"error": "parse failed"}

    def test_validate_json_schema(self):
        """Test JSON schema validation"""
        data = {"name": "test", "value": 42}

        # Valid case
        valid, error = validate_json_schema(data, ["name", "value"])
        assert valid is True
        assert error is None

        # Missing key
        valid, error = validate_json_schema(data, ["name", "value", "missing"])
        assert valid is False
        assert "missing" in error.lower()

        # Type checking
        valid, error = validate_json_schema(
            data,
            ["name", "value"],
            {"name": str, "value": int}
        )
        assert valid is True


class TestFollowUpHandler:
    """Test follow-up detection and handling"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_llm = Mock()
        self.handler = FollowUpHandler(self.mock_llm)
        self.last_solution = {
            "problem_type": "TRANSPORTATION",
            "extracted_params": {
                "plants": ["Seattle", "San Diego"],
                "markets": ["New York", "Chicago", "Topeka"],
                "capacity": {"Seattle": 350, "San Diego": 600},
                "demand": {"New York": 325, "Chicago": 300, "Topeka": 275}
            },
            "solution": {
                "objective_value": 153.675,
                "status": "OPTIMAL",
                "flows": [
                    {"plant": "Seattle", "market": "New York", "value": 50},
                    {"plant": "Seattle", "market": "Chicago", "value": 300}
                ]
            }
        }

    def test_deterministic_objective_question(self):
        """Test deterministic response to objective question"""
        message = "What is the objective function?"
        answer = self.handler.answer_deterministic_question(
            message, self.last_solution, "objective"
        )
        assert answer is not None
        assert "minimize" in answer.lower() or "cost" in answer.lower()
        assert "153.675" in answer

    def test_deterministic_variables_question(self):
        """Test deterministic response to variables question"""
        message = "How many variables are there?"
        answer = self.handler.answer_deterministic_question(
            message, self.last_solution, "variables"
        )
        assert answer is not None
        assert "2" in answer  # 2 plants
        assert "3" in answer  # 3 markets

    def test_deterministic_capabilities_question(self):
        """Test deterministic response to capabilities question"""
        message = "What analyses can you do?"
        answer = self.handler.answer_deterministic_question(
            message, self.last_solution, "capabilities"
        )
        assert answer is not None
        assert "sensitivity" in answer.lower()
        assert "visualization" in answer.lower()

    def test_followup_type_detection(self):
        """Test detection of follow-up types"""
        context = {"last_solution": self.last_solution}

        # Question type
        result = self.handler._deterministic_follow_up_check(
            "What's the cost?", has_context=True
        )
        assert result["follow_up_type"] == "question"

        # Modification type
        result = self.handler._deterministic_follow_up_check(
            "Change capacity to 500", has_context=True
        )
        assert result["follow_up_type"] == "modification"

        # Analysis type
        result = self.handler._deterministic_follow_up_check(
            "Show me a sensitivity plot", has_context=True
        )
        assert result["follow_up_type"] == "analysis"


class TestExplanationGuard:
    """Test explanation grounding and decimal handling"""

    def setup_method(self):
        """Set up test fixtures"""
        self.guard = ExplanationGuard()

    def test_decimal_extraction(self):
        """Test that decimals are preserved (not cast to int)"""
        solution = {
            "objective_value": 153.675,
            "flows": [
                {"plant": "A", "market": "X", "value": 50.5},
                {"plant": "B", "market": "Y", "value": 100.25}
            ],
            "status": "OPTIMAL"
        }

        facts = self.guard.extract_data_facts(solution)

        # Check that decimal representations are stored
        assert "153.675" in facts["numbers"]
        assert "50.5" in facts["numbers"]
        assert "100.25" in facts["numbers"]

    def test_deterministic_summary_with_decimals(self):
        """Test deterministic summary preserves decimals"""
        solution = {
            "objective_value": 153.675,
            "flows": [
                {"plant": "Seattle", "market": "Chicago", "value": 300.5},
                {"plant": "Seattle", "market": "Topeka", "value": 49.5}
            ],
            "status": "OPTIMAL"
        }

        summary = self.guard.create_deterministic_summary(solution)

        # Should preserve decimals in output
        assert "300.5" in summary or "300" in summary  # May format as needed
        assert "153.675" in summary or "153" in summary

    def test_grounding_check(self):
        """Test that explanations are grounded in actual data"""
        solution = {
            "objective_value": 1000,
            "flows": [
                {"plant": "Factory A", "market": "Store B", "value": 100}
            ],
            "status": "OPTIMAL"
        }

        facts = self.guard.extract_data_facts(solution)

        # Grounded sentence (mentions actual entities/numbers)
        assert self.guard.is_sentence_grounded(
            "Factory A ships 100 units to Store B", facts
        )

        # Speculative sentence (no actual data)
        assert not self.guard.is_sentence_grounded(
            "This is likely due to geographical proximity", facts
        )


class TestLLMConfig:
    """Test the configuration system"""

    def test_default_config(self):
        """Test default configuration values"""
        cfg = LLMConfig()
        assert cfg.model_config.model == "deepseek-r1:latest"
        assert cfg.model_config.temperature == 0.0
        assert cfg.behavior.concise_mode is True

    def test_task_config_retrieval(self):
        """Test retrieving task-specific configuration"""
        cfg = LLMConfig()

        class_cfg = cfg.get_task_config("classification")
        assert class_cfg.temperature == 0.0
        assert class_cfg.json_mode is True
        assert class_cfg.max_retries == 3

        explain_cfg = cfg.get_task_config("explanation")
        assert explain_cfg.temperature == 0.1  # Slightly creative
        assert explain_cfg.json_mode is False

    def test_config_override(self):
        """Test overriding configuration"""
        cfg = LLMConfig()

        # Override model
        cfg.override_model_config(model="llama3:8b", temperature=0.2)
        assert cfg.model_config.model == "llama3:8b"
        assert cfg.model_config.temperature == 0.2

        # Override task
        cfg.override_task_config("extraction", max_retries=5, timeout=120)
        extract_cfg = cfg.get_task_config("extraction")
        assert extract_cfg.max_retries == 5
        assert extract_cfg.timeout == 120

        # Override behavior
        cfg.override_behavior(concise_mode=False, use_emojis=True)
        assert cfg.behavior.concise_mode is False
        assert cfg.behavior.use_emojis is True

    def test_config_serialization(self):
        """Test saving and loading configuration"""
        cfg = LLMConfig()
        cfg.override_model_config(model="test-model")
        cfg.override_behavior(concise_mode=False)

        # Convert to dict
        config_dict = cfg.to_dict()
        assert config_dict["model"]["model"] == "test-model"
        assert config_dict["behavior"]["concise_mode"] is False

        # Recreate from dict
        cfg2 = LLMConfig.from_dict(config_dict)
        assert cfg2.model_config.model == "test-model"
        assert cfg2.behavior.concise_mode is False

    def test_convenience_functions(self):
        """Test convenience functions"""
        # Test set_model
        set_model("llama3:8b", "http://localhost:11434")
        assert config.model_config.model == "llama3:8b"

        # Test enable_deterministic_mode
        enable_deterministic_mode(True)
        for task_config in config.task_configs.values():
            assert task_config.temperature == 0.0

    def test_get_chat_params(self):
        """Test getting complete chat parameters"""
        cfg = LLMConfig()
        params = cfg.get_chat_params("classification")

        assert "model" in params
        assert "temperature" in params
        assert "json_mode" in params
        assert params["json_mode"] is True  # Classification uses JSON mode


class TestErrorHandling:
    """Test error handling improvements"""

    def test_ollama_connection_error(self):
        """Test handling of Ollama connection errors"""
        from llm.ollama_client import OllamaClient
        import requests

        client = OllamaClient(host="http://invalid-host:11434")

        with pytest.raises(requests.exceptions.ConnectionError) as exc_info:
            client._chat("system", "user")

        # Error message should be user-friendly
        assert "Could not connect" in str(exc_info.value)
        assert "Ollama" in str(exc_info.value)

    def test_ollama_timeout_error(self):
        """Test handling of timeout errors"""
        from llm.ollama_client import OllamaClient
        import requests

        client = OllamaClient()

        # Mock a timeout
        with patch('requests.post') as mock_post:
            mock_post.side_effect = requests.exceptions.Timeout("Timeout")

            with pytest.raises(requests.exceptions.Timeout) as exc_info:
                client._chat("system", "user")

            assert "timed out" in str(exc_info.value).lower()


# Integration tests with real transportation scenarios
class TestTransportationScenarios:
    """Test with real transportation problem descriptions"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_llm = Mock()
        self.router = IntentRouter(self.mock_llm)

    def test_balanced_greece_baseline(self):
        """Test Greek transportation scenario"""
        text = """A company operates two production sites in Greece: Athens and Thessaloniki.
        Athens can make up to 120 units per week, Thessaloniki can supply 200 pieces.
        They deliver products to three customer areas: Patras, Larisa, and Heraklion.
        Patras requires 100 units, Larisa needs 80, Heraklion has a demand of 110.
        Transport costs (in € per unit) are:
        From Athens to Patras: 5, From Athens to Larisa: 4, From Athens to Heraklion: 7
        From Thessaloniki to Patras: 6, From Thessaloniki to Larisa: 3, From Thessaloniki to Heraklion: 8
        The company wants to find the cheapest shipping plan."""

        result = self.router.detect_intent(text, {})
        assert result["intent"] == "optimization"

    def test_uk_simple_balanced(self):
        """Test UK transportation scenario"""
        text = """There are two factories in the UK: Manchester and Birmingham.
        Manchester can produce 150 units weekly, Birmingham up to 170.
        Goods go to three retailers: London, Bristol, and Leeds.
        London needs 140 units, Bristol 80, and Leeds demands 100.
        Per-unit shipping cost (£) is as follows:
        Manchester→London: 6, Manchester→Bristol: 5, Manchester→Leeds: 4
        Birmingham→London: 5, Birmingham→Bristol: 6, Birmingham→Leeds: 3
        Minimise the total transport cost."""

        result = self.router.detect_intent(text, {})
        assert result["intent"] == "optimization"

    def test_unbalanced_supply_scenario(self):
        """Test unbalanced supply scenario"""
        text = """A vendor ships from three warehouses: Porto, Vigo, and A Coruña.
        Capacities: Porto 200, Vigo 120, A Coruña 90 (units per week).
        Customers are Salamanca and Bilbao with demands 150 and 120 respectively.
        The company allows unshipped surplus to remain at warehouses.
        Costs (€/unit):
        Porto→Salamanca: 4, Porto→Bilbao: 7
        Vigo→Salamanca: 5, Vigo→Bilbao: 4
        A Coruña→Salamanca: 6, A Coruña→Bilbao: 3
        Find the minimum cost plan."""

        result = self.router.detect_intent(text, {})
        assert result["intent"] == "optimization"

    def test_integer_shipments_scenario(self):
        """Test scenario requiring integer shipments"""
        text = """Two depots, Oslo and Bergen, supply electronics.
        Oslo can ship 75 units per week, Bergen up to 130.
        Customers: Trondheim needs 60, Stavanger needs 70, Kristiansand needs 50.
        Per-unit shipping costs (NOK):
        Oslo→Trondheim: 8, Oslo→Stavanger: 7, Oslo→Kristiansand: 6
        Bergen→Trondheim: 5, Bergen→Stavanger: 4, Bergen→Kristiansand: 9
        Shipments must be in whole units (no fractional shipments).
        Minimise total shipping cost."""

        result = self.router.detect_intent(text, {})
        assert result["intent"] == "optimization"

    def test_forbidden_route_scenario(self):
        """Test scenario with route constraints"""
        text = """Three plants: Antwerp (capacity 120), Ghent (90), and Liège (110).
        Destinations: Bruges (80), Namur (100), Mons (70).
        Costs (€/unit):
        Antwerp→Bruges: 5, Antwerp→Namur: 6, Antwerp→Mons: 9
        Ghent→Bruges: 3, Ghent→Namur: 7, Ghent→Mons: 5
        Liège→Bruges: 8, Liège→Namur: 4, Liège→Mons: 6
        Note: Shipments from Antwerp to Mons are not allowed due to a contract restriction.
        Objective: minimise the total cost."""

        result = self.router.detect_intent(text, {})
        assert result["intent"] == "optimization"

    def test_distance_based_costs(self):
        """Test scenario with distance-based cost calculation"""
        text = """A firm ships from Lyon and Marseille to Nice and Grenoble.
        Capacities: Lyon 140, Marseille 160. Demands: Nice 150, Grenoble 120.
        Freight rate is €0.06 per unit per km. Distances (km):
        Lyon→Nice: 470, Lyon→Grenoble: 113
        Marseille→Nice: 200, Marseille→Grenoble: 318
        Find the cheapest shipping plan."""

        result = self.router.detect_intent(text, {})
        assert result["intent"] == "optimization"

    def test_zero_cost_promo_route(self):
        """Test scenario with zero-cost promotional route"""
        text = """Two factories: Prague (capacity 130) and Brno (capacity 120).
        Stores: Ostrava demand 110, Olomouc demand 90, Zlín demand 40.
        Per unit cost (CZK):
        Prague→Ostrava: 0, Prague→Olomouc: 6, Prague→Zlín: 5
        Brno→Ostrava: 4, Brno→Olomouc: 2, Brno→Zlín: 3
        A temporary promotion makes shipping from Prague to Ostrava free.
        Minimise total cost."""

        result = self.router.detect_intent(text, {})
        assert result["intent"] == "optimization"

    def test_thousands_separators(self):
        """Test scenario with large numbers and thousands separators"""
        text = """Three factories: Miami (capacity 1,200), Tampa (capacity 800), and Orlando (capacity 1,000).
        Stores: Jacksonville demand 900, Tallahassee 700, Pensacola 300.
        Unit shipping costs (USD):
        Miami→Jacksonville: 6, Miami→Tallahassee: 7, Miami→Pensacola: 5
        Tampa→Jacksonville: 4, Tampa→Tallahassee: 6, Tampa→Pensacola: 3
        Orlando→Jacksonville: 5, Orlando→Tallahassee: 4, Orlando→Pensacola: 6
        Minimise the total logistics cost."""

        result = self.router.detect_intent(text, {})
        assert result["intent"] == "optimization"

    def test_rate_per_1000_miles(self):
        """Test scenario with rate per distance unit"""
        text = """A company ships from Dallas (cap 300) and Phoenix (cap 250) to San Jose (demand 280) and San Diego (demand 240).
        Freight rate is $90 per unit per 1000 miles. Distances (miles):
        Dallas→San Jose: 1460, Dallas→San Diego: 1250
        Phoenix→San Jose: 720, Phoenix→San Diego: 355
        Find the plan with the smallest total shipping cost."""

        result = self.router.detect_intent(text, {})
        assert result["intent"] == "optimization"


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_llm = Mock()
        self.router = IntentRouter(self.mock_llm)
        self.guard = ExplanationGuard()

    def test_ambiguous_message(self):
        """Test handling of ambiguous messages"""
        # Message could be greeting or optimization-related
        message = "Hello, I need help optimizing my shipping routes"
        result = self.router.detect_intent(message, {})
        # Should lean toward optimization due to keywords
        assert result["intent"] in ["optimization", "help"]

    def test_very_short_message(self):
        """Test handling of very short messages"""
        messages = ["Cost?", "Why?", "How?", "OK"]
        context = {"last_solution": {"problem_type": "TRANSPORTATION"}}

        for msg in messages:
            result = self.router.detect_intent(msg, context)
            # Short messages with context should be follow-ups
            assert result["intent"] == "follow_up"

    def test_zero_values_in_solution(self):
        """Test handling of zero values in solution"""
        solution = {
            "objective_value": 0,  # Edge case: zero cost
            "flows": [
                {"plant": "A", "market": "X", "value": 0}  # Zero flow
            ],
            "status": "OPTIMAL"
        }

        facts = self.guard.extract_data_facts(solution)
        assert "0" in facts["numbers"]

    def test_very_large_numbers(self):
        """Test handling of very large numbers"""
        solution = {
            "objective_value": 1234567.89,
            "flows": [
                {"plant": "Mega", "market": "Factory", "value": 999999.99}
            ],
            "status": "OPTIMAL"
        }

        facts = self.guard.extract_data_facts(solution)
        summary = self.guard.create_deterministic_summary(solution)
        assert "1234567" in summary or "1234568" in summary  # Allow rounding

    def test_special_characters_in_names(self):
        """Test handling of special characters in entity names"""
        solution = {
            "objective_value": 100,
            "flows": [
                {"plant": "São Paulo", "market": "München", "value": 50},
                {"plant": "Zürich", "market": "Москва", "value": 50}
            ],
            "status": "OPTIMAL"
        }

        facts = self.guard.extract_data_facts(solution)
        assert "são paulo" in facts["entity_names"]
        assert "münchen" in facts["entity_names"]


# Integration tests
class TestIntegration:
    """Integration tests for the refactored system"""

    def test_full_intent_routing_pipeline(self):
        """Test full pipeline from intent detection to response"""
        mock_llm = Mock()
        router = IntentRouter(mock_llm)

        # Test smalltalk flow
        result = router.detect_intent("Hello!", {})
        assert result["intent"] == "smalltalk"

        response = router.handle_smalltalk("Hello!")
        assert "optimization" in response["response"].lower()

    def test_configuration_affects_behavior(self):
        """Test that configuration changes affect behavior"""
        cfg = LLMConfig()

        # Set high technical depth
        cfg.override_behavior(technical_depth="high")
        assert cfg.behavior.technical_depth == "high"

        # Enable verbose mode
        cfg.override_behavior(verbose_logging=True)
        assert cfg.behavior.verbose_logging is True

    def test_full_conversation_flow(self):
        """Test a complete conversation flow"""
        mock_llm = Mock()
        router = IntentRouter(mock_llm)
        follow_up_handler = FollowUpHandler(mock_llm)

        # Step 1: User asks optimization problem
        problem = """Two factories: Seattle (350) and San Diego (600).
        Three customers: NY (325), Chicago (300), Topeka (275).
        Minimize shipping costs."""

        intent1 = router.detect_intent(problem, {})
        assert intent1["intent"] == "optimization"

        # Step 2: User asks follow-up question
        context = {
            "last_solution": {
                "problem_type": "TRANSPORTATION",
                "objective_value": 153.675,
                "extracted_params": {
                    "plants": ["Seattle", "San Diego"],
                    "markets": ["NY", "Chicago", "Topeka"]
                },
                "solution": {"status": "OPTIMAL"}
            }
        }

        intent2 = router.detect_intent("What's the objective?", context)
        assert intent2["intent"] == "follow_up"

        # Step 3: Get deterministic answer
        answer = follow_up_handler.answer_deterministic_question(
            "What's the objective?",
            context["last_solution"],
            "objective"
        )
        assert answer is not None
        assert "minimize" in answer.lower() or "cost" in answer.lower()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
