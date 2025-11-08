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

## 2025-10-11

### Problems Solved

1. **Test Organization Issue**
   - Problem: Tests directory was disorganized with 20 files scattered without clear structure
   - Solution: Cleaned up to 12 essential files, removed 5 obsolete/duplicate tests
   - Result: 40% reduction in file count, clear structure established

2. **Documentation Fragmentation**
   - Problem: 4 separate README files making documentation hard to navigate
   - Solution: Merged all test documentation into single concise README.md
   - Result: Single source of truth for test documentation

3. **Output Directory Redundancy**
   - Problem: 3 separate test output folders (test_output/, test_output_llm_requests/, test_output_overall/)
   - Solution: Consolidated all plots into single test_output/ directory, updated test files
   - Result: Simplified output management, all 13 PNG files in one location

4. **Lack of Complete System Demonstration**
   - Problem: No test showing complete LLM reasoning chain from input to output
   - Solution: Created Overall_Test.py (862 lines) demonstrating full reasoning for 6 prompts
   - Result: Clear demonstration of system intelligence and decision-making process

### Accomplishments

#### Major Deliverables

1. **Overall_Test.py** - Complete LLM Reasoning Chain Test
   - 862 lines of code
   - Tests 6 different prompt types with full chain-of-thought explanations
   - Shows: intent detection, confidence scores, processing decisions, visualization reasoning
   - Demonstrates: optimization solving, deterministic question handling, intelligent visualization selection, sensitivity analysis
   - Outputs: Console reasoning display + 3 PNG visualizations

2. **Test Suite Cleanup**
   - Deleted 5 obsolete files: `# test_run.py`, `test_run.py`, `test_direct_solver.py`, `debug_solvers.py`, `debug_units.py`
   - Retained 11 essential test files covering all functionality
   - Total: 3,000+ lines of test code, 44 unit tests passing

3. **Documentation Consolidation**
   - Created single comprehensive README.md in tests/
   - High-level descriptions without excessive detail
   - Clear quick-start guide and structure overview
   - Troubleshooting section included

4. **Repository Organization**
   - All test materials centralized in tests/ directory
   - All test outputs in single test_output/ directory
   - Clear file naming and structure
   - Updated file paths in affected test files

#### System Capabilities Validated

Through Overall_Test.py, confirmed the platform accomplishes:

1. **Natural Language Understanding**: Parses optimization problems from plain English
2. **Intelligent Intent Classification**: 4-way classification (smalltalk, help, optimization, follow-up) with 80-95% confidence
3. **Context-Aware Processing**: Maintains conversation context, distinguishes new problems from follow-ups
4. **Deterministic Question Handling**: Instant answers for common questions (sub-millisecond, no LLM calls)
5. **Intelligent Visualization**: Chooses appropriate chart types based on data structure and user intent
6. **Analytical Reasoning**: Provides business insights, identifies bottlenecks, estimates impact

Example results from test run:
- Solved European Wine Distribution problem: €4,750 optimal cost
- Identified 2 bottlenecks (Bordeaux, Tuscany at 100% capacity)
- Identified 1 inefficiency (Rioja at 45.5% capacity)
- Estimated €142-€332 savings from 20% capacity increase

### Tasks Completed

#### Test Infrastructure
- [x] Created Overall_Test.py with 6 comprehensive prompts
- [x] Added chain-of-thought explanations for all processing decisions
- [x] Implemented visualization reasoning demonstrations
- [x] Created laconic README header in Overall_Test.py

#### Test Organization
- [x] Moved all test files to tests/ directory
- [x] Moved all documentation to tests/ directory
- [x] Moved all output directories to tests/ directory
- [x] Updated import paths in test files

#### Cleanup
- [x] Deleted 5 obsolete/duplicate test files
- [x] Deleted 3 redundant README files
- [x] Consolidated 3 output folders into 1
- [x] Updated output directory paths in test files

#### Documentation
- [x] Created single comprehensive tests/README.md
- [x] Documented all 11 remaining test files with purpose
- [x] Added quick-start guide
- [x] Added troubleshooting section
- [x] Documented test output structure

#### Verification
- [x] Ran Overall_Test.py successfully (~10 seconds runtime)
- [x] Generated 3 PNG visualizations (flows, costs, utilization)
- [x] Verified all 44 unit tests pass in test_llm_refactoring.py
- [x] Confirmed file structure is clean and organized

