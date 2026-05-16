"""
Phase 1 — live-progress job model.

Unit tests for ProgressStore plus an end-to-end test of the async
POST /jobs + GET /jobs/{run_id} flow with the solve stubbed (the real
solve makes ~2-3 min of LLM calls; here we only verify the plumbing:
stages stream through, the final payload is delivered, the heuristic
continuation job_id survives the async round-trip).
"""

import time

import pytest

from agent.progress_store import ProgressStore


def test_progress_store_lifecycle():
    store = ProgressStore()
    run = store.create()
    assert run.state == "running"

    store.add_stage(run.run_id, "Detecting intent...", 5)
    store.add_stage(run.run_id, "Extracting parameters...", 40)
    got = store.get(run.run_id)
    assert [s["step"] for s in got.stages] == [
        "Detecting intent...", "Extracting parameters..."
    ]

    store.finish(run.run_id, {"success": True, "solution": {"objective": 1660}})
    assert store.get(run.run_id).state == "done"
    # Stages are frozen once finished.
    store.add_stage(run.run_id, "late", 99)
    assert len(store.get(run.run_id).stages) == 2


def test_progress_store_error_paths():
    store = ProgressStore()
    run = store.create()
    store.finish(run.run_id, {"success": False, "error": "infeasible"})
    rec = store.get(run.run_id)
    assert rec.state == "error" and rec.error == "infeasible"

    run2 = store.create()
    store.fail(run2.run_id, "RuntimeError: boom")
    assert store.get(run2.run_id).state == "error"

    assert store.get("does-not-exist") is None


def test_progress_store_ttl_eviction():
    store = ProgressStore(ttl_seconds=0.0)  # instantly stale
    run = store.create()
    time.sleep(0.01)
    assert store.get(run.run_id) is None


def test_async_jobs_endpoint_streams_stages_and_result(monkeypatch):
    import api

    def fake_solve(description, progress_callback=None, mode="exact"):
        progress_callback("Detecting intent...", 5)
        progress_callback("Identified as TRANSPORTATION problem", 25)
        progress_callback("Running heuristic...", 70)
        return {
            "success": True,
            "problem_type": "TRANSPORTATION",
            "job_id": "heuristic-continuation-123",
            "solution": {"objective_value": 1660, "best_bound": 1660, "gap": 0.0},
        }

    monkeypatch.setattr(api.agent, "solve_natural_language", fake_solve)

    from fastapi.testclient import TestClient
    client = TestClient(api.app)

    run_id = client.post(
        "/jobs", json={"description": "ship widgets", "mode": "heuristic_then_ask"}
    ).json()["run_id"]
    assert run_id

    deadline = time.time() + 5
    body = None
    while time.time() < deadline:
        body = client.get(f"/jobs/{run_id}").json()
        if body["state"] in ("done", "error"):
            break
        time.sleep(0.05)

    assert body["state"] == "done"
    assert [s["step"] for s in body["stages"]][0] == "Detecting intent..."
    # The heuristic continuation job_id must survive the async round-trip.
    assert body["result"]["job_id"] == "heuristic-continuation-123"
    assert body["result"]["solution"]["gap"] == 0.0


def test_unknown_run_id():
    import api
    from fastapi.testclient import TestClient
    client = TestClient(api.app)
    body = client.get("/jobs/nope").json()
    assert body["success"] is False
