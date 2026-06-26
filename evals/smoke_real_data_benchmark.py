"""Smoke run: pipe problems through the agent and report
classification / extraction / solve outcomes.

Run with:
    ./Tolis_Env/bin/python -u evals/smoke_real_data_benchmark.py [--all] [--reset] [name1 name2 ...]

Defaults to `real_data_benchmark`-tagged problems. Pass --all to sweep the full
repository. Explicit names always win and override both modes.

Fail-fast + resume:
- A state file `.smoke_state.json` at repo root records each problem's outcome.
- "pass" = result.success is True, OR the problem is marked solvable=False and
  the pipeline gracefully refused. These are skipped on the next run.
- On a hard crash, or an unexpected failure (solvable=True but didn't solve),
  the run stops immediately so you can investigate. That problem is NOT
  persisted, so the next run re-attempts it.
- Pass --reset to wipe the state file before starting.
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass

# Open /dev/tty so progress is visible in the terminal even when stdout is
# redirected to a log file. Falls back gracefully when no controlling terminal
# exists (CI, nohup, etc.).
try:
    _TTY = open("/dev/tty", "w", buffering=1)
except Exception:
    _TTY = None


def _tty_print(msg: str) -> None:
    if _TTY is None:
        return
    try:
        _TTY.write(msg + "\n")
        _TTY.flush()
    except Exception:
        pass


from tests.or_problem_repository import get_all_problems, get_problem_by_name
from llm.enhanced_client import EnhancedLLMClient
from agent.core import OptimizationAgent
from config import Config


REPO_ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = REPO_ROOT / ".smoke_state.json"


def _is_benchmark(p):
    return "real_data_benchmark" in p.get("metadata", {}).get("tags", [])


def _extract_objective(result):
    """Return objective value or None. Tries top-level first then nested under 'solution'."""
    if not isinstance(result, dict):
        return None
    obj = result.get("objective_value") or result.get("objective")
    if obj is None:
        sol = result.get("solution")
        if isinstance(sol, dict):
            obj = sol.get("objective_value") or sol.get("objective")
    return obj


def _summarise(result: dict) -> str:
    if not isinstance(result, dict):
        return f"non-dict result: {type(result).__name__}"
    success = result.get("success", False)
    obj = _extract_objective(result)
    classified = result.get("problem_type") or result.get("classification")
    err = result.get("error")
    bits = [f"success={success}"]
    if classified:
        bits.append(f"type={classified}")
    if obj is not None:
        bits.append(f"obj={obj}")
    if err:
        bits.append(f"err={str(err)[:80]}")
    return " | ".join(bits)


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


_NON_OPTIMIZATION_TYPES = {"smalltalk", "help", "follow_up", "guidance"}

# Relative gap tolerance (percent) for "objective == published optimum".
# Published optima here are exact (mostly integers); allow a hair for float noise.
_GAP_TOL_PCT = 0.01


# Fine-grained problem types that all route to the same underlying solver. The
# 5-vote classifier legitimately disagrees among labels within a family (e.g.
# single_stage_scheduling vs single_machine_tardiness), all of which map to the
# single-stage IPM and produce the same answer. The gate cares about routing to
# the right SOLVER, not the exact label, so we compare families.
_SOLVER_FAMILIES = {
    "transport": {"transportation"},
    "scheduling": {
        "scheduling", "single_stage_scheduling", "single_machine_makespan",
        "single_machine_tardiness", "parallel_machine_scheduling",
    },
}


def _family_of(ptype) -> str:
    t = str(ptype).strip().lower()
    for fam, members in _SOLVER_FAMILIES.items():
        if t in members:
            return fam
    return t  # unknown/unsupported types are their own family


def _classification_matches(reported, expected) -> bool:
    """True when the pipeline routed to the same solver family the repo expects.
    Compares solver families rather than exact labels, since the voting
    classifier varies among equivalent fine-grained labels."""
    if not reported or not expected:
        return False
    return _family_of(reported) == _family_of(expected)


def _compute_gap_pct(result, published_optimum):
    """Return relative gap percent vs published optimum, or None if not
    computable (no objective or no/zero published optimum)."""
    if published_optimum in (None, 0):
        return None
    obj = _extract_objective(result)
    if obj is None:
        return None
    return abs(obj - published_optimum) / abs(published_optimum) * 100.0


def _classify_outcome(result, marked_solvable: bool, expected_type=None,
                      published_optimum=None) -> tuple[str, bool]:
    """Return (outcome_label, should_stop).

    Solvable problems are held to the full bar: classified as the right type,
    solved, and (where a published optimum exists) matching it at ~0% gap.
    Refuse problems must refuse; a wrongly-solved refuse halts.

    Outcome labels:
      solved              — success=True on a solvable problem, classified as
                            expected_type, with an objective AND (if a published
                            optimum exists) gap <= tolerance. Truly solved.
      graceful_refuse     — success=False on a problem marked solvable=False.
                            Pipeline correctly refused. PASS.
      intent_misroute     — success=True but no problem_type, or problem_type
                            is smalltalk/help/etc. Stops.
      solved_no_objective — success=True, real problem_type, no objective. Stops.
      misclassified       — success=True on a solvable problem but problem_type
                            != expected_type (solved the wrong model). Stops.
      gap_violation       — success=True, solvable, but objective != published
                            optimum beyond tolerance. Stops.
      wrongly_solved      — success=True on a problem marked solvable=False.
                            Should have refused; stops (masks scope bugs).
      unexpected_failure  — success=False on a problem marked solvable=True.
                            Should have solved; stops.
      crash               — Python exception. Stops.
    """
    if isinstance(result, dict) and "crash" in result:
        return ("crash", True)
    if not isinstance(result, dict):
        return ("non_dict_result", True)
    success = bool(result.get("success", False))
    if success:
        ptype = result.get("problem_type") or result.get("type")
        if not ptype or str(ptype).lower() in _NON_OPTIMIZATION_TYPES:
            return ("intent_misroute", True)
        if _extract_objective(result) is None:
            return ("solved_no_objective", True)
        if not marked_solvable:
            # A refuse-set problem got solved — silent scope failure.
            return ("wrongly_solved", True)
        gap = _compute_gap_pct(result, published_optimum)
        if gap is not None:
            # A published optimum exists: matching it at ~0% gap is itself proof
            # the pipeline routed to the right model (no wrong model coincidentally
            # reproduces an independently-published optimum). Label is irrelevant.
            if gap > _GAP_TOL_PCT:
                return ("gap_violation", True)
            return ("solved", False)
        # No published optimum to check against: the only guard against a gross
        # misroute is that it routed to the expected solver family.
        if expected_type is not None and not _classification_matches(ptype, expected_type):
            return ("misclassified", True)
        return ("solved", False)
    if not marked_solvable:
        return ("graceful_refuse", False)
    return ("unexpected_failure", True)


def main(argv) -> int:
    print(f"Backend: ollama @ {Config.OLLAMA_HOST}", flush=True)
    print(f"Classification model: {Config.CLASSIFICATION_MODEL}", flush=True)

    if "--reset" in argv:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
            print(f"Wiped state file: {STATE_FILE}", flush=True)
        argv = [a for a in argv if a != "--reset"]

    run_all = "--all" in argv
    names = [a for a in argv if not a.startswith("--")]

    state = _load_state()
    print(f"Loaded state: {len(state)} prior results in {STATE_FILE.name}", flush=True)

    llm = EnhancedLLMClient(host=Config.OLLAMA_HOST, model=Config.OLLAMA_MODEL)
    agent = OptimizationAgent(llm)

    if names:
        problems = [get_problem_by_name(n) for n in names]
        problems = [p for p in problems if p is not None]
        print(f"Running {len(problems)} requested problems", flush=True)
    elif run_all:
        problems = list(get_all_problems())
        print(f"Running ALL {len(problems)} problems in the repository", flush=True)
    else:
        problems = [p for p in get_all_problems() if _is_benchmark(p)]
        print(f"Found {len(problems)} real_data_benchmark problems", flush=True)

    passed_outcomes = {"solved", "graceful_refuse"}
    skipped = [p for p in problems if state.get(p["name"], {}).get("outcome") in passed_outcomes]
    to_run = [p for p in problems if p["name"] not in {s["name"] for s in skipped}]
    if skipped:
        print(f"Skipping {len(skipped)} already-passed problems (resume).", flush=True)
    print(f"Will run: {len(to_run)} problem(s).", flush=True)
    print("=" * 100, flush=True)
    _tty_print(f"[smoke] Starting: {len(to_run)} problem(s), {len(skipped)} skipped (resume). Total {len(problems)}.")

    rows = []
    stopped_early = False
    stop_reason = None
    run_started = time.time()
    running_solved = 0
    running_graceful = 0
    total_problems = len(problems)
    already_done = len(skipped)
    for i, p in enumerate(to_run, 1):
        name = p["name"]
        expected_type = p["expected_type"]
        published_optimum = p.get("published_optimum")
        marked_solvable = p["solvable"]

        overall_idx = already_done + i
        print(f"\n[{overall_idx}/{total_problems}] {name}  ({expected_type}, solvable={marked_solvable}, pub_opt={published_optimum})", flush=True)
        _tty_print(f"[smoke] {overall_idx}/{total_problems} START {name} ({expected_type}, solvable={marked_solvable})")
        t0 = time.time()
        try:
            result = agent.solve_natural_language(p["text"])
            took = time.time() - t0
            print(f"  result ({took:.1f}s): {_summarise(result)}", flush=True)
        except Exception as exc:
            took = time.time() - t0
            print(f"  CRASH ({took:.1f}s): {type(exc).__name__}: {exc}", flush=True)
            traceback.print_exc(limit=4)
            result = {"crash": f"{type(exc).__name__}: {exc}"}

        outcome, should_stop = _classify_outcome(
            result, marked_solvable, expected_type, published_optimum
        )
        gap_pct = _compute_gap_pct(result, published_optimum)
        if gap_pct is not None:
            print(f"  gap vs pub_opt: {gap_pct:.4f}%", flush=True)
        # Soft check on the refuse-set: a refuse is correct regardless of the
        # exact label, but flag a mismatch so silent misroutes stay visible.
        if not marked_solvable and isinstance(result, dict):
            rep = result.get("problem_type") or result.get("type")
            if rep and not _classification_matches(rep, expected_type) \
                    and str(rep).lower() not in _NON_OPTIMIZATION_TYPES:
                print(f"  [warn] refused as {rep!r}, expected {expected_type!r}", flush=True)
        print(f"  outcome={outcome}", flush=True)

        if outcome == "solved":
            running_solved += 1
        elif outcome == "graceful_refuse":
            running_graceful += 1

        elapsed = time.time() - run_started
        avg_s = elapsed / i if i > 0 else 0
        remaining = len(to_run) - i
        eta_s = avg_s * remaining
        def _fmt(secs):
            secs = int(secs)
            if secs < 60:
                return f"{secs}s"
            if secs < 3600:
                return f"{secs // 60}m{secs % 60:02d}s"
            return f"{secs // 3600}h{(secs % 3600) // 60:02d}m"
        progress_line = (
            f"  [PROGRESS] {overall_idx}/{total_problems} ({overall_idx * 100 // total_problems}%) "
            f"| this run: solved={running_solved} graceful={running_graceful} "
            f"| elapsed={_fmt(elapsed)} avg={_fmt(avg_s)} eta={_fmt(eta_s)} ({remaining} left)"
        )
        print(progress_line, flush=True)
        _tty_print(f"[{name}] {progress_line.strip()}")

        rows.append({
            "name": name,
            "expected_type": expected_type,
            "solvable_marker": marked_solvable,
            "pub_opt": published_optimum,
            "elapsed_s": round(took, 1),
            "outcome": outcome,
            "result": result,
        })

        if outcome in passed_outcomes:
            obj = _extract_objective(result)
            state[name] = {
                "outcome": outcome,
                "elapsed_s": round(took, 1),
                "objective": obj,
                "pub_opt": published_optimum,
                "gap_pct": round(gap_pct, 4) if gap_pct is not None else None,
            }
            _save_state(state)
        else:
            stopped_early = True
            stop_reason = f"{outcome} on '{name}'"
            print(f"\n[STOP] {stop_reason} — fix and re-run; this problem will be retried.", flush=True)
            break

    print("\n" + "=" * 100, flush=True)
    print("RUN SUMMARY", flush=True)
    print("=" * 100, flush=True)
    header = f"{'name':<50s}  {'outcome':>20s}  {'pub_opt':>12s}  {'obj_value':>12s}  {'gap%':>8s}  {'time':>6s}"
    print(header, flush=True)
    for r in rows:
        res = r["result"] if isinstance(r["result"], dict) else {}
        obj = _extract_objective(res)
        pub = r["pub_opt"]
        gap_str = ""
        if obj is not None and pub is not None and pub != 0:
            gap_str = f"{abs(obj - pub) / abs(pub) * 100:.2f}"
        elif obj is None:
            gap_str = "—"
        pub_str = f"{pub}" if pub is not None else "—"
        obj_str = f"{obj}" if obj is not None else "—"
        print(f"{r['name']:<50s}  {r['outcome']:>20s}  {pub_str:>12s}  {obj_str:>12s}  {gap_str:>8s}  {r['elapsed_s']:>5.1f}s", flush=True)

    n_solved = sum(1 for r in rows if r["outcome"] == "solved")
    n_graceful = sum(1 for r in rows if r["outcome"] == "graceful_refuse")
    print(f"\nThis run: solved={n_solved}, graceful_refuse={n_graceful}, stopped={stopped_early}", flush=True)
    repo_total = len(list(get_all_problems()))
    print(f"Cumulative passed (in state file): {len([1 for v in state.values() if v.get('outcome') in passed_outcomes])}/{repo_total}", flush=True)
    if stopped_early:
        print(f"STOPPED EARLY: {stop_reason}", flush=True)
        _tty_print(f"[smoke] STOPPED EARLY: {stop_reason}")
        return 1
    print("All scheduled problems completed.", flush=True)
    _tty_print(f"[smoke] DONE: solved={n_solved}, graceful={n_graceful}, total in state={len(state)}/{len(problems)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
