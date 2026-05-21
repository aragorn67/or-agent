"""
Analysis Router - Central orchestrator for post-solution analysis

Routes user queries to appropriate analysis engines:
- Sensitivity analysis
- What-if scenarios
- Re-solve with modifications
- Pareto front generation
"""

from typing import Dict, Any, Optional


def detect_analysis_type_with_llm(query: str, llm_client) -> str:
    """
    Use LLM to detect analysis type from natural language (robust to typos and variations).

    Args:
        query: User's natural language query
        llm_client: LLM client for intent detection

    Returns:
        Analysis type: 'sensitivity', 'what_if', 'resolve', 'pareto', or 'unknown'
    """
    system_prompt = """You are analyzing a user's follow-up question about an optimization solution.
Classify the query into ONE of these analysis types:

1. "what_if" - User wants to test a SINGLE scenario with SPECIFIC values (temporary exploration)
   Key indicators: "what if", "suppose", "let's see if", "happens if", mentions SPECIFIC values
   Examples:
   - "what if demand was 100"
   - "let's see what happens if A becomes 58"
   - "suppose capacity increased by 20"
   - "hat if demand increases by 2" (typo for "what if")

2. "sensitivity" - User wants to test MULTIPLE values/range to see overall impact (systematic analysis)
   Key indicators: "sensitivity", "impact", "effect", "range", NO specific values mentioned
   Examples:
   - "sensitivity on capacity"
   - "impact of changing demand"
   - "how does capacity affect cost"

3. "resolve" - User wants to PERMANENTLY change parameters and get a new solution
   Key indicators: "resolve", "re-solve", "reoptimize", "update and solve", "change to"
   Examples:
   - "resolve with X=100"
   - "re-solve with new capacity"
   - "update capacity to 500 and solve"

4. "pareto" - User wants multi-objective tradeoff analysis
   Key indicators: "pareto", "tradeoff", "trade-off", "multi-objective", "vs", "versus"
   Examples:
   - "show me the pareto front"
   - "what's the tradeoff between cost and distance"
   - "analyze cost vs distance"
   - "generate pareto analysis"
   - "I want to see cost versus distance tradeoffs"

5. "unknown" - None of the above or unclear

CRITICAL RULES:
- If query mentions SPECIFIC values → likely "what_if"
- If query asks about general "impact" without specific values → likely "sensitivity"
- If query says "resolve" or "re-solve" → definitely "resolve"
- Be flexible with typos and informal language

Return ONLY the classification word: sensitivity, what_if, resolve, pareto, or unknown"""

    user_prompt = f"Classify this query: {query}"

    try:
        response = llm_client.reasoning_client._chat(system_prompt, user_prompt)

        # Handle responses with <think> tags - extract answer after </think>
        if '</think>' in response:
            detected_type = response.split('</think>')[-1].strip().lower()
        else:
            detected_type = response.strip().lower()

        # Validate response
        valid_types = ['sensitivity', 'what_if', 'resolve', 'pareto', 'unknown']
        if detected_type in valid_types:
            return detected_type
        else:
            # Try to extract from response
            for vtype in valid_types:
                if vtype in detected_type:
                    return vtype
            return 'unknown'
    except Exception:
        # Fallback to keyword matching if LLM fails
        return detect_analysis_type_keyword_based(query)


def detect_analysis_type_keyword_based(query: str) -> str:
    """
    Fallback keyword-based detection (fast but rigid).

    Args:
        query: User's natural language query

    Returns:
        Analysis type: 'sensitivity', 'what_if', 'resolve', 'pareto', or 'unknown'
    """
    query_lower = query.lower()

    # Sensitivity analysis. 'sensitiv' covers "sensitivity" AND "sensitive"
    # ("how sensitive is X to Y"); "how does X affect" / "responsive to"
    # are the other common sensitivity phrasings the rigid list missed.
    if any(kw in query_lower for kw in
           ['sensitiv', 'impact', 'effect', 'how does', 'responsive to']):
        return 'sensitivity'

    # What-if scenario. Added the natural "what changes/happens if/when"
    # phrasings (the keyword catalogue showed these were punting to the
    # LLM purely for lack of a trigger substring — not a reasoning gap).
    if any(kw in query_lower for kw in
           ['what if', 'what-if', 'scenario', 'suppose', "let's see",
            'happens if', 'what changes if', 'what happens if',
            'what happens when', 'happens when']):
        return 'what_if'

    # Re-solve with modifications
    if any(kw in query_lower for kw in ['resolve', 're-solve', 'reoptimize', 'update and solve']):
        return 'resolve'

    # Pareto front
    if any(kw in query_lower for kw in ['pareto', 'multi-objective', 'tradeoff', 'trade-off',
                                          ' vs ', ' versus ', 'analyze cost', 'cost and distance']):
        return 'pareto'

    return 'unknown'


