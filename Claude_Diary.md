# Claude Development Diary

---

## 2025-11-03

### 🎯 Agentic AI Development Roadmap - Complete Plan

Based on discussion with user, comprehensive plan for building an advanced agentic AI for OR problems.

---

### **PHASE 1: UNBLOCK CLASSIFICATION (CRITICAL - Must Do First)** 🚨

**Current Blocker**: LLM-only classification has 17-25% accuracy on scheduling subcategories
- System rejects solvable problems (single_stage_scheduling)
- Cannot route to correct solvers
- Parameter extraction fails due to wrong problem type detection

#### Tasks:

**1.1 Collect Training Data** ⏱️ 1-2 weeks (IN PROGRESS)
- Target: 90-120 labeled OR problems (60 base + 30-60 adversarial)
- Priority: Heavy focus on SCHEDULING subcategories
- Google Sheet: https://docs.google.com/spreadsheets/d/1_dQ9_0rXrzR6ISr51h6H44eDfQPi2Xh-wLRY0hAHJuU/edit
- Status: Team member collecting data

**1.2 Download and Validate Data** ⏱️ 5-10 minutes
```bash
mkdir -p data_collection
# Download CSV from Google Sheet → data_collection/training_data.csv
# Validate: check counts, categories, scheduling subtypes
```

**1.3 Create Training Scripts** ⏱️ 4-6 hours
- `scripts/train_level1_classifier.py` - Train 9-category classifier
- `scripts/train_subtype_classifiers.py` - Train per-family subcategory classifiers
- `scripts/evaluate_classifiers.py` - Evaluate on phase1 test cases
- Target accuracy: 85-90%+ (vs current 17-25%)

**1.4 Train ML Classifiers** ⏱️ 2-3 hours
- Train Level-1 classifier (categories: TRANSPORTATION, SCHEDULING, etc.)
- Train SCHEDULING subtype classifier (CRITICAL: single_stage vs job_shop vs flow_shop)
- Train other subtype classifiers per family
- Uses existing infrastructure: `or_classify/feature_pipeline.py`, 25 labeling functions

**1.5 Integrate ML Classifier** ⏱️ 2-3 hours
- Replace LLM classification in `agent/core.py:84`
- Implement hybrid voting: ML + LLM for consensus
- Add confidence thresholding
- Fallback to LLM for edge cases

**Success Metrics**:
- ✅ Scheduling subcategories: 90%+ accuracy (vs 17-25% current)
- ✅ Inference time: <50ms (vs 2-5 seconds LLM)
- ✅ single_stage problems correctly routed to solver
- ✅ Phase 1 test suite: 85%+ overall accuracy

---

### **PHASE 1.5: RAG SYSTEM FOR OR KNOWLEDGE** 📚

**Goal**: Load PhD thesis and OR papers to improve LLM's domain understanding

**Why**: Enhance LLM with domain-specific OR knowledge without fine-tuning

#### Tasks:

**1.5.1 Setup RAG Infrastructure** ⏱️ 30 minutes
- Install dependencies: `langchain`, `chromadb`, `pypdf`, `sentence-transformers`
- Install Ollama embedding model: `ollama pull nomic-embed-text` (274MB)
- Create directory structure:
  ```
  knowledge/
    papers/              # User's PDFs go here
    vectorstore/         # Chroma database (auto-created)
  ```

**1.5.2 Build Knowledge Base System** ⏱️ 2 hours
- Create `llm/knowledge_base.py`:
  - Load PDFs from `knowledge/papers/`
  - Chunk documents (1000 chars, 200 overlap)
  - Create embeddings using `nomic-embed-text`
  - Store in Chroma vector database
  - Query interface: `search(query, k=3)` returns relevant chunks
- Create `llm/rag_embeddings.py`:
  - Wrapper for Ollama embeddings
  - Fallback to sentence-transformers
  - Caching for frequently embedded queries

**1.5.3 Integrate RAG into Specialists** ⏱️ 2 hours
- Modify specialists to use knowledge base:
  ```python
  class TransportationSpecialist:
      def __init__(self, llm_client, knowledge_base=None):
          self.kb = knowledge_base

      def extract_parameters(self, text):
          # Get relevant context from papers
          if self.kb:
              context = self.kb.get_context(
                  "transportation problem parameters",
                  max_tokens=800
              )
              system_prompt += f"\n\nRelevant OR knowledge:\n{context}"
  ```
- Apply to: `transportation_specialist.py`, `scheduling_specialist.py`

**1.5.4 Integrate RAG into Agent** ⏱️ 1 hour
- Modify `agent/core.py`:
  ```python
  class OptimizationAgent:
      def __init__(self, llm_client, knowledge_base=None):
          self.kb = knowledge_base
          # Pass KB to specialists
          self.transportation_specialist = TransportationSpecialist(
              llm_client, knowledge_base
          )
  ```
- Initialize KB on startup in `api.py`:
  ```python
  kb = KnowledgeBase("knowledge/papers", "knowledge/vectorstore")
  if not kb.index_exists():
      kb.load_papers()
      kb.build_index()  # 5-10 minutes first time
  agent = OptimizationAgent(llm_client, knowledge_base=kb)
  ```

**1.5.5 Create Management Scripts** ⏱️ 1 hour
- `scripts/rebuild_knowledge_base.py` - Rebuild index when adding papers
- `scripts/query_knowledge.py` - Query KB directly for testing
- `scripts/kb_stats.py` - Show statistics (papers, chunks, size)

**1.5.6 User Actions Required** ⏱️ 5-10 minutes
- Gather PDF files (PhD thesis + OR papers)
- Copy PDFs to `knowledge/papers/` directory
- Run initial indexing: `python scripts/rebuild_knowledge_base.py`

