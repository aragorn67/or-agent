"""
Typed instance schemas for feasibility checking.

Provides structured dataclasses for different problem types to enable
type-safe validation and better IDE support.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ParsedInstance:
    """
    Base class for all problem instances.

    This is the generic representation that works with dict-based instances
    from the current system. Problem-specific subclasses add typed fields.
    """
    problem_type: str
    solver_id: str
    sets: dict[str, list]
    params: dict[str, Any]
    bounds: Optional[dict[str, tuple]] = None
    metadata: Optional[dict] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'ParsedInstance':
        """Create ParsedInstance from dict representation."""
        return cls(
            problem_type=data.get('problem_type', ''),
            solver_id=data.get('solver_id', ''),
            sets=data.get('sets', {}),
            params=data.get('params', {}),
            bounds=data.get('bounds'),
            metadata=data.get('metadata')
        )


@dataclass
class TransportInstance(ParsedInstance):
    """
    Typed instance for transportation problems.

    Provides type-safe access to transportation-specific fields.
    """
    sources: Optional[list[str]] = None
    sinks: Optional[list[str]] = None
    supply: Optional[dict[str, float]] = None
    demand: Optional[dict[str, float]] = None
    cost: Optional[dict[tuple, float]] = None
    capacity: Optional[dict[tuple, float]] = None

    @classmethod
    def from_parsed_instance(cls, instance: ParsedInstance) -> 'TransportInstance':
        """
        Convert generic ParsedInstance to TransportInstance.

        Extracts transportation-specific fields from sets/params dicts.
        """
        # Extract sources and sinks from sets
        sources = instance.sets.get('I', instance.sets.get('I_sources',
                 instance.sets.get('I_plants', instance.sets.get('I_factories', []))))
        sinks = instance.sets.get('J', instance.sets.get('J_sinks',
                instance.sets.get('J_markets', instance.sets.get('J_warehouses', []))))

        # Extract params
        supply = instance.params.get('supply', instance.params.get('capacity', {}))
        demand = instance.params.get('demand', {})
        cost = instance.params.get('cost', {})
        capacity = instance.params.get('arc_capacity', instance.params.get('capacity', None))

        return cls(
            problem_type=instance.problem_type,
            solver_id=instance.solver_id,
            sets=instance.sets,
            params=instance.params,
            bounds=instance.bounds,
            metadata=instance.metadata,
            sources=sources,
            sinks=sinks,
            supply=supply,
            demand=demand,
            cost=cost,
            capacity=capacity
        )


@dataclass
class SchedulingInstance(ParsedInstance):
    """
    Typed instance for scheduling problems.

    TODO: Expand in Phase 3 when adding scheduling feasibility checks.
    """
    jobs: Optional[list[str]] = None
    machines: Optional[list[str]] = None
    processing_time: Optional[dict] = None
    due_date: Optional[dict] = None
    release_date: Optional[dict] = None


def normalize_instance(instance: Any) -> ParsedInstance:
    """
    Normalize various instance formats to ParsedInstance.

    Handles:
    - dict representations
    - ParsedInstance objects
    - Problem-specific instances (TransportInstance, etc.)

    Args:
        instance: Problem instance in any supported format

    Returns:
        ParsedInstance object
    """
    if isinstance(instance, ParsedInstance):
        return instance
    elif isinstance(instance, dict):
        return ParsedInstance.from_dict(instance)
    else:
        raise TypeError(f"Unsupported instance type: {type(instance)}")
