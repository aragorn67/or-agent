"""
Unit tests for feasibility checking module.

Tests all three layers:
- Layer 0: Structural checks
- Layer 1: Problem-specific necessary conditions (transportation)
- Layer 2: Solver-based feasibility (TODO: Phase 2)

Uses infeasible problems from or_problem_repository to test failure modes.
"""

import pytest
from feasibility import check_feasibility, FeasStatus, FeasibilityReport
from feasibility.schemas import ParsedInstance


class TestLayer0Structural:
    """Test Layer 0 structural/sanity checks."""

    def test_empty_sets(self):
        """Layer 0 should reject instances with empty sets."""
        instance = ParsedInstance(
            problem_type="TRANSPORTATION",
            solver_id="transport_basic_bipartite",
            sets={'I': [], 'J': ['J1', 'J2']},  # Empty source set
            params={'cost': {}}
        )

        report = check_feasibility(instance)

        assert report.status == FeasStatus.INFEASIBLE
        assert report.layer_passed == 0
        assert "empty" in report.reasons[0].lower()

    def test_dimension_mismatch(self):
        """Layer 0 should catch cost matrix dimension mismatches."""
        # Simulate the infeasible_transport_struct_mismatched_costs problem
        instance = ParsedInstance(
            problem_type="TRANSPORTATION",
            solver_id="transport_basic_bipartite",
            sets={
                'I_factories': ['F1', 'F2'],
                'J_warehouses': ['W1', 'W2', 'W3']
            },
            params={
                'supply': {'F1': 80, 'F2': 60},
                'demand': {'W1': 40, 'W2': 50, 'W3': 30},
                # Missing cost for F2→W3
                'cost': {
                    ('F1', 'W1'): 10, ('F1', 'W2'): 12, ('F1', 'W3'): 15,
                    ('F2', 'W1'): 11, ('F2', 'W2'): 13
                    # ('F2', 'W3'): missing!
                }
            }
        )

        report = check_feasibility(instance)

        assert report.status == FeasStatus.INFEASIBLE
        assert report.layer_passed == 0
        assert "dimension" in report.reasons[0].lower() or "missing" in report.reasons[0].lower()
        assert "cost" in report.reasons[0].lower()

    def test_negative_values(self):
        """Layer 0 should reject negative capacities/demands."""
        instance = ParsedInstance(
            problem_type="TRANSPORTATION",
            solver_id="transport_basic_bipartite",
            sets={
                'I': ['I1', 'I2'],
                'J': ['J1', 'J2']
            },
            params={
                'supply': {'I1': 100, 'I2': -50},  # Negative supply!
                'demand': {'J1': 75, 'J2': 75},
                'cost': {
                    ('I1', 'J1'): 5, ('I1', 'J2'): 8,
                    ('I2', 'J1'): 7, ('I2', 'J2'): 6
                }
            }
        )

        report = check_feasibility(instance)

        assert report.status == FeasStatus.INFEASIBLE
        assert report.layer_passed == 0
        assert "negative" in report.reasons[0].lower()

    def test_valid_structure_passes(self):
        """Layer 0 should pass well-formed instances."""
        instance = ParsedInstance(
            problem_type="TRANSPORTATION",
            solver_id="transport_basic_bipartite",
            sets={
                'I': ['I1', 'I2'],
                'J': ['J1', 'J2']
            },
            params={
                'supply': {'I1': 100, 'I2': 100},
                'demand': {'J1': 80, 'J2': 80},
                'cost': {
                    ('I1', 'J1'): 5, ('I1', 'J2'): 8,
                    ('I2', 'J1'): 7, ('I2', 'J2'): 6
                }
            }
        )

        report = check_feasibility(instance)

        # Should pass Layer 0 (might fail later layers, but not this one)
        assert report.layer_passed >= 0


