"""
End-to-end demo of the two-call protocol with the real LLM stack (Ollama +
qwen3:14b) driving the agent.

Flow:
    1. User submits an NL transport problem with mode=heuristic_then_ask
    2. Agent classifies → extracts → runs VAM + LP relaxation
    3. Response includes the heuristic answer, the LP bound, the gap, and
       a job_id
    4. User replies with free text ("can you make it better")
    5. /chat/continue parses the free text → action="optimize"
    6. Agent warm-starts the exact solver (gated off for pure LP — see
       ANALYSIS.md), returns the proven-optimal answer + explanation

Run prerequisites:
    - Ollama up with qwen3:14b pulled
    - API running with LLM_BACKEND=ollama on port 8765:
        LLM_BACKEND=ollama uvicorn api:app --host 127.0.0.1 --port 8765
"""

import json
import time
import urllib.request


BASE = "http://127.0.0.1:8765"
TIMEOUT = 600


def post(path, body):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read())


def hr(title):
    print(f"\n{'─' * 72}")
    print(f"  {title}")
    print("─" * 72)


PROBLEM = (
    "I have a transportation problem. Two factories produce widgets: "
    "Seattle has capacity 350 and San Diego has capacity 600. I need to "
    "ship to three customers — New York wants 325, Chicago wants 300, "
    "Topeka wants 275. Distances in thousand miles: Seattle to New York "
    "2.5, Seattle to Chicago 1.7, Seattle to Topeka 1.8; San Diego to "
    "New York 2.5, San Diego to Chicago 1.8, San Diego to Topeka 1.4. "
    "Freight rate is 90 dollars per case per thousand miles. Minimize "
    "total shipping cost."
)


def main():
    hr("STEP 1 — User submits NL problem with mode=heuristic_then_ask")
    print(f"NL input:\n  {PROBLEM[:200]}...\n")

    t0 = time.time()
    resp = post("/solve", {"description": PROBLEM, "mode": "heuristic_then_ask"})
    t = time.time() - t0
    print(f"elapsed: {t:.1f}s")

    if not resp.get("success"):
        print("FAILED:", json.dumps(resp, indent=2)[:1200])
        return

    sol = resp["solution"]
    print(f"problem_type:   {resp['problem_type']}")
    print(f"confidence:     {resp.get('confidence')}")
    print(f"job_id:         {resp['job_id']}")
    print(f"heuristic cost: {sol['objective_value']:.4f}")
    print(f"LP bound:       {sol['best_bound']:.4f}")
    print(f"gap:            {sol['gap']*100:.4f}%")
    print(f"summary:        {resp['summary']}")
    if "follow_up_prompt" in resp:
        print(f"\nagent prompt:\n  {resp['follow_up_prompt']}")

    job_id = resp["job_id"]

    hr("STEP 2 — User replies in plain English: 'yes can you make it better'")

    t0 = time.time()
    resp2 = post("/chat/continue", {
        "job_id": job_id,
        "message": "yes can you make it better",
    })
    t = time.time() - t0
    print(f"elapsed: {t:.1f}s")
    print(f"parsed action:  {resp2.get('parsed_action')}")

    if not resp2.get("success"):
        print("FAILED:", json.dumps(resp2, indent=2)[:1200])
        return

    s2 = resp2["solution"]
    print(f"exact status:   {s2.get('status')}")
    print(f"exact cost:     {s2.get('objective_value'):.4f}")
    print(f"best bound:     {s2.get('best_bound'):.4f}")
    print(f"gap:            {(s2.get('gap') or 0)*100:.6f}%")
    print(f"warm_started:   {s2.get('warm_started')}  (False expected — pure LP, gate skipped)")
    print(f"\nheuristic baseline: {resp2.get('heuristic_baseline')}")
    summary = resp2.get("summary", "")
    if summary:
        print(f"\nLLM summary:\n  {summary[:500]}")

    hr("DONE")


if __name__ == "__main__":
    main()
