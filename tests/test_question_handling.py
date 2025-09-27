#!/usr/bin/env python3

import sys
sys.path.append('.')

from conversation.agent import ConversationalAgent
from llm.ollama_client import OllamaClient

# Initialize the conversational agent
llm_client = OllamaClient()
agent = ConversationalAgent(llm_client)

# First, solve a transportation problem
print("=== Testing Question Handling with Different Terminology ===")
print("\n1. First, solving a transportation problem...")

transportation_problem = """
A company operates two production sites in Greece: Athens and Thessaloniki.
Athens can make up to 120 units per week, Thessaloniki can supply 200 pieces.
They deliver products to three customer areas: Patras, Larisa, and Heraklion.
Patras requires 100 units, Larisa needs 80, Heraklion has a demand of 110.
Transport costs (in € per unit) are:
From Athens to Patras: 5
From Athens to Larisa: 4
From Athens to Heraklion: 7
From Thessaloniki to Patras: 6
From Thessaloniki to Larisa: 3
From Thessaloniki to Heraklion: 8
The company wants to find the cheapest shipping plan that respects production limits and fulfils all customer needs.
"""

# Create a proper session first
session_id = agent.memory.create_conversation()
print(f"Created session: {session_id}")

result1 = agent.process_message(session_id, transportation_problem)
print(f"Problem solved: {result1.get('success', False)}")

# Test edge cases with different terminology
test_questions = [
    "What kind of analysis options are available?",
    "What can you do with this solution?",
    "What are we trying to maximize here?",
    "What function are we minimizing?",
    "How many cities are involved in this problem?",
    "How many decision variables exist?",
    "What rules must the solution follow?",
    "What limitations does this problem have?",
    "What sort of mathematical analysis can you perform?",
    "What insights can you give me about this?",
    "How many locations are we dealing with?",
    "What's the goal of this optimization?",
    "What restrictions apply to this problem?"
]

print(f"\n2. Testing {len(test_questions)} different question variations...")

for i, question in enumerate(test_questions, 1):
    print(f"\n--- Question {i}: '{question}' ---")
    result = agent.process_message(session_id, question)

    if result.get('success'):
        content = result.get('content', '')
        # Show first 100 characters to see what type of response we got
        preview = content[:100] + "..." if len(content) > 100 else content
        print(f"✅ Response: {preview}")

        # Check if it's the generic analysis response (bad) or specific info (good)
        if "For more specific analysis, try asking:" in content:
            print("⚠️  Got generic analysis response (should be avoided)")
        elif any(keyword in content for keyword in ["Available Analysis Types", "Objective Function", "Problem Dimensions", "Problem Constraints"]):
            print("✅ Got specific problem information (good!)")
        else:
            print("❓ Got other type of response")
    else:
        print(f"❌ Failed: {result.get('error', 'Unknown error')}")

print("\nTest completed!")