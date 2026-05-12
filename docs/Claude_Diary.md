# Claude Development Diary

---

## 📝 Recent Session Notes

### 2025-12-04: Repository Cleanup + Test Dataset Planning 📋

**What We Did Today:**

1. **Repository Reorganization** ✅
   - Created `docs/` directory and moved all documentation files
   - Created `data/` directory structure for Priority 1 (data layer)
   - Created `archive/` and moved old code:
     - `archive/old_analyzers/` - Old problem-specific analyzers (replaced by generic framework)
     - `archive/old_api/` - Old Flask templates/static files
     - `archive/ML_RAG_archive/` - Archived ML & RAG experiments
   - Created `STRUCTURE.md` - Repository navigation guide
   - All 17/17 feasibility tests still passing after cleanup

2. **LLM System Review** 🤖
   - **3 LLMs in pipeline:**
     - Qwen 2.5 Instruct (3B) - Classification
     - Qwen 2.5 Coder (7B) - Parameter extraction
     - DeepSeek R1 (~70B) - Reasoning/explanations
   - **RAG:** Optional feature, not used by default (no knowledge base loaded)

3. **Test Dataset Analysis** 📊
   - **Current:** 35 problems (10 solvable)
   - **ML Archive Dataset:** 523 problems in `ML_RAG_archive/ML_approaches/ML/FINAL_ML_DATASET.csv`
     - 82 job_shop, 288 LPWP (linear programming), 31 knapsack, 31 flow_shop, etc.
   - **Key Insight:** Can use ALL 523 for **classification testing** (don't need solvers!)
     - Classification test: LLM → label → compare to expected
     - End-to-end test: LLM → extract → solve (needs solver)

4. **Added ML Metrics to Classification Tests** ✅
   - Added F1-score, Precision, Recall calculations to `tests/test_classification.py`
   - Output now includes proper ML metrics alongside accuracy

**⏭️ NEXT SESSION TASK: Create Standardized Test Dataset CSV**

### 📋 Plan: tests/test_problems.csv

**Problem:** Test problems currently hardcoded in Python (`tests/or_problem_repository.py`)
- Hard to maintain and update
- Mixing code with data
- Difficult to add new problems

**Solution:** Create `tests/test_problems.csv` with standardized schema

**Proposed GOLD Dataset CSV Schema:**

This is a **GOLD STANDARD** test dataset - includes expected solutions for validation!

**Minimal Required Schema (Start with this):**
```csv
problem_id,title,description,category,subtype,feasible,solvable,source,expected_objective_value,expected_objective_sense,confidence_level,notes
```

**Example Rows:**
```csv
transport_001,European Wine Distribution,"A European winery ships...",TRANSPORTATION,transportation,true,true,manual,150.0,minimize,gold,"Golden test - regression testing"
schedule_001,Job Shop 10x10,"Manufacturing facility...",SCHEDULING,job_shop,true,false,orlib,,,bronze,"Need job shop solver"
lpwp_160,Florist Bouquets,"A florist transports...",TRANSPORTATION,transportation,true,false,LPWP,,,silver,"Linear program not bipartite"
```

**Core Column Definitions:**
- `problem_id`: Unique identifier (e.g., `transport_001`, `lpwp_160`)
- `title`: Short descriptive title
- `description`: Full problem text (natural language)
- `category`: High-level family (TRANSPORTATION, SCHEDULING, KNAPSACK, etc.)
- `subtype`: Specific type (transportation, job_shop, flow_shop, knapsack, etc.)
- `feasible`: Is problem mathematically feasible? (true/false)
- `solvable`: Can our current solvers handle it? (true/false)
- `source`: Where from (manual, orlib, Chain-of-Experts, synthetic)
- `expected_objective_value`: **GOLD STANDARD** - The optimal objective value for validation
- `expected_objective_sense`: `minimize` or `maximize`
- `confidence_level`: `gold` (verified), `silver` (likely correct), `bronze` (unverified), `none`
- `notes`: Additional context

**Additional Columns to Add Later (Phase 2):**

*Solution Validation:*
- `solution_json`: Full solution details in JSON format
  - Example: `{"flows": [{"from": "F1", "to": "A", "value": 100}], "objective": 150}`
- `alternative_solutions`: JSON array if multiple optimal solutions exist
- `solution_bounds_lower`: Lower bound on objective (if exact unknown)
- `solution_bounds_upper`: Upper bound on objective

*Extraction Testing:*
- `expected_params_json`: Expected extracted parameters for testing extraction accuracy
  - Example: `{"plants": ["F1", "F2"], "markets": ["A", "B", "C"], "capacity": {"F1": 200}}`
- `param_extraction_difficulty`: `easy`, `medium`, `hard`

*Testing Metadata:*
- `test_type`: `classification_only`, `extraction_only`, `end_to_end`, `benchmark`
- `solver_type`: `bipartite_transport`, `single_stage_ipm`, `none`
- `problem_size`: `small` (<10 vars), `medium` (10-100), `large` (100+)
- `runtime_budget_ms`: Max expected solve time for performance regression testing

*Quality Assurance:*
- `validation_status`: `verified`, `needs_verification`, `failed`, `deprecated`
- `last_validated_date`: When solution was last verified (YYYY-MM-DD)
- `known_issues`: Any known problems with this test case
- `problem_variant_of`: Links to base problem if this is a variation

**Why These Columns Matter:**

✅ **Can validate solver correctness** - Compare computed objective to `expected_objective_value`
✅ **Can test extraction accuracy** - Compare extracted params to `expected_params_json`
✅ **Can detect regressions** - If objective changes, we broke something
✅ **Can measure test coverage** - Filter by `test_type`, `solvable`, `confidence_level`
✅ **Can benchmark performance** - Use `runtime_budget_ms` to catch slowdowns
✅ **Can track quality** - `confidence_level` and `validation_status` show which tests to trust

**Migration Plan:**

1. **Phase 1: Create CSV from current problems** (30 min)
   - Extract **all 35 existing problems** from `tests/or_problem_repository.py`
   - These are our golden test cases (European Wine, US Manufacturing, etc.)
   - Create `tests/test_problems.csv` with these problems first
   - Keep Python file as loader for backward compatibility

2. **Phase 2: Import ML dataset problems** (1 hour)
   - **Add** 523 problems from `ML_RAG_archive/ML_approaches/ML/FINAL_ML_DATASET.csv`
   - Map columns: `id → problem_id`, `text → description`, `level1_family → category`, `subtype → subtype`
   - Mark `solvable=false` for problems needing solvers we don't have
   - **Result:** 35 (existing) + 523 (ML dataset) = **558 total problems for classification testing!**

3. **Phase 3: Update test files** (30 min)
   - Create `tests/csv_problem_loader.py` - Load from CSV
   - Update `tests/test_classification.py` to use CSV loader
   - Update `tests/test_problem_classification_runner.py` to use CSV
   - Keep `tests/or_problem_repository.py` for backward compatibility (wrapper around CSV)

4. **Phase 4: Generate synthetic problems** (future)
   - Add script to generate synthetic transport/scheduling problems
   - Append to CSV file
   - Target: 100+ solvable problems

**Benefits:**
- ✅ Easy to add/remove/modify problems (just edit CSV)
- ✅ Separates data from code
- ✅ Can filter by category/solvable/source easily
- ✅ Can import from multiple sources (ML dataset, OR-Library, synthetic)
- ✅ Better for version control (see what problems changed)
- ✅ Can use standard data tools (pandas, Excel) to analyze test coverage

**Test Coverage Goals After Migration:**
```
Classification Testing: 558 problems
  - 82 job_shop
  - 288 LPWP/linear_programming
  - 31 knapsack
  - 31 flow_shop
  - 24 facility_location
  - 15 assignment
  - 15 single_stage_scheduling
  - 10 bin_packing
  - 8 transportation
  - etc.

End-to-End Testing: ~33 solvable problems
  - 10 transportation (current)
  - ~15 single_stage_scheduling (from ML dataset)
  - ~8 additional transport (from ML dataset)
```

**Files to Create:**
- `tests/test_problems.csv` - The main GOLD STANDARD test dataset
- `tests/csv_problem_loader.py` - CSV loader utility
- `scripts/import_ml_dataset_to_csv.py` - Import script (one-time use)
- `scripts/validate_gold_solutions.py` - Script to verify all gold solutions are still correct

**Priority for Tomorrow:**
1. ⭐ **START HERE:** Create Phase 1 - Extract 35 existing problems to CSV with solutions
2. For each problem, include `expected_objective_value` from test files
3. Mark confidence level based on whether we've validated it
4. Add the minimal required columns first, expand later

**Status:** Plan documented with full schema details, ready for implementation! 🚀

---

### 2025-11-29: Test Suite Complete - ALL 4/4 TESTS PASSING 🎉

**Final Test Results: 4/4 PASSING**

- ✅ **Layer 0** (infeasible_transport_struct_mismatched_costs): FULL PASS
- ✅ **Layer 1** (infeasible_transport_supply_less_than_demand): FULL PASS
- ✅ **Layer 2** (infeasible_transport_capacity_pattern): FULL PASS
- ✅ **Feasible** (european_wine_distribution): FULL PASS

All tests include: detection → fix → solve → sensitivity → what-if → resolve

#### ✅ Critical Fixes Today:

1. **Fixed Layer 0 - Extraction with validation errors**
   - **Problem**: When LLM detected negative capacity, it returned ONLY `{"error": "..."}` with NO params
   - **Impact**: Fix couldn't be applied because there was no capacity dict to modify
   - **Fix**: Modified `llm/transportation_specialist.py`:
     - Line 58: Updated prompt to extract ALL data even if invalid
     - Line 73-76: Return params WITH error flag instead of error-only dict
   - **Result**: Now returns `{'plants': [...], 'capacity': {..., 'F2': -60}, 'error': '...'}`

2. **Fixed Layer 2 - Wrong fix query**
   - **Problem**: Fix "Increase arc capacity from F1 to C to 50" didn't make problem feasible
   - **Fix**: Changed to "Increase arc capacity from F2 to A to 50" in test_complete_analysis_suite.py:280
   - **Result**: Problem now solves with optimal cost €150.00

3. **Fixed extraction failure status**
   - Added `status='infeasible'` when extraction fails (agent/core.py:150)

4. **Fixed cost dict format mismatch**
   - Agent passed nested `{i: {j: c}}` but feasibility checker expected flat `{(i,j): c}`
   - Updated `_convert_params_for_feasibility()` in agent/core.py:747-761 to flatten

5. **Fixed missing objective_value key**
   - Solver returned `"objective"` but code looked for `"objective_value"`
   - Added both keys in bipartite.py:264

6. **Fixed arc capacity modifications**
   - Added `is_arc` detection in enhanced_client.py:331
   - Consolidated arc_capacity handling for nested dict format (lines 346-366)
   - Updated `_parse_route()` to handle "arc from X to Y" (lines 419-433)

#### 📊 All Analysis Features Working:

- **Sensitivity Analysis**: Tests parameters at multiple values, shows cost impacts
- **What-If Scenarios**: Temporary modifications with feasibility checking & retry loop
- **Resolve**: Permanent modifications with parameter diff
- **LLM Intent Detection**: Handles typos and natural language variations
- **Fuzzy Entity Matching**: Case-insensitive, handles "center" vs "centre"

#### 🔧 Files Modified Today:

1. `llm/transportation_specialist.py:58, 73-76, 139-146` - Extract params even with validation errors
2. `agent/core.py:150, 155` - Add status and extracted_params to extraction failures
3. `agent/core.py:747-761` - Flatten nested cost dict for feasibility checker
4. `solvers/transport/bipartite.py:264` - Add objective_value key
5. `llm/enhanced_client.py:331, 346-366, 419-433` - Arc capacity modifications
6. `tests/test_complete_analysis_suite.py:280` - Correct Layer 2 fix query

**Status**: Analysis framework fully functional for transportation problems! 🚀

---

## 🎯 NEXT TASK: Problem-Agnostic Refactoring

### Current Limitation:

The analysis framework is **HARDCODED to transportation problems**:

**Hardcoded locations:**
- `analysis/sensitivity/engine.py:30-39` - Checks for 'plants', 'markets', 'capacity', 'demand'
- `analysis/scenarios/engine.py:225-233` - Creates instance with `I_plants`, `J_markets`
- `analysis/modification/engine.py:105-118` - Only handles capacity/demand/cost

**Won't work for:**
- ❌ Scheduling (jobs, machines, processing_time, due_date)
- ❌ Knapsack (items, weights, values)
- ❌ Portfolio (assets, returns, risk)
- ❌ Facility Location (facilities, customers, fixed_cost)

### Refactoring Plan:

#### Phase 1: Dynamic Parameter Detection (2-3 hours)

**Goal**: Detect which parameter to analyze WITHOUT hardcoding

**Current (hardcoded):**
```python
# sensitivity/engine.py:30-39
if 'plants' in params:
    param_name = 'capacity'
    entity_set = params['plants']
elif 'jobs' in params:
    param_name = 'processing_time'
    # ... MORE HARDCODING
```

**New (LLM-based):**
```python
# New file: analysis/parameter_detector.py
def detect_parameter_from_query(query: str, params: Dict, llm_client) -> Dict:
    """
    Use LLM to detect which parameter to analyze.

    Args:
        query: "sensitivity on Plant North capacity"
        params: {'plants': [...], 'capacity': {...}, 'demand': {...}}
        llm_client: For intelligent parsing

    Returns:
        {
            'parameter_name': 'capacity',  # Which dict to modify
            'entity': 'Plant North',       # Which entity in that dict
            'entity_type': 'plants'        # Which set the entity belongs to
        }
    """
    # LLM prompt to extract parameter from query
    system = """
    Given a sensitivity analysis query and available parameters, identify:
    1. Which parameter to analyze (capacity, demand, cost, processing_time, etc.)
    2. Which entity is mentioned (Plant North, Job 5, etc.)
    3. Which set that entity belongs to (plants, markets, jobs, machines, etc.)

    Available parameters: {list(params.keys())}
    Available sets: {infer from params structure}
    """

    # Return structured info
    return llm_client.parse_parameter_query(query, params, system)
```

**Implementation steps:**
1. Create `analysis/parameter_detector.py`
2. Add `detect_parameter_from_query()` function
3. Update `sensitivity/engine.py` to use it
4. Update `modification/engine.py` to use it

#### Phase 2: Generic Instance Creation (1-2 hours)

**Goal**: Create ParsedInstance WITHOUT hardcoding set names

**Current (hardcoded):**
```python
# scenarios/engine.py:225-233
instance = ParsedInstance(
    problem_type='TRANSPORTATION',
    solver_id='transport_basic_bipartite',
    sets={
        'I_plants': params['plants'],      # HARDCODED
        'J_markets': params['markets']     # HARDCODED
    },
    params={
        'supply': params['capacity'],      # HARDCODED
        'demand': params['demand'],        # HARDCODED
        'cost': flatten(params['cost'])    # HARDCODED
    }
)
```

**New (dynamic):**
```python
# New file: analysis/instance_builder.py
def build_instance_from_params(params: Dict, problem_type: str, solver_id: str) -> ParsedInstance:
    """
    Dynamically build ParsedInstance from ANY params dict.

    Works by:
    1. Detecting sets (lists in params)
    2. Detecting parameters (dicts/numbers in params)
    3. Mapping param names based on problem_type conventions
    """
    sets = {}
    instance_params = {}

    # Auto-detect sets (lists of entities)
    for key, value in params.items():
        if isinstance(value, list) and value:
            # This is a set (plants, markets, jobs, machines, etc.)
            set_name = _map_to_set_name(key, problem_type)  # e.g., 'plants' → 'I_plants'
            sets[set_name] = value

    # Auto-detect parameters (dicts/numbers)
    for key, value in params.items():
        if isinstance(value, dict):
            # Flatten if nested (for cost matrix, etc.)
            instance_params[key] = _flatten_if_nested(value, sets)
        elif isinstance(value, (int, float)):
            instance_params[key] = value

    return ParsedInstance(
        problem_type=problem_type,
        solver_id=solver_id,
        sets=sets,
        params=instance_params
    )
```

**Implementation steps:**
1. Create `analysis/instance_builder.py`
2. Add `build_instance_from_params()` function
3. Add `_map_to_set_name()` helper (plants → I_plants, jobs → I_jobs, etc.)
4. Add `_flatten_if_nested()` helper
5. Update all 3 engines to use it

#### Phase 3: Generic Parameter Modification (1 hour)

**Goal**: Apply modifications to ANY parameter type

**Current approach:**
```python
# Already mostly generic in llm/enhanced_client.py
# Just needs to handle more parameter types
```

**Improvements needed:**
1. Add support for scheduling params (processing_time, due_date)
2. Add support for knapsack params (weights, values)
3. Make entity detection completely generic

#### Phase 4: Testing (1 hour)

**Create test for scheduling problem:**
```python
# tests/test_analysis_scheduling.py
def test_scheduling_sensitivity():
    """Test sensitivity analysis on scheduling problem"""
    problem = get_problem_by_name('bottling_line_parallel_machines')
    agent = OptimizationAgent(llm)

    result = agent.solve_natural_language(problem['text'])

    # Test sensitivity on processing time
    sa_result = execute_analysis(
        'sensitivity',
        solver=result['solver'],
        params=result['params'],
        solution=result['solution'],
        query='sensitivity on Job 1 processing time',
        llm_client=llm
    )

    assert sa_result['success'] == True
```

**Implementation steps:**
1. Create `tests/test_analysis_scheduling.py`
2. Test sensitivity on processing_time parameter
3. Test what-if on machine assignment
4. Test resolve with modified due dates

#### Phase 5: Documentation (30 min)

Update docstrings to explain problem-agnostic design:
- How parameter detection works
- How instance creation works
- Examples for different problem types

### Estimated Total Time: 5-7 hours

### Implementation Order:
1. **Phase 1** - Parameter detector (most critical, enables everything else)
2. **Phase 2** - Instance builder (second most critical)
3. **Phase 3** - Parameter modification improvements (nice-to-have)
4. **Phase 4** - Scheduling tests (validates it works)
5. **Phase 5** - Documentation (finishing touch)

### Key Design Principles:
- **Zero Hardcoding**: Never check for specific parameter names
- **LLM-Driven**: Use LLM to understand user intent and parameter structure
- **Convention-Based**: Follow OR naming conventions (I_* for source sets, J_* for sink sets)
- **Fail Gracefully**: If parameter detection fails, ask user to clarify

---

## ✅ Implemented Features

### Core System
- **Multi-Stage Solver Architecture** (2025-11-15)
  - Modular solver structure with registry system
  - Separated OR taxonomy from solver capabilities
  - Location: `/solvers/registry.py`, `/solvers/transport/`, `/solvers/scheduling/`

- **3-Layer Feasibility Checking** (2025-11-17) ⭐ PRODUCTION-READY
  - **Layer 0 (Structural)**: Dimensions, empty sets, domain validity
  - **Layer 1 (Problem-specific)**: Supply/demand balance, reachability
  - **Layer 2 (Solver-based)**: LP relaxation feasibility with GLPK
  - Location: `/feasibility/` module
  - Status: All infeasible problems caught correctly

- **LLM Classification System** (2025-11-27) ⭐ PRODUCTION-READY
  - DeepSeek-R1 with structural checklists
  - Accuracy: **100%** on solvable problems
  - Location: `/llm/problem_classifier.py`, `/llm/schemas.py`

- **Analysis Framework** (2025-11-29) ⭐ PRODUCTION-READY (Transportation only)
  - Sensitivity analysis, what-if scenarios, resolve modifications
  - LLM-based intent detection with fuzzy entity matching
  - Interactive retry loops for infeasible scenarios
  - Location: `/analysis/` module
  - Status: **4/4 tests passing** for transportation problems
  - **TODO**: Refactor for problem-agnostic design

### Data & Knowledge
- **OR Problem Repository** (2025-11-27)
  - 35 diverse OR problems with metadata
  - Location: `/tests/or_problem_repository.py`

---

## 🎯 Current Project State

### What's Working Well
- ✅ LLM classification (100% accuracy)
- ✅ Feasibility checking (3-layer system, production-ready)
- ✅ Analysis framework (sensitivity, what-if, resolve) - **Transportation only**
- ✅ Comprehensive test suite (4/4 passing)

### Solver Capabilities
**Currently Solvable:**
- Transportation (bipartite): `transport_basic_bipartite`
- Single-stage scheduling (makespan): `single_stage_ipm_scheduling`

**Need Solvers:**
- Min-cost flow, max flow, shortest path
- Job-shop, flow-shop
- Assignment, knapsack, facility location, VRP

---

**Last Updated**: 2025-11-29
**Project Status**: ✅ Analysis framework production-ready for transportation, needs refactoring for other problem types

---
