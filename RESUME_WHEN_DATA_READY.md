# Resume Point: When Training Data is Ready

## Current Status (2025-10-18)

### ✅ Completed (Tasks 1-5)
1. **Taxonomy** - 9 families, 25+ subtypes (`or_classify/taxonomy.yml`)
2. **Normalizer** - Alias mapping, 50+ synonyms (`or_classify/normalizer.py`)
3. **LF Framework** - ABSTAIN, priority, registry (`or_classify/labeling_function.py`)
4. **25 Core LFs** - All families covered (`or_classify/lfs/`)
5. **Feature Pipeline** - TF-IDF + LF + engineered features (`or_classify/feature_pipeline.py`)
6. **Hierarchical Classification System** - Categories + subcategories with solver routing (`solvers/capabilities.py`, `llm/schemas.py`)

### 🔄 In Progress (Task 6)
- **Training Data Collection** - Team member collecting 60+ base + 30+ adversarial variants
- **Google Sheet**: https://docs.google.com/spreadsheets/d/1_dQ9_0rXrzR6ISr51h6H44eDfQPi2Xh-wLRY0hAHJuU/edit?usp=drive_link

### ⚠️ **CRITICAL: Classifier Confusion Issue Discovered**
**Date**: 2025-10-18
**Problem**: Current LLM-based classifier cannot distinguish between scheduling subcategories:
- Classifying `single_stage_scheduling` problems as `job_shop` (95-100% confidence)
- Classifying `flow_shop` problems as `job_shop`
- Missing key structural differences between subcategories

**Test Results**:
```
[1/18] Single-Stage: Batch Processing
❌ Result: job_shop (expected: single_stage_scheduling) - 95% confidence

[2/18] Single-Stage: Chemical Reactors
❌ Result: job_shop (expected: single_stage_scheduling) - 100% confidence

[4/18] Flow Shop Scheduling
❌ Result: job_shop (expected: flow_shop) - 100% confidence
```

**Root Cause**: Zero-shot LLM classification without training examples cannot reliably distinguish fine-grained scheduling subtypes.

**Impact**:
- Cannot route solvable problems (single_stage_scheduling) to correct solver
- Users get "not solvable" messages for problems we CAN solve
- Solver capabilities mapping is useless without accurate classification

### ⏳ Pending (Tasks 7-14) - **NOW CRITICAL**
- **🔥 Train Level-1 classifier** (BLOCKING - fixes confusion above)
- **🔥 Train subtype classifiers** (BLOCKING - especially for SCHEDULING)
- Conflict resolution
- Grammar parsers
- CI gates
- Logging
- Active learning notebook

---

## When You Have the Data

### 1. Download & Convert (5 minutes)

```bash
# Download Google Sheet as CSV
# Save to: data_collection/training_data.csv

# Activate environment
source Tolis_Env/bin/activate

# Verify data format
python -c "
import pandas as pd
df = pd.read_csv('data_collection/training_data.csv')
print(f'Loaded {len(df)} problems')
print(f'Families: {df.level1_family.value_counts()}')
print(f'Subtypes (SCHEDULING): {df[df.level1_family == \"SCHEDULING\"].subtype.value_counts()}')
print(f'Base vs Adversarial: {df.notes.str.contains(\"adversarial\").value_counts()}')
"
```

### 2. Quick Data Validation (10 minutes)

**⚠️ EXTRA CRITICAL for SCHEDULING subcategories**:
- ✅ At least 8-10 examples of `single_stage_scheduling` (we can solve these!)
- ✅ At least 8-10 examples of `job_shop` (we cannot solve, but need to reject correctly)
- ✅ At least 5+ examples each of `flow_shop`, `shift_rostering`, `project_scheduling`
- ✅ Clear structural differences in problem descriptions (operations, precedence, etc.)

Check for:
- ✅ All required columns present
- ✅ `licence_ok = yes` for all rows
- ✅ At least 60 problems total
- ✅ Each family has 6+ examples
- ✅ Objectives present ("minimise" / "maximise")
- ✅ No duplicates
- ✅ Text length 3-8 sentences

### 3. Next Steps (In Order)

**Option A: Train ML Classifiers (Tasks 7-8) - ⚠️ NOW MANDATORY**
**Why**: Current LLM classifier has 70-80% failure rate on scheduling subcategories. This is blocking basic functionality.

1. Split data: 70% train, 15% val, 15% test
2. Train Level-1 classifier (9 families) - Gets us to category level
3. **Train SCHEDULING subtype classifier** (job_shop vs single_stage vs flow_shop) - CRITICAL
4. Train other subtype classifiers (per family) - Nice to have
5. Implement conflict resolution (LF + ML voting)
6. Test on Phase 1 suite - Target: 90%+ accuracy on scheduling subcategories

**Option B: Skip ML, Go Production (Tasks 9-13)** - ⚠️ NO LONGER VIABLE
Without proper classification, we cannot:
- Route solvable problems to correct solver
- Tell users what we can/cannot solve
- Extract parameters correctly (each subtype has different structure)

