"""
In-memory registry for in-flight solve *runs* (Phase 1: live progress).

A blocking /solve hides ~2-3 min of local-LLM work behind one spinner. The
agent already emits stages via its `update_progress(step, percent)` callback;
this store lets an async run capture those stages so the UI can poll them.

Separate from `job_store.py`: that one holds the heuristic *continuation*
state (optimize/accept after a heuristic answer). This one tracks the
progress + final result of a single solve_natural_language call.

Same Phase-1 constraints: in-memory dict, UUID-keyed, short TTL,
single-process, lock-guarded. Swap for Redis later without touching callers.
"""

from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, List, Optional
from uuid import uuid4
import time


@dataclass
class RunJob:
    run_id: str
    created_at: float
    state: str = "running"                       # running | done | error
    stages: List[Dict[str, Any]] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None      # solve payload when done
    error: Optional[str] = None


class ProgressStore:
    def __init__(self, ttl_seconds: float = 900.0):
        self._ttl = ttl_seconds
        self._runs: Dict[str, RunJob] = {}
        self._lock = RLock()

    def create(self) -> RunJob:
        with self._lock:
            self._evict_expired()
            run_id = uuid4().hex
            run = RunJob(run_id=run_id, created_at=time.time())
            self._runs[run_id] = run
            return run

    def add_stage(self, run_id: str, step: str, percent: int) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.state != "running":
                return
            run.stages.append(
                {"step": step, "percent": percent, "ts": time.time()}
            )

    def finish(self, run_id: str, result: Dict[str, Any]) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return
            run.result = result
            run.state = "error" if result.get("success") is False else "done"
            if run.state == "error":
                run.error = result.get("error") or result.get("message")

    def fail(self, run_id: str, error: str) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                return
            run.state = "error"
            run.error = error

    def get(self, run_id: str) -> Optional[RunJob]:
        with self._lock:
            self._evict_expired()
            return self._runs.get(run_id)

    def _evict_expired(self) -> None:
        now = time.time()
        for rid in [r for r, run in self._runs.items()
                    if now - run.created_at > self._ttl]:
            self._runs.pop(rid, None)
