"""Structured-spreadsheet input for the xlsx fast path (#2).

Parses a purpose-built ``.xlsx`` workbook straight into the params dict
the solvers + 3-layer feasibility gate expect — bypassing both qwen3
calls (classify + extract). This is the "instant demo lane".

The workbook is a *purpose-built input contract*, deliberately NOT the
shape produced by ``POST /export/xlsx`` (whose ``Parameters`` sheet is
``str(v)``-lossy and whose ``Flows`` sheet is output, not input).

Transport workbook
    Supply      : columns [plant, capacity]
    Demand      : columns [market, demand]
    Cost        : matrix — first column = plant, header row = markets,
                  cells = unit cost (plant -> market)
    FixedCost   : (optional) same matrix shape — per-route fixed charge
    ArcCapacity : (optional) same matrix shape — per-route max flow

Scheduling workbook
    Processing  : matrix — first column = order, header row = units,
                  cells = processing time. A blank cell means the order
                  is NOT eligible on that unit.
    DueDate     : columns [order, due_date]

Every parser error is a ``ValueError`` with an actionable message; the
endpoint maps it to a 4xx so a malformed upload never 500s.
"""

from __future__ import annotations

import io
from typing import Any, Dict, Tuple, Union

import pandas as pd

# Accept the classifier's aliases so the form field is forgiving.
_TRANSPORT = {"TRANSPORTATION", "TRANSPORT"}
_SCHEDULING = {
    "SCHEDULING",
    "SINGLE_STAGE_SCHEDULING",
    "PARALLEL_MACHINE_SCHEDULING",
    "SINGLE_MACHINE_MAKESPAN",
}

# (problem_type, solver_id) the fast path resolves to per domain. Mirrors
# the classifier's fallback mapping so downstream dispatch is identical.
_RESOLVED = {
    "transport": ("TRANSPORTATION", "transport_basic_bipartite"),
    "scheduling": ("SINGLE_STAGE_SCHEDULING", "single_stage_ipm_scheduling"),
}

WorkbookSource = Union[str, bytes, io.BytesIO]


def domain_of(problem_type: str) -> str:
    """Map a (possibly aliased) problem_type string to 'transport' or
    'scheduling'. Raises ValueError on anything unsupported."""
    pt = (problem_type or "").strip().upper()
    if pt in _TRANSPORT:
        return "transport"
    if pt in _SCHEDULING:
        return "scheduling"
    raise ValueError(
        f"Unsupported problem_type {problem_type!r}. The spreadsheet fast "
        f"path supports transportation and single-stage scheduling."
    )


def resolved_ids(problem_type: str) -> Tuple[str, str]:
    """Return the canonical (problem_type, solver_id) for the domain."""
    return _RESOLVED[domain_of(problem_type)]


def _read_book(src: WorkbookSource) -> Dict[str, pd.DataFrame]:
    """Read every sheet. Sheet names are matched case-insensitively."""
    try:
        book = pd.read_excel(src, sheet_name=None, engine="openpyxl")
    except Exception as exc:  # noqa: BLE001 — corrupt/locked/not-xlsx
        raise ValueError(
            f"Could not read the workbook as .xlsx: {exc}. Ensure it is a "
            f"valid Excel file (not .csv / not password-protected)."
        ) from exc
    return {str(name).strip().lower(): df for name, df in book.items()}


def _need(sheets: Dict[str, pd.DataFrame], name: str) -> pd.DataFrame:
    df = sheets.get(name.lower())
    if df is None:
        raise ValueError(
            f"Missing required sheet '{name}'. Workbook has: "
            f"{sorted(s for s in sheets)}."
        )
    if df.empty:
        raise ValueError(f"Sheet '{name}' is empty.")
    return df


def _two_col_map(df: pd.DataFrame, sheet: str) -> Dict[str, float]:
    """A [key, value] sheet -> {str(key): float(value)}."""
    if df.shape[1] < 2:
        raise ValueError(
            f"Sheet '{sheet}' needs two columns (name, value); "
            f"found {df.shape[1]}."
        )
    out: Dict[str, float] = {}
    for _, row in df.iloc[:, :2].iterrows():
        key = row.iloc[0]
        val = row.iloc[1]
        if pd.isna(key):
            continue
        if pd.isna(val):
            raise ValueError(
                f"Sheet '{sheet}': missing value for '{key}'."
            )
        try:
            out[str(key).strip()] = float(val)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Sheet '{sheet}': value for '{key}' is not a number "
                f"({val!r})."
            ) from exc
    if not out:
        raise ValueError(f"Sheet '{sheet}' has no usable rows.")
    return out


