# llm/explanation_guard.py
import re
from typing import Dict, Any, List, Set

class ExplanationGuard:
    """Generic grounding system - only allow facts that reference actual data"""

    def __init__(self):
        pass

    def extract_data_facts(self, solution_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract all factual elements that can be referenced"""

        facts = {
            'total_cost': None,
            'status': solution_data.get('status', 'UNKNOWN'),
            'entity_names': set(),
            'routes': [],
            'utilization': {},
            'numbers': set()
        }

        # Extract total cost
        cost = solution_data.get('objective_value') or solution_data.get('objective_thousand_usd', 0)
        if cost:
            facts['total_cost'] = cost
            facts['numbers'].add(str(int(cost)))

        # Extract entity names and routes from flows
        flows = solution_data.get('flows', [])
        for flow in flows:
            if flow.get('value', 0) > 0.01:  # Only meaningful flows
                plant = flow.get('plant', '')
                market = flow.get('market', '')
                value = flow.get('value', 0)

                facts['entity_names'].add(plant.lower())
                facts['entity_names'].add(market.lower())
                facts['routes'].append({
                    'from': plant,
                    'to': market,
                    'value': value
                })
                facts['numbers'].add(str(int(value)))

        # Extract utilization data
        utilization = solution_data.get('utilization', {})
        for plant, data in utilization.items():
            facts['entity_names'].add(plant.lower())
            rate = data.get('utilization_rate', 0)
            if rate:
                facts['utilization'][plant] = rate
                facts['numbers'].add(str(int(rate * 100)))

        return facts

    def is_sentence_grounded(self, sentence: str, facts: Dict[str, Any]) -> bool:
        """Check if sentence only references actual data"""

        sentence_lower = sentence.lower()

        # Must reference at least one actual entity name or number
        references_entities = any(entity in sentence_lower for entity in facts['entity_names'])
        references_numbers = any(num in sentence for num in facts['numbers'])
        references_cost = 'cost' in sentence_lower and facts['total_cost'] is not None
        references_status = any(word in sentence_lower for word in ['optimal', 'solution', 'status'])

        has_data_reference = references_entities or references_numbers or references_cost or references_status

        return has_data_reference

    def filter_explanation(self, explanation: str, solution_data: Dict[str, Any]) -> str:
        """Filter explanation to keep only grounded sentences"""

        facts = self.extract_data_facts(solution_data)

        # Split into sentences
        sentences = re.split(r'[.!?]+', explanation.strip())
        grounded_sentences = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if self.is_sentence_grounded(sentence, facts):
                grounded_sentences.append(sentence)

        if grounded_sentences:
            return '. '.join(grounded_sentences) + '.'
        else:
            # Fallback to deterministic summary
            return self.create_deterministic_summary(solution_data)

    def create_deterministic_summary(self, solution_data: Dict[str, Any]) -> str:
        """Create purely factual deterministic summary"""

        facts = self.extract_data_facts(solution_data)
        summary_parts = []

        # Status and cost
        if facts['status'] == 'OPTIMAL' and facts['total_cost']:
            summary_parts.append(f"Optimal solution with total cost {facts['total_cost']}")

        # Top routes
        routes = sorted(facts['routes'], key=lambda x: x['value'], reverse=True)[:3]
        if routes:
            route_strs = [f"{r['from']} → {r['to']}: {int(r['value'])} units" for r in routes]
            summary_parts.append(f"Key routes: {', '.join(route_strs)}")

        # Utilization if available
        if facts['utilization']:
            util_strs = [f"{plant}: {int(rate*100)}%" for plant, rate in facts['utilization'].items()]
            summary_parts.append(f"Utilization: {', '.join(util_strs)}")

        return '. '.join(summary_parts) + '.' if summary_parts else "Solution obtained."

    def create_concise_prompt(self, problem_type: str) -> str:
        """Create prompt for concise, factual explanations"""

        return f"""
Explain this {problem_type} solution in exactly 2 sentences using ONLY data from the solution.

RULES:
- Reference only entity names, numbers, and values present in the data
- NO speculation about reasons, geography, or business context
- Format: "Total cost X. Key routes: [entity → entity: number units]."
- Maximum 40 words

Example: "Total cost €1600. Key routes: Athens → Larisa: 80 units, Thessaloniki → Heraklion: 110 units."
"""