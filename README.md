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
- **Plugin-Based Solvers**: Easily add new optimization problem types
- **Hybrid Classification**: Combines rule-based labeling functions with ML (ready for training)
- **Local LLM Integration**: Uses Ollama for privacy and cost-effectiveness
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
- `tests/` - **Working examples** - run these to see how it works (7 tests, all pass)
- `api.py` - Web server (FastAPI) - for future chat/web interface
- `setup.bat` / `setup.sh` - Installation scripts
- `run.bat` - Quick launcher (Windows)

### **Core System** (Main logic flow)
- `agent/` - **Main orchestrator**
  - `core.py` - Entry point, routes all requests (READ THIS FIRST)
- `llm/` - **Language understanding** (14 files)
  - `intent_router.py` - Detects: new problem vs question vs analysis
  - `transportation_specialist.py` - Extracts shipping parameters from text
  - `scheduling_specialist.py` - Extracts scheduling parameters from text
  - `ollama_client.py` - Communicates with Ollama LLM
- `solvers/` - **Mathematical optimization** (7 files)
  - `transportation_solver.py` - Solves shipping/distribution problems
  - `scheduling_solver.py` - Solves task scheduling problems
  - `base.py` - Interface all solvers must implement
- `analysis/` - **Post-processing**
  - Creates charts (flow diagrams, cost breakdowns, utilization)
  - Runs sensitivity analysis

### **Classification System** (Problem type detection)
- `or_classify/` - **Hybrid classifier** (rules + ML)
  - `lfs/` - 25 labeling functions (deterministic pattern matching)
  - `feature_pipeline.py` - Converts text to ML features
  - `taxonomy.yml` - 9 problem families, 25+ subtypes
  - **Status:** Works with rules, ML training optional for better accuracy

### **Web Interface** (For future use)
- `schemas/` - API request/response validation schemas
- `templates/` - HTML pages for web UI
- `static/` - CSS/JavaScript (empty, for future use)

### **Configuration**
- `config.py` - System settings (Ollama host/model, API port)
- `requirements.txt` - Python dependencies
- `Claude_Diary.md` - Development log and roadmap
- `.gitignore` - Excludes Tolis_Env/, __pycache__, etc.

## 🚦 Quick Start

### **Windows Users:**
```batch
setup.bat           # Install (5-10 min, one-time)
run.bat            # Run tests
```
See `INSTALL_WINDOWS.md` for detailed help.

### **Mac/Linux Users:**
```bash
./setup.sh         # Install
source Tolis_Env/bin/activate
cd tests
python Overall_Test.py  # See it work!
```

### **Prerequisites:**
- Python 3.8+ ([python.org](https://python.org))
- Ollama with qwen2:7b model ([ollama.ai](https://ollama.ai))
- GLPK solver (see INSTALL_WINDOWS.md)

### **Run the Tests** (Recommended):
```bash
cd tests/
python Overall_Test.py              # Main demo - shows full reasoning
python test_complete_workflow.py   # Wine distribution example
python -m pytest test_llm_refactoring.py -v  # 44 unit tests
```
See `tests/README.md` for details.

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
- **Subcategory-level**: ⚠️ **BLOCKED** - requires ML training
  - Zero-shot LLM: ~25% accuracy on scheduling subtypes
  - Infrastructure ready: 25 labeling functions + feature pipeline
  - **Waiting for training data** (see `RESUME_WHEN_DATA_READY.md`)

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

# All tests
python -m pytest tests/ -v

# Specific test suites
python tests/test_llm_refactoring.py          # 44 unit tests
python tests/test_phase1_runner.py --categories TRANSPORTATION
python tests/test_phase1_runner.py --categories SCHEDULING

# Integration tests
python tests/Overall_Test.py                   # Full reasoning chain demo
python tests/test_complete_workflow.py
```

### **Test Coverage**
- 15 test files covering all components
- 44+ unit tests for LLM refactoring
- 30+ classification test cases
- 18 scheduling test cases
- Integration tests for end-to-end workflows

See `tests/README.md` for detailed test documentation.

## 🔧 Configuration

### **Environment Variables**
```bash
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2:7b
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
- ⚠️ **Classification blocked**: Scheduling subcategories require ML training
  - Current: 25% accuracy on subcategories
  - Infrastructure ready, waiting for training data
  - See `RESUME_WHEN_DATA_READY.md` for details

- ⚠️ **Scheduling scope limited**: Only single-stage problems
  - ✅ Can solve: single_stage_scheduling, batch_scheduling
  - ❌ Cannot solve: job_shop, flow_shop, shift_rostering, project_scheduling

- 🚧 **Other problem types**: Infrastructure ready, solvers not implemented yet

### **Development Roadmap**
See `RESUME_WHEN_DATA_READY.md` for:
- ML training requirements
- Data collection progress
- Success metrics
- Next steps

## 📂 Detailed File Map

**Main execution flow** (in order):
1. `agent/core.py` - Entry point, orchestrates everything
2. `llm/intent_router.py` - Classifies user intent
3. `llm/*_specialist.py` - Extracts structured parameters
4. `solvers/*_solver.py` - Solves optimization problem
5. `analysis/engine.py` - Generates visualizations

**Key files to understand:**
- `agent/core.py` - Start here, 400 lines, main orchestrator
- `llm/ollama_client.py` - LLM communication, structured output
- `solvers/transportation_solver.py` - Example solver (Pyomo + GLPK)
- `or_classify/lfs/` - Classification rules (25 files)

**Complete tree:**
```
agent/core.py              Main orchestrator (read this first)
llm/intent_router.py       Detects problem vs question vs analysis
llm/transportation_specialist.py   Extracts shipping params
llm/scheduling_specialist.py       Extracts scheduling params
llm/ollama_client.py       Talks to Ollama LLM
solvers/transportation_solver.py   Solves shipping problems
solvers/scheduling_solver.py       Solves scheduling problems
solvers/base.py            Solver interface
analysis/engine.py         Creates charts
or_classify/lfs/           25 classification rules
tests/Overall_Test.py      Best example to understand flow
api.py                     Web server (not updated)
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

- 📖 **Documentation**: See `tests/README.md`, `RESUME_WHEN_DATA_READY.md`
- 📝 **Development Log**: `Claude_Diary.md`
- 🐛 **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)

---

**Current Status**: Transportation fully working, Scheduling solver implemented but classification blocked on ML training.

**Next Milestone**: Train hybrid classifier to fix scheduling subcategory detection (requires 40-50 training examples).

**Made with ❤️ for the optimization community**
