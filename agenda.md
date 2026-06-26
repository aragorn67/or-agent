# Agenda — TODO

Forward plan for Optimization-AI. **Tasks only — no results, no analysis, no
"shipped" log.** Completed work lives in `git log` and `ANALYSIS.md`.

**Strategic pivot (2026-06-26): safety artifact, not OR tool.** The project is
being repositioned from "better OR tool" toward an "AI-safety-relevant artifact"
— calibration, knowing-when-not-to-answer, eval validity, contradiction
handling. **Tier 1/2 below are the new priorities; the former OR-feature roadmap
is parked in Tier 3 ("resist").** Anchors in [[feedback_evals_are_synthetic]].

**Governing thesis (still holds):** the LLM routes to *published / validated* OR
models and never invents the formulation. The Tier-1 work is a **meta layer**
(confidence, abstention, consistency) — it does not touch the math, so the
thesis is intact. Tripwire unchanged: any task needing a model not in the solver
registry → stop and tell the user, do not synthesise.

---

## ⚠️ OPEN DECISIONS — resolve at the START of next session

Raised 2026-06-26, deferred. Answer these four before building:

1. **GitLab scope.** Learning exercise only (mirror + see how CI works), or the
   primary home for the safety-eval pipeline? Do you already have a gitlab.com
   account/project, or is creating one part of the learning?
   - *Context:* shared runners have no GPU/Ollama, so only the **deterministic**
     checks (pytest, solver ground-truth, gate-logic units, repo validator) run
     there. The LLM-dependent eval needs a **self-hosted runner** (your machine)
     — itself the most instructive GitLab piece. To start I need a GitLab project
     URL (you create it; I can't).
2. **Build vs plan.** Start *building* a Tier-1 capability this session, or keep
   mapping/sequencing so the build happens later (possibly away from the machine)?
3. **Machine availability.** Calibration measurement + a GitLab self-hosted
   runner need the machine + Ollama; the methodology writeup + agenda work don't.
   Which stretches are at-machine vs no-machine? (May join from Windows.)
4. **Agenda parking.** OK to park ~8 of the 10 former priorities as Tier-3
   "resist", or keep any live — e.g. the one legit "new family *purely as an
   eval-generalisation probe*"?

**Recommended start (mine):** Tier-1 **#1 + #3 together** — they share the same
57-problem correctness labels (the calibration harness *is* the eval-validity
harness, built once). Lowest-risk: instruments the N-vote voting that already
exists, no new capability required.

---

## Tier 1 — Priority (safety capabilities that compound)

1. **Calibration layer + measurement.** Turn the classifier's existing N-vote
   majority distribution into a confidence score; add a verbalised-confidence
   step to the extractor; measure calibration (ECE, Brier, reliability diagram)
   against actual correctness across the 57-problem set. The first increment of
   the calibration project, on a system already known cold. *Absorbs the former
   "confidence / disagreement surfacing in UI" task.*
2. **Selective prediction / abstention.** Use those confidences to make the agent
   abstain or escalate when it is likely wrong; plot the risk–coverage curve.
   "Knowing when not to answer" is a genuine safety capability and a clean result
   to show.
3. **Eval-validity / distribution shift.** Quantify the gap between
   synthetic-eval performance and the held-out textbook set — i.e. how much the
   system's *own* evaluation over-estimates real performance. A finding about
   *when evals lie* is far more safety-relevant than another solver. Builds on
   [[feedback_evals_are_synthetic]] + today's hardened 57-problem gate (the
   ground-truth labels it measures against).
4. **Contradiction-aware extraction.** Detect mutually inconsistent constraints
   and fail closed rather than silently resolving them — directly the "don't emit
   confident wrong answers" muscle, applied at extraction time. (The named gap.)

## Tier 2 — Communication & legibility

- **Methodology writeup** *(no machine needed — pure thinking/writing; doable in
  the next ~2 weeks)*: "catching confidently-wrong outputs in agentic tool-use
  systems," with the OR agent as the case study. Highest communication leverage
  of anything here.
- **Inspect port of one harness** *(when back at the machine)*: port one eval to
  the Inspect framework — makes the work legible to AISI-type reviewers and
  teaches their framework.

## Tier 3 — Resist (former OR-tool roadmap; parked, not deleted)

These make a better OR *tool*, not a better safety *artifact*, and the user is
not targeting optimisation roles. **Keep parked.** The ONLY legitimate revival is
adding one new problem family *purely to test whether the eval method generalises
across domains* — and that is an evaluation task, not a feature.

- Large-scale OR via xlsx · Web UI · Persistent REST / Cloudflare deployment ·
  Cost/ROI framing · Pick-a-vertical-and-go-deep · VNS heuristic layer +
  constraint-template whitelist · third problem family · Benders / Dantzig-Wolfe
  decomposition · CSV/Excel loaders.
- Original detail retained below under **Tier 3 — parked detail** for if/when the
  strategy changes.

### Quick wins (still fine anytime, low-risk)

