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

## 🏗️ Architecture

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Web Interface   │───▶│  Optimization    │───▶│    Solvers       │
│  (FastAPI +      │    │     Agent        │    │  (Pyomo +       │
│     HTML)        │    │  (Intent Router) │    │     GLPK)       │
└──────────────────┘    └──────────────────┘    └──────────────────┘
         │                       │                        │
         │              ┌──────────────────┐             │
         └─────────────▶│   Analysis       │◀────────────┘
                        │    Engine        │
                        │ (Plots & Stats)  │
                        └──────────────────┘
                                 │
                        ┌──────────────────┐
                        │  Hybrid          │
                        │  Classifier      │
                        │  (LFs + ML)      │
                        └──────────────────┘
```

### 🧱 **Core Components**

1. **🌐 Web Layer** (`api.py`) - FastAPI server with file upload and real-time progress
2. **🧠 AI Agent** (`agent/core.py`) - Intelligent orchestrator with intent routing
3. **⚙️ Solvers** (`solvers/`) - Mathematical optimization engines
   - `transportation_solver.py` - Multi-source distribution problems
   - `scheduling_solver.py` - Single-stage continuous process scheduling (IPM model)
   - `capabilities.py` - Solver capability mapping
4. **🔍 Analysis** (`analysis/`) - Dynamic plotting and sensitivity studies
5. **🤖 LLM Clients** (`llm/`) - Natural language understanding
   - `ollama_client.py` - Base LLM client
   - `intent_router.py` - Intent detection (smalltalk, help, optimization, follow-up)
   - `follow_up_handler.py` - Deterministic follow-up responses
   - `*_specialist.py` - Problem-specific parameter extraction
6. **📊 Hybrid Classifier** (`or_classify/`) - Production-grade classification system
   - 25 rule-based labeling functions
   - Feature pipeline (TF-IDF + engineered features)
   - Ready for ML training

## 🚦 Quick Start

### Prerequisites
- Python 3.8+
- [Ollama](https://ollama.ai/) installed and running
- GLPK optimization solver

### 🔧 Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd Optimization-AI-
   ```

2. **Run setup script**
   ```bash
   ./setup.sh
   ```

   Or manually:
   ```bash
   python3 -m venv Tolis_Env
   source Tolis_Env/bin/activate
   pip install -r requirements.txt
   ```

3. **Install GLPK solver**
   ```bash
   # Ubuntu/Debian
   sudo apt install glpk-utils

   # macOS
   brew install glpk
   ```

4. **Install and start Ollama**
   ```bash
   # Install Ollama (see https://ollama.ai)
   ollama pull qwen2:7b  # Or any supported model
   ```

### 🚀 Launch

```bash
source Tolis_Env/bin/activate
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Open your browser to **http://localhost:8000**

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

### **Adding New Solvers**
1. Create `solvers/new_problem_solver.py`
2. Implement `OptimizationSolver` interface:
   ```python
   class NewProblemSolver(OptimizationSolver):
       def solve(self, params: Dict) -> Dict:
           # Your optimization logic
           pass

       def validate_params(self, params: Dict) -> List[str]:
           # Validation logic
           pass

       def get_example_params(self) -> Dict:
           # Example parameter structure
           pass
   ```
3. Add to `solvers/__init__.py` registration
4. Update `solvers/capabilities.py` with supported subcategories
5. Solver automatically available via API

### **Adding Labeling Functions**
```python
# or_classify/lfs/custom_lfs.py
from or_classify.labeling_function import LabelingFunction, LFResult, LFPriority

@LabelingFunction.register
class MyCustomLF(LabelingFunction):
    priority = LFPriority.HIGH

    def apply(self, text: str) -> LFResult:
        if "custom pattern" in text.lower():
            return LFResult(
                label="my_problem_type",
                confidence=0.95,
                evidence=["Found custom pattern"],
                priority=self.priority
            )
        return self.abstain()
```

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

## 📂 Project Structure

```
Optimization-AI-/
├── agent/                  # Core agent orchestration
│   ├── core.py            # Main OptimizationAgent with intent routing
│   └── __init__.py
├── solvers/               # Optimization solvers
│   ├── base.py            # OptimizationSolver interface
│   ├── transportation_solver.py
│   ├── scheduling_solver.py
│   ├── capabilities.py    # Solver capability mapping
│   ├── ipm_scheduler.py   # IPM model implementation
│   └── __init__.py
├── llm/                   # LLM clients and utilities
│   ├── client.py          # Abstract LLM interface
│   ├── ollama_client.py   # Ollama implementation
│   ├── intent_router.py   # Intent detection
│   ├── follow_up_handler.py
│   ├── scheduling_specialist.py
│   ├── transportation_specialist.py
│   └── ... (14 files total)
├── or_classify/           # Hybrid classifier infrastructure
│   ├── taxonomy.yml       # 9 families, 25+ subtypes
│   ├── aliases.yml        # 50+ synonym mappings
│   ├── normalizer.py      # Label normalization
│   ├── labeling_function.py  # LF framework
│   ├── feature_pipeline.py   # ML feature extraction
│   └── lfs/               # 25 labeling functions
│       ├── assignment_lfs.py
│       ├── scheduling_lfs.py
│       ├── knapsack_lfs.py
│       └── ... (7 files total)
├── analysis/              # Analysis engines
│   ├── engine.py
│   ├── detector.py
│   └── analyzers/         # Problem-specific analyzers
├── tests/                 # Test suite
│   ├── README.md
│   ├── phase1_test_cases.py   # 30 classification tests
│   ├── test_phase1_runner.py  # Test runner with CLI
│   └── ... (15 files total)
├── api.py                 # FastAPI web server
├── requirements.txt       # Python dependencies
├── README.md              # This file
├── Claude_Diary.md        # Development log
├── RESUME_WHEN_DATA_READY.md  # ML training blocker
├── docs/                  # Documentation
│   └── archive/           # Old documentation
│       ├── ROADMAP.md
│       └── REFACTORING_SUMMARY.md
└── archive/               # Unused code
    └── conversation/      # Old conversation module
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