class TestLayer1Transportation:
    """Test Layer 1 transportation-specific checks."""

    def test_supply_less_than_demand(self):
        """Layer 1 should catch total supply < total demand."""
        # Simulate infeasible_transport_supply_less_than_demand problem
        instance = ParsedInstance(
            problem_type="TRANSPORTATION",
            solver_id="transport_basic_bipartite",
            sets={
                'I_plants': ['Plant_North', 'Plant_South'],
                'J_centres': ['Centre_A', 'Centre_B', 'Centre_C']
            },
            params={
                'supply': {'Plant_North': 40, 'Plant_South': 30},  # Total: 70
                'demand': {'Centre_A': 35, 'Centre_B': 25, 'Centre_C': 20},  # Total: 80
                'cost': {
                    ('Plant_North', 'Centre_A'): 10, ('Plant_North', 'Centre_B'): 8, ('Plant_North', 'Centre_C'): 12,
                    ('Plant_South', 'Centre_A'): 9, ('Plant_South', 'Centre_B'): 11, ('Plant_South', 'Centre_C'): 7
                }
            }
        )

        report = check_feasibility(instance)

        assert report.status == FeasStatus.INFEASIBLE
        assert report.layer_passed == 1  # Passed Layer 0, failed Layer 1
        assert any("supply" in msg.lower() and "demand" in msg.lower() for msg in report.reasons)
        assert any("70" in msg and "80" in msg for msg in report.reasons)  # Specific values

    def test_balanced_supply_demand_passes(self):
        """Layer 1 should pass when supply >= demand."""
        instance = ParsedInstance(
            problem_type="TRANSPORTATION",
            solver_id="transport_basic_bipartite",
            sets={
                'I': ['I1', 'I2'],
                'J': ['J1', 'J2']
            },
            params={
                'supply': {'I1': 100, 'I2': 100},  # Total: 200
                'demand': {'J1': 80, 'J2': 80},    # Total: 160
                'cost': {
                    ('I1', 'J1'): 5, ('I1', 'J2'): 8,
                    ('I2', 'J1'): 7, ('I2', 'J2'): 6
                }
            }
        )

        report = check_feasibility(instance)

        # Should pass both Layer 0 and Layer 1
        assert report.status == FeasStatus.FEASIBLE
        assert report.layer_passed >= 1

    def test_arc_capacity_infeasible(self):
        """Layer 1 should catch insufficient arc capacity to meet sink demand."""
        instance = ParsedInstance(
            problem_type="TRANSPORTATION",
            solver_id="transport_basic_bipartite",
            sets={
                'I_factories': ['F1'],
                'J_plants': ['P1']
            },
            params={
                'supply': {'F1': 100},
                'demand': {'P1': 50},
                'cost': {('F1', 'P1'): 10},
                'arc_capacity': {('F1', 'P1'): 30}  # Capacity 30 < demand 50
            }
        )

        report = check_feasibility(instance)

        assert report.status == FeasStatus.INFEASIBLE
        assert report.layer_passed == 1
        assert any("capacity" in msg.lower() for msg in report.reasons)


