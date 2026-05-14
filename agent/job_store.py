"""
In-memory job store for the two-call solve protocol.

When /solve runs in heuristic mode it returns a job_id; the client then calls
/continue with that job_id and an action (optimize / accept / use_heuristic).
Between the two calls we need to hold onto the extracted params + heuristic
solution so the second call can warm-start the exact solver.

Phase 1 design constraints (from brainstorm_ideas.md LOCKED PLAN):
- In-memory dict, UUID-keyed, 10-minute TTL.
- Single-process. A restart drops in-flight jobs; that is acceptable.
- No Redis, no persistence, no multi-process safety.

If we ever multi-process, swap this module for one backed by Redis without
touching callers — the JobStore interface is intentionally minimal.
"""

from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4
import time


@dataclass
class JobRecord:
    job_id: str
    created_at: float
    problem_type: str
    solver_id: str
    params: Dict[str, Any]
    heuristic_flows: Dict[Tuple[str, str], float]
    heuristic_cost: float
    lp_bound: Optional[float]
    description: str
    classification: Dict[str, Any] = field(default_factory=dict)


class JobStore:
    """Threadsafe in-memory job store with TTL eviction on read/write."""

    def __init__(self, ttl_seconds: float = 600.0):
        self._ttl = ttl_seconds
        self._jobs: Dict[str, JobRecord] = {}
        self._lock = RLock()

    def create(
        self,
        problem_type: str,
        solver_id: str,
        params: Dict[str, Any],
        heuristic_flows: Dict[Tuple[str, str], float],
        heuristic_cost: float,
        lp_bound: Optional[float],
        description: str,
        classification: Optional[Dict[str, Any]] = None,
    ) -> JobRecord:
        with self._lock:
            self._evict_expired()
            job_id = uuid4().hex
            record = JobRecord(
                job_id=job_id,
                created_at=time.time(),
                problem_type=problem_type,
                solver_id=solver_id,
                params=params,
                heuristic_flows=heuristic_flows,
                heuristic_cost=heuristic_cost,
                lp_bound=lp_bound,
                description=description,
                classification=classification or {},
            )
            self._jobs[job_id] = record
            return record

    def get(self, job_id: str) -> Optional[JobRecord]:
        with self._lock:
            self._evict_expired()
            return self._jobs.get(job_id)

    def drop(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [jid for jid, rec in self._jobs.items()
                   if now - rec.created_at > self._ttl]
        for jid in expired:
            self._jobs.pop(jid, None)


# Module-level default store. The API layer imports this; tests can build their
# own JobStore for isolation.
default_store = JobStore(ttl_seconds=600.0)
