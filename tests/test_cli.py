"""Tests for CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

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
        assert "0.1.0" in result.output


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
        """Explore fails for nonexistent file."""
        result = runner.invoke(cli, ["explore", "nonexistent.yaml"])
        assert result.exit_code == 1
        assert "Error" in result.output


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