**Expected Benefits**:
- ✅ Better classification (uses definitions from papers)
- ✅ Better parameter extraction (follows notation from papers)
- ✅ Better explanations (uses terminology from papers)
- ✅ Can cite sources: "According to [thesis, p.45]..."

**Resource Requirements**:
- Storage: ~400-600 MB (papers + vector DB + embedding model)
- RAM: ~600-700 MB additional
- Initial indexing: 5-10 minutes (one-time)
- Query overhead: ~50-100ms per retrieval

**Success Metrics**:
- ✅ Successfully indexes all provided papers
- ✅ Retrieval accuracy: Returns relevant chunks for queries
- ✅ Integration: All specialists can access KB
- ✅ Performance: <100ms retrieval time

---

### **PHASE 2: CLARIFICATION DIALOGUE (Agentic Feature)** 🤔

**Goal**: LLM asks questions to ensure understanding before solving

#### Tasks:

**2.1 Create Clarification Handler** ⏱️ 1 day
- New file: `llm/clarification_handler.py`
- Detects missing/ambiguous parameters after extraction
- Generates targeted questions (not generic)
- Example:
  ```
  User: "Optimize shipping from 3 factories to 5 customers"
  Agent detects missing: capacities, demands, costs
  Agent asks:
  1. "What are the supply capacities for each factory?"
  2. "What are the demands at each customer?"
  3. "Do you have shipping costs, or should I calculate from distances?"
  ```

**2.2 Integrate into Agent Pipeline** ⏱️ 2-3 hours
- Modify `agent/core.py` extraction flow:
  ```python
  # After extraction
  params = self.llm.extract_parameters(...)
  if clarification_handler.needs_clarification(params):
      questions = clarification_handler.generate_questions(params, description)
      return {"type": "clarification_needed", "questions": questions}
  ```

**2.3 Add API Support** ⏱️ 2-3 hours
- New endpoint: `POST /agent/clarify`
- Web UI: Show questions to user, collect answers
- Re-extract parameters with answers incorporated
- Continue with solving

**2.4 Add Question Types** ⏱️ 1 day
- **Missing fields**: "What is the capacity at Factory A?"
- **Ambiguous values**: "You said 'several' - can you specify exact numbers?"
- **Validation**: "Should I minimize cost or time?"
- **Constraints**: "Are there any restrictions on routes/assignments?"

**Features**:
- Problem-specific questions (transportation vs scheduling vs assignment)
- Context-aware (uses already-extracted info)
- Limited to 3-5 questions max (avoid overwhelming)
- LLM generates validation questions for edge cases

**Success Metrics**:
- ✅ Detects 90%+ of missing required fields
- ✅ Reduces extraction errors by 50%+
- ✅ User satisfaction: problems solve correctly on first try

---

### **PHASE 3: MULTI-TURN CONVERSATION MEMORY** 💬

**Goal**: Agent remembers context across multiple interactions

#### Tasks:

**3.1 Implement Conversation State** ⏱️ 1 day
- Extend `agent/core.py`:
  ```python
  class OptimizationAgent:
      def __init__(self):
          self.conversation_memory = []       # Full history
          self.solutions_cache = {}           # By problem ID
          self.user_preferences = {}          # Learned patterns
  ```

**3.2 Add Session Management** ⏱️ 1 day
- Session IDs for multi-turn conversations
- Store in-memory (later: Redis/database)
- API: `POST /agent/session/create`, `POST /agent/session/{id}/message`

**3.3 Context-Aware Follow-ups** ⏱️ 1-2 days
- "Solve the same problem but for Chicago instead"
- "Compare this solution to the previous one"
- "What if I double the capacity we discussed earlier?"
- Reference previous problems: "Use the same costs as last time"

**3.4 User Preference Learning** ⏱️ 1-2 days
- Track: always wants sensitivity analysis, prefers certain formats
- Auto-suggest based on history
- "Last time you asked for charts - should I generate them now?"

**Success Metrics**:
- ✅ Correctly references previous problems (90%+ accuracy)
- ✅ Maintains context for 5+ turns
- ✅ Learns user preferences after 3-5 interactions

---

### **PHASE 4: PROACTIVE ANALYSIS SUGGESTIONS** 📊

**Goal**: Agent suggests analyses without being asked

#### Tasks:

**4.1 Post-Solve Analysis Detection** ⏱️ 1 day
- After solving, analyze solution structure:
  ```python
  def suggest_analyses(solution, problem_type):
      suggestions = []
      if has_bottleneck(solution):
          suggestions.append("I noticed X is at 100% capacity. Sensitivity analysis?")
      if has_slack(solution):
          suggestions.append("Y has unused capacity. Want to see optimization opportunities?")
      return suggestions
  ```

**4.2 Problem-Specific Suggestions** ⏱️ 1 day
- Transportation: bottleneck analysis, route efficiency
- Scheduling: makespan analysis, utilization charts
- Assignment: cost distribution, workload balance

**4.3 Interactive Analysis Flow** ⏱️ 1 day
- Show suggestions as clickable options
- User selects → agent runs analysis automatically
- No need to re-phrase as questions

**Success Metrics**:
- ✅ Suggests relevant analyses 80%+ of the time
- ✅ User engagement: 40%+ click-through on suggestions

---

### **PHASE 5: AUTONOMOUS PROBLEM REFINEMENT** 🔄

**Goal**: Iterative improvement loop with user feedback

#### Tasks:

**5.1 Solution Feedback Collection** ⏱️ 1 day
- After showing solution: "What would you like to change?"
- Parse feedback: "Make Seattle cheaper", "Increase capacity", "Add constraint"

