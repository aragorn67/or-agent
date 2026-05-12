# 🧠 Optimization AI Agent

> **Transform natural language into optimized solutions with AI-powered mathematical optimization**

An intelligent optimization agent that understands complex problems described in plain English, automatically extracts parameters, solves them using state-of-the-art optimization techniques, and provides comprehensive analysis with dynamic visualizations.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.117+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## ✨ Key Features

### 🎯 **Intelligent Problem Understanding**
- **Natural Language Processing**: Describe optimization problems in plain English
- **Automatic Parameter Extraction**: AI extracts capacities, demands, costs, and constraints
- **Hierarchical Classification**: Detects problem categories and specific subtypes
- **Smart Validation**: Provides helpful feedback for incomplete or inconsistent descriptions
- **Intent Detection**: Distinguishes between new problems, follow-up questions, and analysis requests

### 🔬 **Advanced Analysis Capabilities**
- **Sensitivity Analysis**: "Show how Seattle capacity affects total cost"
- **What-If Scenarios**: "What happens if freight costs increase by 20%?"
- **Variable Relationships**: "Plot the connection between production and demand"
- **Dynamic Visualizations**: Professional charts generated automatically
- **Solution Explanations**: Clear, business-friendly interpretations

### 🚀 **Modern Architecture**
- **Modular Solver Registry**: Solvers register via `OptimizationSolver` interface (`solvers/base.py`); currently ships two: bipartite transportation and single-stage IPM scheduling
- **LLM-Based Classification**: DeepSeek-R1 with a 5-vote majority over a JSON-Schema-bound taxonomy. (Rule-based labeling functions and an ML classifier were prototyped — both underperformed and are preserved in `ML_RAG_archive/` for reference.)
- **Local LLM Integration**: Three-stage Ollama pipeline (small classifier, coder for extraction, reasoning model for explanations) for privacy and cost-effectiveness
- **Real-Time Progress**: Beautiful progress indicators during solving
- **Scalable Design**: Ready for production deployment
- **Web Interface**: Clean, intuitive browser-based interface

## 🏗️ How It Works: Input → Answer

**You give:** Natural language text describing an optimization problem

**System does:**
1. **Classify** problem type (transportation, scheduling, etc.) → `or_classify/` or `llm/`
2. **Extract** parameters (capacities, costs, constraints) → `llm/*_specialist.py`
3. **Solve** using mathematical optimization → `solvers/`
4. **Analyze** results and create visualizations → `analysis/`
5. **Return** solution + explanation + charts

**Data Flow:**
```
Text Input → agent/core.py → LLM classifies → Specialist extracts params → Solver optimizes → Analysis plots → Answer
```

---

## 📁 Folder Structure & Purpose

### **Entry Points** (Start here)
- `tests/` - **Working examples** - run these to see how it works (11 tests, all pass)
- `api.py` - Web server (FastAPI) - for future chat/web interface
- `setup.bat` / `setup.sh` - Installation scripts
- `run.bat` - Quick launcher (Windows)

### **Core System** (Main logic flow)
- `agent/` - **Main orchestrator**
  - `core.py` - Entry point, routes all requests (READ THIS FIRST)
- `llm/` - **Language understanding**
  - `intent_router.py` - Detects: new problem vs question vs analysis
  - `problem_classifier.py` - LLM-based classification (70% on 27-problem OR-Library; 90% on 10-problem solvable subset)
  - `transportation_specialist.py` - Extracts shipping parameters from text
  - `scheduling_specialist.py` - Extracts scheduling parameters from text
  - `ollama_client.py` - Communicates with Ollama LLM
- `solvers/` - **Mathematical optimization**
  - `registry.py` - Central solver registration system
  - `transport/bipartite.py` - Bipartite matching for transportation
  - `scheduling/single_stage_ipm.py` - Interior point method for scheduling
  - `base.py` - Interface all solvers must implement
- `feasibility/` - **3-Layer Feasibility Checking** ⭐ NEW
  - Layer 0: Structural validation (dimensions, empty sets)
  - Layer 1: Problem-specific logic (supply/demand balance)
  - Layer 2: LP relaxation feasibility check
- `analysis/` - **Post-processing**
  - Creates charts (flow diagrams, cost breakdowns, utilization)
  - Runs sensitivity analysis

