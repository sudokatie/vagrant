"""Request chaining for extracting and interpolating variables.

Allows extracting values from responses and using them in subsequent requests.
Supports dot notation for JSON paths and {{variable}} interpolation syntax.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# Pattern for variable interpolation: {{variable}} or {{response.data.id}}
INTERPOLATION_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*\}\}")


@dataclass
class ExtractRule:
    """Rule for extracting a value from a response.
    
    Attributes:
        name: Variable name to store the extracted value.
        path: JSON path to extract (dot notation, e.g., "data.user.id").
        default: Default value if path not found.
    """

    name: str
    path: str
    default: Any = None


@dataclass
class ChainContext:
    """Context for request chaining with variable storage.
    
    Attributes:
        variables: Dict of variable name -> value.
    """

    variables: dict[str, Any] = field(default_factory=dict)

    def set(self, name: str, value: Any) -> None:
        """Set a variable value."""
        self.variables[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        """Get a variable value."""
        return self.variables.get(name, default)

    def clear(self) -> None:
        """Clear all variables."""
        self.variables.clear()

    def has(self, name: str) -> bool:
        """Check if a variable exists."""
        return name in self.variables


def extract_value(data: Any, path: str, default: Any = None) -> Any:
    """Extract a value from nested data using dot notation.
    
    Args:
        data: The data to extract from (dict, list, or primitive).
        path: Dot-notation path (e.g., "data.users.0.name").
        default: Value to return if path not found.
        
    Returns:
        The extracted value, or default if not found.
        
    Examples:
        >>> extract_value({"data": {"id": 123}}, "data.id")
        123
        >>> extract_value({"items": [{"name": "a"}]}, "items.0.name")
        'a'
        >>> extract_value({}, "missing", "default")
        'default'
    """
    if not path:
        return data if data is not None else default

    parts = path.split(".")
    current = data

    for part in parts:
        if current is None:
            return default

        # Handle list index
        if isinstance(current, list):
            try:
                index = int(part)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return default
            except ValueError:
                return default
        # Handle dict key
        elif isinstance(current, dict):
            if part in current:
                current = current[part]
            else:
                return default
        # Can't traverse further
        else:
            return default

    return current


def extract_from_response(
    response_body: Any,
    rules: list[ExtractRule],
    context: ChainContext,
) -> dict[str, Any]:
    """Extract values from a response and store in context.
    
    Args:
        response_body: The parsed response body.
        rules: List of extraction rules.
        context: Chain context to store variables.
        
    Returns:
        Dict of variable name -> extracted value.
    """
    extracted = {}

    for rule in rules:
        value = extract_value(response_body, rule.path, rule.default)
        context.set(rule.name, value)
        extracted[rule.name] = value

    return extracted


def interpolate_string(text: str, context: ChainContext) -> str:
    """Interpolate variables in a string.
    
    Replaces {{variable}} with the value from context.
    Unknown variables are left unchanged.
    
    Args:
        text: String with {{variable}} placeholders.
        context: Chain context with variable values.
        
    Returns:
        String with variables replaced.
        
    Examples:
        >>> ctx = ChainContext(variables={"token": "abc123"})
        >>> interpolate_string("Bearer {{token}}", ctx)
        'Bearer abc123'
    """

    def replace(match: re.Match) -> str:
        var_name = match.group(1)
        if context.has(var_name):
            value = context.get(var_name)
            return str(value) if value is not None else ""
        # Leave unknown variables unchanged
        return match.group(0)

    return INTERPOLATION_PATTERN.sub(replace, text)


def interpolate_dict(data: dict[str, Any], context: ChainContext) -> dict[str, Any]:
    """Interpolate variables in a dict (recursively).
    
    Args:
        data: Dict with potential {{variable}} values.
        context: Chain context with variable values.
        
    Returns:
        New dict with variables interpolated.
    """
    result = {}

    for key, value in data.items():
        # Interpolate key
        new_key = interpolate_string(key, context) if isinstance(key, str) else key

        # Interpolate value
        if isinstance(value, str):
            result[new_key] = interpolate_string(value, context)
        elif isinstance(value, dict):
            result[new_key] = interpolate_dict(value, context)
        elif isinstance(value, list):
            result[new_key] = interpolate_list(value, context)
        else:
            result[new_key] = value

    return result


def interpolate_list(data: list[Any], context: ChainContext) -> list[Any]:
    """Interpolate variables in a list (recursively).
    
    Args:
        data: List with potential {{variable}} values.
        context: Chain context with variable values.
        
    Returns:
        New list with variables interpolated.
    """
    result = []

    for item in data:
        if isinstance(item, str):
            result.append(interpolate_string(item, context))
        elif isinstance(item, dict):
            result.append(interpolate_dict(item, context))
        elif isinstance(item, list):
            result.append(interpolate_list(item, context))
        else:
            result.append(item)

    return result


def find_variables(text: str) -> list[str]:
    """Find all variable references in a string.
    
    Args:
        text: String with {{variable}} placeholders.
        
    Returns:
        List of variable names found.
        
    Examples:
        >>> find_variables("Hello {{name}}, your id is {{user.id}}")
        ['name', 'user.id']
    """
    return INTERPOLATION_PATTERN.findall(text)


def has_unresolved_variables(text: str, context: ChainContext) -> list[str]:
    """Check for variables that can't be resolved.
    
    Args:
        text: String with {{variable}} placeholders.
        context: Chain context with variable values.
        
    Returns:
        List of variable names that are not in context.
    """
    variables = find_variables(text)
    return [v for v in variables if not context.has(v)]