**5.2 Iterative Solving Loop** ⏱️ 2 days
```python
while not user_satisfied:
    solution = solve(problem)
    show(solution)
    feedback = ask_user("What would you like to change?")
    if "nothing" or "looks good" in feedback:
        break
    problem = modify_based_on_feedback(problem, feedback)
```

**5.3 Smart Modification Detection** ⏱️ 1-2 days
- Use LLM to parse modification requests
- "Add 100 to Seattle capacity" → update params['supply']['Seattle'] += 100
- "Remove route from A to B" → add constraint

**Success Metrics**:
- ✅ Correctly interprets 85%+ of modification requests
- ✅ Average 2-3 iterations to user satisfaction

---

### **PHASE 6: ADD MORE PROBLEM TYPES** 🧩

**Goal**: Expand solver capabilities beyond Transportation and Scheduling

**Priority order** (infrastructure already exists):

**6.1 Assignment Problems** ⏱️ 3-4 days
- Labeling functions: ✅ Ready (`or_classify/lfs/assignment_lfs.py`)
- Solver: Create `solvers/assignment_solver.py` (Hungarian algorithm or LP)
- Specialist: Create `llm/assignment_specialist.py` (extract workers, tasks, costs)
- Test cases: Add to `tests/phase1_test_cases.py`

**6.2 Knapsack Problems** ⏱️ 3-4 days
- Labeling functions: ✅ Ready (`or_classify/lfs/knapsack_lfs.py`)
- Solver: Create `solvers/knapsack_solver.py` (dynamic programming or MIP)
- Specialist: Create `llm/knapsack_specialist.py` (extract items, weights, values, capacity)

**6.3 Network Flow Problems** ⏱️ 4-5 days
- Labeling functions: ✅ Ready (`or_classify/lfs/network_flow_lfs.py`)
- Solver: Create `solvers/network_flow_solver.py` (max flow, min-cost flow)
- Specialist: Create `llm/network_flow_specialist.py` (extract nodes, edges, capacities)

**Per problem type checklist**:
1. Create solver implementing `OptimizationSolver` interface
2. Create LLM specialist for parameter extraction
3. Update `solvers/capabilities.py` with subcategories
4. Add test cases (5-10 examples)
5. Train classifier on new examples (20+ needed)
6. Add to solver registry in `solvers/__init__.py`

**Success Metrics** (per problem type):
- ✅ Solver produces correct solutions on test cases
- ✅ Parameter extraction accuracy: 85%+
- ✅ Classification accuracy: 85%+

---

### **PHASE 7: ADVANCED AGENTIC FEATURES** 🚀

**7.1 Multi-Objective Optimization** ⏱️ 3-5 days
- Detect multiple objectives: "Minimize cost AND carbon emissions"
- Ask user about priorities or generate Pareto front
- Visualize trade-offs
- Let user pick point on Pareto curve

**7.2 Explanation & Education** ⏱️ 2-3 days
- "Why did you choose this solution?"
- Explain optimization technique used
- Show mathematical formulation
- Offer to teach concepts: "Want to learn about LP?"

**7.3 Autonomous Tool Selection** ⏱️ 3-4 days
- Agent chooses best solver/algorithm based on problem size
- Example: "10,000 nodes detected. Recommend Gurobi (fast) vs GLPK (free). Which?"
- Explain trade-offs: exact vs heuristic, speed vs optimality

**7.4 Sensitivity Analysis Automation** ⏱️ 2-3 days
- Automatically identify critical parameters
- Run sensitivity analysis without being asked
- Report: "Your solution is most sensitive to Seattle capacity and freight costs"

**7.5 Constraint Negotiation** ⏱️ 3-4 days
- If problem is infeasible: identify conflicting constraints
- Suggest which constraints to relax
- "Your demands exceed supply by 50 units. Options: 1) Increase supply, 2) Reduce demand, 3) Allow partial fulfillment"

---

### **IMPLEMENTATION TIMELINE**

**Week 1-2**: Phase 1 - Unblock Classification
- Collect data (ongoing)
- Create training scripts
- Train ML classifiers
- Integrate into system
- **Deliverable**: 85-90%+ classification accuracy

**Week 3**: Phase 2 - Clarification Dialogue
- Create clarification handler
- Integrate into agent pipeline
- Add API support
- **Deliverable**: Agent asks targeted questions for incomplete problems

**Week 4**: Phase 3 - Conversation Memory
- Implement state management
- Session handling
- Context-aware follow-ups
- **Deliverable**: Multi-turn conversations work

**Week 5**: Phase 4 & 5 - Proactive Analysis + Iterative Refinement
- Post-solve suggestions
- Feedback loop
- Smart modifications
- **Deliverable**: Interactive improvement workflow

**Week 6-8**: Phase 6 - New Problem Types
- Assignment (Week 6)
- Knapsack (Week 7)
- Network Flow (Week 8)
- **Deliverable**: 3 additional problem types fully working

**Week 9-10**: Phase 7 - Advanced Features
- Multi-objective
- Explanations
- Tool selection
- **Deliverable**: Advanced agentic capabilities

---

### **CURRENT STATUS (2025-11-03)**

#### ✅ What Works:
- Transportation optimization (end-to-end)
- Scheduling solver (single-stage)
- Natural language understanding
- Intent detection and routing
- Follow-up question handling
- Dynamic visualizations
- Web interface with file upload

#### ⚠️ Blockers:
- **CRITICAL**: Classification accuracy (17-25% on scheduling subtypes)
  - Waiting for training data (60-120 examples)
  - Infrastructure ready: feature pipeline + 25 labeling functions

#### 🚧 Next Immediate Actions:
1. **Check training data status** in Google Sheet
2. **Create training scripts** (if data ready)
3. **Train ML classifiers** (2-3 hours)
4. **Implement clarification handler** (in parallel with training)

