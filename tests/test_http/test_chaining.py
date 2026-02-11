"""Tests for request chaining."""


from vagrant.http.chaining import (
    ChainContext,
    ExtractRule,
    extract_from_response,
    extract_value,
    find_variables,
    has_unresolved_variables,
    interpolate_dict,
    interpolate_list,
    interpolate_string,
)


class TestExtractValue:
    """Tests for extract_value function."""

    def test_simple_key(self):
        """Extract a simple top-level key."""
        data = {"id": 123, "name": "test"}
        assert extract_value(data, "id") == 123
        assert extract_value(data, "name") == "test"

    def test_nested_key(self):
        """Extract nested values with dot notation."""
        data = {"data": {"user": {"id": 456}}}
        assert extract_value(data, "data.user.id") == 456

    def test_list_index(self):
        """Extract list items by index."""
        data = {"items": [{"name": "first"}, {"name": "second"}]}
        assert extract_value(data, "items.0.name") == "first"
        assert extract_value(data, "items.1.name") == "second"

    def test_default_on_missing(self):
        """Return default when path not found."""
        data = {"id": 123}
        assert extract_value(data, "missing", "default") == "default"
        assert extract_value(data, "nested.missing", None) is None

    def test_default_on_index_out_of_range(self):
        """Return default when list index is out of range."""
        data = {"items": [1, 2, 3]}
        assert extract_value(data, "items.10", "not found") == "not found"

    def test_empty_path(self):
        """Empty path returns the data itself."""
        data = {"id": 123}
        assert extract_value(data, "") == data

    def test_none_data(self):
        """Handle None data gracefully."""
        assert extract_value(None, "anything", "default") == "default"


class TestChainContext:
    """Tests for ChainContext."""

    def test_set_and_get(self):
        """Set and retrieve variables."""
        ctx = ChainContext()
        ctx.set("token", "abc123")
        assert ctx.get("token") == "abc123"

    def test_get_default(self):
        """Get with default for missing variable."""
        ctx = ChainContext()
        assert ctx.get("missing", "fallback") == "fallback"

    def test_has(self):
        """Check variable existence."""
        ctx = ChainContext()
        ctx.set("exists", "value")
        assert ctx.has("exists") is True
        assert ctx.has("missing") is False

    def test_clear(self):
        """Clear all variables."""
        ctx = ChainContext(variables={"a": 1, "b": 2})
        ctx.clear()
        assert ctx.has("a") is False
        assert ctx.has("b") is False


class TestExtractFromResponse:
    """Tests for extract_from_response function."""

    def test_extract_multiple_rules(self):
        """Extract multiple values from a response."""
        response = {
            "data": {
                "user": {"id": 123, "name": "Alice"},
                "token": "xyz789",
            }
        }
        rules = [
            ExtractRule(name="user_id", path="data.user.id"),
            ExtractRule(name="user_name", path="data.user.name"),
            ExtractRule(name="auth_token", path="data.token"),
        ]
        ctx = ChainContext()
        extracted = extract_from_response(response, rules, ctx)

        assert extracted == {"user_id": 123, "user_name": "Alice", "auth_token": "xyz789"}
        assert ctx.get("user_id") == 123
        assert ctx.get("auth_token") == "xyz789"

    def test_extract_with_default(self):
        """Use default value when path not found."""
        response = {"data": {}}
        rules = [ExtractRule(name="missing", path="data.user.id", default=-1)]
        ctx = ChainContext()
        extracted = extract_from_response(response, rules, ctx)

        assert extracted == {"missing": -1}
        assert ctx.get("missing") == -1


