# llm/units_handler.py
import re
from typing import Dict, Any, Optional, Tuple

class UnitsHandler:
    """Generic unit detection and preservation system"""

    def __init__(self):
        # Handle spaced symbols and postfix currencies
        self.currency_patterns = [
            (r'€\s*([0-9]+(?:[.,][0-9]+)?)', 'EUR', '€{}'),
            (r'([0-9]+(?:[.,][0-9]+)?)\s*€', 'EUR', '€{}'),
            (r'\$\s*([0-9]+(?:[.,][0-9]+)?)', 'USD', '${}'),
            (r'([0-9]+(?:[.,][0-9]+)?)\s*USD', 'USD', '${}'),
            (r'£\s*([0-9]+(?:[.,][0-9]+)?)', 'GBP', '£{}'),
            (r'([0-9]+(?:[.,][0-9]+)?)\s*GBP', 'GBP', '£{}'),
            (r'([0-9]+(?:[.,][0-9]+)?)\s*euros?', 'EUR', '€{}'),
            (r'([0-9]+(?:[.,][0-9]+)?)\s*dollars?', 'USD', '${}'),
            (r'([0-9]+(?:[.,][0-9]+)?)\s*pounds?', 'GBP', '£{}'),
        ]

        self.unit_patterns = [
            (r'per\s+unit', 'per unit'),
            (r'per\s+item', 'per item'),
            (r'per\s+piece', 'per piece'),
            (r'per\s+hour', 'per hour'),
            (r'per\s+day', 'per day'),
            (r'per\s+kg', 'per kg'),
            (r'per\s+mile', 'per mile'),
            (r'per\s+km', 'per km'),
        ]

    def _norm_num(self, s: str) -> float:
        """Normalise numbers with comma decimals"""
        s = s.strip().replace(' ', '')
        # if both separators appear, assume European style (dot thousands, comma decimal)
        if ',' in s and '.' in s and s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '.')
        return float(s)

    def detect_units(self, description: str) -> Dict[str, Any]:
        """Detect currency and units from problem description"""

        units_info = {
            'currency': None,
            'currency_symbol': None,
            'currency_format': '{}',
            'cost_units': None,
            'quantity_units': None,
            'has_thousands': False
        }

        text_lower = description.lower()

        # Detect currency
        for pattern, currency, format_str in self.currency_patterns:
            if re.search(pattern, description, re.IGNORECASE):
                units_info['currency'] = currency
                units_info['currency_symbol'] = format_str.split('{}')[0] if '{}' in format_str else currency
                units_info['currency_format'] = format_str
                break

        # Detect cost units context
        for pattern, unit in self.unit_patterns:
            if re.search(pattern, text_lower):
                units_info['cost_units'] = unit
                break

        # Avoid false "k" positives
        if re.search(r'\b\d+(?:[.,]\d+)?\s*k\b', text_lower) or \
           re.search(r'\bthousands?\b', text_lower) or \
           re.search(r'\bthousand\b', text_lower):
            units_info['has_thousands'] = True

        # Extended quantity units list
        quantity_words = ['unit', 'units', 'piece', 'pieces', 'pallet', 'pallets', 'case', 'cases',
                         'tonne', 'tonnes', 't', 'kg', 'items', 'item', 'ton', 'tons']
        for word in quantity_words:
            if word in text_lower:
                units_info['quantity_units'] = word
                break

        return units_info

    def format_cost(self, amount: float, units_info: Dict[str, Any], is_total: bool = False) -> str:
        """Format cost with proper units"""

        currency_format = units_info.get('currency_format', '{}')
        cost_units = units_info.get('cost_units', '')
        has_thousands = units_info.get('has_thousands', False)

        # Don't add thousands notation unless explicitly in input
        if has_thousands and is_total:
            # If input had thousands, show as thousands
            formatted_amount = f"{amount/1000:.1f}k" if amount >= 1000 else f"{amount:.0f}"
        else:
            # Otherwise show raw number
            formatted_amount = f"{amount:,.0f}" if amount >= 1000 else f"{amount:.0f}"

        # Apply currency formatting
        if currency_format != '{}':
            result = currency_format.format(formatted_amount)
        else:
            # No currency detected, use raw number
            result = str(formatted_amount)

        # Add per-unit context for unit costs (not totals)
        if not is_total and cost_units:
            result += f" {cost_units}"

        return result

    def format_solution_summary(self, solution: Dict[str, Any], units_info: Dict[str, Any]) -> str:
        """Format solution with proper units - GENERIC for any problem type"""

        total_cost = solution.get('objective_value') or solution.get('objective_thousand_usd', 0)
        status = solution.get('status', 'UNKNOWN')

        if status != 'OPTIMAL':
            return f"⚠️ Solution status: {status}"

        # Format total cost properly
        cost_str = self.format_cost(total_cost, units_info, is_total=True)

        return f"✅ Optimal solution: {cost_str} total cost"