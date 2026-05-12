# Repository Structure

**Last Updated:** 2025-12-04
**Status:** Cleaned and organized

---

## 📁 Directory Overview

```
optimization-ai/
├── agent/                    # Main orchestration agent
├── analysis/                 # Post-solution analysis (sensitivity, what-if, pareto)
│   ├── modification/         # Re-solve with modifications
│   ├── pareto/               # Multi-objective Pareto front (in progress)
│   ├── scenarios/            # What-if scenario analysis
│   └── sensitivity/          # Sensitivity analysis
├── feasibility/              # 3-layer feasibility checking
│   └── problem_specific/     # Problem-specific feasibility rules
├── solvers/                  # Optimization solvers
│   ├── transport/            # Transportation problem solvers
│   └── scheduling/           # Scheduling problem solvers
├── or_classify/              # Problem type classification
│   ├── lfs/                  # Labeling functions for classification
│   ├── grammar/              # NLP grammar patterns
│   └── eval/                 # Evaluation utilities
├── llm/                      # LLM client integrations
├── data/                     # Data layer (NEW - for Priority 1)
│   ├── loaders/              # CSV/Excel/JSON loaders
│   ├── mappers/              # Schema detection and mapping
│   └── examples/             # Sample data files
├── tests/                    # All test files
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   └── fixtures/             # Test data and fixtures
├── docs/                     # Documentation
│   ├── README.md             # Main documentation
│   ├── brainstorm_ideas.md   # Architecture and roadmap
│   └── Claude_Diary.md       # Development log
├── archive/                  # Old/deprecated code
│   ├── old_analyzers/        # Old problem-specific analyzers (replaced)
│   ├── old_api/              # Old Flask API components
│   └── ML_RAG_archive/       # Archived ML experiments
├── schemas/                  # JSON/Pydantic schemas
├── scripts/                  # Utility scripts
├── config.py                 # Configuration
├── api.py                    # REST API (still in use)
└── requirements.txt          # Python dependencies
```

---

## 🔑 Core Modules

### **agent/** - Main Orchestrator
- `core.py` - OptimizationAgent main entry point
- Handles intent detection, problem routing, and solution generation
- Coordinates all other modules

### **analysis/** - Post-Solution Analysis
- **Problem-agnostic design** - works with ANY OR problem type
- `router.py` - Detects and routes analysis requests
- `parameter_detector.py` - LLM-based parameter detection
- `instance_builder.py` - Generic instance creation
- `sensitivity/engine.py` - Sensitivity analysis
- `scenarios/engine.py` - What-if scenarios
- `modification/engine.py` - Re-solve with modifications
- `pareto/engine.py` - Multi-objective optimization (in progress)

**Status:** Production-ready for transportation and scheduling

### **feasibility/** - 3-Layer Feasibility Checking
- Layer 0: Structural validation (empty sets, negative values)
- Layer 1: Aggregate constraints (supply vs demand)
- Layer 2: Solver-based verification
- Provides clear reasons and suggestions when infeasible

### **solvers/** - Optimization Solvers
- `transport/bipartite.py` - Transportation problem solver
- `scheduling/single_stage_ipm.py` - Single-stage scheduling
- `base.py` - Base solver interface
- `registry.py` - Solver registration and discovery

### **or_classify/** - Problem Type Classification
- Uses LLMs (DeepSeek-R1) for 100% accuracy on solvable problems
- Labeling functions for pattern matching
- Supports 8+ problem types

### **llm/** - LLM Integrations
- `enhanced_client.py` - Enhanced LLM client with follow-up support
- `client.py` - Base LLM client
- `intent_router.py` - Intent detection
- `follow_up_handler.py` - Conversational follow-ups

---

## 🆕 New Directories (Created 2025-12-04)

### **data/** - Data Layer (Priority 1 - To Be Implemented)
Empty directory structure ready for:
- `loaders/` - CSV/Excel/JSON file loaders
- `mappers/` - Schema detection and LLM-assisted mapping
- `examples/` - Sample data files for testing

This is the **#1 priority** for enabling production usage with real business data.

### **docs/** - Centralized Documentation
Moved all documentation files here:
- `README.md` - Main project documentation
- `brainstorm_ideas.md` - Architecture, roadmap, and priorities
- `Claude_Diary.md` - Development history and decisions

### **archive/** - Old/Unused Code
Safely archived:
- `old_analyzers/` - Problem-specific analyzers (replaced by generic analysis framework)
- `old_api/` - Old Flask templates and static files
- `ML_RAG_archive/` - Previous ML experiments

---

## 🧹 What Was Cleaned Up

### **Removed from Root**
- `test_infeasibility_handling.py` → moved to `tests/`
- `templates/` → archived (old Flask templates)
- `static/` → archived (old static files)
- `analysis/analyzers/` → archived (replaced by generic framework)

### **Organized**
- Documentation centralized in `docs/`
- Tests properly organized in `tests/` with subdirectories
- Old experiments archived in `archive/`

### **Preserved**
- All working code remains in place
- Import structure unchanged (no breaking changes)
- `api.py` kept at root (still used by agent for visualization)

---

## 📊 Current Status

### ✅ Production Ready
- Problem classification (100% accuracy)
- 3-layer feasibility checking
- Sensitivity analysis
- What-if scenarios
- Re-solve with modifications
- Transportation & scheduling solvers

### 🚧 In Progress
- Pareto front generation (started)

### 📋 Priority Queue
1. **Data Layer** (Priority 1) - CSV/Excel loading
2. **Model Persistence** (Priority 2) - Cache models for faster analysis
3. **Solver Strategy Selection** (Priority 3) - Auto-route to exact/heuristic/decomposition
4. **Decomposition** (Priority 4) - Benders, Dantzig-Wolfe, column generation

---

## 🔍 Finding Your Way Around

**Want to solve a problem?** → Start with `agent/core.py`

**Want to add analysis features?** → Check `analysis/README.md`

**Want to add a new solver?** → See `solvers/base.py` and `solvers/registry.py`

**Want to add data loading?** → Implement in `data/loaders/` (see `docs/brainstorm_ideas.md` Priority 1)

**Looking for old code?** → Check `archive/` directories

**Need documentation?** → See `docs/` directory

---

## 🧪 Running Tests

```bash
# All tests
pytest tests/

# Specific module
pytest tests/test_feasibility.py

# With coverage
pytest tests/ --cov=.
```

---

## 📚 Key Documentation Files

- `docs/README.md` - Main project documentation
- `docs/brainstorm_ideas.md` - Architecture, bottlenecks, and 6-month roadmap
- `docs/Claude_Diary.md` - Detailed development history
- `analysis/README.md` - Analysis framework documentation (comprehensive)
- `STRUCTURE.md` - This file - repository organization

---

## 🎯 Next Steps

According to `docs/brainstorm_ideas.md`, the most critical task is:

**Priority 1: Data Layer (2-3 days)**
- Implement CSV/Excel loaders in `data/loaders/`
- Add schema detection in `data/mappers/`
- Enable users to load real business data files

This is **blocking production usage** and should be tackled first.

---

**Repository Status:** Clean and ready for Priority 1 implementation!