---

### **ARCHITECTURE DECISIONS**

#### Hybrid ML + LLM Approach:
- **ML Classifier**: Fast (<50ms), accurate on trained categories
- **LLM**: Flexible, handles parameter extraction, explanations, follow-ups
- **Why both?**: ML for speed/accuracy on classification, LLM for everything else

#### Clarification Questions:
- Detect missing fields automatically
- Generate problem-specific questions
- Limit to 3-5 questions max
- Use LLM for validation questions

#### Conversation Memory:
- In-memory for prototyping
- Later: Redis or database for production
- Session-based (not global state)

---

## Historical Context (2025-10-11 to 2025-10-18)

**Key milestones** (see full details in git history if needed):
- 2025-10-11: Test organization, Overall_Test.py creation (862 lines)
- 2025-10-12: Hybrid classifier design, taxonomy/alias system, 25 labeling functions
- 2025-10-18: Hierarchical classification, discovered LLM cannot distinguish scheduling subtypes (20-30% accuracy)

**Note**: Detailed logs archived. Focus remains on current priorities.

---

## Historical Context (2025-10-12)

**Hybrid Classifier Development** (see git history for details):
- Built 25 labeling functions (LFs) across 9 problem families
- Created normalizer, LF framework, feature pipeline
- Baseline: Pure LLM 80% accuracy, 7-10s per classification
- Infrastructure ready for ML training (blocked on training data)

**Note**: Archived detailed Phase 1b/1c logs. Core infrastructure complete but ML training blocked.

## 2025-10-18

### Main Objective: Implement Hierarchical Classification System

**Goal**: Create a two-level classification system where problems are classified into specific subcategories (e.g., `job_shop`, `single_stage_scheduling`) but organized under broader categories (e.g., SCHEDULING) for routing to appropriate solvers.

### Problems Discovered

#### **CRITICAL: LLM Classifier Cannot Distinguish Scheduling Subcategories**

**Issue**: Current zero-shot LLM classification fails to distinguish between scheduling subtypes with acceptable accuracy.

**Test Results** (2025-10-18):
```
[1/18] Single-Stage: Batch Processing
❌ Result: job_shop (expected: single_stage_scheduling) - 95% confidence

[2/18] Single-Stage: Chemical Reactors
❌ Result: job_shop (expected: single_stage_scheduling) - 100% confidence

[4/18] Flow Shop Scheduling
❌ Result: job_shop (expected: flow_shop) - 100% confidence
```

**Accuracy**: ~20-30% on scheduling subcategories (3/18 correct)
**Impact**: Users cannot solve problems we CAN solve because classifier routes them incorrectly

**Root Cause**: Zero-shot LLM classification without training examples cannot reliably distinguish fine-grained scheduling subtypes. The structural differences between:
- `single_stage_scheduling` (we CAN solve - single processing step, IPM model)
- `job_shop` (we CANNOT solve - multi-stage with operation sequences)
- `flow_shop` (we CANNOT solve - fixed machine sequence)
- `shift_rostering` (we CANNOT solve - employee scheduling)
- `project_scheduling` (we CANNOT solve - PERT/CPM with precedence)

...are too subtle for zero-shot prompting.

### Accomplishments

#### 1. Hierarchical Classification Architecture (Completed ✅)

**Design**: Two-level system
- **Category Level**: Broad problem families for organization (SCHEDULING, TRANSPORTATION, etc.)
- **Subcategory Level**: Specific problem types for classification (job_shop, single_stage_scheduling, etc.)
- **Solver Level**: Generic solvers that can handle multiple subcategories

**Implementation**:

1. **Updated Classification Schema** (`llm/schemas.py`)
   - Added scheduling subcategories to `CLASS_ENUM`:
     - `job_shop` - Multi-stage with operation sequences
     - `flow_shop` - Fixed machine sequence
     - `single_stage_scheduling` - Single processing step (solvable)
     - `shift_rostering` - Employee/nurse scheduling
     - `project_scheduling` - PERT/CPM with precedence

2. **Created Solver Capabilities Mapping** (`solvers/capabilities.py` - 128 lines)
   - Documents which solvers can handle which subcategories
   - `SOLVER_CAPABILITIES` dict maps solver → supported subcategories
   - Helper functions:
     - `get_solver_capabilities(solver_name)` - Get capabilities
     - `can_solver_handle(solver, subcategory)` - Check if solvable
     - `get_subcategory_description(problem, subcat)` - Human-readable descriptions

   Example:
   ```python
   "scheduling": {
       "subcategories": [
           "single_stage_scheduling",     # WE CAN SOLVE
           "batch_scheduling",
           "parallel_machine_simple",
       ],
       "cannot_solve": [
           "job_shop",                    # CANNOT SOLVE
           "flow_shop",
           "project_scheduling",
           "shift_rostering",
       ]
   }
   ```

3. **Implemented Routing Logic** (`agent/core.py:375-391`)
   - `_map_to_solver()` function maps subcategories to actual solvers
   - Routes all scheduling subcategories → `scheduling` solver
   - Allows classifier to be specific while solver handles multiple types

   ```python
   def _map_to_solver(self, problem_type: str) -> str:
       scheduling_types = [
           "job_shop", "flow_shop", "single_stage_scheduling",
           "shift_rostering", "project_scheduling"
       ]
       if problem_type.lower() in scheduling_types:
           return "scheduling"
       return problem_type
   ```

