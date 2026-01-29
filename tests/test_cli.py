"""Tests for CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from vagrant import __version__
from vagrant.cli.commands import cli


@pytest.fixture
def runner():
    """Create CLI test runner."""
    return CliRunner()


class TestCLIBasics:
    """Tests for basic CLI functionality."""

    def test_cli_help(self, runner):
        """CLI shows help text."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Vagrant - API Explorer" in result.output

    def test_cli_version(self, runner):
        """CLI shows version."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output


class TestExploreCommand:
    """Tests for explore command."""

    def test_explore_spec_file(self, runner, specs_dir: Path):
        """Explore command parses spec file."""
        result = runner.invoke(cli, ["explore", str(specs_dir / "petstore.yaml")])
        assert result.exit_code == 0
        assert "Petstore API" in result.output

    def test_explore_shows_operations(self, runner, specs_dir: Path):
        """Explore shows operations count."""
        result = runner.invoke(cli, ["explore", str(specs_dir / "petstore.yaml")])
        assert "Operations:" in result.output
        assert "endpoints" in result.output

    def test_explore_shows_servers(self, runner, specs_dir: Path):
        """Explore shows server info."""
        result = runner.invoke(cli, ["explore", str(specs_dir / "petstore.yaml")])
        assert "Servers:" in result.output
        assert "api.petstore.com" in result.output

    def test_explore_nonexistent_file(self, runner):
        """Explore fails for nonexistent file with parse error exit code."""
        result = runner.invoke(cli, ["explore", "nonexistent.yaml"])
        # Exit code 3 = parse error per spec section 2.3
        assert result.exit_code == 3
        assert "error" in result.output.lower()


class TestHistoryCommand:
    """Tests for history command."""

    def test_history_empty(self, runner, tmp_path, monkeypatch):
        """History shows empty message."""
        monkeypatch.setattr(
            "vagrant.cli.commands.HistoryStorage",
            lambda **kw: _MockHistoryStorage([])
        )
        result = runner.invoke(cli, ["history"])
        assert result.exit_code == 0
        assert "No history" in result.output

    def test_history_with_limit(self, runner, tmp_path, monkeypatch):
        """History accepts limit option."""
        monkeypatch.setattr(
            "vagrant.cli.commands.HistoryStorage",
            lambda **kw: _MockHistoryStorage([])
        )
        result = runner.invoke(cli, ["history", "-n", "10"])
        assert result.exit_code == 0


class _MockHistoryStorage:
    """Mock history storage for tests."""
    def __init__(self, entries):
        self._entries = entries

    def list(self, limit=50):
        return self._entries[:limit]

    def search(self, query):
        return self._entries


class TestEnvCommands:
    """Tests for environment commands."""

    def test_env_list_empty(self, runner, tmp_path, monkeypatch):
        """Env list shows empty message."""
        monkeypatch.setattr(
            "vagrant.cli.commands.EnvironmentManager",
            lambda **kw: _MockEnvManager(tmp_path)
        )
        monkeypatch.setattr(
            "vagrant.cli.commands.load_config",
            lambda: _MockConfig()
        )
        result = runner.invoke(cli, ["env", "list"])
        assert result.exit_code == 0
        assert "No environments" in result.output

    def test_env_create(self, runner, tmp_path, monkeypatch):
        """Env create creates environment."""
        mgr = _MockEnvManager(tmp_path)
        monkeypatch.setattr(
            "vagrant.cli.commands.EnvironmentManager",
            lambda **kw: mgr
        )
        result = runner.invoke(cli, [
            "env", "create", "test",
            "-u", "https://api.example.com"
        ])
        assert result.exit_code == 0
        assert "Created" in result.output

    def test_env_create_with_auth(self, runner, tmp_path, monkeypatch):
        """Env create with auth."""
        mgr = _MockEnvManager(tmp_path)
        monkeypatch.setattr(
            "vagrant.cli.commands.EnvironmentManager",
            lambda **kw: mgr
        )
        result = runner.invoke(cli, [
            "env", "create", "test",
            "-u", "https://api.example.com",
            "-a", "bearer",
            "-t", "secret123"
        ])
        assert result.exit_code == 0
        assert "Created" in result.output

    def test_env_show(self, runner, tmp_path, monkeypatch):
        """Env show displays environment."""
        from vagrant.storage.environments import Environment
        mgr = _MockEnvManager(tmp_path)
        mgr._envs["test"] = Environment(name="test", base_url="https://api.example.com")
        monkeypatch.setattr(
            "vagrant.cli.commands.EnvironmentManager",
            lambda **kw: mgr
        )
        result = runner.invoke(cli, ["env", "show", "test"])
        assert result.exit_code == 0
        assert "test" in result.output
        assert "api.example.com" in result.output

    def test_env_delete(self, runner, tmp_path, monkeypatch):
        """Env delete removes environment."""
        from vagrant.storage.environments import Environment
        mgr = _MockEnvManager(tmp_path)
        mgr._envs["test"] = Environment(name="test")
        monkeypatch.setattr(
            "vagrant.cli.commands.EnvironmentManager",
            lambda **kw: mgr
        )
        result = runner.invoke(cli, ["env", "delete", "test", "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.output


class _MockEnvManager:
    """Mock environment manager for tests."""
    def __init__(self, tmp_path):
        self._envs = {}
        self.env_dir = tmp_path / "environments"
        self.env_dir.mkdir(exist_ok=True)

    def list(self):
        return list(self._envs.keys())

    def exists(self, name):
        return name in self._envs

    def get(self, name):
        if name not in self._envs:
            raise FileNotFoundError(f"Environment not found: {name}")
        return self._envs[name]

    def save(self, env):
        self._envs[env.name] = env

    def delete(self, name):
        if name not in self._envs:
            raise FileNotFoundError(f"Environment not found: {name}")
        del self._envs[name]


class _MockConfig:
    """Mock config for tests."""
    default_environment = ""
    timeout = 30
    verify_ssl = True

    def to_dict(self):
        return {
            "default_environment": self.default_environment,
            "timeout": self.timeout,
            "verify_ssl": self.verify_ssl,
        }


class TestConfigCommands:
    """Tests for config commands."""

    def test_config_list(self, runner, tmp_path, monkeypatch):
        """Config list shows values."""
        monkeypatch.setattr(
            "vagrant.cli.commands.load_config",
            lambda: _MockConfig()
        )
        result = runner.invoke(cli, ["config", "list"])
        assert result.exit_code == 0
        assert "timeout" in result.output
        assert "verify_ssl" in result.output

    def test_config_get(self, runner, tmp_path, monkeypatch):
        """Config get shows single value."""
        monkeypatch.setattr(
            "vagrant.cli.commands.get_config_value",
            lambda k: 30
        )
        result = runner.invoke(cli, ["config", "get", "timeout"])
        assert result.exit_code == 0
        assert "timeout:" in result.output

    def test_config_set(self, runner, tmp_path, monkeypatch):
        """Config set updates value."""
        monkeypatch.setattr(
            "vagrant.cli.commands.set_config_value",
            lambda k, v: None
        )
        result = runner.invoke(cli, ["config", "set", "timeout", "60"])
        assert result.exit_code == 0
        assert "Set" in result.output


class TestImportCommand:
    """Tests for import command."""

    def test_import_spec(self, runner, specs_dir, tmp_path, monkeypatch):
        """Import command caches spec."""
        # Mock config dir to use tmp_path
        monkeypatch.setattr(
            "vagrant.cli.commands.get_config_dir",
            lambda: tmp_path
        )
        result = runner.invoke(cli, ["import", str(specs_dir / "petstore.yaml")])
        assert result.exit_code == 0
        assert "Imported" in result.output
        assert (tmp_path / "specs" / "petstore.yaml").exists()

    def test_import_with_name(self, runner, specs_dir, tmp_path, monkeypatch):
        """Import with custom name."""
        monkeypatch.setattr(
            "vagrant.cli.commands.get_config_dir",
            lambda: tmp_path
        )
        result = runner.invoke(cli, ["import", str(specs_dir / "petstore.yaml"), "-n", "myapi"])
        assert result.exit_code == 0
        assert "myapi" in result.output
        assert (tmp_path / "specs" / "myapi.yaml").exists()

    def test_import_nonexistent(self, runner):
        """Import fails for nonexistent file."""
        result = runner.invoke(cli, ["import", "nonexistent.yaml"])
        assert result.exit_code == 3  # Parse error


class TestGlobalOptions:
    """Tests for global CLI options."""

    def test_quiet_mode(self, runner, specs_dir):
        """Quiet mode suppresses extra output."""
        result = runner.invoke(cli, ["--quiet", "explore", str(specs_dir / "petstore.yaml")])
        # In quiet mode, explore still shows output (it's not a request command)
        assert result.exit_code == 0

    def test_verbose_mode(self, runner, specs_dir):
        """Verbose mode exists."""
        result = runner.invoke(cli, ["--verbose", "explore", str(specs_dir / "petstore.yaml")])
        assert result.exit_code == 0

    def test_output_format_option(self, runner):
        """Output format option is accepted."""
        result = runner.invoke(cli, ["--help"])
        assert "--output" in result.output or "-o" in result.output

    def test_timeout_option(self, runner):
        """Timeout option is accepted."""
        result = runner.invoke(cli, ["--help"])
        assert "--timeout" in result.output

    def test_no_verify_option(self, runner):
        """No-verify option is accepted."""
        result = runner.invoke(cli, ["--help"])
        assert "--no-verify" in result.output

    def test_auth_option(self, runner):
        """Auth option is accepted."""
        result = runner.invoke(cli, ["--help"])
        assert "--auth" in result.output

    def test_header_option(self, runner):
        """Header option is accepted."""
        result = runner.invoke(cli, ["--help"])
        assert "--header" in result.output or "-H" in result.output


class TestEnvSetCommand:
    """Tests for env set command (spec 2.1)."""

    def test_env_set_with_default_env(self, runner, tmp_path, monkeypatch):
        """Env set uses default environment."""
        from vagrant.storage.environments import Environment
        mgr = _MockEnvManager(tmp_path)
        mgr._envs["default"] = Environment(name="default")
        
        mock_config = _MockConfig()
        mock_config.default_environment = "default"
        
        monkeypatch.setattr("vagrant.cli.commands.EnvironmentManager", lambda **kw: mgr)
        monkeypatch.setattr("vagrant.cli.commands.load_config", lambda: mock_config)
        
        result = runner.invoke(cli, ["env", "set", "api_key", "secret123"])
        assert result.exit_code == 0
        assert "Set" in result.output
        assert mgr._envs["default"].variables.get("api_key") == "secret123"

    def test_env_set_with_env_option(self, runner, tmp_path, monkeypatch):
        """Env set uses specified environment."""
        from vagrant.storage.environments import Environment
        mgr = _MockEnvManager(tmp_path)
        mgr._envs["production"] = Environment(name="production")
        
        monkeypatch.setattr("vagrant.cli.commands.EnvironmentManager", lambda **kw: mgr)
        monkeypatch.setattr("vagrant.cli.commands.load_config", lambda: _MockConfig())
        
        result = runner.invoke(cli, ["--env", "production", "env", "set", "token", "abc"])
        assert result.exit_code == 0
        assert mgr._envs["production"].variables.get("token") == "abc"

    def test_env_set_no_env_specified(self, runner, tmp_path, monkeypatch):
        """Env set fails without environment."""
        mgr = _MockEnvManager(tmp_path)
        mock_config = _MockConfig()
        mock_config.default_environment = ""
        
        monkeypatch.setattr("vagrant.cli.commands.EnvironmentManager", lambda **kw: mgr)
        monkeypatch.setattr("vagrant.cli.commands.load_config", lambda: mock_config)
        
        result = runner.invoke(cli, ["env", "set", "key", "value"])
        assert result.exit_code == 2  # Config error


class TestParseAuthString:
    """Tests for parse_auth_string function."""

    def test_parse_bearer_auth(self):
        """Parse bearer auth string."""
        from vagrant.cli.commands import parse_auth_string
        
        config = parse_auth_string("bearer:my-secret-token")
        assert config is not None
        assert config.type == "bearer"
        assert config.credentials["token"] == "my-secret-token"

    def test_parse_basic_auth_with_password(self):
        """Parse basic auth string with password."""
        from vagrant.cli.commands import parse_auth_string
        
        config = parse_auth_string("basic:user:password")
        assert config is not None
        assert config.type == "basic"
        assert config.credentials["username"] == "user"
        assert config.credentials["password"] == "password"

    def test_parse_basic_auth_without_password(self):
        """Parse basic auth string without password."""
        from vagrant.cli.commands import parse_auth_string
        
        config = parse_auth_string("basic:user")
        assert config is not None
        assert config.type == "basic"
        assert config.credentials["username"] == "user"
        assert config.credentials["password"] == ""

    def test_parse_apikey_simple(self):
        """Parse simple API key auth string."""
        from vagrant.cli.commands import parse_auth_string
        
        config = parse_auth_string("apikey:my-api-key")
        assert config is not None
        assert config.type == "apikey"
        assert config.credentials["key"] == "my-api-key"

    def test_parse_apikey_with_header_location(self):
        """Parse API key auth with header location."""
        from vagrant.cli.commands import parse_auth_string
        
        config = parse_auth_string("apikey:header:X-Custom-Key:my-api-key")
        assert config is not None
        assert config.type == "apikey"
        assert config.credentials["key"] == "my-api-key"
        assert config.credentials["name"] == "X-Custom-Key"
        assert config.credentials["location"] == "header"

    def test_parse_apikey_with_query_location(self):
        """Parse API key auth with query location."""
        from vagrant.cli.commands import parse_auth_string
        
        config = parse_auth_string("apikey:query:api_key:secret123")
        assert config is not None
        assert config.type == "apikey"
        assert config.credentials["key"] == "secret123"
        assert config.credentials["name"] == "api_key"
        assert config.credentials["location"] == "query"

    def test_parse_empty_string(self):
        """Parse empty auth string returns None."""
        from vagrant.cli.commands import parse_auth_string
        
        assert parse_auth_string("") is None
        assert parse_auth_string(None) is None

    def test_parse_invalid_format(self):
        """Parse invalid auth string returns None."""
        from vagrant.cli.commands import parse_auth_string
        
        # No colon separator
        assert parse_auth_string("justtoken") is None

    def test_parse_unknown_type(self):
        """Parse unknown auth type returns None."""
        from vagrant.cli.commands import parse_auth_string
        
        # Unknown type
        assert parse_auth_string("unknown:value") is None


class TestHistoryCleanup:
    """Tests for history auto-cleanup on startup."""

    def test_cleanup_called_on_startup(self, runner, tmp_path, monkeypatch):
        """History cleanup is called on CLI startup."""
        cleanup_called = []
        
        class MockHistoryStorage:
            def __init__(self, **kw):
                pass
            def cleanup(self, limit):
                cleanup_called.append(limit)
            def list(self, limit=50):
                return []
        
        class MockConfig:
            history_limit = 500
            default_environment = ""
            timeout = 30
            verify_ssl = True
            def to_dict(self):
                return {"history_limit": 500}
        
        monkeypatch.setattr("vagrant.cli.commands.HistoryStorage", MockHistoryStorage)
        monkeypatch.setattr("vagrant.cli.commands.load_config", lambda: MockConfig())
        
        result = runner.invoke(cli, ["history"])
        
        # Cleanup should be called with the config limit
        assert 500 in cleanup_called


class TestEnvShowWithAuth:
    """Tests for env show with auth details."""

    def test_env_show_with_auth(self, runner, tmp_path, monkeypatch):
        """Env show displays auth type."""
        from vagrant.storage.environments import Environment
        from vagrant.http.auth import AuthConfig
        
        mgr = _MockEnvManager(tmp_path)
        mgr._envs["test"] = Environment(
            name="test",
            base_url="https://api.example.com",
            auth=AuthConfig(type="bearer", credentials={"token": "secret"})
        )
        monkeypatch.setattr("vagrant.cli.commands.EnvironmentManager", lambda **kw: mgr)
        
        result = runner.invoke(cli, ["env", "show", "test"])
        assert result.exit_code == 0
        assert "bearer" in result.output.lower()

    def test_env_show_with_variables(self, runner, tmp_path, monkeypatch):
        """Env show displays variables."""
        from vagrant.storage.environments import Environment
        
        mgr = _MockEnvManager(tmp_path)
        mgr._envs["test"] = Environment(
            name="test",
            variables={"api_key": "visible", "secret_password": "hidden"}
        )
        monkeypatch.setattr("vagrant.cli.commands.EnvironmentManager", lambda **kw: mgr)
        
        result = runner.invoke(cli, ["env", "show", "test"])
        assert result.exit_code == 0
        # Variables should be shown
        assert "api_key" in result.output
        # Secret variables should be masked
        assert "****" in result.output


class TestEnvCreateAuthTypes:
    """Tests for env create with different auth types."""

    def test_env_create_with_apikey_auth(self, runner, tmp_path, monkeypatch):
        """Env create with API key auth."""
        mgr = _MockEnvManager(tmp_path)
        monkeypatch.setattr("vagrant.cli.commands.EnvironmentManager", lambda **kw: mgr)
        
        result = runner.invoke(cli, [
            "env", "create", "test",
            "-a", "apikey",
            "-t", "my-key"
        ])
        assert result.exit_code == 0
        assert mgr._envs["test"].auth.type == "apikey"

    def test_env_create_with_basic_auth(self, runner, tmp_path, monkeypatch):
        """Env create with basic auth (token as user:pass)."""
        mgr = _MockEnvManager(tmp_path)
        monkeypatch.setattr("vagrant.cli.commands.EnvironmentManager", lambda **kw: mgr)
        
        result = runner.invoke(cli, [
            "env", "create", "test",
            "-a", "basic",
            "-t", "user:password"
        ])
        assert result.exit_code == 0
        assert mgr._envs["test"].auth.type == "basic"


class TestEnvCreateExisting:
    """Tests for env create when environment exists."""

    def test_env_create_existing_fails(self, runner, tmp_path, monkeypatch):
        """Env create fails if environment already exists."""
        from vagrant.storage.environments import Environment
        
        mgr = _MockEnvManager(tmp_path)
        mgr._envs["existing"] = Environment(name="existing")
        monkeypatch.setattr("vagrant.cli.commands.EnvironmentManager", lambda **kw: mgr)
        
        result = runner.invoke(cli, ["env", "create", "existing"])
        assert result.exit_code == 2
        assert "already exists" in result.output


class TestEnvSetNonexistent:
    """Tests for env set with nonexistent environment."""

    def test_env_set_nonexistent_env(self, runner, tmp_path, monkeypatch):
        """Env set fails if specified environment doesn't exist."""
        mgr = _MockEnvManager(tmp_path)
        mock_config = _MockConfig()
        mock_config.default_environment = ""
        
        monkeypatch.setattr("vagrant.cli.commands.EnvironmentManager", lambda **kw: mgr)
        monkeypatch.setattr("vagrant.cli.commands.load_config", lambda: mock_config)
        
        result = runner.invoke(cli, ["--env", "nonexistent", "env", "set", "key", "value"])
        assert result.exit_code == 2


class TestEnvListWithDefault:
    """Tests for env list showing default environment."""

    def test_env_list_shows_default(self, runner, tmp_path, monkeypatch):
        """Env list marks default environment."""
        from vagrant.storage.environments import Environment
        
        mgr = _MockEnvManager(tmp_path)
        mgr._envs["production"] = Environment(name="production")
        mgr._envs["staging"] = Environment(name="staging")
        
        mock_config = _MockConfig()
        mock_config.default_environment = "production"
        
        monkeypatch.setattr("vagrant.cli.commands.EnvironmentManager", lambda **kw: mgr)
        monkeypatch.setattr("vagrant.cli.commands.load_config", lambda: mock_config)
        
        result = runner.invoke(cli, ["env", "list"])
        assert result.exit_code == 0
        assert "production" in result.output
        assert "default" in result.output.lower()
