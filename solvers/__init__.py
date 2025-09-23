# solvers/__init__.py
import importlib
import pkgutil
from typing import Dict, Type
from .base import OptimizationSolver

# Auto-discover and register all solvers
_SOLVERS: Dict[str, Type[OptimizationSolver]] = {}

def _auto_register_solvers():
    """Automatically import and register all solver modules"""
    for _, module_name, _ in pkgutil.iter_modules(__path__):
        if module_name != 'base':
            try:
                module = importlib.import_module(f'solvers.{module_name}')

                # Find solver classes in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and
                        issubclass(attr, OptimizationSolver) and
                        attr != OptimizationSolver):
                        solver_instance = attr()
                        _SOLVERS[solver_instance.problem_type] = attr
            except Exception as e:
                print(f"Warning: Could not register solver from {module_name}: {e}")

def get_solver(problem_type: str) -> OptimizationSolver:
    """Get solver instance for problem type"""
    if not _SOLVERS:
        _auto_register_solvers()

    if problem_type not in _SOLVERS:
        raise ValueError(f"Unknown problem type: {problem_type}")
    return _SOLVERS[problem_type]()

def list_problem_types() -> list:
    """Get all registered problem types"""
    if not _SOLVERS:
        _auto_register_solvers()
    return list(_SOLVERS.keys())