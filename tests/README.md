# Tests Directory

This directory contains all test, debug, and analysis files for the Optimization AI project.

## Test Files

- `test_run.py` - Basic transportation problem test
- `# test_run.py` - Alternative test format
- `test_greek_problem.py` - Test with Greek cities
- `test_direct_solver.py` - Direct solver testing
- `test_question_handling.py` - Question handling functionality tests

## Debug Files

- `debug_classification.py` - Debug LLM question classification
- `debug_solvers.py` - Debug solver functionality
- `debug_units.py` - Debug unit handling

## Analysis Files

- `analyze_failures.py` - Analyze failing test cases

## Running Tests

From the main project directory:

```bash
# Activate environment
source Tolis_Env/bin/activate

# Run a specific test
python tests/test_question_handling.py

# Run debug analysis
python tests/debug_classification.py
```