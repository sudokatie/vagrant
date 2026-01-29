"""Tests for environment management."""

from pathlib import Path

import pytest

from vagrant.http.auth import AuthConfig
from vagrant.storage.environments import Environment, EnvironmentManager


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Return path to temporary config directory."""
    return tmp_path / "config"


@pytest.fixture
def manager(temp_config_dir: Path) -> EnvironmentManager:
    """Create test environment manager."""
    return EnvironmentManager(config_dir=temp_config_dir)


@pytest.fixture
def sample_env() -> Environment:
    """Create sample environment."""
    return Environment(
        name="production",
        base_url="https://api.example.com/v1",
        auth=AuthConfig(type="bearer", credentials={"token": "secret"}),
        variables={"api_version": "v1", "timeout": "30"},
    )


class TestEnvironment:
    """Tests for Environment dataclass."""

    def test_minimal_environment(self):
        """Environment with just name."""
        env = Environment(name="test")
        assert env.name == "test"
        assert env.base_url == ""
        assert env.auth is None
        assert env.variables == {}

    def test_full_environment(self, sample_env: Environment):
        """Environment with all fields."""
        assert sample_env.name == "production"
        assert sample_env.base_url == "https://api.example.com/v1"
        assert sample_env.auth is not None
        assert sample_env.variables == {"api_version": "v1", "timeout": "30"}

    def test_to_dict(self, sample_env: Environment):
        """Environment can be converted to dict."""
        data = sample_env.to_dict()
        assert data["name"] == "production"
        assert data["base_url"] == "https://api.example.com/v1"
        assert data["auth"]["type"] == "bearer"
        assert data["variables"] == {"api_version": "v1", "timeout": "30"}

    def test_from_dict(self):
        """Environment can be created from dict."""
        data = {
            "name": "staging",
            "base_url": "https://staging.example.com",
            "auth": {"type": "apikey", "credentials": {"key": "abc123"}},
            "variables": {"env": "staging"},
        }
        env = Environment.from_dict(data)
        assert env.name == "staging"
        assert env.base_url == "https://staging.example.com"
        assert env.auth.type == "apikey"
        assert env.variables == {"env": "staging"}

    def test_from_dict_minimal(self):
        """Environment from minimal dict."""
        data = {"name": "minimal"}
        env = Environment.from_dict(data)
        assert env.name == "minimal"
        assert env.auth is None


class TestEnvironmentManagerInit:
    """Tests for EnvironmentManager initialization."""

    def test_creates_env_dir(self, temp_config_dir: Path):
        """Manager creates environments directory."""
        EnvironmentManager(config_dir=temp_config_dir)
        assert (temp_config_dir / "environments").exists()


class TestEnvironmentManagerList:
    """Tests for listing environments."""

    def test_list_empty(self, manager: EnvironmentManager):
        """list() returns empty for no environments."""
        assert manager.list() == []

    def test_list_after_save(self, manager: EnvironmentManager, sample_env: Environment):
        """list() includes saved environments."""
        manager.save(sample_env)
        envs = manager.list()
        assert "production" in envs

    def test_list_sorted(self, manager: EnvironmentManager):
        """list() returns sorted names."""
        manager.save(Environment(name="zebra"))
        manager.save(Environment(name="alpha"))
        manager.save(Environment(name="beta"))

        envs = manager.list()
        assert envs == ["alpha", "beta", "zebra"]


class TestEnvironmentManagerSaveGet:
    """Tests for saving and getting environments."""

    def test_save_creates_file(self, manager: EnvironmentManager, sample_env: Environment):
        """save() creates YAML file."""
        manager.save(sample_env)
        assert (manager.env_dir / "production.yaml").exists()

    def test_get_returns_environment(self, manager: EnvironmentManager, sample_env: Environment):
        """get() retrieves saved environment."""
        manager.save(sample_env)
        retrieved = manager.get("production")

        assert retrieved.name == "production"
        assert retrieved.base_url == sample_env.base_url

    def test_get_preserves_auth(self, manager: EnvironmentManager, sample_env: Environment):
        """get() preserves auth config."""
        manager.save(sample_env)
        retrieved = manager.get("production")

        assert retrieved.auth is not None
        assert retrieved.auth.type == "bearer"

    def test_get_preserves_variables(self, manager: EnvironmentManager, sample_env: Environment):
        """get() preserves variables."""
        manager.save(sample_env)
        retrieved = manager.get("production")

        assert retrieved.variables == sample_env.variables

    def test_get_nonexistent(self, manager: EnvironmentManager):
        """get() raises for nonexistent environment."""
        with pytest.raises(FileNotFoundError):
            manager.get("nonexistent")


class TestEnvironmentManagerDelete:
    """Tests for deleting environments."""

    def test_delete_removes_file(self, manager: EnvironmentManager, sample_env: Environment):
        """delete() removes environment file."""
        manager.save(sample_env)
        manager.delete("production")

        assert not (manager.env_dir / "production.yaml").exists()
        assert "production" not in manager.list()

    def test_delete_nonexistent(self, manager: EnvironmentManager):
        """delete() raises for nonexistent environment."""
        with pytest.raises(FileNotFoundError):
            manager.delete("nonexistent")


class TestEnvironmentManagerExists:
    """Tests for checking environment existence."""

    def test_exists_true(self, manager: EnvironmentManager, sample_env: Environment):
        """exists() returns True for existing."""
        manager.save(sample_env)
        assert manager.exists("production") is True

    def test_exists_false(self, manager: EnvironmentManager):
        """exists() returns False for nonexistent."""
        assert manager.exists("nonexistent") is False


class TestEnvironmentManagerSubstitute:
    """Tests for variable substitution."""

    def test_substitute_variable(self, manager: EnvironmentManager):
        """Substitute environment variables."""
        env = Environment(
            name="test",
            variables={"host": "api.example.com"},
        )
        result = manager.substitute("https://{{host}}/v1", env)
        assert result == "https://api.example.com/v1"

    def test_substitute_base_url(self, manager: EnvironmentManager):
        """Substitute base_url."""
        env = Environment(
            name="test",
            base_url="https://api.example.com",
        )
        result = manager.substitute("{{base_url}}/users", env)
        assert result == "https://api.example.com/users"

    def test_substitute_os_env(self, manager: EnvironmentManager, monkeypatch):
        """Substitute OS environment variables."""
        monkeypatch.setenv("TEST_API_KEY", "secret123")
        env = Environment(name="test")
        result = manager.substitute("Token: {{env.TEST_API_KEY}}", env)
        assert result == "Token: secret123"

    def test_substitute_missing_variable(self, manager: EnvironmentManager):
        """Missing variables left as-is."""
        env = Environment(name="test")
        result = manager.substitute("{{missing}}", env)
        assert result == "{{missing}}"

    def test_substitute_whitespace_in_braces(self, manager: EnvironmentManager):
        """Handle whitespace in variable braces."""
        env = Environment(
            name="test",
            variables={"host": "example.com"},
        )
        result = manager.substitute("{{ host }}", env)
        assert result == "example.com"

    def test_substitute_multiple(self, manager: EnvironmentManager):
        """Substitute multiple variables."""
        env = Environment(
            name="test",
            base_url="https://api.example.com",
            variables={"version": "v2"},
        )
        result = manager.substitute("{{base_url}}/{{version}}/users", env)
        assert result == "https://api.example.com/v2/users"


class TestEnvironmentManagerSubstituteAll:
    """Tests for substituting in dictionaries."""

    def test_substitute_all_strings(self, manager: EnvironmentManager):
        """Substitute in all string values."""
        env = Environment(
            name="test",
            variables={"host": "example.com", "key": "secret"},
        )
        data = {
            "url": "https://{{host}}/api",
            "token": "{{key}}",
            "static": "no substitution",
        }
        result = manager.substitute_all(data, env)

        assert result["url"] == "https://example.com/api"
        assert result["token"] == "secret"
        assert result["static"] == "no substitution"

    def test_substitute_all_nested(self, manager: EnvironmentManager):
        """Substitute in nested dictionaries."""
        env = Environment(
            name="test",
            variables={"token": "abc123"},
        )
        data = {
            "headers": {
                "Authorization": "Bearer {{token}}",
            },
        }
        result = manager.substitute_all(data, env)

        assert result["headers"]["Authorization"] == "Bearer abc123"

    def test_substitute_all_non_strings(self, manager: EnvironmentManager):
        """Non-string values passed through."""
        env = Environment(name="test")
        data = {
            "count": 42,
            "enabled": True,
            "items": [1, 2, 3],
        }
        result = manager.substitute_all(data, env)

        assert result["count"] == 42
        assert result["enabled"] is True
        assert result["items"] == [1, 2, 3]


class TestEnvironmentManagerResponseSubstitution:
    """Tests for response variable substitution."""

    def test_set_last_response_dict(self, manager: EnvironmentManager):
        """set_last_response stores dict response."""
        response = {"id": 123, "name": "test"}
        manager.set_last_response(response)
        assert manager._last_response == response

    def test_set_last_response_non_dict(self, manager: EnvironmentManager):
        """set_last_response ignores non-dict responses."""
        manager.set_last_response("just a string")
        assert manager._last_response is None
        
        manager.set_last_response([1, 2, 3])
        assert manager._last_response is None

    def test_substitute_response_simple(self, manager: EnvironmentManager):
        """Substitute simple response field."""
        env = Environment(name="test")
        manager.set_last_response({"id": 123, "name": "John"})
        
        result = manager.substitute("User ID: {{response.id}}", env)
        assert result == "User ID: 123"

    def test_substitute_response_nested(self, manager: EnvironmentManager):
        """Substitute nested response field."""
        env = Environment(name="test")
        manager.set_last_response({
            "data": {
                "user": {
                    "id": 456,
                    "email": "test@example.com"
                }
            }
        })
        
        result = manager.substitute("Email: {{response.data.user.email}}", env)
        assert result == "Email: test@example.com"

    def test_substitute_response_array_index(self, manager: EnvironmentManager):
        """Substitute response array element by index."""
        env = Environment(name="test")
        manager.set_last_response({
            "items": [
                {"name": "first"},
                {"name": "second"},
                {"name": "third"}
            ]
        })
        
        result = manager.substitute("Second item: {{response.items.1.name}}", env)
        assert result == "Second item: second"

    def test_substitute_response_missing_field(self, manager: EnvironmentManager):
        """Missing response field left as-is."""
        env = Environment(name="test")
        manager.set_last_response({"id": 123})
        
        result = manager.substitute("{{response.nonexistent}}", env)
        assert result == "{{response.nonexistent}}"

    def test_substitute_response_no_response(self, manager: EnvironmentManager):
        """No response stored leaves variable as-is."""
        env = Environment(name="test")
        # Don't set any response
        
        result = manager.substitute("{{response.id}}", env)
        assert result == "{{response.id}}"

    def test_substitute_response_array_out_of_bounds(self, manager: EnvironmentManager):
        """Out of bounds array index left as-is."""
        env = Environment(name="test")
        manager.set_last_response({"items": [1, 2]})
        
        result = manager.substitute("{{response.items.99}}", env)
        assert result == "{{response.items.99}}"

    def test_substitute_response_invalid_array_index(self, manager: EnvironmentManager):
        """Invalid array index (non-integer) left as-is."""
        env = Environment(name="test")
        manager.set_last_response({"items": [1, 2, 3]})
        
        result = manager.substitute("{{response.items.abc}}", env)
        assert result == "{{response.items.abc}}"

    def test_substitute_response_with_other_vars(self, manager: EnvironmentManager):
        """Mix response vars with other variable types."""
        env = Environment(
            name="test",
            base_url="https://api.example.com",
            variables={"api_key": "secret"}
        )
        manager.set_last_response({"user_id": 789})
        
        result = manager.substitute(
            "{{base_url}}/users/{{response.user_id}}?key={{api_key}}", 
            env
        )
        assert result == "https://api.example.com/users/789?key=secret"

    def test_get_response_value_non_dict_value(self, manager: EnvironmentManager):
        """_get_response_value handles traversing to non-dict/non-list."""
        manager.set_last_response({"value": "string"})
        
        # Trying to access a property on a string should return None
        result = manager._get_response_value("value.length")
        assert result is None

    def test_get_response_value_converts_to_string(self, manager: EnvironmentManager):
        """_get_response_value converts values to strings."""
        manager.set_last_response({
            "int_val": 42,
            "float_val": 3.14,
            "bool_val": True,
        })
        
        assert manager._get_response_value("int_val") == "42"
        assert manager._get_response_value("float_val") == "3.14"
        assert manager._get_response_value("bool_val") == "True"
