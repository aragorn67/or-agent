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

# Test just a few key cases to debug classification
test_cases = [
    "What types of analyses can you provide?",
    "What are we trying to minimize?",
    "How many cities are involved?",
    "What constraints apply?"
]

print("\n=== Debugging Classification ===")

for question in test_cases:
    print(f"\n🔍 Testing: '{question}'")

    # Check follow-up detection first
    context = agent.memory.get_context(session_id)
    follow_up_info = agent.llm.detect_follow_up_intent(question, context)

    print(f"   Follow-up type: {follow_up_info.get('follow_up_type', 'unknown')}")

    if follow_up_info.get('follow_up_type') == 'question':
        # Test our question categorization
        last_solution = context.get("last_solution", {})
        question_type = agent._categorize_question(question, last_solution)
        print(f"   Question category: {question_type}")

    # Get the actual response
    result = agent.process_message(session_id, question)
    content = result.get('content', '')

    if "Available Analysis Types" in content:
        print(f"   ✅ Got capabilities response")
    elif "Objective Function" in content:
        print(f"   ✅ Got objective response")
    elif "Problem Dimensions" in content:
        print(f"   ✅ Got dimensions response")
    elif "Problem Constraints" in content:
        print(f"   ✅ Got constraints response")
    elif "For more specific analysis, try asking:" in content:
        print(f"   ⚠️ Got generic analysis response")
    else:
        print(f"   ❓ Got other response: {content[:50]}...")