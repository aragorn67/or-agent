# 🧠 Optimization AI Agent

> **Transform natural language into optimized solutions with AI-powered mathematical optimization**

An intelligent optimization agent that understands complex problems described in plain English, automatically extracts parameters, solves them using state-of-the-art optimization techniques, and provides comprehensive analysis with dynamic visualizations.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## ✨ Features

### 🎯 **Intelligent Problem Understanding**
- **Natural Language Processing**: Describe optimization problems in plain English
- **Automatic Parameter Extraction**: AI extracts capacities, demands, costs, and constraints
- **Problem Classification**: Automatically detects problem types (Transportation, Scheduling, etc.)
- **Smart Validation**: Provides helpful feedback for incomplete or inconsistent descriptions

### 🔬 **Advanced Analysis Capabilities**
- **Sensitivity Analysis**: "Show how Seattle capacity affects total cost"
- **What-If Scenarios**: "What happens if freight costs increase by 20%?"
- **Variable Relationships**: "Plot the connection between production and demand"
- **Dynamic Visualizations**: Professional charts generated automatically
- **Pareto Analysis**: Multi-objective optimization insights

### 🚀 **Modern Architecture**
- **Plugin-Based Solvers**: Easily add new optimization problem types
- **Local LLM Integration**: Uses Ollama for privacy and cost-effectiveness
- **Real-Time Progress**: Beautiful progress indicators during solving
- **Scalable Design**: Ready for production deployment
- **Web Interface**: Clean, intuitive browser-based interface

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Interface │───▶│  Optimization   │───▶│     Solvers     │
│   (FastAPI +    │    │     Agent       │    │   (Pyomo +     │
│     HTML)       │    │   (LLM Core)    │    │     GLPK)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐             │
         └─────────────▶│   Analysis      │◀────────────┘
                        │    Engine       │
                        │ (Plots & Stats) │
                        └─────────────────┘
```

### 🧱 **Core Components**

1. **🌐 Web Layer** (`api.py`) - FastAPI server handling HTTP requests
2. **🧠 AI Agent** (`agent/core.py`) - Intelligent problem orchestrator
3. **⚙️ Solvers** (`solvers/`) - Mathematical optimization engines
4. **🔍 Analysis** (`analysis/`) - Dynamic plotting and sensitivity studies
5. **🤖 LLM Client** (`llm/`) - Natural language understanding

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

### 📝 **Text Input**
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

Shipping costs $90 per case per 1000 miles. Show me how Seattle
capacity affects total costs.
```

### 🎯 **Expected Output**
- ✅ **Optimal shipping plan** with minimum cost
- 📊 **Sensitivity analysis plot** showing capacity vs cost
- 📝 **Natural language explanation** of the solution
- 🔢 **Detailed technical results** in JSON format

### 📁 **File Input**
Create a `.txt` file with your problem description and use the file input tab.

## 🔬 Analysis Capabilities

### **Sensitivity Analysis**
- "How does factory capacity affect total cost?"
- "Show the impact of freight rates on shipping decisions"
- "Plot demand sensitivity"

### **Scenario Comparison**
- "Compare solutions with different freight costs"
- "What if I add another factory?"
- "Analyze best-case vs worst-case scenarios"

### **Variable Relationships**
- "Show connection between Seattle production and Chicago demand"
- "Plot capacity utilization across all plants"
- "Visualize cost trade-offs"

## 🛠️ Technical Details

### **Supported Problem Types**
- ✅ **Transportation Problems** (factories → customers)
- 🚧 **Knapsack Problems** (coming soon)
- 🚧 **Scheduling Problems** (coming soon)
- 🚧 **Assignment Problems** (coming soon)

### **LLM Integration**
- **Local Processing**: Uses Ollama for privacy
- **Configurable Models**: Support for various open-source models
- **Smart Prompting**: Optimized prompts for mathematical problems
- **Error Handling**: Graceful fallbacks and user-friendly error messages

### **Optimization Engine**
- **Pyomo**: Professional optimization modeling
- **GLPK**: Open-source linear programming solver
- **Extensible**: Easy to add new solvers (CPLEX, Gurobi, etc.)

## 📡 API Reference

### **Core Endpoints**

- `POST /solve/natural` - Solve from natural language
- `POST /solve/file` - Solve from text file
- `GET /agent/capabilities` - List supported problem types
- `POST /agent/classify` - Classify problem type only

### **Legacy Endpoints**
- `POST /solve/transport` - Direct structured input
- `POST /qa/transport` - Q&A about solutions
- `POST /plots/transport` - Generate visualizations

## 🔧 Configuration

### **Environment Variables**
```bash
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2:7b
API_HOST=0.0.0.0
API_PORT=8000
```

### **Adding New Solvers**
1. Create `solvers/new_problem.py`
2. Implement `OptimizationSolver` interface
3. Add to auto-registration system
4. Solver automatically available via API

## 🚀 Deployment

### **Development**
```bash
uvicorn api:app --reload
```

### **Production**
```bash
uvicorn api:app --host 0.0.0.0 --port 80 --workers 4
```

### **Docker** (Coming Soon)
```bash
docker build -t optimization-ai .
docker run -p 8000:8000 optimization-ai
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### **Adding New Problem Types**
- Implement `OptimizationSolver` interface
- Add corresponding analysis capabilities
- Update LLM prompts for problem classification
- Add examples and tests

## 📋 Roadmap

- [ ] **More Problem Types**: Knapsack, Scheduling, Assignment
- [ ] **Advanced Analysis**: Pareto fronts, Monte Carlo simulation
- [ ] **React Frontend**: Professional web application
- [ ] **User Authentication**: Save and share optimization models
- [ ] **Cloud Deployment**: Kubernetes, Docker support
- [ ] **API Documentation**: Interactive OpenAPI docs
- [ ] **Performance**: Caching, optimization
- [ ] **Integrations**: Excel, CSV import/export

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Pyomo** for the optimization modeling framework
- **FastAPI** for the modern web framework
- **Ollama** for local LLM capabilities
- **GLPK** for the linear programming solver

## 📞 Support

- 🐛 **Issues**: [GitHub Issues](link-to-issues)
- 💬 **Discussions**: [GitHub Discussions](link-to-discussions)
- 📧 **Email**: your-email@domain.com

---

**Made with ❤️ for the optimization community**