class TestInterpolateString:
    """Tests for interpolate_string function."""

    def test_simple_variable(self):
        """Interpolate a simple variable."""
        ctx = ChainContext(variables={"name": "Alice"})
        assert interpolate_string("Hello {{name}}", ctx) == "Hello Alice"

    def test_multiple_variables(self):
        """Interpolate multiple variables."""
        ctx = ChainContext(variables={"first": "Alice", "last": "Smith"})
        result = interpolate_string("{{first}} {{last}}", ctx)
        assert result == "Alice Smith"

    def test_nested_path_variable(self):
        """Variables can have dots in the name (they're just identifiers)."""
        ctx = ChainContext(variables={"user.id": 123})
        assert interpolate_string("ID: {{user.id}}", ctx) == "ID: 123"

    def test_whitespace_in_braces(self):
        """Handle whitespace inside braces."""
        ctx = ChainContext(variables={"token": "abc"})
        assert interpolate_string("Bearer {{ token }}", ctx) == "Bearer abc"

    def test_unknown_variable_unchanged(self):
        """Unknown variables are left unchanged."""
        ctx = ChainContext()
        assert interpolate_string("{{unknown}}", ctx) == "{{unknown}}"

    def test_none_value(self):
        """None values become empty string."""
        ctx = ChainContext(variables={"empty": None})
        assert interpolate_string("Value: {{empty}}", ctx) == "Value: "

    def test_numeric_value(self):
        """Numeric values are converted to string."""
        ctx = ChainContext(variables={"count": 42})
        assert interpolate_string("Count: {{count}}", ctx) == "Count: 42"


class TestInterpolateDict:
    """Tests for interpolate_dict function."""

    def test_interpolate_values(self):
        """Interpolate variables in dict values."""
        ctx = ChainContext(variables={"token": "secret123"})
        data = {"Authorization": "Bearer {{token}}"}
        result = interpolate_dict(data, ctx)
        assert result == {"Authorization": "Bearer secret123"}

    def test_interpolate_nested(self):
        """Interpolate in nested dicts."""
        ctx = ChainContext(variables={"id": 456})
        data = {"user": {"id": "{{id}}"}}
        result = interpolate_dict(data, ctx)
        assert result == {"user": {"id": "456"}}

    def test_interpolate_keys(self):
        """Interpolate variables in dict keys."""
        ctx = ChainContext(variables={"header": "X-Custom"})
        data = {"{{header}}": "value"}
        result = interpolate_dict(data, ctx)
        assert result == {"X-Custom": "value"}

    def test_non_string_values_unchanged(self):
        """Non-string values pass through unchanged."""
        ctx = ChainContext()
        data = {"count": 123, "active": True, "ratio": 0.5}
        result = interpolate_dict(data, ctx)
        assert result == {"count": 123, "active": True, "ratio": 0.5}


class TestInterpolateList:
    """Tests for interpolate_list function."""

    def test_interpolate_items(self):
        """Interpolate variables in list items."""
        ctx = ChainContext(variables={"a": "first", "b": "second"})
        data = ["{{a}}", "{{b}}"]
        result = interpolate_list(data, ctx)
        assert result == ["first", "second"]

    def test_interpolate_nested_dicts(self):
        """Interpolate nested dicts in list."""
        ctx = ChainContext(variables={"name": "test"})
        data = [{"name": "{{name}}"}]
        result = interpolate_list(data, ctx)
        assert result == [{"name": "test"}]


class TestFindVariables:
    """Tests for find_variables function."""

    def test_find_single(self):
        """Find a single variable."""
        assert find_variables("Hello {{name}}") == ["name"]

    def test_find_multiple(self):
        """Find multiple variables."""
        vars = find_variables("{{a}} and {{b}} and {{c}}")
        assert vars == ["a", "b", "c"]

    def test_find_none(self):
        """Return empty list when no variables."""
        assert find_variables("No variables here") == []

    def test_find_with_dots(self):
        """Find variables with dots."""
        assert find_variables("ID: {{user.id}}") == ["user.id"]


class TestHasUnresolvedVariables:
    """Tests for has_unresolved_variables function."""

    def test_all_resolved(self):
        """Return empty list when all variables resolved."""
        ctx = ChainContext(variables={"a": 1, "b": 2})
        assert has_unresolved_variables("{{a}} {{b}}", ctx) == []

    def test_some_unresolved(self):
        """Return unresolved variable names."""
        ctx = ChainContext(variables={"a": 1})
        unresolved = has_unresolved_variables("{{a}} {{b}} {{c}}", ctx)
        assert unresolved == ["b", "c"]

    def test_none_resolved(self):
        """Return all variables when none resolved."""
        ctx = ChainContext()
        unresolved = has_unresolved_variables("{{x}} {{y}}", ctx)
        assert unresolved == ["x", "y"]
