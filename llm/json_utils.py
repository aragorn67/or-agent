# llm/json_utils.py
"""
Centralized JSON extraction utilities for parsing LLM responses.
Eliminates duplicate ad-hoc JSON parsing scattered across the codebase.
"""

import json
import re
from typing import Dict, Any, Optional


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON object from text that may contain extra content.

    Handles common cases:
    - Text with JSON wrapped in markdown code blocks
    - Text with JSON embedded in prose
    - Pure JSON text
    - Multiple JSON objects (returns first)

    Args:
        text: String that may contain JSON

    Returns:
        Parsed JSON dict, or None if no valid JSON found
    """

    # Strip whitespace
    text = text.strip()

    # Try parsing as-is first (fastest path)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Remove markdown code blocks if present
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)

    # Try again after removing markdown
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Find JSON by locating braces
    start_idx = text.find('{')
    end_idx = text.rfind('}')

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = text[start_idx:end_idx + 1]

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # Try to find array-based JSON
    start_idx = text.find('[')
    end_idx = text.rfind(']')

    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = text[start_idx:end_idx + 1]

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # No valid JSON found
    return None


def safe_json_parse(text: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Safely parse JSON with fallback to default.

    Args:
        text: Text to parse
        default: Default value if parsing fails (defaults to empty dict)

    Returns:
        Parsed JSON dict or default value
    """

    if default is None:
        default = {}

    result = extract_json_from_text(text)
    return result if result is not None else default


def validate_json_schema(data: Dict[str, Any], required_keys: list, expected_types: Optional[Dict[str, type]] = None) -> tuple[bool, Optional[str]]:
    """
    Validate JSON data against a simple schema.

    Args:
        data: JSON data to validate
        required_keys: List of required keys
        expected_types: Optional dict mapping keys to expected types

    Returns:
        (is_valid, error_message) tuple
    """

    # Check required keys
    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        return False, f"Missing required keys: {', '.join(missing_keys)}"

    # Check types if specified
    if expected_types:
        for key, expected_type in expected_types.items():
            if key in data and not isinstance(data[key], expected_type):
                return False, f"Key '{key}' has wrong type: expected {expected_type.__name__}, got {type(data[key]).__name__}"

    return True, None


def extract_code_block(text: str, language: str = "") -> Optional[str]:
    """
    Extract code from markdown code blocks.

    Args:
        text: Text potentially containing code blocks
        language: Optional language specifier (e.g., "python", "json")

    Returns:
        Extracted code or None
    """

    pattern = rf'```{language}\s*(.*?)\s*```'
    match = re.search(pattern, text, re.DOTALL)

    if match:
        return match.group(1).strip()

    # Try without language specifier
    if language:
        pattern = r'```\s*(.*?)\s*```'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()

    return None
