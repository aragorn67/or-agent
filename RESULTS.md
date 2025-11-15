# Classification Results

## Test 1: Initial Comparison (2025-11-11)

**Test Set:** 10 problems (6 transportation + 4 single-stage scheduling)

### Results Summary

| Approach | Accuracy | Avg Confidence | Speed |
|----------|----------|----------------|-------|
| DeepSeek-R1 (n=3) | 70% (7/10) | 94.3% | ~30s |
| ML Classifier | 70% (7/10) | 15-30% | <1s |
| DeepSeek-R1 + RAG (n=1) | 50% (5/10) | 90% | ~35s |

**Winner:** DeepSeek-R1 (no RAG, n=3)

### Failed Problems (DeepSeek-R1 n=3)
1. transport/pharma_coldchain/001 - Expected: min_cost_flow, Got: transportation
2. transport/us_mfg/001 - Expected: transportation, Got: max_flow
3. sched/chem_batch/001 - Expected: single_stage_scheduling, Got: job_shop

---

## Test 2: DeepSeek-R1 with n=5 votes (2025-11-11)

**Accuracy:** 70% (7/10) - **NO IMPROVEMENT**
**Avg Confidence:** 94.3%
**Speed:** ~50 seconds (slower due to more votes)

### Failed Problems (same as n=3)
1. transport/pharma_coldchain/001 - Expected: min_cost_flow, Got: transportation (90%)
2. transport/us_mfg/001 - Expected: transportation, Got: max_flow (95%)
3. sched/chem_batch/001 - Expected: single_stage_scheduling, Got: job_shop (90%)

**Conclusion:** Increasing votes from n=3 to n=5 did NOT improve accuracy. The model consistently makes the same classification decisions. More votes = more consensus on wrong answers.

**Next Steps:** Need to improve the prompt or add few-shot examples, not just more votes.

---

## Test 2: DeepSeek-R1 with n=5 votes (2025-11-11)

**Accuracy:** 70% (7/10) - **NO IMPROVEMENT**
**Avg Confidence:** 94.3%

Same 3 failures as n=3. More votes = more consensus on wrong answers.

---

## Test 3: Ensemble Approaches (2025-11-11)

### Attempt 1: Standard Ensemble (both agree → use result)
**Result:** 60% - WORSE than either alone

### Attempt 2: Smart Ensemble (only use ML when LLM uncertain)
**Config:** LLM threshold 90%, 91%, 92%
**Result:** 60-70% depending on threshold

**Key Finding:** ML correctly predicts 2 out of 3 LLM failures:
- ✅ transport/pharma_coldchain/001 (ML: transportation ✓)
- ✅ transport/us_mfg/001 (ML: transportation ✓)
- ❌ sched/chem_batch/001 (ML: scheduling ✗)

But ensemble doesn't help because LLM is always confident (90-95%), even when wrong.

### Attempt 3: Two-Stage (ML suggests → LLM verifies)
**Strategy:** ML makes fast prediction, LLM validates if it's correct
**Result:** 60%

**What happened:**
- LLM accepted 7 ML suggestions
- LLM corrected 3 ML suggestions
- Problem: LLM verification still makes mistakes:
  - ✅ Fixed problem 3: assignment → transportation (GOOD!)
  - ❌ Problem 8: "corrected" to job_shop (should be single_stage_scheduling)
  - ❌ Problem 9: "corrected" to job_shop (should be single_stage_scheduling)

**Issue:** LLM conflates single_stage_scheduling with job_shop

---

## Current Status: 70% ceiling

**All approaches plateau at 70%:**
- DeepSeek-R1 alone: 70%
- ML alone: 70%
- Ensemble: 60-70%
- Two-stage: 60%
- RAG: 50% (worse)

**The 3 persistent failures:**
1. `transport/pharma_coldchain/001` - Expected: min_cost_flow, Got: transportation
2. `transport/us_mfg/001` - Expected: transportation, Got: max_flow (LLM) or transportation (ML✓)
3. `sched/chem_batch/001` - Expected: single_stage_scheduling, Got: job_shop

---

## Next Steps: Two Promising Ideas

### Idea 1: Few-shot examples in prompt
Add 2-3 example classifications showing:
- transportation vs min_cost_flow vs max_flow (differences)
- single_stage_scheduling vs job_shop (key distinction: one stage vs multi-stage)

### Idea 2: Improve problem descriptions ⭐
**Problem:** Current problem text may not emphasize key OR structural features

**Solution:** Preprocess problems to extract and highlight:
- Number of stages (single vs multi)
- Decision variable types (binary, integer, continuous)
- Constraint types (capacity, flow conservation, precedence, etc.)
- Objective type (minimize cost, makespan, tardiness, etc.)

**Implementation approach:**
1. Create a problem preprocessor that analyzes text
2. Generate a "structural summary" to prepend to problem
3. Feed enhanced description to classifier

Example enhanced description:
```
STRUCTURE:
- Stages: Single stage (orders assigned to machines)
- Variables: Binary assignment + continuous completion times
- Constraints: Each order to exactly one machine, due dates
- Objective: Minimize maximum lateness

PROBLEM:
[original problem text...]
```

This would help LLM focus on mathematical structure rather than getting confused by domain keywords.

---

## Recommendation for Tomorrow

**Try Idea 2 first** (problem description enhancement):
1. Build problem preprocessor
2. Test on the 3 failing cases
3. If it works, apply to all problems

If that doesn't reach 80-90%, then try Idea 1 (few-shot examples).

**Current best:** DeepSeek-R1 alone at 70% (simplest, most reliable)

---

## Important Consideration: Classification Schema Design

**Potential Issue:** The way we classify OR problems might not be optimal.

Current schema uses fine-grained categories (transportation, min_cost_flow, max_flow, single_stage_scheduling, job_shop, etc.). This creates confusion:
- Is min_cost_flow really different from transportation for our purposes?
- Is single_stage_scheduling vs job_shop distinction necessary?
- Are we over-categorizing?

**Questions to consider:**
1. **What's the end goal?**
   - If goal is parameter extraction → maybe we only need broad categories (transport, scheduling, assignment, etc.)
   - If goal is solver selection → fine-grained types matter more

2. **Are the boundaries clear?**
   - min_cost_flow vs transportation: Both are network flow with costs
   - single_stage vs job_shop: Both schedule jobs on machines
   - Maybe the "ground truth" labels in or_problem_repository.py are too specific?

3. **Should we use hierarchical classification?**
   - Level 1: Broad category (transportation, scheduling, assignment, etc.) - 90% accurate
   - Level 2: Specific subtype (only if needed for solving) - 70% accurate
   - This would give high confidence on what matters most

**Action items:**
1. Review the expected_type labels in or_problem_repository.py
2. Check if solver needs fine-grained types or broad categories work
3. Consider collapsing similar types (e.g., min_cost_flow → transportation)
4. Re-evaluate accuracy with simplified schema

**This could be why we're stuck at 70%** - the classification task itself might be ambiguous or unnecessarily difficult.