### **Classification System** (Problem type detection)
- `or_classify/` - Hybrid-classifier scaffolding (rules + ML); **not used in production** — production path is `llm/problem_classifier.py`
  - `lfs/` - 25 labeling functions (deterministic pattern matching)
  - `feature_pipeline.py` - Converts text to ML features
  - `taxonomy.yml` - 9 problem families, 25+ subtypes
  - **Status:** LLM-based classification used in production (70% on 27-problem OR-Library; 90% on 10-problem solvable subset). ML classifier was prototyped, scored 44% on OR-Library, and was archived (`ML_RAG_archive/`).

### **Web Interface** (For future use)
- `schemas/` - API request/response validation schemas
- `templates/` - HTML pages for web UI
- `static/` - CSS/JavaScript (empty, for future use)

### **Configuration & Documentation**
- `config.py` - System settings (Ollama host/model, API port)
- `requirements.txt` - Python dependencies
- `Claude_Diary.md` - Development log with TODO list and implemented features
- `ML_RAG_archive/` - ⚠️ **Archived experiments** (ML classifier & RAG - not used in production)
- `.gitignore` - Excludes Tolis_Env/, __pycache__, etc.

## 🚦 Quick Start

### **Windows Users:**
```batch
setup.bat           # Install (5-10 min, one-time)
run.bat            # Run tests
```

### **Mac/Linux Users:**
```bash
./setup.sh         # Install
source Tolis_Env/bin/activate
python tests/demos/OptAI_interactive.py  # See it work
```