def _matrix(df: pd.DataFrame, sheet: str, *, allow_blanks: bool):
    """A matrix sheet (first col = row label, header = col labels) ->
    (nested {row: {col: float}}, row_labels, col_labels).

    With allow_blanks, NaN cells are simply omitted (used by Processing
    to express eligibility). Without, a NaN is an error.
    """
    if df.shape[1] < 2:
        raise ValueError(
            f"Sheet '{sheet}' must have a label column plus at least one "
            f"data column."
        )
    df = df.set_index(df.columns[0])
    rows = [str(r).strip() for r in df.index if not pd.isna(r)]
    cols = [str(c).strip() for c in df.columns]
    nested: Dict[str, Dict[str, float]] = {}
    for r in df.index:
        if pd.isna(r):
            continue
        rk = str(r).strip()
        nested[rk] = {}
        for c in df.columns:
            val = df.at[r, c]
            ck = str(c).strip()
            if pd.isna(val):
                if allow_blanks:
                    continue
                raise ValueError(
                    f"Sheet '{sheet}': blank cell at row '{rk}', "
                    f"column '{ck}'. Every cell must be a number."
                )
            try:
                nested[rk][ck] = float(val)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Sheet '{sheet}': cell at row '{rk}', column "
                    f"'{ck}' is not a number ({val!r})."
                ) from exc
    return nested, rows, cols


def _parse_transport(sheets: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    capacity = _two_col_map(_need(sheets, "Supply"), "Supply")
    demand = _two_col_map(_need(sheets, "Demand"), "Demand")
    cost, plants, markets = _matrix(
        _need(sheets, "Cost"), "Cost", allow_blanks=False
    )

    # Supply/Demand are authoritative for the index sets; Cost must cover
    # exactly them so a typo can't silently drop a route.
    if set(plants) != set(capacity):
        raise ValueError(
            f"Cost sheet plants {sorted(plants)} don't match Supply "
            f"{sorted(capacity)}."
        )
    if set(markets) != set(demand):
        raise ValueError(
            f"Cost sheet markets {sorted(markets)} don't match Demand "
            f"{sorted(demand)}."
        )

    params: Dict[str, Any] = {
        "plants": list(capacity.keys()),
        "markets": list(demand.keys()),
        "capacity": capacity,
        "demand": demand,
        "cost": cost,
    }

    # Optional sheets — presence flips the model (fixed_cost -> MIP).
    if "fixedcost" in sheets:
        fc, _, _ = _matrix(sheets["fixedcost"], "FixedCost",
                            allow_blanks=False)
        params["fixed_cost"] = fc
    if "arccapacity" in sheets:
        ac, _, _ = _matrix(sheets["arccapacity"], "ArcCapacity",
                            allow_blanks=False)
        params["arc_capacity"] = ac
    return params


def _parse_scheduling(sheets: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    pt, orders, units = _matrix(
        _need(sheets, "Processing"), "Processing", allow_blanks=True
    )
    eligible = {o: list(pt[o].keys()) for o in orders}
    for o, elig in eligible.items():
        if not elig:
            raise ValueError(
                f"Order '{o}' has no eligible unit (all Processing cells "
                f"blank). Give it at least one processing time."
            )
    due = _two_col_map(_need(sheets, "DueDate"), "DueDate")
    if set(due) != set(orders):
        raise ValueError(
            f"DueDate orders {sorted(due)} don't match Processing "
            f"{sorted(orders)}."
        )
    return {
        "orders": orders,
        "units": units,
        "eligible": eligible,
        "processing_time": pt,
        "due_date": due,
    }


def parse_workbook(src: WorkbookSource, problem_type: str) -> Dict[str, Any]:
    """Parse an input workbook into solver params for ``problem_type``.

    Returns exactly the dict the NL extractor would have produced, so
    ``validate_params`` + ``check_feasibility`` + the solver run
    unchanged. Raises ``ValueError`` (never 500s) on any malformed input.
    """
    domain = domain_of(problem_type)
    sheets = _read_book(src)
    if domain == "transport":
        return _parse_transport(sheets)
    return _parse_scheduling(sheets)


def build_template(problem_type: str) -> bytes:
    """Return a blank-but-shaped example workbook for the domain, so a
    user can see the exact expected layout. Bytes, ready to stream."""
    domain = domain_of(problem_type)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        if domain == "transport":
            pd.DataFrame({"plant": ["P1", "P2"],
                          "capacity": [350, 600]}).to_excel(
                xw, sheet_name="Supply", index=False)
            pd.DataFrame({"market": ["M1", "M2", "M3"],
                          "demand": [325, 300, 275]}).to_excel(
                xw, sheet_name="Demand", index=False)
            pd.DataFrame(
                {"plant": ["P1", "P2"],
                 "M1": [225, 225], "M2": [153, 162], "M3": [162, 126]}
            ).to_excel(xw, sheet_name="Cost", index=False)
        else:
            pd.DataFrame(
                {"order": ["O1", "O2", "O3"],
                 "U1": [2.0, 1.5, 3.0], "U2": [3.0, None, 2.5]}
            ).to_excel(xw, sheet_name="Processing", index=False)
            pd.DataFrame({"order": ["O1", "O2", "O3"],
                          "due_date": [10, 8, 12]}).to_excel(
                xw, sheet_name="DueDate", index=False)
    buf.seek(0)
    return buf.getvalue()