class TestFeasibleInstances:
    """Test that feasible problems pass all checks."""

    def test_simple_feasible_transport(self):
        """A basic feasible transportation problem should pass."""
        instance = ParsedInstance(
            problem_type="TRANSPORTATION",
            solver_id="transport_basic_bipartite",
            sets={
                'I_sources': ['Seattle', 'Denver', 'Detroit'],
                'J_sinks': ['Chicago', 'New_York', 'Atlanta']
            },
            params={
                'supply': {'Seattle': 350, 'Denver': 200, 'Detroit': 150},
                'demand': {'Chicago': 250, 'New_York': 180, 'Atlanta': 270},
                'cost': {
                    ('Seattle', 'Chicago'): 2, ('Seattle', 'New_York'): 4, ('Seattle', 'Atlanta'): 5,
                    ('Denver', 'Chicago'): 3, ('Denver', 'New_York'): 6, ('Denver', 'Atlanta'): 2,
                    ('Detroit', 'Chicago'): 5, ('Detroit', 'New_York'): 3, ('Detroit', 'Atlanta'): 4
                }
            }
        )

        report = check_feasibility(instance)

        assert report.status == FeasStatus.FEASIBLE
        assert report.layer_passed >= 1
        assert any("balance" in msg.lower() for msg in report.reasons)

    def test_unbalanced_excess_supply_feasible(self):
        """Unbalanced problem with excess supply should still be feasible."""
        instance = ParsedInstance(
            problem_type="TRANSPORTATION",
            solver_id="transport_basic_bipartite",
            sets={
                'I_plants': ['Athens', 'Thessaloniki'],
                'J_markets': ['Patras', 'Larisa', 'Heraklion']
            },
            params={
                'supply': {'Athens': 120, 'Thessaloniki': 200},  # Total: 320
                'demand': {'Patras': 100, 'Larisa': 80, 'Heraklion': 110},  # Total: 290
                'cost': {
                    ('Athens', 'Patras'): 5, ('Athens', 'Larisa'): 4, ('Athens', 'Heraklion'): 7,
                    ('Thessaloniki', 'Patras'): 6, ('Thessaloniki', 'Larisa'): 3, ('Thessaloniki', 'Heraklion'): 8
                }
            }
        )

        report = check_feasibility(instance)

        assert report.status == FeasStatus.FEASIBLE
        assert report.layer_passed >= 1
        assert any("surplus" in msg.lower() for msg in report.reasons)


class TestDictInstanceSupport:
    """Test that dict-based instances (current format) work correctly."""

    def test_dict_instance_infeasible(self):
        """Dict instances should work same as ParsedInstance."""
        instance = {
            'problem_type': 'TRANSPORTATION',
            'solver_id': 'transport_basic_bipartite',
            'sets': {
                'I_plants': ['North', 'South'],
                'J_centres': ['A', 'B', 'C']
            },
            'params': {
                'supply': {'North': 40, 'South': 30},
                'demand': {'A': 35, 'B': 25, 'C': 20},
                'cost': {
                    ('North', 'A'): 10, ('North', 'B'): 8, ('North', 'C'): 12,
                    ('South', 'A'): 9, ('South', 'B'): 11, ('South', 'C'): 7
                }
            }
        }

        report = check_feasibility(instance)

        assert report.status == FeasStatus.INFEASIBLE
        assert "70" in str(report.reasons) and "80" in str(report.reasons)

    def test_dict_instance_feasible(self):
        """Dict instances should pass when valid."""
        instance = {
            'problem_type': 'TRANSPORTATION',
            'solver_id': 'transport_basic_bipartite',
            'sets': {
                'I': ['I1', 'I2'],
                'J': ['J1', 'J2']
            },
            'params': {
                'supply': {'I1': 100, 'I2': 100},
                'demand': {'J1': 80, 'J2': 80},
                'cost': {
                    ('I1', 'J1'): 5, ('I1', 'J2'): 8,
                    ('I2', 'J1'): 7, ('I2', 'J2'): 6
                }
            }
        }

        report = check_feasibility(instance)

        assert report.status == FeasStatus.FEASIBLE


class TestReportStructure:
    """Test FeasibilityReport structure and content."""

    def test_report_has_required_fields(self):
        """FeasibilityReport should have all required fields."""
        instance = ParsedInstance(
            problem_type="TRANSPORTATION",
            solver_id="transport_basic_bipartite",
            sets={'I': ['I1'], 'J': ['J1']},
            params={
                'supply': {'I1': 100},
                'demand': {'J1': 80},
                'cost': {('I1', 'J1'): 5}
            }
        )

        report = check_feasibility(instance)

        assert hasattr(report, 'status')
        assert hasattr(report, 'reasons')
        assert hasattr(report, 'layer_passed')
        assert hasattr(report, 'suggestions')
        assert isinstance(report.status, FeasStatus)
        assert isinstance(report.reasons, list)
        assert isinstance(report.layer_passed, int)

    def test_infeasible_report_has_clear_reasons(self):
        """Infeasible reports should have clear, actionable reasons."""
        instance = ParsedInstance(
            problem_type="TRANSPORTATION",
            solver_id="transport_basic_bipartite",
            sets={
                'I': ['I1'],
                'J': ['J1']
            },
            params={
                'supply': {'I1': 50},
                'demand': {'J1': 100},
                'cost': {('I1', 'J1'): 5}
            }
        )

        report = check_feasibility(instance)

        assert report.status == FeasStatus.INFEASIBLE
        assert len(report.reasons) > 0
        # Reasons should be human-readable strings
        for reason in report.reasons:
            assert isinstance(reason, str)
            assert len(reason) > 10  # Non-trivial message