4. **Updated Test Cases** (`tests/phase1_test_cases.py`)
   - Changed all 18 scheduling tests from generic `"expected": "scheduling"` to specific subcategories
   - Added `"category": "SCHEDULING"` field for context
   - Added `"solvable": True/False` flag
   - Added `"expected_solution"` validation criteria

   Example:
   ```python
   {
       "name": "Single-Stage: Batch Processing",
       "expected": "single_stage_scheduling",  # Specific subcategory
       "category": "SCHEDULING",               # Organizational category
       "solvable": True,                       # We CAN solve this
       "expected_solution": {
           "status": "OPTIMAL",
           "makespan_max": 4.0,
           "all_on_time": True,
           "num_assignments": 3
       }
   }
   ```

5. **Enhanced Test Runner** (`tests/test_phase1_runner.py`)
   - Added command-line arguments: `--categories`, `--no-save`
   - Updated output format: `job_shop (expected: job_shop [SCHEDULING])`
   - Added subcategory routing in `try_solve_problem()`
   - Only attempts to solve problems marked `solvable=True`
   - Verifies solutions against expected criteria

#### 2. Documentation Updates

**Updated**: `RESUME_WHEN_DATA_READY.md`
- Added **CRITICAL BLOCKER** section documenting classification failure
- Changed status of ML training from "optional" to **MANDATORY**
- Added specific success metrics for scheduling subtype classifier:
  - job_shop vs single_stage_scheduling precision ≥ 0.90
  - Overall accuracy ≥ 0.85 across all 5 scheduling subtypes
- Documented current baseline: ~20-30% accuracy on scheduling subcategories
- Added "Why This is Now Blocking" section with concrete example of user impact

### Tasks Completed

#### Architecture Implementation
- [x] Designed hierarchical classification system (categories + subcategories)
- [x] Created `solvers/capabilities.py` mapping file
- [x] Updated `llm/schemas.py` with scheduling subcategories
- [x] Implemented `_map_to_solver()` routing logic in `agent/core.py`
- [x] Updated all 18 scheduling test cases with subcategories
- [x] Added CLI arguments to test runner
- [x] Enhanced test output to show category context

#### Testing & Discovery
- [x] Ran scheduling classification tests
- [x] Discovered critical classification failure (20-30% accuracy)
- [x] Documented impact on user experience
- [x] Updated documentation with blocker status

### Critical Finding: Why ML Training is Now Mandatory

**Before Testing** (Assumption):
- LLM could classify subcategories with 70-80% accuracy
- ML training would be "nice to have" for improvement

**After Testing** (Reality):
- LLM classifies subcategories with ~20-30% accuracy
- ML training is **MANDATORY** to make system functional

**User Impact Scenario**:
```
Current (Broken):
1. User: "Schedule 3 production orders on 2 processing units..."
   → single_stage_scheduling (WE CAN SOLVE)
2. Classifier: job_shop (95% confidence) ❌ WRONG
3. Parameter extraction fails (wrong structure expected)
4. User gets: "Parameter extraction failed" ❌
5. Result: User cannot solve a problem we CAN solve

After ML Training (Expected):
1. User: "Schedule 3 production orders on 2 processing units..."
   → single_stage_scheduling (WE CAN SOLVE)
2. Trained classifier: single_stage_scheduling (90% confidence) ✅
3. Correct parameters extracted (right structure)
4. Problem solved successfully ✅
5. Result: User gets solution ✅
```

### Remaining Tasks (Now Blocking)

#### **CRITICAL: Train Scheduling Subtype Classifier**
- [ ] Collect training data with 8-10 examples each of:
  - `single_stage_scheduling` (solvable)
  - `job_shop` (not solvable)
  - `flow_shop` (not solvable)
  - `shift_rostering` (not solvable)
  - `project_scheduling` (not solvable)
- [ ] Train classifier using feature pipeline + LFs
- [ ] Target: ≥90% precision on job_shop vs single_stage_scheduling
- [ ] Target: ≥85% overall accuracy across all subtypes

#### Infrastructure (Ready for ML)
- ✅ Feature pipeline built (`or_classify/feature_pipeline.py`)
- ✅ 25 labeling functions implemented
- ✅ Test framework with 18 scheduling cases
- ✅ Solver capabilities documented
- ✅ Routing logic implemented

### Technical Notes

#### Why Zero-Shot LLM Classification Fails

**Problem**: Scheduling subcategories have overlapping surface features:
- All mention: "schedule", "machines", "processing times", "minimize makespan"
- Differences are structural (single-stage vs multi-stage, precedence vs not)
- LLM without examples defaults to most common type (`job_shop`)

**Evidence from Test Output**:
```
single_stage_scheduling test:
  LLM detected: "changeover_times", "multiple operations per order"
  LLM classified: job_shop (95%)
  Reality: Single processing step per order (single_stage_scheduling)
```

**Why ML Will Work**:
- Can learn subtle patterns from training examples
- Feature pipeline includes LF signals (structure detection)
- Supervised learning with labeled data beats zero-shot prompting
- Expected improvement: 20-30% → 85-90% accuracy

#### Architecture Benefits

**Clean Separation of Concerns**:
1. **Classification Layer**: Returns specific subcategory (e.g., `job_shop`)
2. **Routing Layer**: Maps subcategory to solver (e.g., `job_shop` → `scheduling`)
3. **Solver Layer**: Attempts solution or returns capability error

**Advantages**:
- Classifier can be specific without knowing about solvers
- Adding new subcategories doesn't require new solvers
- Clear error messages: "job_shop problems cannot be solved by current scheduling solver"
- Easy to track which problem types we can/cannot handle

### Files Created/Modified This Session

**Created**:
1. `solvers/capabilities.py` (128 lines) - Solver capability mapping