**Recommendation**: Option A is now MANDATORY. The LLM-based zero-shot classification cannot distinguish scheduling subcategories with acceptable accuracy.

**Estimated Time**:
- With 60+ training examples: 2-3 hours to train and test
- With 120+ training examples: Same time, better accuracy

---

## Files Ready for Training

**Infrastructure**:
- `or_classify/feature_pipeline.py` - Extract features from text
- `or_classify/normalizer.py` - Normalize labels
- `or_classify/labeling_function.py` - LF framework

**Data** (when ready):
- `data_collection/training_data.csv` - Your collected problems

**Tests**:
- `tests/phase1_test_cases.py` - 30 test cases for evaluation

---

## Quick Start Commands (When Ready)

```bash
# 1. Load and validate data
cd /home/thanasis/Documents/Opt_Project/Optimization-AI-
source Tolis_Env/bin/activate
python -c "import pandas as pd; print(pd.read_csv('data_collection/training_data.csv').info())"

# 2. Train Level-1 classifier
python scripts/train_level1_classifier.py --data data_collection/training_data.csv --output models/level1_classifier.pkl

# 3. Evaluate on Phase 1 tests
python tests/test_hybrid_classifier.py --model models/level1_classifier.pkl

# 4. Compare results
python scripts/compare_classifiers.py --llm-baseline 0.80 --hybrid results/hybrid_results.json
```

---

## Success Metrics (When Training)

**Level-1 Classifier** (Category level):
- ✅ Macro-F1 ≥ 0.85 (vs 0.80 LLM baseline)
- ✅ Per-family precision ≥ 0.80
- ✅ Classification time < 50ms
- ✅ Calibrated confidence scores

**SCHEDULING Subtype Classifier** (CRITICAL - fixes current blocker):
- ✅ **job_shop vs single_stage_scheduling precision ≥ 0.90** (we MUST route correctly)
- ✅ **flow_shop precision ≥ 0.85**
- ✅ Accuracy ≥ 0.85 overall across all 5 scheduling subtypes
- ✅ Classification time < 50ms
- ✅ Low false positive rate for solvable problems (don't want to reject problems we can solve)

**Other Subtype Classifiers** (per family):
- ✅ Accuracy ≥ 0.75 per family
- ✅ Only train families with ≥20 examples

**Current Baseline to Beat**:
- LLM zero-shot on scheduling subcategories: ~20-30% accuracy (3/18 correct in tests)
- LLM zero-shot on categories: ~80% accuracy

---

## Contact Points

**Data Collection**:
- Team member working on: https://docs.google.com/spreadsheets/d/1_dQ9_0rXrzR6ISr51h6H44eDfQPi2Xh-wLRY0hAHJuU/edit?usp=drive_link
- Target: 60 base + 30 adversarial = 90 total (minimum)
- Ideal: 60 base + 60 adversarial = 120 total

**Current Todo List**: 6 tasks done, 8 remaining
- Task 6 (data collection): IN PROGRESS
- Tasks 7-14: PENDING (blocked on Task 6)

---

## Resume Checklist

When you return with data:
1. ☐ Download CSV from Google Sheet
2. ☐ Run validation checks (columns, licensing, counts)
3. ☐ Decide: Train ML (Option A) or LF-only (Option B)
4. ☐ Create training scripts (I'll help with this)
5. ☐ Train and evaluate
6. ☐ Compare vs baseline (80% LLM)
7. ☐ Update diary with results

---

## Why This is Now Blocking

The hierarchical classification system is in place:
- ✅ Categories defined (SCHEDULING, TRANSPORTATION, etc.)
- ✅ Subcategories defined (job_shop, single_stage_scheduling, etc.)
- ✅ Solver capabilities documented (`solvers/capabilities.py`)
- ✅ Routing logic implemented (`agent/core.py:_map_to_solver()`)
- ✅ Test cases with expected subcategories (`tests/phase1_test_cases.py`)

**BUT**: The LLM classifier cannot distinguish subcategories accurately enough to make the system work.

**What happens now**:
1. User asks: "Schedule 3 production orders on 2 processing units..." (single_stage_scheduling - WE CAN SOLVE THIS)
2. LLM classifies as: `job_shop` (95% confidence)
3. System routes to: scheduling solver (correct route, by accident)
4. Solver tries to extract parameters for job_shop structure (WRONG)
5. Parameter extraction fails
6. User gets error: "Parameter extraction failed"
7. **User cannot solve a problem we CAN solve**

**What needs to happen**:
1. User asks: "Schedule 3 production orders on 2 processing units..."
2. **Trained classifier** correctly identifies: `single_stage_scheduling` (90%+ confidence)
3. System routes to: scheduling solver (correct)
4. Solver extracts parameters for single_stage structure (correct)
5. Problem solved successfully
6. **User gets solution**

---

**Session Paused**: 2025-10-18
**Resume When**: Training data CSV ready
**Next Task**: Train SCHEDULING subtype classifier (Task 7-8) - NOW CRITICAL/BLOCKING