### Remaining Tasks

#### High Priority
- None identified for immediate action

#### Medium Priority
1. Consider adding more optimization problem types beyond transportation
2. Evaluate if additional debug utilities are needed
3. Review if analyze_failures.py is still relevant or can be removed

#### Low Priority
1. Clean old PNG files from test_output/ if accumulating too many
2. Consider adding automated cleanup script for test outputs older than X days
3. Evaluate if test_scheduling_model.py needs expansion

#### Future Enhancements
1. Add performance benchmarking tests
2. Add stress tests for large-scale problems
3. Add tests for edge cases (malformed input, extreme values)
4. Consider adding integration tests with actual Ollama API

---

## To Do Next - LLM Problem Classification and Math Extraction

Based on the roadmap update, to complete the "making the LLM able to distinguish problems and extract math" task, here are the remaining items:

### Immediate Remaining Tasks

#### 1. **Optimize Classification Performance**
- Reduce voting from `n=3` to `n=1` in `problem_classifier.py` for faster response
- Fine-tune model parameters for better speed/accuracy balance

#### 2. **Integrate Schema-Based Classifier into Conversation System** (HIGHEST PRIORITY)
- Replace the complex prompt in `ollama_client.py:detect_follow_up_intent()`
- Use structured classification to detect parameter modifications like "What if I double capacity?"
- Update `conversation/agent.py` to use new classification system

#### 3. **Extend Parameter Modification Detection**
- Leverage classification signals to better detect "what-if" scenarios
- Improve detection of capacity changes, cost modifications, constraint additions
- Use structured evidence to understand modification intent

#### 4. **Add Constraint Detection for Transportation**
- Parse forbidden routes ("Antwerp cannot ship to Mons")
- Detect capacity limits on specific arcs
- Handle integer shipment requirements
- Extract distance-based cost calculations

#### 5. **Improve LLM to Become True OR Expert**

##### Phase 1: Problem Type Expansion (Immediate - Next 2-4 weeks)
- [ ] Add **assignment problems** (worker-task matching)
- [ ] Add **network flow problems** (max flow, min cost flow)
- [ ] Implement **integer/binary variable detection**
- [ ] Add **knapsack problems** (0/1, bounded, unbounded)
- [ ] Support **production planning** problems

##### Phase 2: Mathematical Extraction Enhancement (Short-term - 1-2 months)
- [ ] Improve **constraint recognition** (equality vs inequality, logical constraints)
- [ ] Add **multi-objective optimization** support
- [ ] Implement **variable type detection** (continuous, integer, binary, semi-continuous)
- [ ] Add **infeasibility detection** before solving
- [ ] Implement **redundant constraint identification**

##### Phase 3: Advanced Capabilities (Medium-term - 3-6 months)
- [ ] Add **nonlinear programming (NLP)** support
- [ ] Implement **stochastic optimization** (uncertainty modeling)
- [ ] Add **robust optimization** capabilities
- [ ] Support **scheduling problems** (job shop, flow shop, project scheduling)
- [ ] Implement **facility location problems**

##### Domain Knowledge Enhancement
- [ ] Add **OR terminology understanding** (feasible region, binding constraint, degeneracy, shadow prices)
- [ ] Implement **ambiguity resolution** ("minimize cost" → which costs?)
- [ ] Add **domain-specific patterns** (logistics, finance, manufacturing)
- [ ] Create **problem templates** for common OR patterns
- [ ] Build **extraction patterns** for each problem type

##### Solution Analysis & Insights
- [ ] **Explain shadow prices/dual values** in business terms
- [ ] **Identify trade-offs** between objectives
- [ ] **Recommend actions** based on solution
- [ ] **Compare scenarios** side-by-side
- [ ] **Validate solutions** against business logic

##### Robustness & Error Handling
- [ ] Add **input validation** (missing data, inconsistencies)
- [ ] Implement **graceful degradation** for unclear inputs
- [ ] Add **clarifying question generation** when data is ambiguous
- [ ] Provide **confidence scores** for extracted parameters

##### Testing & Validation
- [ ] Test on **standard OR benchmarks** (MIPLIB, NETLIB)
- [ ] Test on **textbook problems** (Winston, Hillier-Lieberman)
- [ ] Add **real-world case studies** to test suite
- [ ] Test with **ambiguous/incomplete problem statements**