**Modified**:
2. `llm/schemas.py` - Added scheduling subcategories to CLASS_ENUM
3. `agent/core.py` - Added `_map_to_solver()` routing function
4. `tests/phase1_test_cases.py` - Updated all scheduling cases with subcategories
5. `tests/test_phase1_runner.py` - Added CLI args and subcategory routing
6. `RESUME_WHEN_DATA_READY.md` - Documented critical blocker and mandatory ML training

**Total Changes**: 1 new file, 5 files modified, ~200 lines added/changed

### Context for Next Session

#### Current State
- **Architecture**: ✅ Complete and clean
- **Infrastructure**: ✅ Ready for ML training
- **Blocker**: ❌ Classifier cannot distinguish scheduling subcategories
- **Status**: Waiting for training data to train scheduling subtype classifier

#### What's Ready
- Feature pipeline with TF-IDF + LFs + engineered features
- 25 labeling functions providing structural signals
- 18 test cases for evaluation
- Solver capabilities documented
- Routing logic implemented

#### What's Blocking
- Training data collection (need 40-50 labeled scheduling problems)
- ML model training (2-3 hours once data ready)
- Cannot proceed with production deployment until classification works

#### Immediate Next Steps (When Data Ready)
1. Train scheduling subtype classifier
2. Test on 18 scheduling cases (target: 85-90% accuracy)
3. If successful, extend to other problem families
4. Deploy to production

#### Performance Baselines
- **Category-level** (SCHEDULING vs TRANSPORTATION): 80% (acceptable)
- **Subcategory-level** (job_shop vs single_stage): ~25% (BROKEN)
- **Target after training**: ≥85% subcategory accuracy

---

**Session Duration**: ~2 hours
**Primary Focus**: Hierarchical classification architecture + critical blocker discovery
**Status**: Architecture complete; ML training now mandatory (was optional)

---

## 2025-11-08

### 🎯 RAG System Implementation (Retrieval-Augmented Generation)

**Goal**: Enhance LLM understanding by giving it access to PhD thesis and OR papers for better problem classification, parameter extraction, and explanations.

#### ✅ Completed Tasks:

**Infrastructure Setup**:
- ✅ Added RAG dependencies to `requirements.txt`:
  - `langchain==0.3.7`
  - `langchain-community==0.3.7`
  - `chromadb==0.5.20`
  - `pypdf==5.1.0`
  - `sentence-transformers==3.3.1`
- ✅ Created `knowledge/` directory structure:
  - `knowledge/papers/` - for PDF files
  - `knowledge/vectorstore/` - auto-generated vector DB
- ✅ Updated `.gitignore` to exclude PDFs and vectorstore

**Core RAG System**:
- ✅ Created `llm/knowledge_base.py` (278 lines):
  - PDF loading from `knowledge/papers/`
  - Document chunking (1000 chars, 200 overlap)
  - Vector embeddings using sentence-transformers
  - ChromaDB storage
  - Semantic search functionality
  - Context retrieval for LLM prompts

**Management Tools**:
- ✅ Created `scripts/manage_knowledge_base.py`:
  - `build` - Build index from PDFs
  - `rebuild` - Rebuild index
  - `stats` - Show status
  - `search` - Test retrieval

**LLM Integration**:
- ✅ Modified `llm/transportation_specialist.py`:
  - Added `knowledge_base` parameter to `__init__()`
  - Retrieves context before parameter extraction
  - Query: "transportation problem parameters supply demand cost"
- ✅ Modified `llm/scheduling_specialist.py`:
  - Added `knowledge_base` parameter to `__init__()`
  - Retrieves context before parameter extraction
  - Query: "scheduling problem makespan processing time changeover"
- ✅ Modified `llm/enhanced_client.py`:
  - Accepts `knowledge_base` parameter
  - Passes KB to all specialists

**Documentation**:
- ✅ Created `RAG_GUIDE.md` (337 lines):
  - Complete usage guide
  - Technical details
  - Configuration options
  - Troubleshooting
- ✅ Created `knowledge/README.md`:
  - Quick reference for adding PDFs
  - Management commands

**Sample PDFs for Testing**:
- ✅ Downloaded 5 industrial OR PDFs (6.6 MB total):
  1. `intro_to_optimization.pdf` (800 KB) - MIT optimization fundamentals
  2. `supply_chain_optimization_berkeley.pdf` (333 KB) - Berkeley computational case studies
  3. `nike_supply_chain_case_study.pdf` (1.8 MB) - Nike responsive supply chain
  4. `ghsupply_chain_optimization.pdf` (976 KB) - Global health supply chain
  5. `production_scheduling_case_study.pdf` (2.8 MB) - CMU production scheduling

**RAG Index Built**:
- ✅ Successfully built vector index:
  - **373 pages** loaded from 5 PDFs
  - **719 chunks** created
  - Saved to `knowledge/vectorstore/`
- ✅ Verified search works:
  - Test query "transportation problem" → Found relevant chunks from Berkeley PDF
  - Test query "production scheduling makespan" → Found relevant chunks from CMU PDF

**Test Integration**:
- ✅ Modified `tests/Overall_Test.py`:
  - Loads knowledge base on startup
  - Passes KB to EnhancedLLMClient
  - Shows "✓ RAG knowledge base loaded (5 PDFs, 719 chunks)" on init

#### 🔧 Issues Found (Need Fixing Tomorrow):

**Bug in Transportation Specialist**:
- ❌ F-string formatting error in `llm/transportation_specialist.py:36-42`
- **Problem**: Lines use `{plant}` and `{market}` inside f-string, Python tries to evaluate as variables
- **Error**: `name 'plant' is not defined`
- **Fix needed**: Escape with double braces: `{{plant}}`, `{{market: {{number}}}}`
- **Location**: Lines 40-42 in prompt template