class TestRealRepositoryProblems:
    """Test against actual infeasible problems from or_problem_repository using full workflow."""

    @pytest.fixture(scope="class")
    def agent(self):
        """Setup agent for end-to-end testing (same as test_end_to_end_workflow.py)."""
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        from llm.enhanced_client import EnhancedLLMClient
        from agent.core import OptimizationAgent
        from config import Config

        llm_client = EnhancedLLMClient(
            host=Config.OLLAMA_HOST,
            model=Config.OLLAMA_MODEL
        )
        return OptimizationAgent(llm_client)

    def test_infeasible_struct_missing_cost(self, agent):
        """
        Test infeasible_transport_struct_mismatched_costs from repository.
        Expected: Agent should catch Layer 0 failure (missing cost matrix entry).
        """
        from tests.or_problem_repository import get_problem_by_name

        problem = get_problem_by_name("infeasible_transport_struct_mismatched_costs")
        assert problem is not None
        assert problem['solvable'] == False

        # Use full agent workflow (same as end-to-end test)
        result = agent.solve_natural_language(problem['text'])

        # Should detect infeasibility
        assert 'error' in result or 'infeasible' in str(result).lower() or not result.get('success', True)

    def test_infeasible_supply_less_demand(self, agent):
        """
        Test infeasible_transport_supply_less_than_demand from repository.
        Expected: Agent should catch Layer 1 failure (supply < demand).
        """
        from tests.or_problem_repository import get_problem_by_name

        problem = get_problem_by_name("infeasible_transport_supply_less_than_demand")
        assert problem is not None
        assert problem['solvable'] == False

        # Use full agent workflow
        result = agent.solve_natural_language(problem['text'])

        # Should detect infeasibility
        assert 'error' in result or 'infeasible' in str(result).lower() or not result.get('success', True)

    def test_feasible_us_manufacturing(self, agent):
        """
        Test us_manufacturing_distribution from repository (feasible).
        Expected: Should solve successfully.
        """
        from tests.or_problem_repository import get_problem_by_name

        problem = get_problem_by_name("us_manufacturing_distribution")
        assert problem is not None
        assert problem['solvable'] == True

        # Use full agent workflow
        result = agent.solve_natural_language(problem['text'])

        # Should solve successfully
        assert result.get('success', False) == True
        assert 'objective_value' in result or 'solution' in result

    def test_infeasible_capacity_pattern(self, agent):
        """
        Test infeasible_transport_capacity_pattern from repository.
        Expected: Agent should catch Layer 2 failure (arc capacity pattern makes it infeasible).

        This problem:
        - Total supply = total demand = 150 (balanced) ✓
        - All sinks reachable ✓
        - But arc capacity constraints make it infeasible ✗

        Only Layer 2 (solver-based) can catch this!
        """
        from tests.or_problem_repository import get_problem_by_name

        problem = get_problem_by_name("infeasible_transport_capacity_pattern")
        assert problem is not None
        assert problem['solvable'] == False

        # Use full agent workflow
        result = agent.solve_natural_language(problem['text'])

        # Should detect infeasibility
        assert 'error' in result or 'infeasible' in str(result).lower() or not result.get('success', True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