- Flow / Gantt / network visualisation
- Fuzzy-match entity-name errors ("did you mean 'Seattle'?")
- 2-D parameter sensitivity (currently 1-D)
- Constraint-relaxation suggestion on infeasible ("relax demand by 10%?")
- Move keyword-analysis check ahead of `detect_intent` (bare what-if becomes fully LLM-free)
- Quiet the caught Pyomo "No eligible units" log emitted during a *successful* scheduling solve
- **Prompt for missing numeric parameters instead of failing extraction.** When a problem text describes the *schema* (warehouses/stores/cost matrix) but supplies no actual numbers, the extractor returns "Parameter validation failed." Better: detect "schema described, values missing" and ask the user to supply them. Surfaced by smoke benchmark 2026-05-24 (fresh_food_distribution / steel_supply_construction / wafer_processing_single_stage). *(Mildly safety-relevant — graceful elicitation over confident failure.)*
- **Anchor scheduling's parallel / due-date / makespan features.** Hillier
  12.6-8 only exercises the single-machine changeover objective. The
  parallel-assignment, due-date, and makespan paths have no published-optimum
  anchor — find a tiny published instance or enumeration-verify one. *(Feeds
  Tier-1 #3: more verified labels = tighter eval-validity measurement.)* Surfaced 2026-06-06.

---

## Details

### Tier 1 — task notes

Flesh these out as they're picked up. Shared infrastructure: all four measure
predictions against the 57-problem labelled set in `tests/or_problem_repository.py`
(10 solvable w/ optima, 47 refuse-path), so build the measurement scaffold once.

- **#1 Calibration.** Source signal already exists: `ProblemClassifier` runs
  `DEFAULT_VOTING_ROUNDS` votes — expose the vote histogram as `p(label)`. Add a
  verbalised-confidence ask to the extractor (separate from the value extraction).
  Metrics: ECE (binned), Brier, reliability diagram. Label = did the final
  objective match the published optimum / did classification route correctly.
- **#2 Abstention.** Threshold on the #1 confidence → answer / abstain / escalate.
  Output the risk–coverage curve (accuracy on answered vs fraction answered).
- **#3 Eval-validity.** Run the synthetic round-trip eval AND the textbook
  smoke gate, report the delta per metric (classification acc, param recall,
  objective gap, pass rate). The headline is the *over-estimate*: synthetic minus
  real.
- **#4 Contradiction detection.** At extraction, run a cheap consistency pass
  (e.g. supply<demand already caught by Layer-1; extend to mutually exclusive
  constraints, impossible due-dates vs processing, over-determined params) and
  fail closed with the specific contradiction surfaced.

### Tier 3 — parked detail

**Large-scale OR via xlsx.** Industry-scale instances fed as `.xlsx` (xlsx
fast-path bypasses LLM extraction → exercises the solver at realistic scale).
Pair each with a published optimum/reference so `objective_gap` stays meaningful.

**Third problem family.** Multi-period or multi-commodity flow. Tests
`FeasibilityPlugin` generalisation + registry wiring. *(Only revive as the
eval-generalisation probe per Tier-3 note.)*

**Consolidated problem formulation (Overview-PDF expansion).** Objective /
constraints / assumptions / failure-cases for transport LP-MIP + scheduling IPM
in one place.

**Web UI (clean front-end).** Real web front-end over the existing job/poll
pipeline. Presentation, not new backend.

**Persistent REST deployment.** Stable URL via persistent API (previous
cloudflared tunnel was ephemeral). Pairs with Web UI.

**Cost / ROI framing in-app.** "This solve would take a consultant ~X hrs / ~$Y"
next to each result. Pure UX/marketing layer.

**Pick one vertical and go deep.** Choose a concrete buyer; make one end-to-end
workflow excellent. Strategic gate before Web UI / REST / Cost-ROI.

**Agentic frontier — on-thesis only.**
- *A2 — Multi-stage decomposition (composer over the registry).* Decompose a
  compound request into a sequence of *existing registered solvers*; LLM chooses
  order, never writes math. Tripwire: a stage needing an unregistered model →
  stop.
- *A3 — Autonomous infeasibility repair (within a known formulation).* Replace
  the capped 3 retries with an LLM reason→edit→re-check→revise loop over the
  *parameters / toggleable constraints of the already-selected model*. Tripwire:
  repair needing a structurally different model → escalate, don't reformulate.
  *(This slice has the most safety flavour of the Tier-3 set — abstention-adjacent.)*

**VNS + constraint-template whitelist.** *(Blocked on real-data benchmark.)*
- *A. VNS (Mladenović & Hansen 1997)* as the heuristic layer where VAM/LPT
  under-perform (fixed-charge transport, scheduling IPM). Problem-specific
  neighborhood ladders; deterministic descent inside, shake+restart outside.
  Two-call UX stays; HiGHS still proves the bound. Honest caveat: still heuristic.
- *B. Whitelist constraint translation (NL → MILP template).* Each solver
  declares toggleable templates (`forbid_arc`, `force_arc_open`, …); LLM picks
  template+params from a fixed list; deterministic linearizer instantiates. On
  no match → stop, never synthesise. Williams ch. 9 boolean-encoding zoo for
  binary patterns.

**Longer-term architecture (aspirational).** General CSV/Excel loaders + schema
inference; compiled-model warm caching (5–10× on sweeps); Benders/Dantzig-Wolfe/
column-generation for industrial scale; fixed-charge-aware construction
heuristic; tighter (positional/time-indexed) scheduling formulation.

---

## Research framing (CV / publication angle)

**Primary (post-pivot):** safety-relevant evaluation of agentic tool-use —
calibration, selective prediction / abstention, eval-validity under distribution
shift, contradiction-aware fail-closed extraction. "Catching confidently-wrong
outputs in agentic tool-use systems," OR agent as case study.

**Secondary (the substrate):** LLM-assisted OR (NL → optimal solution with OR
concepts surfaced in plain English) — consistent with the governing thesis (the
LLM orchestrates validated solvers; it does not do the math).
