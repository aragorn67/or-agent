"""Tests for the xlsx structured-input fast path (Phase 3 #2).

Covers the parser (workbook -> solver params, and its error contract)
and the POST /solve/file endpoint. The whole point of this lane is that
it skips BOTH qwen3 calls — the tests use a bare dummy LLM with no
methods, so any accidental LLM call would raise immediately.
"""

import io

import pytest
from fastapi.testclient import TestClient

from agent import spreadsheet_input as si
from agent.core import OptimizationAgent
from api import app


class _DummyLLM:
    """No methods — the fast path must never touch the LLM."""


@pytest.fixture
def agent():
    ag = OptimizationAgent(_DummyLLM())
    # Keep deterministic + offline: analysis detection is irrelevant here
    # and could otherwise reach the (dummy) LLM.
    ag.analysis_detector.detect_analysis_requests = (
        lambda *a, **k: {"wants_analysis": False}
    )
    return ag


# ---------------------------------------------------------------- parser

def test_transport_template_parses_to_expected_params():
    book = si.build_template("TRANSPORTATION")
    p = si.parse_workbook(io.BytesIO(book), "TRANSPORTATION")
    assert set(p) == {"plants", "markets", "capacity", "demand", "cost"}
    assert p["plants"] == ["P1", "P2"]
    assert p["markets"] == ["M1", "M2", "M3"]
    assert p["capacity"] == {"P1": 350.0, "P2": 600.0}
    assert p["demand"] == {"M1": 325.0, "M2": 300.0, "M3": 275.0}
    assert p["cost"]["P1"] == {"M1": 225.0, "M2": 153.0, "M3": 162.0}


def test_scheduling_template_parses_eligibility_from_blanks():
    book = si.build_template("SINGLE_STAGE_SCHEDULING")
    p = si.parse_workbook(io.BytesIO(book), "SCHEDULING")
    assert p["orders"] == ["O1", "O2", "O3"]
    assert p["units"] == ["U1", "U2"]
    # O2 has a blank U2 cell in the template -> not eligible on U2.
    assert p["eligible"]["O2"] == ["U1"]
    assert "U2" not in p["processing_time"]["O2"]
    assert p["due_date"] == {"O1": 10.0, "O2": 8.0, "O3": 12.0}


def test_optional_fixed_cost_sheet_flips_to_mip():
    import pandas as pd
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame({"plant": ["P1"], "capacity": [100]}).to_excel(
            xw, sheet_name="Supply", index=False)
        pd.DataFrame({"market": ["M1"], "demand": [80]}).to_excel(
            xw, sheet_name="Demand", index=False)
        pd.DataFrame({"plant": ["P1"], "M1": [5]}).to_excel(
            xw, sheet_name="Cost", index=False)
        pd.DataFrame({"plant": ["P1"], "M1": [999]}).to_excel(
            xw, sheet_name="FixedCost", index=False)
    buf.seek(0)
    p = si.parse_workbook(buf, "TRANSPORTATION")
    assert p["fixed_cost"] == {"P1": {"M1": 999.0}}


@pytest.mark.parametrize("pt", ["KNAPSACK", "", "tsp"])
def test_unsupported_domain_raises(pt):
    with pytest.raises(ValueError, match="Unsupported problem_type"):
        si.domain_of(pt)


def test_missing_required_sheet_raises():
    import pandas as pd
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame({"plant": ["P1"], "capacity": [100]}).to_excel(
            xw, sheet_name="Supply", index=False)
    buf.seek(0)
    with pytest.raises(ValueError, match="Missing required sheet 'Demand'"):
        si.parse_workbook(buf, "TRANSPORTATION")


def test_cost_index_mismatch_raises():
    import pandas as pd
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame({"plant": ["P1", "P2"], "capacity": [100, 100]}).to_excel(
            xw, sheet_name="Supply", index=False)
        pd.DataFrame({"market": ["M1"], "demand": [150]}).to_excel(
            xw, sheet_name="Demand", index=False)
        # Cost only has P1 — must not silently drop P2.
        pd.DataFrame({"plant": ["P1"], "M1": [5]}).to_excel(
            xw, sheet_name="Cost", index=False)
    buf.seek(0)
    with pytest.raises(ValueError, match="don't match Supply"):
        si.parse_workbook(buf, "TRANSPORTATION")


