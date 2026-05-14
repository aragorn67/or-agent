"""Compare generated (ground-truth) params against agent-recovered params.

Two primary helpers:
- param_recall: how many of the original entities/values came back, per key + overall.
- objective_gap: relative difference between true and recovered objective.

Both helpers are tolerant about cost being given as nested-dict or flat-tuple form,
because the agent extractor may produce either.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple


_REL_TOL = 0.02   # 2% — costs are LLM-rephrased, small rounding is expected
_ABS_TOL = 0.5    # capacities/demands are integers; 0.5 absorbs rounding drift


def _num_close(a: float, b: float) -> bool:
    if a is None or b is None:
        return False
    diff = abs(a - b)
    return diff <= _ABS_TOL or diff <= _REL_TOL * max(abs(a), abs(b), 1.0)


def _flat_cost(cost: Any) -> Dict[Tuple[str, str], float]:
    """Normalize cost to {(plant, market): float}; accept nested or flat-tuple input."""
    if not isinstance(cost, dict) or not cost:
        return {}
    first_key = next(iter(cost))
    if isinstance(first_key, tuple) and len(first_key) == 2:
        return {(str(i), str(j)): float(v) for (i, j), v in cost.items()}
    flat: Dict[Tuple[str, str], float] = {}
    for i, inner in cost.items():
        if isinstance(inner, dict):
            for j, v in inner.items():
                flat[(str(i), str(j))] = float(v)
    return flat


def _set_recall(generated: list, recovered: list) -> float:
    g = {str(x) for x in (generated or [])}
    r = {str(x) for x in (recovered or [])}
    if not g:
        return 1.0
    return len(g & r) / len(g)


def _dict_recall(generated: Dict[str, float], recovered: Dict[str, float]) -> float:
    if not generated:
        return 1.0
    if not recovered:
        return 0.0
    matched = 0
    for k, v in generated.items():
        rv = recovered.get(k) if k in recovered else recovered.get(str(k))
        try:
            if rv is not None and _num_close(float(v), float(rv)):
                matched += 1
        except (TypeError, ValueError):
            continue
    return matched / len(generated)


def _cost_recall(generated: Any, recovered: Any) -> float:
    g = _flat_cost(generated)
    r = _flat_cost(recovered)
    if not g:
        return 1.0
    if not r:
        return 0.0
    matched = sum(1 for k, v in g.items() if k in r and _num_close(v, r[k]))
    return matched / len(g)


_TRANSPORT_KEYS = ("plants", "markets", "capacity", "demand", "cost")
_SCHEDULING_KEYS = ("orders", "units", "processing_time", "due_date")


def _flat_processing_time(pt: Any) -> Dict[Tuple[str, str], float]:
    """Normalize processing_time to {(order, unit): float}; nested or flat-tuple."""
    return _flat_cost(pt)


def _processing_time_recall(generated: Any, recovered: Any) -> float:
    g = _flat_processing_time(generated)
    r = _flat_processing_time(recovered)
    if not g:
        return 1.0
    if not r:
        return 0.0
    matched = sum(1 for k, v in g.items() if k in r and _num_close(v, r[k]))
    return matched / len(g)


def param_recall(
    generated: Dict[str, Any],
    recovered: Dict[str, Any],
    domain: str = "transport",
) -> Dict[str, Any]:
    """Per-key recall + macro-average overall score.

    Returns:
        {"overall": 0..1, "by_key": {<domain-specific keys>: ...}}
    """
    if not isinstance(recovered, dict):
        recovered = {}

    if domain == "scheduling":
        per_key = {
            "orders":          _set_recall(generated.get("orders", []),  recovered.get("orders", [])),
            "units":           _set_recall(generated.get("units", []),   recovered.get("units", [])),
            "processing_time": _processing_time_recall(generated.get("processing_time", {}), recovered.get("processing_time", {})),
            "due_date":        _dict_recall(generated.get("due_date", {}), recovered.get("due_date", {})),
        }
    else:
        per_key = {
            "plants":   _set_recall(generated.get("plants", []),  recovered.get("plants", [])),
            "markets":  _set_recall(generated.get("markets", []), recovered.get("markets", [])),
            "capacity": _dict_recall(generated.get("capacity", {}), recovered.get("capacity", {})),
            "demand":   _dict_recall(generated.get("demand", {}),   recovered.get("demand", {})),
            "cost":     _cost_recall(generated.get("cost", {}),     recovered.get("cost", {})),
        }
    overall = sum(per_key.values()) / len(per_key)
    return {"overall": overall, "by_key": per_key}


def objective_gap(true_obj: float, recovered_obj: float) -> float:
    """Relative absolute gap; returns inf if recovered_obj is missing."""
    if recovered_obj is None:
        return float("inf")
    try:
        true_f = float(true_obj)
        rec_f = float(recovered_obj)
    except (TypeError, ValueError):
        return float("inf")
    return abs(true_f - rec_f) / max(abs(true_f), 1e-9)