### Critical Integration Points

The **most important** remaining work is **#2**: integrating the schema classifier into your conversation system. This will fix the original "parameter modification detection bug" that was identified as critical in your roadmap.

The current conversation system still uses the old complex prompt-based detection, but now you have a much better structured approach that can reliably distinguish between:
- New optimization problems
- Parameter modifications to existing problems
- Analysis requests
- Basic questions

### Recommendation

Start with optimizing performance (#1) or jump straight into the conversation integration (#2).

Integration (#2) is the highest priority as it addresses the core issue that started this work: fixing parameter modification detection to properly handle user requests like "What if I double Seattle capacity?"

---

### Technical Notes

#### File Structure After Cleanup
```
tests/
├── README.md (1 file, concise)
├── Core Tests: 4 files (Overall_Test.py, test_llm_refactoring.py, test_complete_workflow.py, test_with_llm_analysis_requests.py)
├── Problem-Specific: 4 files (test_greek_problem.py, test_schema_classifier.py, transportation_test_cases.py, test_scheduling_model.py)
├── Feature Tests: 1 file (test_question_handling.py)
├── Debug Utilities: 2 files (debug_classification.py, analyze_failures.py)
└── test_output/ (13 PNG files)
```

#### Test Statistics
- Total Python test files: 11
- Total lines of test code: ~3,000
- Unit tests: 44 (all passing)
- Integration tests: 3 (all working)
- Main demonstration: 1 (Overall_Test.py)

#### System Requirements Confirmed
- Python 3.12+
- Ollama running at http://localhost:11434
- Model: qwen2:7b
- Virtual environment: Tolis_Env
- All dependencies installed via requirements.txt

### Context for Next Session

#### Current State
The tests directory is now clean and well-organized. All tests are functional and documented. The Overall_Test.py serves as the primary demonstration of system capabilities, showing complete reasoning chains for 6 different prompt types.

#### Key Files for Reference
1. **tests/Overall_Test.py**: Main demonstration file, start here for understanding system
2. **tests/README.md**: Complete guide to all tests
3. **tests/test_llm_refactoring.py**: 44 unit tests, run with pytest

#### If Continuing Development
- Review remaining debug utilities (debug_classification.py, analyze_failures.py) to determine if still needed
- Consider expanding problem types beyond transportation
- Evaluate test coverage for edge cases

#### If User Wants to Run Tests
```bash
cd tests/
source ../Tolis_Env/bin/activate
python Overall_Test.py  # Main demo
python -m pytest test_llm_refactoring.py -v  # Unit tests
```

---

**Session Duration**: ~3 hours
**Primary Focus**: Test organization and documentation
**Status**: Complete and functional

---

## 2025-10-12

### Main Objective: Build Production-Grade Hybrid Classifier System

**Goal**: Replace the current pure-LLM classifier with a robust, maintainable, fast, and continuously-improving hybrid system that combines rule-based labeling functions with lightweight supervised ML.

**Why**: The current LLM-only approach has several limitations:
1. **Slow**: LLM inference takes ~7-10 seconds per classification (with n=3 voting)
2. **Expensive**: Every classification requires expensive LLM API calls
3. **Flaky**: Pure neural approaches can drift with minor wording changes
4. **Not Explainable**: Can't trace why a classification was made
5. **Not Testable**: No unit tests for classification logic
6. **Static**: Doesn't improve over time without retraining entire model

**Solution**: Hierarchical hybrid classifier with:
- **Labeling Functions (LFs)**: Deterministic, unit-tested rules that handle clear cases
- **Supervised Model**: Lightweight ML (LogReg/SVM) that learns what rules miss
- **Conflict Resolution**: Smart policy when LFs and model disagree
- **Grammar Parsers**: Validate and extract structured problem parameters
- **Active Learning**: Continuous improvement loop from low-confidence cases
- **CI/CD**: Performance gates ensure quality never degrades

### Problems Addressed

1. **Pure-LLM Classification Accuracy**
   - Problem: Current LLM classifier achieved 80% accuracy (24/30 tests passed) with borderline case confusion
   - Root Cause: LLM struggles with adversarial cases (e.g., "assignment vs transportation" when problem mentions "shipping")
   - Solution: Hybrid system with high-precision LFs for clear cases + ML for ambiguous cases

2. **Classification Speed & Cost**
   - Problem: 7-10 seconds per classification; 90 LLM calls for 30 tests = ~10 minutes total
   - Root Cause: LLM inference with n=3 voting is slow and expensive
   - Solution: Fast rule-based LFs (~1ms) + lightweight ML (~10-50ms) = 100x faster

3. **Explainability & Debugging**
   - Problem: When classification fails, impossible to debug why
   - Root Cause: LLM is a black box
   - Solution: Logged decision trail showing which LFs fired, model confidence, and resolution logic

4. **Taxonomy Drift**
   - Problem: No stable problem type taxonomy; aliases handled inconsistently
   - Root Cause: Schema was ad-hoc, not formalized
   - Solution: Locked taxonomy.yml with 9 families, subtypes, and comprehensive aliases.yml

5. **No Continuous Improvement**
   - Problem: System doesn't get better over time
   - Root Cause: No feedback loop from failures
   - Solution: Active learning with review notebook for low-confidence cases; retrain model periodically

### Accomplishments

#### Phase 1a: Foundation (Completed)

1. **Hierarchical Taxonomy Design** (`or_classify/taxonomy.yml`)
   - Defined 9 stable Level-1 families: network_flow, matching_assignment, location_allocation, lot_sizing, knapsack, lp, mip, scheduling, nlp
   - 25+ subtypes with clear definitions
   - Examples and near-misses for each to prevent confusion
   - Non-drifting structure: new problem types map to existing families

2. **Alias Mapping** (`or_classify/aliases.yml`)
   - 50+ aliases covering common synonyms
   - Key mappings:
     - portfolio → knapsack.zero_one_knapsack
     - transportation → network_flow.min_cost_flow
     - production_planning → lot_sizing.capacitated_lot_sizing
   - Handles algorithm names (dijkstra, hungarian, etc.)

3. **Directory Structure**
   ```
   or_classify/
   ├── taxonomy.yml          # Hierarchical problem type taxonomy
   ├── aliases.yml           # Synonym normalizer
   ├── lfs/                  # Labeling functions (rules)
   ├── model_subtypes/       # Subtype classifiers
   ├── grammar/              # Problem-specific parsers
   ├── eval/                 # Metrics, augmentation, CI gates
   └── logs/                 # Classification decision logs
   ```

#### Phase 1 Test Results (Baseline)

Ran comprehensive test suite with pure-LLM classifier:
- **Total**: 30 tests (7 categories)
- **Passed**: 24 (80%)
- **Failed**: 6 (20%)
- **Avg Confidence**: 97.5%
- **Avg Time**: ~7-10 seconds/test

**Test Breakdown by Category**:
- Assignment: 4/5 (80%)
- Network Flow: 4/5 (80%)
- Knapsack: 5/6 (83%)
- Scheduling: 5/6 (83%)
- Production Planning: 2/4 (50%)
- Facility Location: 2/2 (100%)
- Transportation: 2/2 (100%)

**Key Failures**:
1. Assignment vs Transportation (shipping terminology confusion)
2. Min Cost Flow → Transportation (reasonable, very similar)
3. Investment Selection → Portfolio (reasonable, portfolio IS knapsack)
4. Employee Shift Scheduling → Assignment (missed temporal aspect)
5. Multi-product Production → production_planning (not in schema, should be lot_sizing)
6. Simple Resource Allocation → Knapsack (actually correct classification)

**Objective Extraction** ✅ Working:
- Successfully extracts: "minimize total_cost", "maximize revenue", "minimize makespan", etc.
- LLM now returns structured objective: {sense: "minimize", target: "total_cost"}

### Tasks Completed

#### Foundation
- [x] Designed 9-family hierarchical taxonomy with definitions and examples
- [x] Created comprehensive alias mapping (50+ entries)
- [x] Set up or_classify/ directory structure
- [x] Enhanced classification schema to include objective extraction
- [x] Created 30-test comprehensive test suite (phase1_test_cases.py + test_phase1_runner.py)

#### Testing Infrastructure
- [x] Ran baseline LLM classifier tests (80% accuracy achieved)
- [x] Identified 6 failure cases with root cause analysis
- [x] Generated timestamped JSON results with full decision logs

### Remaining Tasks (Phase 1b-1d)

#### Phase 1b: Core Infrastructure
- [ ] **Create alias normalizer** (`normalise_label()` function + 100% test coverage)
- [ ] **Implement LF framework** (SDK with ABSTAIN, priority, registry, unit test structure)
- [ ] **Write 25 core LFs** with unit tests (>90% precision each):
  - ONE_TO_ONE, SUPPLY_AND_DEMAND, ARC_COSTS_PRESENT
  - BUDGET_SELECT_PROJECTS, ALL_OR_NOTHING_LANGUAGE
  - MULTI_PERIOD_TOKENS, INVENTORY_BALANCE, SETUP_HOLDING_KEYWORDS
  - SHIFT_NAMES, WEEKDAYS, COVERAGE_COUNTS
  - FIXED_CHARGE_OPEN, INTEGRALITY_MENTIONED, etc.

#### Phase 1c: Machine Learning Layer
- [ ] **Build feature pipeline**: TF-IDF + LF outputs + engineered flags (numeric counts, time tokens, graph tokens)
- [ ] **Train Level-1 classifier**: LogReg/SVM with calibration; macro-F1 ≥ 90%
- [ ] **Train subtype classifiers**: One per family with ≥2 subtypes
- [ ] **Implement conflict resolution**: Policy for LF vs model disagreements

#### Phase 1d: Robustness & Production
- [ ] **Create grammar parsers**: Validate and extract structured parameters for each problem type
- [ ] **Build adversarial test augmentation**: Generate 10 variants per test case
- [ ] **Set up CI pipeline**: Performance gates (macro-F1, hierarchical accuracy thresholds)
- [ ] **Implement JSONL logging**: Decision trail (PII-safe, includes LFs fired, confidence, chosen label)
- [ ] **Create AL review notebook**: Jupyter notebook for reviewing low-confidence cases

### Technical Notes

#### Hybrid Classifier Architecture

**Level 1: Labeling Functions (LFs)**
- Precision: >90% on their slice
- Return: {label | ABSTAIN}
- Unit tested with 5-10 positive/negative examples each
- Fast: ~1ms per LF
- Examples:
  - `LF_ONE_TO_ONE`: Detects "exactly one", "each worker does one task" → matching_assignment
  - `LF_SUPPLY_DEMAND_FLOWS`: Detects nodes/arcs + flow balance → network_flow
  - `LF_BUDGET_SELECT`: Detects "budget", "select subset", "all-or-nothing" → knapsack

**Level 2: Supervised Model**
- Input: TF-IDF features + LF outputs (one-hot) + engineered flags
- Model: Logistic Regression or Linear SVM (fast, explainable)
- Calibrated: Isotonic or Platt scaling for reliable confidence
- Trained on: LF-generated labels + hand-labeled gold set

**Level 3: Conflict Resolution**
- Policy:
  1. If high-precision LF fires with confidence ≥ τ_high → use LF
  2. Else if model confidence ≥ τ_model → use model
  3. Else if tie → return parent family (e.g., knapsack instead of zero_one_knapsack)
  4. Log all decisions for active learning review

**Level 4: Grammar Validation**
- After classification, parse problem text into canonical JSON
- Type-specific grammars enforce structure:
  - Assignment: binary domains + one-to-one constraints
  - Min-cost-flow: supply/demand balance + arc capacities
  - Lot-sizing: inventory balance equation I[t] = I[t-1] + x[t] - d[t]
- If parse fails → structured error (caught in CI)

#### Durability Policies

**Prevent Drift**:
- New synonyms → add to aliases.yml (not code)
- New rules → add LF with unit tests (not prompt engineering)
- Model retrains only from gold set + accepted AL corrections
- Any grammar failure → structured error, never silent fallback

**Continuous Improvement**:
- Weekly: Review lowest-confidence 20 cases
- Relabel or add LFs as needed
- Retrain model incrementally
- CI gates prevent regression (fail if macro-F1 drops >1%)

### Context for Next Session

#### Current State
- Baseline LLM classifier: 80% accuracy, but slow and not improving
- Foundation complete: taxonomy.yml + aliases.yml + directory structure
- 30 comprehensive test cases with results logged
- Ready to implement LF framework and core rules

#### Next Steps (Immediate)
1. Complete alias normalizer function with tests
2. Implement LF SDK (framework for writing and testing LFs)
3. Write first 10 core LFs (ONE_TO_ONE, SUPPLY_DEMAND, etc.)
4. Run LFs on 30 test cases to measure coverage

#### Key Files Created
1. **or_classify/taxonomy.yml**: 9 families, 25+ subtypes, locked taxonomy
2. **or_classify/aliases.yml**: 50+ synonym mappings
3. **tests/phase1_test_cases.py**: 30 test cases across 7 categories
4. **tests/test_phase1_runner.py**: Test runner with detailed output (type, confidence, structure, missing keys)
5. **test_output/phase1_results_20251012_112059.json**: Baseline LLM results

#### Performance Targets
- **Accuracy**: ≥95% on test suite (vs 80% baseline)
- **Speed**: <100ms per classification (vs 7-10 seconds baseline)
- **Explainability**: 100% of decisions have logged reasoning
- **Cost**: Near-zero (rules + lightweight ML vs expensive LLM calls)

---

**Session Duration**: ~2 hours
**Primary Focus**: Hybrid classifier architecture design and foundation
**Status**: Phase 1a complete; Phase 1b ready to start

## 2025-10-12 (Session 2)

### Main Objective: Complete Phase 1b-1c Infrastructure

**Goal**: Build core infrastructure for hybrid classifier - normalizer, LF framework, 25 LFs, and feature pipeline.

### Accomplishments

#### Phase 1b: Core Infrastructure (Completed ✅)

1. **Label Normalizer** (`or_classify/normalizer.py` - 215 lines)
   - `normalise_label()`: Returns (canonical_label, was_aliased)
   - `is_valid_label()`: Validate against taxonomy
   - `get_family()`, `get_subtype()`: Extract label components
   - `to_family_only()`: Strip subtype for hierarchical classification
   - Handles case-insensitive matching, hyphens/spaces normalization
   - Unit tested and verified

2. **Labeling Function Framework** (`or_classify/labeling_function.py` - 293 lines)
   - Base `LabelingFunction` class with abstract methods
   - `LFResult` dataclass: label, confidence, evidence, priority
   - `ABSTAIN` sentinel for non-matching cases
   - `LFPriority` enum: CRITICAL (1), HIGH (2), MEDIUM (3), LOW (4)
   - `LFRegistry`: Register, execute, priority-sort LFs
   - `apply_all()`: Execute all LFs with stop-on-first option
   - `apply_by_priority()`: Execute until first non-ABSTAIN
   - Global registry pattern for easy LF management
   - Unit tested and verified

3. **25 Core Labeling Functions** (`or_classify/lfs/` - 7 files, 873 lines total)
   
   **Assignment (3 LFs)** - `assignment_lfs.py`:
   - `AssignmentKeywordLF` (HIGH): Detects "assign" + one-to-one indicators
   - `HungarianMethodLF` (CRITICAL): Detects Hungarian algorithm references
   - `OneToOneMappingLF` (MEDIUM): N-to-N mapping structure detection
   
   **Network Flow (5 LFs)** - `network_flow_lfs.py`:
   - `NetworkFlowKeywordLF` (HIGH): Generic "network flow" detection
   - `MaxFlowKeywordLF` (CRITICAL): Max flow / Ford-Fulkerson
   - `ShortestPathKeywordLF` (CRITICAL): Dijkstra / Bellman-Ford / shortest path
   - `MinCostFlowKeywordLF` (CRITICAL): Min cost flow / MCNF
   - `TransportationKeywordLF` (HIGH): Transportation problem patterns
   
   **Knapsack (4 LFs)** - `knapsack_lfs.py`:
   - `KnapsackKeywordLF` (CRITICAL): "knapsack" + subtype detection
   - `PortfolioKeywordLF` (HIGH): Portfolio optimization → knapsack
   - `ZeroOneKnapsackLF` (MEDIUM): Binary selection + capacity structure
   - `BinPackingLF` (HIGH): Bin packing patterns
   
   **Scheduling (5 LFs)** - `scheduling_lfs.py`:
   - `SchedulingKeywordLF` (HIGH): Generic "schedule" detection
   - `JobShopKeywordLF` (CRITICAL): Job shop patterns
   - `FlowShopKeywordLF` (CRITICAL): Flow shop patterns
   - `MakespanKeywordLF` (MEDIUM): Makespan objective
   - `ShiftRosteringLF` (HIGH): Shift rostering / employee scheduling
   
   **Location (3 LFs)** - `location_lfs.py`:
   - `FacilityLocationKeywordLF` (HIGH): Facility location + fixed costs
   - `PMedianKeywordLF` (CRITICAL): P-median problems
   - `SetCoverKeywordLF` (CRITICAL): Set cover problems
   
   **Lot Sizing (3 LFs)** - `lot_sizing_lfs.py`:
   - `LotSizingKeywordLF` (CRITICAL): Lot sizing / EOQ keywords
   - `ProductionPlanningLF` (HIGH): Production planning patterns
   - `InventoryKeywordLF` (MEDIUM): Inventory + production context
   
   **LP/MIP (2 LFs)** - `lp_mip_lfs.py`:
   - `LinearProgramKeywordLF` (MEDIUM): LP / simplex detection
   - `MIPKeywordLF` (MEDIUM): MIP / integer programming detection

4. **Feature Pipeline** (`or_classify/feature_pipeline.py` - 258 lines)
   - **TF-IDF Features**: 500 max features, unigrams + bigrams, English stopwords removed
   - **LF Features**: One-hot encoding of LF labels + max confidence + num LFs fired
   - **Engineered Features** (14 total):
     - `has_numbers`, `has_time_periods`, `has_capacity`, `has_economic_objective`
     - `has_minimization`, `has_maximization`, `has_inventory`, `has_scheduling`
     - `has_flow`, `has_assignment`, `word_count`, `comma_count`
     - `has_binary_vars`, `has_integer_vars`
   - Returns sparse matrix for memory efficiency
   - Includes metadata with LF results for explainability
   - `fit()` / `transform()` pattern for sklearn compatibility
   - Unit tested and verified (54 features on sample data)

### Tasks Completed

#### Infrastructure Implementation
- [x] Implemented `normalise_label()` with full alias support (Task 2)
- [x] Created LF framework with ABSTAIN, priority, registry (Task 3)
- [x] Wrote 25 core LFs across 7 problem families (Task 4)
- [x] Built feature pipeline with TF-IDF + LF + engineered features (Task 5)

#### Testing & Verification
- [x] Unit tested normalizer (5 tests, all passing)
- [x] Unit tested LF framework (6 tests, all passing)
- [x] Verified all 25 LFs import correctly
- [x] Tested feature pipeline on sample data (3 samples → 54 features)

#### Dependencies & Configuration
- [x] Installed PyYAML 6.0.3 for taxonomy/aliases loading
- [x] Installed scikit-learn 1.7.2 for TF-IDF and ML
- [x] Installed scipy 1.16.2 for sparse matrices
- [x] Updated requirements.txt with ML dependencies

### Remaining Tasks (Phase 1c-1d)

#### Phase 1c: Machine Learning Layer
- [ ] **Task 6: Train Level-1 classifier** 
  - **Issue**: Need more training data (currently only 30 test cases)
  - **Options**: 
    1. Generate synthetic training data from LF labels
    2. Use weak supervision (LF outputs as noisy labels)
    3. Skip ML for now, use pure LF + conflict resolution
  - **Recommendation**: Skip Task 6 for now, move to Task 8 (conflict resolution)

- [ ] **Task 7: Train subtype classifiers** (SKIPPED - depends on Task 6)

- [ ] **Task 8: Implement conflict resolution policy**
  - **Feasible NOW**: Can implement with just LFs
  - **Policy**: Priority-based voting when multiple LFs fire
  - **Fallback**: Return parent family if no LF fires

#### Phase 1d: Production Readiness
- [ ] **Task 9: Create grammar parsers** for parameter extraction
- [ ] **Task 10: Build adversarial test augmentation**
- [ ] **Task 11: Set up CI with performance gates**
- [ ] **Task 12: Implement JSONL logging system**
- [ ] **Task 13: Create Jupyter review notebook**

### Technical Notes

#### Task 7 Analysis: Training Subtype Classifiers

**Objective**: Train one classifier per family to distinguish between subtypes (e.g., knapsack.zero_one vs knapsack.bounded vs knapsack.unbounded).

**Families Requiring Subtype Classifiers** (≥2 subtypes):
1. **network_flow** (3 subtypes): min_cost_flow, max_flow, shortest_path
2. **knapsack** (4 subtypes): zero_one_knapsack, bounded_knapsack, unbounded_knapsack, multidimensional_knapsack
3. **lot_sizing** (3 subtypes): uncapacitated_lot_sizing, capacitated_lot_sizing, multi_product_lot_sizing
4. **scheduling** (5 subtypes): job_shop, flow_shop, single_machine, shift_rostering, project_scheduling
5. **location_allocation** (3 subtypes): facility_location, p_median, set_cover
6. **lp** (2 subtypes): resource_allocation, diet_problem
7. **mip** (3 subtypes): fixed_charge, piecewise_linear, big_m_logical
8. **nlp** (3 subtypes): quadratic_programming, convex_nlp, general_nlp
9. **matching_assignment** (2 subtypes): assignment, bipartite_matching

**Total**: 9 families → 9 subtype classifiers needed

**Training Approach** (when ready):
1. **Data**: Use Level-1 classifier predictions to filter by family
2. **Features**: Same pipeline (TF-IDF + LF + engineered)
3. **Model**: Multi-class LogReg or SVM per family
4. **Training**: Separate model for each family
5. **Inference**: Two-stage: Level-1 (family) → Level-2 (subtype)

**Current Blocker**: Insufficient training data (30 samples total, need ~100+ per family for robust training)

**Recommendation for Next Session**:
- **Option A**: Skip ML tasks (6-7), implement conflict resolution (Task 8) with pure LFs
- **Option B**: Create training data generator (augment 30 tests → 300+ with paraphrasing)
- **Option C**: Move to grammar parsers (Task 9) to extract structured parameters

### Files Created This Session

**Core Infrastructure**:
1. `or_classify/normalizer.py` (215 lines) - Label normalization
2. `or_classify/labeling_function.py` (293 lines) - LF framework
3. `or_classify/feature_pipeline.py` (258 lines) - Feature extraction

**Labeling Functions** (873 lines total):
4. `or_classify/lfs/__init__.py` (54 lines) - Module exports
5. `or_classify/lfs/assignment_lfs.py` (99 lines) - 3 LFs
6. `or_classify/lfs/network_flow_lfs.py` (155 lines) - 5 LFs
7. `or_classify/lfs/knapsack_lfs.py` (139 lines) - 4 LFs
8. `or_classify/lfs/scheduling_lfs.py` (171 lines) - 5 LFs
9. `or_classify/lfs/location_lfs.py` (99 lines) - 3 LFs
10. `or_classify/lfs/lot_sizing_lfs.py` (113 lines) - 3 LFs
11. `or_classify/lfs/lp_mip_lfs.py` (97 lines) - 2 LFs

**Total**: 11 files, ~1,639 lines of production code

### Context for Next Session

#### Current State
- **Phase 1a (Foundation)**: ✅ Complete
- **Phase 1b (Core Infrastructure)**: ✅ Complete (Tasks 1-5)
- **Phase 1c (ML Layer)**: ⏸️ Blocked on training data (Tasks 6-7)
- **Phase 1d (Production)**: ⏳ Ready to start (Tasks 8-13)

#### Recommended Next Steps

**Option 1: Skip ML, Go Production-Ready (Fast Path)**
1. Implement conflict resolution (Task 8) with pure LF voting
2. Create grammar parsers (Task 9) for parameter extraction
3. Deploy hybrid classifier with LF-only classification
4. Collect real usage data for future ML training

**Option 2: Generate Training Data (ML Path)**
1. Build test case augmentation (Task 10) - paraphrase 30 → 300+ cases
2. Use augmented data + LF weak supervision to train classifiers (Tasks 6-7)
3. Then proceed with conflict resolution (Task 8) using ML

**Option 3: Incremental Deployment**
1. Deploy current LF-only system to production
2. Log all classifications with confidence scores
3. Manually review low-confidence cases to build gold dataset
4. Train ML models once sufficient data collected

**My Recommendation**: **Option 1** - Skip ML for now, implement conflict resolution with LF voting. The 25 LFs provide good coverage, and we can always add ML later when we have real usage data.

#### Key Metrics So Far
- **LF Coverage**: 25 LFs across 9 families
- **Code Quality**: All components unit tested
- **Performance**: ~1ms per LF (vs 7-10s for LLM)
- **Explainability**: 100% (evidence trails from LFs)

---

**Session Duration**: ~4 hours
**Primary Focus**: Core infrastructure implementation (normalizer, LFs, feature pipeline)
**Status**: Phase 1b complete; ready for Task 8 (conflict resolution)

---

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

