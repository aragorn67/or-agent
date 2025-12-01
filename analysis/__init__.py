"""
Analysis Module for Post-Solution Analysis

Provides sensitivity analysis, what-if scenarios, re-solve with modifications,
and Pareto front generation for optimization solutions.
"""

from .router import detect_analysis_type, execute_analysis, format_analysis_output

__all__ = [
    'detect_analysis_type',
    'execute_analysis',
    'format_analysis_output'
]
