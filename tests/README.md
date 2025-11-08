# Tests Directory

All tests for the Optimization AI platform.

---

## Quick Start

```bash
# Run the main test (recommended)
python Overall_Test.py

# Run all unit tests
python -m pytest test_llm_refactoring.py -v
```

---

## Structure

```
tests/
├── Overall_Test.py                       ⭐ Main demo (6 prompts with reasoning)
├── test_llm_refactoring.py               44 unit tests (all pass)
├── test_complete_workflow.py             End-to-end with plots (passes)
├── test_with_llm_analysis_requests.py    LLM request handling (passes)
│
├── test_normalizer.py                    Label normalization tests (5 pass)
├── transportation_test_cases.py          19 test scenarios (data file)
├── phase1_test_cases.py                  30 classification tests
├── test_phase1_runner.py                 Classification test runner
│
└── test_output/                          Generated plots (PNG files)
```

---

## Core Tests

### ⭐ **Overall_Test.py** (Start Here)
Shows complete LLM reasoning for 6 prompts:
1. Optimization problem → Solves it
2. "What is the objective?" → Deterministic answer
3. "Show me flows" → Creates horizontal bar chart
4. "Show me costs" → Creates vertical bar chart
5. "Show utilization" → Creates stacked bar chart
6. "What if +20% capacity?" → Sensitivity analysis

**Output:** Console reasoning + 3 PNG plots

---

### **test_llm_refactoring.py**
44 unit tests covering:
- Intent detection
- Follow-up handling
- JSON extraction
- Configuration
- Error handling
- 10 transportation scenarios

**Run:** `python -m pytest test_llm_refactoring.py -v`
**Expected:** 44/44 pass

---

### **test_complete_workflow.py**
European Wine Distribution problem:
- 3 wineries → 4 cities
- Optimal cost: €4,750
- Generates: flow network, cost breakdown, utilization plots

**Output:** 3 PNG plots in `test_output/`

---

### **test_with_llm_analysis_requests.py**
Tests LLM understanding of 7 analysis requests:
- Objective question
- Variables question
- 3 visualization requests
- Modification request
- Capabilities question

**Output:** 3 PNG plots in `test_output/`

---

## Additional Test Files

- **test_normalizer.py** - Label normalization for classification system (5 tests)
- **transportation_test_cases.py** - 19 transportation problem scenarios (data file)
- **phase1_test_cases.py** - 30 problem classification test cases
- **test_phase1_runner.py** - Runner for classification tests with CLI options

---

## Test Output

All tests save plots to `test_output/` with timestamps:
```
test_output/
├── 20251011_184731_flows.png
├── 20251011_184732_costs.png
├── 20251011_184732_utilization.png
└── ...
```

**Note:** Timestamps prevent overwriting previous runs.

---

## Requirements

```bash
source Tolis_Env/bin/activate
ollama serve  # Start Ollama (required)
```

- Python 3.12+
- Ollama with `qwen2:7b` model
- All dependencies: `pip install -r requirements.txt`

---

## Troubleshooting

**"Connection refused"**
```bash
ollama serve  # Start Ollama in another terminal
```

**"Model not found"**
```bash
ollama pull qwen2:7b
```

**"Module not found"**
```bash
source Tolis_Env/bin/activate
```

---

## Summary

- **7 test files** (cleaned up, removed 6 obsolete tests)
- **49 unit tests** (44 LLM + 5 normalizer - all passing)
- **3 workflow tests** (Overall_Test, complete_workflow, llm_analysis - all passing)
- **2 data files** (transportation scenarios, classification test cases)

Total: Clean, focused test suite with all tests passing.
