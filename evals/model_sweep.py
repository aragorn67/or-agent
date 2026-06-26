"""Model-comparison sweep over the round-trip eval.

Runs ``evals.run_eval`` as an isolated subprocess for each
(config, domain), varying the LLM backend + per-stage models via env,
then tabulates the headline accuracy metrics + per-stage latency and
(optionally) appends a dated section to ANALYSIS.md.

Why subprocess-per-config: ``config.py`` reads ``*_MODEL`` env vars at
import time, and a fresh process also resets Ollama's resident-model
state between configs — so each config is measured cleanly, no bleed.

Usage:
    python -m evals.model_sweep --dry-run
    python -m evals.model_sweep --configs qwen2.5-7b --domains transport \
        --seeds 1 --no-analysis
    python -m evals.model_sweep --seeds 1,2,3            # fast pass
    python -m evals.model_sweep --seeds 1,2,3,4,5,6,7,8,9,10   # solid

Tiered workflow: run a small --seeds pass, prune weak configs with
--configs, re-run survivors at a larger --seeds.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent
_ANALYSIS = _ROOT / "ANALYSIS.md"

# A config is just {per-stage Ollama model names}. Add a row to compare
# another model — no code change needed. Models must be `ollama pull`-ed already.
CONFIGS: List[Dict] = [
    {"name": "baseline",
     "models": ("qwen3:14b", "qwen3:14b", "qwen3:14b")},
    {"name": "qwen3-8b",
     "models": ("qwen3:8b", "qwen3:8b", "qwen3:8b")},
    {"name": "qwen2.5-7b",
     "models": ("qwen2.5:7b-instruct",) * 3},
    # "small classifier, strong instruct extractor" hypothesis.
    {"name": "qwen2.5-extract",
     "models": ("qwen3:8b", "qwen2.5:7b-instruct", "qwen3:8b")},
    {"name": "mistral-7b",
     "models": ("mistral:7b-instruct",) * 3},
]

# config.py env var names per pipeline stage.
_STAGE_ENV = ("CLASSIFICATION_MODEL", "EXTRACTION_MODEL", "REASONING_MODEL")


def _runnable(cfg: Dict) -> Optional[str]:
    """Return a skip-reason string, or None if the config can run."""
    return None


def _run_one(cfg: Dict, domain: str, seeds: str, gap: float,
             timeout: int, raw_dir: Path) -> Dict:
    """Run one (config, domain) as a subprocess; return a result row."""
    env = os.environ.copy()
    if cfg["models"]:
        for var, model in zip(_STAGE_ENV, cfg["models"]):
            env[var] = model

    out_json = raw_dir / f"{cfg['name']}__{domain}.json"
    cmd = [
        sys.executable, "-m", "evals.run_eval",
        "--domain", domain,
        "--seeds", seeds, "--gap-threshold", str(gap),
        "--output", str(out_json),
    ]
    row = {"config": cfg["name"], "domain": domain}
    try:
        proc = subprocess.run(
            cmd, cwd=_ROOT, env=env, timeout=timeout,
            capture_output=True, text=True,
        )
    except subprocess.TimeoutExpired:
        row["error"] = f"timeout >{timeout}s"
        return row
    if proc.returncode != 0 or not out_json.exists():
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        row["error"] = f"rc={proc.returncode}: {' | '.join(tail)[:300]}"
        return row

    report = json.loads(out_json.read_text())
    m = report.get("metrics", {})
    recall = m.get("param_recall") or {}
    gapst = m.get("objective_gap") or {}
    lat = m.get("stage_latency") or {}
    row.update({
        "n": m.get("n"),
        "class_acc": m.get("classification_accuracy"),
        "recall": recall.get("mean_overall"),
        "pass_rate": m.get("end_to_end_pass_rate"),
        "gap_median": gapst.get("median"),
        # 'agent' = full pipeline (the 3 LLM calls + solve) — the headline.
        "agent_ms": (lat.get("agent") or {}).get("median_ms"),
        "wall_s": report.get("wall_seconds"),
        "failures": m.get("failure_histogram") or {},
    })
    return row


def _fmt(v, nd=3):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def _table(rows: List[Dict]) -> str:
    head = ("| config | domain | n | class_acc | recall | pass | "
            "gap_med | agent_ms | wall_s | notes |")
    sep = "|" + "---|" * 10
    lines = [head, sep]
    for r in rows:
        if "error" in r:
            lines.append(
                f"| {r['config']} | {r['domain']} | — | — | — | — | — | — | "
                f"— | ⚠️ {r['error']} |"
            )
            continue
        fail = ", ".join(f"{k}:{v}" for k, v in (r.get("failures") or {}).items())
        lines.append(
            f"| {r['config']} | {r['domain']} | {_fmt(r['n'],0)} | "
            f"{_fmt(r['class_acc'])} | {_fmt(r['recall'])} | "
            f"{_fmt(r['pass_rate'])} | {_fmt(r['gap_median'])} | "
            f"{_fmt(r['agent_ms'],0)} | {_fmt(r['wall_s'],0)} | {fail or 'ok'} |"
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    names = [c["name"] for c in CONFIGS]
    p = argparse.ArgumentParser(description="Model-comparison sweep")
    p.add_argument("--configs", default="",
                   help=f"comma list (default all): {','.join(names)}")
    p.add_argument("--domains", default="transport,scheduling")
    p.add_argument("--seeds", default="1,2,3",
                   help="comma seeds, shared by every config for fairness")
    p.add_argument("--gap-threshold", type=float, default=0.01)
    p.add_argument("--timeout", type=int, default=2400,
                   help="per (config,domain) subprocess timeout (s)")
    p.add_argument("--no-analysis", action="store_true",
                   help="don't append the table to ANALYSIS.md")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    want = set(s.strip() for s in args.configs.split(",") if s.strip())
    chosen = [c for c in CONFIGS if not want or c["name"] in want]
    domains = [d.strip() for d in args.domains.split(",") if d.strip()]

    print("Model sweep plan:", flush=True)
    plan = []
    for c in chosen:
        skip = _runnable(c)
        mdl = "/".join(c["models"]) if c["models"] else f"{c['backend']} default"
        for d in domains:
            tag = f"  {c['name']:16} {d:10} [{mdl}]"
            if skip:
                tag += f"  -- SKIP ({skip})"
            print(tag, flush=True)
            if not skip:
                plan.append((c, d))
    print(f"\n{len(plan)} runs × seeds={args.seeds}", flush=True)
    if args.dry_run:
        return 0
    if not plan:
        print("Nothing runnable.", flush=True)
        return 1

    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_dir = Path(tempfile.mkdtemp(prefix=f"sweep_{ts}_"))
    rows: List[Dict] = []
    for i, (cfg, domain) in enumerate(plan, 1):
        print(f"\n[{i}/{len(plan)}] {cfg['name']} / {domain} …", flush=True)
        row = _run_one(cfg, domain, args.seeds, args.gap_threshold,
                       args.timeout, raw_dir)
        rows.append(row)
        print("   " + (row.get("error") or
              f"acc={_fmt(row.get('class_acc'))} recall={_fmt(row.get('recall'))} "
              f"pass={_fmt(row.get('pass_rate'))} agent_ms={_fmt(row.get('agent_ms'),0)}"),
              flush=True)

    table = _table(rows)
    print("\n" + table, flush=True)
    print(f"\nRaw reports: {raw_dir}", flush=True)

    if not args.no_analysis:
        block = (
            f"\n## Model sweep — {ts} (seeds={args.seeds}, "
            f"gap_threshold={args.gap_threshold})\n\n{table}\n\n"
            f"Raw JSON: `{raw_dir}`\n"
        )
        with _ANALYSIS.open("a") as fh:
            fh.write(block)
        print(f"Appended to {_ANALYSIS}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
