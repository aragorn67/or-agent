# Optimization AI - Architectural Brainstorming

**Date**: 2025-11-29
**Status**: Analysis framework complete for transportation, ready for expansion

---

## 🎯 Current State Summary

### What's Working Well ✅
- **LLM Classification**: 100% accuracy on solvable problems (DeepSeek-R1)
- **3-Layer Feasibility Checking**: Production-ready (structural, aggregate, solver-based)
- **Analysis Framework**: Sensitivity, what-if, resolve - **4/4 tests passing**
- **Solver Coverage**: Transportation (bipartite), Single-stage scheduling (makespan)

### Current Limitations ⚠️
- Analysis framework hardcoded to transportation problems only
- No data layer (can't load CSV/Excel inputs)
- No model persistence (rebuild model every solve)
- No decomposition strategies (won't scale to large MILPs)
- No heuristics (exact solver only)

---

## 🔍 Critical Bottlenecks Identified

### 1. **No Data Layer** - MOST CRITICAL 🔴

**Problem**: Currently can only accept natural language input. Real OR problems use:
- CSV files with supply/demand/cost data
- Excel spreadsheets with multiple sheets (nodes, arcs, parameters)
- JSON/YAML configuration files
- Database queries

**Impact**:
- Can't integrate with real business systems
- Can't handle problems with 1000+ entities (typing them in text is impractical)
- No support for batch processing or automation
- Forces users to manually type problem data into text

**Example Use Case**:
```
User has: supply_chain_data.csv (500 plants × 2000 markets)
Currently: Must type "Plant 1 has capacity 500, Plant 2 has capacity 320..." (impossible)
Should be: "Load supply_chain_data.csv and optimize the distribution network"
```

**Solution Needed**:
- CSV/Excel loader that maps columns to problem parameters
- Schema inference (detect which columns are plants/markets/capacity/demand/cost)
- LLM-assisted mapping when ambiguous ("Is 'Factory' column the source or sink?")
- Support for multiple formats (wide vs long, nested vs flat)

**Files to Create**:
```
data/
  loaders/
    csv_loader.py         # CSV/TSV loading
    excel_loader.py       # Excel multi-sheet loading
    json_loader.py        # Structured JSON
  mappers/
    schema_detector.py    # Auto-detect parameter structure
    llm_mapper.py         # Use LLM to clarify ambiguous schemas
  validators/
    data_validator.py     # Check loaded data matches problem type
```

**Estimated Effort**: 2-3 days

---

### 2. **No Model Persistence** 🟠

**Problem**: Every time user runs analysis (sensitivity, what-if), we:
1. Rebuild the entire Pyomo model from scratch
2. Re-convert parameters to solver format
3. Re-create constraints and objective
4. Solve from scratch

**Impact**:
- Slow for interactive analysis (3-5 second delay per query)
- Wasteful for large models (rebuilding 10,000 variables each time)
- Can't do warm-starts (re-use previous solution as starting point)
- Memory inefficient (create/destroy model objects repeatedly)

**Solution Needed**:
- Cache compiled Pyomo model after first solve
- Only update changed parameters (capacity[i], demand[j], cost[i,j])
- Support warm-starts when solver allows it
- Invalidate cache when structure changes (new plants/markets added)

**Example**:
```python
# Current approach (SLOW):
for test_value in sensitivity_values:
    params['capacity']['Plant A'] = test_value
    model = build_model(params)  # ← Rebuild entire model
    solution = solver.solve(model)

# Better approach (FAST):
model = build_model(params)  # Build once
for test_value in sensitivity_values:
    model.capacity['Plant A'].value = test_value  # ← Just update parameter
    solution = solver.solve(model, warmstart=True)  # ← Re-use previous solution
```

**Files to Modify**:
- `solvers/transport/bipartite.py` - Add model caching
- `solvers/scheduling/single_stage_ipm.py` - Add model caching
- `analysis/sensitivity/engine.py` - Use cached model
- `analysis/scenarios/engine.py` - Use cached model

**Estimated Effort**: 1-2 days

---

### 3. **No Decomposition Strategy** 🟠

**Problem**: For large MILPs (100,000+ variables, 50,000+ constraints):
- Monolithic solve takes hours or runs out of memory
- GLPK/CBC can't handle industrial-scale problems
- No support for Benders decomposition, Dantzig-Wolfe, or column generation

**Impact**:
- Can't solve real-world problems (e.g., nationwide supply chain optimization)
- Locked into small-scale problems only
- Can't compete with commercial solvers (Gurobi/CPLEX have built-in decomposition)

**Solution Needed**:
- Auto-detect problem structure (is it decomposable?)
- Implement Benders decomposition for two-stage problems
- Implement Dantzig-Wolfe for block-diagonal structure
- Column generation for problems with exponential variables (VRP, cutting stock)

**Example Problems That Need Decomposition**:
- **Two-stage stochastic**: Decide plant locations (stage 1), then optimize flows (stage 2)
- **Multi-period planning**: Separate decisions by time period
- **Multi-commodity flow**: Decompose by commodity type
- **VRP with large fleet**: Generate routes on-demand (column generation)

**Files to Create**:
```
decomposition/
  structure_detector.py    # Detect if problem has decomposable structure
  benders.py               # Benders decomposition (master + subproblem)
  dantzig_wolfe.py         # Dantzig-Wolfe decomposition
  column_generation.py     # Column generation framework
```

**Estimated Effort**: 3-5 days (complex, but high impact)

---

### 4. **No Heuristics** 🟡

**Problem**: Only exact solvers available (GLPK, CBC). For large MILPs:
- Exact solve can take hours/days
- Often need "good enough" solution in minutes
- No support for metaheuristics (GA, SA, Tabu Search)
- No support for problem-specific heuristics (greedy, nearest neighbor)

**Impact**:
- Can't provide fast answers for time-sensitive decisions
- Can't handle very large problems (even with decomposition)
- No trade-off between solution quality and speed

**Solution Needed**:
- Implement metaheuristics framework
- Add greedy heuristics for common problems (transportation, assignment)
- LLM-based heuristic selection ("This is urgent, use fast heuristic")
- Hybrid approach: heuristic first for quick answer, exact solver in background

**Example Heuristics Needed**:
- **Transportation**: Vogel's approximation, Northwest corner rule
- **Scheduling**: Earliest Due Date (EDD), Shortest Processing Time (SPT)
- **VRP**: Clarke-Wright savings, sweep algorithm
- **General MILP**: Genetic Algorithm, Simulated Annealing

**Files to Create**:
```
heuristics/
  framework/
    base_heuristic.py       # Abstract base class
    metaheuristic.py        # GA, SA, Tabu Search
  transport/
    vogel.py                # Vogel's approximation method
    northwest_corner.py     # Northwest corner rule
  scheduling/
    priority_rules.py       # EDD, SPT, WSPT
  vrp/
    clarke_wright.py        # Savings algorithm
```

**Estimated Effort**: 2-4 days per heuristic family

---

### 5. **Hardcoded Analysis Framework** 🟡

**Problem**: Sensitivity/what-if/resolve only work for transportation problems
- Checks for 'plants', 'markets', 'capacity', 'demand'
- Won't work for scheduling (jobs, machines, processing_time)
- Won't work for knapsack, portfolio, facility location, VRP

**Impact**:
- Analysis features limited to transportation only
- Need to rewrite analysis code for each new problem type
- Not truly "problem-agnostic"

**Solution Needed**: (Already documented in diary as "Next Task")
- LLM-based parameter detection (detect which parameter to analyze from query)
- Generic instance creation (build ParsedInstance without hardcoding)
- Dynamic modification engine (apply changes to any parameter type)

**Status**: Detailed 5-phase plan already written in `Claude_Diary.md`

**Estimated Effort**: 5-7 hours (see diary for breakdown)

---

## 📊 Recommended Priority Order

### **Priority 1: Data Layer** (2-3 days) 🔴

**Why First?**
1. **Unblocks Real Usage**: Can't deploy to production without CSV/Excel support
2. **Foundation for Everything**: Decomposition/heuristics need data layer too
3. **High Visibility**: Users immediately see value ("I can load my spreadsheet!")
4. **Not Too Hard**: Mostly engineering, not research

**Implementation Steps**:
1. Create `data/loaders/csv_loader.py` with pandas-based CSV reading
2. Create `data/mappers/schema_detector.py` for auto-detecting parameter structure
3. Create `data/mappers/llm_mapper.py` for LLM-assisted ambiguous mapping
4. Update `agent/core.py` to accept file paths as input
5. Add tests with real CSV files (transportation, scheduling)

**Deliverables**:
- Users can run: `agent.solve_from_csv("supply_chain.csv", problem_type="TRANSPORTATION")`
- LLM asks: "Which column contains plant capacities?" if ambiguous
- Works with both wide format (plants × markets matrix) and long format (from, to, cost rows)

---

### **Priority 2: Model Persistence** (1-2 days) 🟠

**Why Second?**
1. **Immediate Performance Boost**: Sensitivity analysis 5-10x faster
2. **Easy to Implement**: Just cache the Pyomo model object
3. **Enables Interactive Analysis**: Users can iterate rapidly
4. **Foundation for Warm-Starts**: Needed for large problems

**Implementation Steps**:
1. Add `model_cache` dict to solver classes
2. Cache compiled model after first solve
3. Update only changed parameters instead of rebuilding
4. Add cache invalidation when structure changes
5. Benchmark performance improvement

**Deliverables**:
- Sensitivity analysis on 10 values: < 1 second (currently 5-10 seconds)
- What-if scenarios: instant feedback
- Memory efficient (only one model in memory)

---

### **Priority 3: Solver Strategy Selection** (2-3 days) 🟡

**Why Third?**
1. **Smart Routing**: Auto-choose exact vs heuristic vs decomposition
2. **User-Friendly**: "I need answer in 30 seconds" → automatically use heuristic
3. **Foundation for Heuristics**: Need strategy layer before implementing heuristics
4. **LLM Integration**: Use LLM to understand user's time/quality trade-offs

**Implementation Steps**:
1. Create `solvers/strategy/selector.py` for strategy selection
2. Add problem size estimator (variables, constraints, structure)
3. Implement decision rules (small → exact, large → heuristic, structured → decomposition)
4. LLM prompt to detect urgency ("I need this in 5 minutes" → heuristic)
5. Add strategy explanation ("Using greedy heuristic due to problem size")

**Deliverables**:
- Auto-detect: "This problem has 100,000 variables, using Benders decomposition"
- User control: "solve this quickly" vs "solve this optimally"
- Transparent: "Heuristic found solution in 30 seconds, exact solver would take 2 hours"

---

### **Priority 4: Decomposition** (3-5 days) 🟠

**Why Fourth?**
1. **Unlocks Large Problems**: Only way to solve industrial-scale MILPs
2. **Builds on Strategy Layer**: Need Priority 3 first to route problems correctly
3. **Differentiator**: Most open-source OR tools don't have decomposition
4. **Research Opportunity**: Can publish results, contribute to OR community

**Implementation Steps**:
1. Implement Benders decomposition for two-stage problems
2. Add structure detector (identify master/subproblem split)
3. Implement Dantzig-Wolfe for block-diagonal structure
4. Add column generation framework (for VRP, cutting stock)
5. Benchmark on large problems (10,000+ variables)

**Deliverables**:
- Solve two-stage stochastic problems with 100,000+ variables
- Multi-period planning with automatic time-period decomposition
- VRP with column generation (100+ vehicles, 1000+ customers)

---

## 🚀 Quick Wins (Do These Anytime)

### **Easy Improvements** (1-2 hours each):
1. **Add progress bars**: Show "Solving... 45% complete" for long solves
2. **Solution export**: Save solutions to CSV/Excel/JSON
3. **Visualization**: Plot flows, Gantt charts, network diagrams
4. **Better error messages**: "Plant 'Seattle' not found. Did you mean 'Seatle'?"
5. **Undo/Redo**: Track modification history, allow rollback
6. **Solution comparison**: "New solution is $500 cheaper (8% improvement)"

### **Nice-to-Haves** (1 day each):
1. **Web UI**: Flask/Streamlit interface for non-technical users
2. **Batch processing**: Solve multiple scenarios overnight
3. **Sensitivity reports**: Auto-generate PDF reports
4. **Constraint relaxation**: "Problem infeasible. Try relaxing demand by 10%?"
5. **Multi-objective**: Minimize cost AND minimize late deliveries

---

## 🎯 6-Month Roadmap

### **Month 1**: Data Layer + Model Persistence
- ✅ CSV/Excel loading
- ✅ Schema detection and LLM mapping
- ✅ Model caching for fast analysis
- ✅ Basic visualization

### **Month 2**: Solver Strategy + Greedy Heuristics
- ✅ Strategy selection framework
- ✅ Problem size estimator
- ✅ Greedy heuristics for transportation/scheduling
- ✅ Performance benchmarking

### **Month 3**: Decomposition (Benders)
- ✅ Benders decomposition implementation
- ✅ Structure detector for two-stage problems
- ✅ Benchmark on large problems

### **Month 4**: Decomposition (Dantzig-Wolfe + Column Gen)
- ✅ Dantzig-Wolfe for block-diagonal
- ✅ Column generation framework
- ✅ VRP solver with column generation

### **Month 5**: Metaheuristics
- ✅ Genetic Algorithm framework
- ✅ Simulated Annealing
- ✅ Tabu Search
- ✅ Hybrid exact+heuristic

### **Month 6**: Polish + Production
- ✅ Web UI
- ✅ Solution export and reporting
- ✅ Multi-objective optimization
- ✅ Documentation and examples

---

## 💡 Research Opportunities

### **Novel Contributions**:
1. **LLM-Driven Decomposition**: Use LLM to suggest decomposition strategy
2. **Adaptive Heuristics**: LLM learns which heuristics work best for user's problems
3. **Hybrid Solving**: Heuristic provides warm-start for exact solver
4. **Natural Language Constraints**: "Minimize cost BUT Plant A must serve at least 30% of Market X"

### **Potential Publications**:
- "LLM-Assisted Operations Research: From Natural Language to Optimal Solutions"
- "Adaptive Decomposition Strategies for Large-Scale MILPs"
- "Hybrid Heuristic-Exact Solving with Language Model Guidance"

---

## 🔑 Key Takeaways

### **Most Important Bottleneck**: Data Layer 🔴
- Blocks real-world usage
- Foundation for everything else
- High visibility, moderate effort
- **DO THIS FIRST**

### **Biggest Performance Win**: Model Persistence 🟠
- 5-10x faster analysis
- Easy to implement
- Immediate user impact
- **DO THIS SECOND**

### **Biggest Scale Unlock**: Decomposition 🟠
- Handle industrial-scale problems
- Differentiator from other tools
- Research opportunity
- **DO THIS AFTER DATA + PERSISTENCE**

### **Best Long-Term Investment**: Solver Strategy Layer 🟡
- Foundation for heuristics/decomposition
- Makes system truly adaptive
- LLM integration opportunity
- **DO THIS THIRD**

---

**Next Steps**: Start with Priority 1 (Data Layer) - create `data/loaders/csv_loader.py` and test with real supply chain CSV files.