**Test Status**:
- ✅ RAG loading works (ChromaDB queries successful)
- ✅ Knowledge base integration works
- ❌ Overall_Test.py fails during parameter extraction due to f-string bug
- ⚠️ ChromaDB telemetry errors (harmless, can be ignored)

#### 📋 TODO for Tomorrow:

**Critical Fixes**:
1. **Fix f-string bug in `llm/transportation_specialist.py`**:
   ```python
   # Line 40-42: Change from
   - capacity: {plant: number}
   - demand: {market: number}
   - cost: {plant: {market: number}}

   # To:
   - capacity: {{plant: number}}
   - demand: {{market: number}}
   - cost: {{plant: {{market: number}}}}
   ```

**Testing**:
2. **Run complete test suite**:
   ```bash
   cd tests
   python Overall_Test.py  # Should pass with RAG context
   python test_complete_workflow.py
   python test_with_llm_analysis_requests.py
   ```

3. **Verify RAG is being used**:
   - Check that LLM prompts include RAG context
   - Monitor retrieval quality (are relevant chunks being found?)
   - Test with transportation and scheduling problems

**Optional Enhancements**:
4. **Add user's PhD thesis**:
   ```bash
   cp ~/path/to/thesis.pdf knowledge/papers/
   python scripts/manage_knowledge_base.py rebuild
   ```

5. **Optimize RAG settings** (if needed):
   - Adjust `max_tokens` in specialists (currently 500)
   - Tune chunk size/overlap if retrieval quality is poor
   - Test different embedding models if needed

6. **Suppress ChromaDB telemetry warnings**:
   - Set environment variable or update ChromaDB settings
   - These are harmless but noisy in output

#### 📊 RAG System Stats:

**Files Created/Modified**: 9 files
- 3 new files: `llm/knowledge_base.py`, `scripts/manage_knowledge_base.py`, `RAG_GUIDE.md`
- 3 modified LLM files: `enhanced_client.py`, `transportation_specialist.py`, `scheduling_specialist.py`
- 1 modified test: `Overall_Test.py`
- 2 docs: `knowledge/README.md`, `requirements.txt`

**Storage**:
- PDFs: 6.6 MB
- Vector DB: ~15-20 MB
- Embedding model: ~90 MB (cached)

**Performance**:
- Index build: ~2 minutes (373 pages → 719 chunks)
- First search: ~1-2 seconds (model loading)
- Subsequent searches: ~100ms

**Integration Points**:
- TransportationSpecialist: Queries "transportation problem parameters supply demand cost"
- SchedulingSpecialist: Queries "scheduling problem makespan processing time changeover"
- Future specialists: Will automatically get RAG support

---

**Session Duration**: ~3 hours
**Primary Focus**: Complete RAG system implementation
**Status**: 95% complete - one f-string bug to fix, then ready for production use

---

## 2025-11-09

### 🎯 Session: RAG Completion, Problem Repository, Test Organization

#### ✅ Completed Tasks:

**RAG System Finalization**:
- Fixed f-string bugs in `transportation_specialist.py` (lines 40-42, 54)
- Fixed f-string bugs in `scheduling_specialist.py` (lines 40-46, 56)
- Built RAG index with 8 PDFs: 5,008 pages → 20,399 chunks
- Added major textbooks: Ahuja Network Flows (46MB), Floudas Encyclopedia (62MB)
- Converted .djvu to PDF, extracted .rar archives
- All tests now run successfully with RAG context

**OR Problem Repository** (`tests/or_problem_repository.py` - 1,184 lines):
- Created centralized repository: 21 problems across 11 categories
- Added rich metadata: units, scale, balanced status, tags
- Added expected_schema: sets, params, vars, objective, constraints
- Implemented Enums: ProblemCategory, ProblemType
- Added argparse CLI: `--list`, `--get`, `--category`, `--solvable`
- Validation functions and helper utilities
- Comprehensive test harness (`test_classification.py`)

**Test Organization & Documentation**:
- Renamed tests descriptively:
  - `Overall_Test.py` → `test_llm_reasoning_chain.py`
  - `test_complete_workflow.py` → `test_end_to_end_workflow.py`
  - `test_with_llm_analysis_requests.py` → `test_llm_analysis_understanding.py`
  - `test_phase1_runner.py` → `test_problem_classification_runner.py`
- Updated all 7 test headers with actual outputs (laconic format)
- Documented expected results: accuracy %, confidence, plots, analyses
- Marked legacy files: `phase1_test_cases.py`, `transportation_test_cases.py`
- All test descriptions in file headers (NO separate MD files per user request)

**Test Execution Results**:
- `test_llm_reasoning_chain.py`: ✓ 6 prompts, €4,750, 3 plots, 80-95% confidence
- `test_end_to_end_workflow.py`: ✓ €4,750, 3 plots, avg €2.79/bottle
- `test_llm_analysis_understanding.py`: ✓ 7 requests, all follow-ups detected
- `test_classification.py --solvable`: ✓ 100% accuracy on 4 problems
- Pytest tests: Import errors (need sys.path fixes)

#### 📊 Current Project State Assessment:

**Strengths** (7/10):
- Well-organized test structure, clear naming
- Centralized problem repository with metadata
- RAG system operational (8 textbooks, 20K+ chunks)
- Modular LLM architecture (intent routing, specialists, follow-up handler)
- Good classification capability (transportation, scheduling)

**Weaknesses**:
- Import path issues (2 pytest tests fail)
- Test data duplication (legacy files should be migrated/deleted)
- Slow tests (`test_problem_classification_runner.py` too slow)
- Limited solver coverage (only transportation + scheduling)
- RAG integration not demonstrated in tests
- No error recovery tests
- No CI/CD pipeline

#### 🎯 Priorities (Added to TODO):

