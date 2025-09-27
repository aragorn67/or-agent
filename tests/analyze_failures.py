#!/usr/bin/env python3

import sys
sys.path.append('.')

from conversation.agent import ConversationalAgent
from llm.ollama_client import OllamaClient

# Initialize the conversational agent
llm_client = OllamaClient()
agent = ConversationalAgent(llm_client)

# First, solve a transportation problem
transportation_problem = """
A company operates two production sites in Greece: Athens and Thessaloniki.
Athens can make up to 120 units per week, Thessaloniki can supply 200 pieces.
They deliver products to three customer areas: Patras, Larisa, and Heraklion.
Patras requires 100 units, Larisa needs 80, Heraklion has a demand of 110.
Transport costs (in € per unit) are:
From Athens to Patras: 5, From Athens to Larisa: 4, From Athens to Heraklion: 7
From Thessaloniki to Patras: 6, From Thessaloniki to Larisa: 3, From Thessaloniki to Heraklion: 8
The company wants to find the cheapest shipping plan.
"""

session_id = agent.memory.create_conversation()
result = agent.process_message(session_id, transportation_problem)

if not result.get('success'):
    print("❌ Initial problem solving failed")
    exit(1)

print("✅ Problem solved successfully")

# Analyze the failing cases specifically
failing_cases = [
    "What can you do with this solution?",                   # Question 2
    "What are we trying to maximize here?",                  # Question 3
    "What limitations does this problem have?",              # Question 8
    "What sort of mathematical analysis can you perform?",   # Question 9
    "What insights can you give me about this?",            # Question 10
    "How many locations are we dealing with?",              # Question 11
]

print("\n=== Analyzing Failing Cases ===")

for i, question in enumerate(failing_cases, 1):
    print(f"\n🔍 Failing Case {i}: '{question}'")

    # Check initial follow-up detection
    context = agent.memory.get_context(session_id)
    follow_up_info = agent.llm.detect_follow_up_intent(question, context)

    print(f"   Step 1 - Follow-up detection: {follow_up_info.get('follow_up_type', 'unknown')}")

    if follow_up_info.get('follow_up_type') == 'question':
        # Check our question categorization
        last_solution = context.get("last_solution", {})
        question_type = agent._categorize_question(question, last_solution)
        print(f"   Step 2 - Question category: {question_type}")

        # Predict what response type we should get
        expected_map = {
            "capabilities": "📋 Available Analysis Types",
            "objective": "🎯 Objective Function",
            "dimensions": "📏 Problem Dimensions",
            "constraints": "⚖️ Problem Constraints",
            "general": "General LLM response"
        }
        print(f"   Expected: {expected_map.get(question_type, 'Unknown')}")

    # Get actual response
    result = agent.process_message(session_id, question)
    content = result.get('content', '')

    if "Available Analysis Types" in content:
        print(f"   ✅ Actual: Got capabilities response")
    elif "Objective Function" in content:
        print(f"   ✅ Actual: Got objective response")
    elif "Problem Dimensions" in content:
        print(f"   ✅ Actual: Got dimensions response")
    elif "Problem Constraints" in content:
        print(f"   ✅ Actual: Got constraints response")
    elif "For more specific analysis, try asking:" in content:
        print(f"   ❌ Actual: Got generic analysis response (BAD)")
    else:
        preview = content[:80] + "..." if len(content) > 80 else content
        print(f"   ❓ Actual: Other response - {preview}")

print("\n=== Analysis Complete ===")