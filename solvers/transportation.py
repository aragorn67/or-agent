# solvers/transportation.py
from typing import Dict, Any, List
from .base import OptimizationSolver
import model  # Import existing model.py

class TransportationSolver(OptimizationSolver):
    """Transportation optimization solver"""

    @property
    def problem_type(self) -> str:
        return "TRANSPORTATION"

    @property
    def description(self) -> str:
        return "Minimize cost of shipping goods from plants to markets"

    def solve(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Solve transportation problem using existing model"""
        return model.solve_transport(params)

    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        """Validate transportation parameters with user-friendly explanations"""
        errors = []

        # Check required fields
        required_fields = ['plants', 'markets', 'capacity', 'demand', 'distance', 'freight']
        for field in required_fields:
            if field not in params:
                errors.append(f"Missing {field}. Please specify your {field} in the problem description.")

        if errors:
            return errors

        # Check data types and content
        if not isinstance(params.get('plants'), list) or not params.get('plants'):
            errors.append("❌ No factories/plants found. Please mention your factories like 'Factory Seattle' or 'Plant A'.")

        if not isinstance(params.get('markets'), list) or not params.get('markets'):
            errors.append("❌ No customers/markets found. Please mention your customers like 'Customer New York' or 'Market Chicago'.")

        # Validate capacity
        if not isinstance(params.get('capacity'), dict):
            errors.append("❌ Factory capacities not found. Please specify how much each factory can produce.")
        else:
            for plant, cap in params.get('capacity', {}).items():
                if cap is None or not isinstance(cap, (int, float)):
                    errors.append(f"❌ Factory '{plant}' has invalid capacity. Please specify a number like '350 units'.")
                elif cap <= 0:
                    errors.append(f"⚠️ Factory '{plant}' has zero or negative capacity ({cap}). This may cause issues.")

        # Validate demand
        if not isinstance(params.get('demand'), dict):
            errors.append("❌ Customer demands not found. Please specify how much each customer needs.")
        else:
            for market, dem in params.get('demand', {}).items():
                if dem is None or not isinstance(dem, (int, float)):
                    errors.append(f"❌ Customer '{market}' has invalid demand. Please specify a number like '300 units'.")
                elif dem <= 0:
                    errors.append(f"⚠️ Customer '{market}' has zero or negative demand ({dem}).")

        # Validate distances
        if not isinstance(params.get('distance'), dict):
            errors.append("❌ Distances not found. Please specify distances between factories and customers.")
        else:
            plants = params.get('plants', [])
            markets = params.get('markets', [])

            for plant in plants:
                if plant not in params['distance']:
                    errors.append(f"❌ Missing distances from factory '{plant}' to customers.")
                else:
                    for market in markets:
                        if market not in params['distance'][plant]:
                            errors.append(f"❌ Missing distance from '{plant}' to '{market}'.")
                        elif params['distance'][plant][market] is None:
                            errors.append(f"❌ Invalid distance from '{plant}' to '{market}'. Please specify a number.")

        # Validate freight cost
        if not isinstance(params.get('freight'), (int, float)) or params.get('freight') is None:
            errors.append("❌ Freight cost not found. Please specify shipping cost like '$90 per unit per mile'.")
        elif params.get('freight') <= 0:
            errors.append("⚠️ Freight cost is zero or negative. Please check your shipping cost.")

        # Check for mismatched counts
        if isinstance(params.get('plants'), list) and isinstance(params.get('markets'), list):
            plant_count = len(params['plants'])
            market_count = len(params['markets'])

            if 'factories' in str(params).lower():
                described_factories = self._extract_number_from_description(str(params), 'factories')
                if described_factories and described_factories != plant_count:
                    errors.append(f"🤔 You mentioned {described_factories} factories but I found {plant_count} factory names. Please check for consistency.")

            if 'customers' in str(params).lower():
                described_customers = self._extract_number_from_description(str(params), 'customers')
                if described_customers and described_customers != market_count:
                    errors.append(f"🤔 You mentioned {described_customers} customers but I found {market_count} customer names. Please check for consistency.")

        return errors

    def _extract_number_from_description(self, text: str, word: str) -> int:
        """Extract number before a word like '10 customers' -> 10"""
        import re
        pattern = r'(\d+)\s+' + word
        match = re.search(pattern, text.lower())
        return int(match.group(1)) if match else None

    def get_example_params(self) -> Dict[str, Any]:
        """Return example parameters for transportation problem"""
        return {
            "plants": ["seattle", "san-diego"],
            "markets": ["new-york", "chicago", "topeka"],
            "capacity": {"seattle": 350, "san-diego": 600},
            "demand": {"new-york": 325, "chicago": 300, "topeka": 275},
            "distance": {
                "seattle": {"new-york": 2.5, "chicago": 1.7, "topeka": 1.8},
                "san-diego": {"new-york": 2.5, "chicago": 1.8, "topeka": 1.4}
            },
            "freight": 90
        }