**HIGH PRIORITY**:
1. Fix import issues - Add `__init__.py` files, use relative imports
2. Consolidate test data - Migrate/delete `phase1_test_cases.py`, `transportation_test_cases.py`
3. Speed up tests - Use pytest fixtures, add parallelization
4. Add CI/CD - GitHub Actions for automated testing
5. Test RAG integration - Show RAG retrieval → LLM usage in tests

**MEDIUM PRIORITY**:
6. Expand solver coverage - Add knapsack, assignment solvers
7. Add performance tests - Track classification speed, solving time
8. Validation tests - Check plot correctness, solution feasibility
9. Error handling tests - Test graceful degradation

**LOW PRIORITY**:
10. Test documentation - pytest-html for reports
11. Coverage metrics - pytest-cov
12. Load testing - Concurrent requests

#### 📝 Files Modified:
- Fixed: 2 specialist files (f-string bugs)
- Created: `or_problem_repository.py`, `test_classification.py`
- Renamed: 4 test files
- Updated: 7 test headers with actual outputs
- Documentation: Claude_Diary.md

---

**Session Duration**: ~3 hours
**Primary Focus**: RAG completion, problem repository, test organization, project assessment
**Status**: Core functionality solid, needs production polish (imports, CI/CD, broader coverage)

---

## 📋 TODO: Development Roadmap

### 🔴 HIGH PRIORITY (Production Blockers)

1. **Fix Import Issues** ⏱️ 1-2 hours
   - Add `__init__.py` files to all packages (llm/, agent/, solvers/, or_classify/)
   - Fix sys.path issues in pytest tests
   - Enable: `test_llm_refactoring.py`, `test_normalizer.py`

2. **Consolidate Test Data** ⏱️ 2-3 hours
   - Migrate useful cases from `phase1_test_cases.py` to `or_problem_repository.py`
   - Migrate useful cases from `transportation_test_cases.py` to repository
   - Delete legacy files after migration
   - Update `test_problem_classification_runner.py` to use repository

3. **Speed Up Tests** ⏱️ 2-3 hours
   - Add pytest fixtures for shared LLM client
   - Implement `@pytest.mark.slow` for slow tests
   - Add parallelization with pytest-xdist
   - Target: <5min for full test suite

4. **CI/CD Pipeline** ⏱️ 3-4 hours
   - Create `.github/workflows/test.yml`
   - Run tests on push/PR
   - Check for: test failures, import errors, performance regression
   - Add status badge to README

5. **Demonstrate RAG Integration** ⏱️ 2-3 hours
   - Create `test_rag_retrieval.py` showing:
     - User asks question about OR concept
     - RAG retrieves relevant textbook section
     - LLM uses context in response
   - Add test showing improved parameter extraction with RAG
   - Document RAG contribution to accuracy

### 🟡 MEDIUM PRIORITY (Expand Capabilities)

6. **Expand Solver Coverage** ⏱️ 2-3 days per solver
   - **Knapsack Solver**: 0/1, bounded, unbounded variants
   - **Assignment Solver**: Hungarian algorithm or LP-based
   - Create specialists: `knapsack_specialist.py`, `assignment_specialist.py`
   - Add to repository: 5+ problems per type
   - Test: Classification accuracy ≥85%, solving correctness 100%

7. **Performance Testing** ⏱️ 1-2 days
   - Create `test_performance.py`:
     - Classification speed: target <100ms
     - Parameter extraction: target <2s
     - Solving time: track by problem size
   - Add pytest benchmark integration
   - Set performance regression gates

8. **Solution Validation Tests** ⏱️ 1-2 days
   - **Plot validation**: Check axes, labels, data ranges
   - **Solution feasibility**: Verify constraints satisfied
   - **Optimality checks**: Compare with known solutions
   - Add to test suite with known-good baseline

9. **Error Handling Tests** ⏱️ 2-3 days
   - **Connection failures**: Ollama down, timeout
   - **Malformed input**: Invalid JSON, missing fields
   - **Infeasible problems**: Supply < demand
   - **Graceful degradation**: Partial results when possible

### 🟢 LOW PRIORITY (Quality of Life)

10. **Test Documentation** ⏱️ 1 day
    - Add pytest-html for nice reports
    - Generate coverage reports with badges
    - Add timing breakdowns per test

11. **Coverage Metrics** ⏱️ 1 day
    - Install pytest-cov
    - Target: ≥80% line coverage
    - Identify untested code paths

12. **Load Testing** ⏱️ 2-3 days
    - Test concurrent requests (10, 50, 100 simultaneous)
    - Identify bottlenecks
    - Add rate limiting if needed

### 🔵 FUTURE WORK (From Phase Plan)

13. **Clarification Dialogue** (Phase 2) ⏱️ 1 week
    - Detect missing parameters
    - Ask targeted questions
    - Re-extract with user answers

14. **Conversation Memory** (Phase 3) ⏱️ 1 week
    - Session management
    - Context across turns
    - User preference learning

15. **Proactive Analysis** (Phase 4) ⏱️ 1 week
    - Suggest analyses based on solution
    - Bottleneck detection
    - Interactive suggestions

16. **Iterative Refinement** (Phase 5) ⏱️ 1-2 weeks
    - Feedback collection
    - Smart modification parsing
    - Loop until user satisfied

17. **ML Classifier Training** (Phase 1 - Unblocked) ⏱️ 2-3 days
    - **BLOCKED**: Need 60-120 labeled training examples
    - When ready: Train scheduling subtype classifier
    - Target: ≥90% accuracy (vs current 20-30%)
    - See: `RESUME_WHEN_DATA_READY.md`

---

**Last Updated**: 2025-11-09
**Next Review**: After completing items 1-5 (high priority)