def detect_analysis_type(query: str, llm_client=None) -> str:
    """
    Detect the type of analysis requested from user query.

    Uses LLM-based detection when llm_client is provided (robust to typos and variations).
    Falls back to keyword matching when llm_client is not provided.

    Args:
        query: User's natural language query
        llm_client: Optional LLM client for intelligent detection

    Returns:
        Analysis type: 'sensitivity', 'what_if', 'resolve', 'pareto', or 'unknown'

    Examples:
        >>> detect_analysis_type("sensitivity on Plant North capacity")
        'sensitivity'
        >>> detect_analysis_type("what if demand increases by 20")
        'what_if'
        >>> detect_analysis_type("hat if demand increases by 20", llm_client)  # LLM handles typo
        'what_if'
        >>> detect_analysis_type("lets see what happens if A becomes 50", llm_client)  # LLM understands intent
        'what_if'
    """
    if llm_client is not None:
        return detect_analysis_type_with_llm(query, llm_client)
    else:
        return detect_analysis_type_keyword_based(query)


def execute_analysis(
    analysis_type: str,
    solver,
    params: Dict[str, Any],
    solution: Dict[str, Any],
    query: str,
    llm_client=None
) -> Dict[str, Any]:
    """
    Execute the appropriate analysis based on type.

    Args:
        analysis_type: Type of analysis ('sensitivity', 'what_if', 'resolve', 'pareto')
        solver: Solver instance for re-solving problems
        params: Current problem parameters
        solution: Current solution
        query: User's query string
        llm_client: LLM client (required for what_if and resolve)

    Returns:
        Analysis results dictionary

    Raises:
        ValueError: If analysis type is unknown
        ValueError: If LLM client is required but not provided
    """
    if analysis_type == 'sensitivity':
        from .sensitivity.engine import perform_sensitivity_analysis
        return perform_sensitivity_analysis(solver, params, solution, query, llm_client)

    elif analysis_type == 'what_if':
        if llm_client is None:
            raise ValueError("LLM client required for what-if scenarios")
        from .scenarios.engine import perform_what_if_scenario
        # Extract problem_type and solver_id from solution/solver
        problem_type = solution.get('problem_type')
        solver_id = getattr(solver, 'solver_id', None)
        return perform_what_if_scenario(llm_client, solver, params, solution, query, problem_type, solver_id)

    elif analysis_type == 'resolve':
        if llm_client is None:
            raise ValueError("LLM client required for re-solve")
        from .modification.engine import resolve_with_modification
        return resolve_with_modification(llm_client, solver, params, solution, query)

    elif analysis_type == 'pareto':
        from .pareto.engine import perform_pareto_analysis
        # Extract problem_type from solution
        problem_type = solution.get('problem_type')
        return perform_pareto_analysis(solver, params, solution, num_points=10, problem_type=problem_type)

    else:
        raise ValueError(f"Unknown analysis type: {analysis_type}")


def format_analysis_output(analysis_type: str, results: Dict[str, Any]) -> str:
    """
    Format analysis results for display.

    Args:
        analysis_type: Type of analysis
        results: Analysis results dictionary

    Returns:
        Formatted string for display
    """
    if analysis_type == 'sensitivity':
        from .sensitivity.engine import format_sensitivity_results
        return format_sensitivity_results(results)

    elif analysis_type == 'what_if':
        from .scenarios.engine import format_scenario_results
        return format_scenario_results(results)

    elif analysis_type == 'resolve':
        from .modification.engine import format_modification_results
        return format_modification_results(results)

    elif analysis_type == 'pareto':
        from .pareto.engine import format_pareto_results
        return format_pareto_results(results)

    else:
        return f"⚠️  Unknown analysis type: {analysis_type}"