def test_non_numeric_cell_raises():
    import pandas as pd
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame({"plant": ["P1"], "capacity": ["lots"]}).to_excel(
            xw, sheet_name="Supply", index=False)
        pd.DataFrame({"market": ["M1"], "demand": [80]}).to_excel(
            xw, sheet_name="Demand", index=False)
        pd.DataFrame({"plant": ["P1"], "M1": [5]}).to_excel(
            xw, sheet_name="Cost", index=False)
    buf.seek(0)
    with pytest.raises(ValueError, match="not a number"):
        si.parse_workbook(buf, "TRANSPORTATION")


def test_corrupt_file_raises_valueerror_not_500():
    with pytest.raises(ValueError, match="Could not read the workbook"):
        si.parse_workbook(io.BytesIO(b"definitely not xlsx"), "TRANSPORTATION")


# -------------------------------------------------- solve (no LLM at all)

def test_fast_path_solves_transport_without_llm(agent):
    book = si.build_template("TRANSPORTATION")
    params = si.parse_workbook(io.BytesIO(book), "TRANSPORTATION")
    ptype, sid = si.resolved_ids("TRANSPORTATION")
    r = agent.solve_with_params(
        params=params, problem_type=ptype, solver_id=sid,
        description="structured input", mode="exact", explain=False,
    )
    assert r["success"] is True
    assert r["solution"]["status"] == "OPTIMAL"
    assert r["solution"]["objective_value"] == pytest.approx(153675.0)
    assert r["grounding_check"] == "skipped_structured_input"
    assert r["summary"]  # deterministic, non-empty


def test_fast_path_solves_scheduling_without_llm(agent):
    book = si.build_template("SINGLE_STAGE_SCHEDULING")
    params = si.parse_workbook(io.BytesIO(book), "SCHEDULING")
    ptype, sid = si.resolved_ids("SCHEDULING")
    r = agent.solve_with_params(
        params=params, problem_type=ptype, solver_id=sid,
        description="structured input", mode="exact", explain=False,
    )
    assert r["success"] is True
    assert r["solution"]["status"] == "OPTIMAL"


# ------------------------------------------------------------- endpoint

@pytest.fixture
def client():
    return TestClient(app)


def test_template_endpoint_returns_xlsx(client):
    r = client.get("/solve/file/template",
                    params={"problem_type": "TRANSPORTATION"})
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    assert r.content[:2] == b"PK"  # valid zip/xlsx magic


def test_endpoint_solves_uploaded_workbook(client):
    book = client.get("/solve/file/template",
                      params={"problem_type": "TRANSPORTATION"}).content
    r = client.post(
        "/solve/file",
        data={"problem_type": "TRANSPORTATION", "mode": "exact",
              "explain": "false"},
        files={"file": ("in.xlsx", book,
                         "application/vnd.openxmlformats-officedocument."
                         "spreadsheetml.sheet")},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["success"] is True
    assert j["solution"]["objective_value"] == pytest.approx(153675.0)
    assert j["input"] == "spreadsheet"
    assert j["skipped_stages"] == ["classify", "extract", "explain"]
    assert "next_options" in j  # continuation chips still attached


def test_endpoint_malformed_upload_is_422_not_500(client):
    r = client.post(
        "/solve/file",
        data={"problem_type": "TRANSPORTATION"},
        files={"file": ("x.xlsx", b"not an xlsx",
                         "application/octet-stream")},
    )
    assert r.status_code == 422
    assert "Could not read the workbook" in r.json()["detail"]


def test_endpoint_empty_upload_is_422(client):
    r = client.post(
        "/solve/file",
        data={"problem_type": "TRANSPORTATION"},
        files={"file": ("x.xlsx", b"", "application/octet-stream")},
    )
    assert r.status_code == 422


def test_endpoint_unsupported_domain_is_422(client):
    r = client.get("/solve/file/template",
                    params={"problem_type": "KNAPSACK"})
    assert r.status_code == 422