### **Prerequisites:**
- Python 3.8+ ([python.org](https://python.org))
- Ollama running locally ([ollama.ai](https://ollama.ai)) with the three models pulled:
  - `qwen2.5:3b-instruct` (classification)
  - `qwen2.5-coder:7b` (parameter extraction)
  - `deepseek-r1:latest` (reasoning / explanations)
- GLPK solver (Linux: `sudo apt install glpk-utils`; macOS: `brew install glpk`)

### **Run the Tests** (Recommended):
```bash
python -m pytest tests/                       # 75 unit/integration tests
python -m pytest tests/test_llm_refactoring.py -v  # 44 LLM-stack unit tests

# Walk-through demos (require Ollama running):
python tests/demos/complete_analysis_suite.py
python tests/demos/OptAI_interactive.py
```

## 💡 Usage Examples

### 📦 **Transportation Problem**
```
I need to optimize shipping costs for my company. We have two factories
and three customers.

Factory Seattle can produce 350 cases per day.
Factory San Diego can produce 600 cases per day.

Customer New York needs 325 cases.
Customer Chicago needs 300 cases.
Customer Topeka needs 275 cases.

The distances are:
- Seattle to New York: 2500 miles
- Seattle to Chicago: 1700 miles
- Seattle to Topeka: 1800 miles
- San Diego to New York: 2500 miles
- San Diego to Chicago: 1800 miles
- San Diego to Topeka: 1400 miles

Shipping costs $90 per case per 1000 miles.
```

### 📅 **Scheduling Problem**
```
Schedule 3 production orders (O1, O2, O3) on 2 processing units (U1, U2).

Order O1: can use U1 (2 hours) or U2 (3 hours), due by hour 10
Order O2: can use U1 (4 hours) or U2 (2 hours), due by hour 8
Order O3: only U2 (3 hours), due by hour 12

Changeover between orders: 0.5 hours
Minimize total completion time (makespan).
```

### 🎯 **Expected Output**
- ✅ **Optimal solution** with minimum cost/makespan
- 📊 **Visualizations** (shipment flows, schedules, utilization)
- 📝 **Natural language explanation** of the solution
- 🔢 **Detailed technical results** in JSON format
- 📈 **Analysis plots** if requested

## 🛠️ Supported Problem Types

### ✅ **Currently Implemented**
- **Transportation Problems** - Multi-source distribution optimization
  - Balanced and unbalanced problems
  - Distance-based and direct cost matrices
  - Capacity constraints and demand requirements

- **Scheduling Problems** - Single-stage continuous process scheduling
  - ✅ `single_stage_scheduling` - Orders on processing units (IPM model)
  - ✅ `batch_scheduling` - Chemical/pharmaceutical batch processing
  - ⚠️ Limited to single processing step per order
  - **Not supported**: job_shop, flow_shop, shift_rostering, project_scheduling

### 🔄 **Classification System Status**
- **Category-level**: 80% accuracy (TRANSPORTATION vs SCHEDULING)
- **Subcategory-level**: ⚠️ **Blocked on evaluation, not model**
  - Zero-shot LLM is ~25% on scheduling subtypes, but with only a 10–27 problem benchmark the noise floor is too high to iterate on
  - Infrastructure ready: 25 labeling functions + feature pipeline
  - The original plan was to gather training data; a more promising path is programmatic eval expansion (paraphrase + metamorphic + reverse-generation) before any retraining

### 🚧 **In Development**
- **Assignment Problems** - Worker-task matching (infrastructure ready)
- **Knapsack Problems** - Resource selection (labeling functions ready)
- **Network Flow** - Max flow, min-cost flow (labeling functions ready)
- **Lot Sizing** - Production planning (labeling functions ready)

## 📡 API Reference

### **Core Endpoints**

#### **Main Solving Endpoint**
```
POST /solve/natural
Body: {"description": "your problem in natural language"}
Response: {
  "success": true,
  "problem_type": "transportation",
  "solution": {...},
  "explanation": "Natural language explanation",
  "summary": "Brief summary"
}
```

#### **Classification Only**
```
POST /agent/classify
Body: {"description": "your problem"}
Response: {
  "problem_type": "transportation",
  "confidence": 0.95,
  "signals": {...}
}
```

#### **Capabilities**
```
GET /agent/capabilities
Response: {
  "supported_types": ["transportation", "scheduling"],
  "capabilities": {
    "transportation": {
      "description": "Multi-source distribution",
      "example_params": {...}
    }
  }
}
```

### **Legacy Endpoints** (for backwards compatibility)
- `POST /solve/transport` - Direct structured input
- `POST /qa/transport` - Q&A about solutions
- `POST /plots/transport` - Generate visualizations

## 🧪 Testing

### **Run Tests**
```bash
source Tolis_Env/bin/activate

# All pytest-collected tests
python -m pytest tests/ -v                       # 75 tests collected

# Specific suites
python -m pytest tests/test_llm_refactoring.py -v   # 44 LLM-stack unit tests
python -m pytest tests/test_feasibility.py -v       # 3-layer feasibility checker
python -m pytest tests/test_normalizer.py -v        # label normalizer

# Walk-through demos (require Ollama running)
python tests/demos/complete_analysis_suite.py
python tests/demos/OptAI_interactive.py
```

### **Test Coverage**
- 75 pytest-collected tests across `tests/`
- 44 LLM-stack unit tests in `test_llm_refactoring.py`
- 3-layer feasibility checker (`test_feasibility.py`) — 12 tests
- Demo / walk-through scripts in `tests/demos/` (not collected by pytest)

## 🔧 Configuration

### **Environment Variables**
```bash
OLLAMA_HOST=http://localhost:11434
CLASSIFICATION_MODEL=qwen2.5:3b-instruct    # intent + problem classifier
EXTRACTION_MODEL=qwen2.5-coder:7b           # structured JSON parameter extraction
REASONING_MODEL=deepseek-r1:latest          # explanations, infeasibility repair
API_HOST=0.0.0.0
API_PORT=8000
```

### **How to Add a New Problem Type**

1. **Create solver** in `solvers/your_problem_solver.py`
   - Implement `OptimizationSolver` interface (see `base.py`)
   - Add to `solvers/__init__.py`

2. **Create LLM specialist** in `llm/your_problem_specialist.py`
   - Extract parameters from natural language
   - See `transportation_specialist.py` as example

3. **Add classification rules** in `or_classify/lfs/your_problem_lfs.py`
   - Write labeling functions to detect this problem type
   - See existing LFs for patterns

4. **Update capabilities** in `solvers/capabilities.py`
   - Document what problem subtypes your solver handles

5. **Add tests** in `tests/`
   - Create test cases for your problem type

**See `transportation_solver.py` + `transportation_specialist.py` as complete example.**

## 📊 Project Status

### **What Works**
- ✅ Transportation optimization (end-to-end)
- ✅ Single-stage scheduling (solver works, classification blocked)
- ✅ Natural language problem understanding
- ✅ Intent detection and routing
- ✅ Follow-up question handling
- ✅ Dynamic visualizations
- ✅ Web interface with file upload

### **Known Limitations**
- ⚠️ **Subcategory classification noisy**: ~25% on scheduling subtypes, but measured on a small (10–27 problem) benchmark — the next step is programmatic eval expansion, not more model work
- ⚠️ **Scheduling scope limited**: Only single-stage problems
  - ✅ Can solve: single_stage_scheduling, batch_scheduling
  - ❌ Cannot solve: job_shop, flow_shop, shift_rostering, project_scheduling
- 🚧 **Other problem types**: Taxonomy + labeling-function scaffolding exist; no solvers yet
- ⚠️ **No data layer**: All input is natural-language text. CSV/Excel ingestion is the next major piece (see `brainstorm_ideas.md` Priority 1)

### **Development Roadmap**
See `brainstorm_ideas.md` for the prioritized roadmap (data layer, model persistence, solver-strategy selection, decomposition).

## 📂 Detailed File Map

**Main execution flow** (in order):
1. `agent/core.py` - Entry point, orchestrates everything
2. `llm/intent_router.py` - Classifies user intent
3. `llm/*_specialist.py` - Extracts structured parameters
4. `solvers/*_solver.py` - Solves optimization problem
5. `analysis/engine.py` - Generates visualizations

**Key files to understand:**
- `agent/core.py` - Start here, ~830 lines, main orchestrator
- `llm/enhanced_client.py` - Three-stage LLM pipeline + specialist dispatch
- `llm/ollama_client.py` - HTTP layer for Ollama, JSON mode, error mapping
- `solvers/transport/bipartite.py` - Bipartite transportation solver (Pyomo + GLPK)
- `solvers/scheduling/single_stage_ipm.py` - Single-stage scheduling solver
- `feasibility/core.py` - 3-layer feasibility checker

**Complete tree:**
```
agent/core.py                            Main orchestrator (read this first)
llm/enhanced_client.py                   3-stage LLM pipeline + specialist dispatch
llm/intent_router.py                     Smalltalk / help / optimization / follow-up
llm/problem_classifier.py                Schema-bound classifier with 5-vote majority
llm/transportation_specialist.py         Extracts shipping params (JSON)
llm/scheduling_specialist.py             Extracts scheduling params (JSON)
llm/ollama_client.py                     Talks to Ollama LLM
solvers/transport/bipartite.py           Solves bipartite shipping problems
solvers/scheduling/single_stage_ipm.py   Solves single-stage scheduling
solvers/base.py                          Solver interface
feasibility/core.py                      3-layer feasibility orchestrator
analysis/engine.py                       Creates charts
or_classify/lfs/                         25 classification rules (scaffolding)
tests/demos/OptAI_interactive.py         Best demo to understand the flow
api.py                                   Web server (not currently used by the agent path)
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### **Development Guidelines**
- All LLM interactions must go through `llm/client.py` interface
- New solvers must implement `OptimizationSolver` interface
- Add labeling functions for new problem types
- Include tests for new features
- Update `solvers/capabilities.py` for new problem subtypes

## 📄 License

This project is licensed under the MIT License.

## 🙏 Acknowledgments

- **Pyomo** for the optimization modeling framework
- **FastAPI** for the modern web framework
- **Ollama** for local LLM capabilities
- **GLPK** for the linear programming solver
- **scikit-learn** for ML infrastructure

## 📞 Support & Contact

- 📖 **Documentation**: See `Claude_Diary.md` for development log and TODO list
- 📝 **Archived Experiments**: `ML_RAG_archive/README.md` - ML classifier & RAG experiments (not used in production)
- 🧪 **Test Repository**: `tests/or_problem_repository.py` - 27 diverse OR problems for testing
- 🐛 **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)

---

**Current Status**: ✅ Core features production-ready (Classification, Feasibility Checking, Multi-Stage Solvers)

**Next Milestone**: Lift classification on the full 27-problem OR-Library set from 70% toward 80-90% (already 90% on the 10-problem solvable subset; see `Claude_Diary.md` TODO list)

**Made with ❤️ for the optimization community**
