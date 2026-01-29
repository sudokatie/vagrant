"""Tests for configuration management."""

import pytest
from pathlib import Path

from vagrant.core.config import (
    Config,
    get_config_dir,
    get_config_path,
    load_config,
    save_config,
    get_config_value,
    set_config_value,
)
from vagrant.core.errors import ConfigError


class TestConfig:
    """Tests for Config dataclass."""

    def test_defaults(self):
        """Config has sensible defaults."""
        config = Config()
        assert config.default_environment == "default"
        assert config.history_limit == 1000
        assert config.timeout == 30
        assert config.verify_ssl is True
        assert config.theme == "dark"
        assert config.editor == ""

    def test_to_dict(self):
        """Config can be serialized to dict."""
        config = Config(history_limit=500, theme="light")
        data = config.to_dict()
        assert data["history_limit"] == 500
        assert data["theme"] == "light"
        assert "default_environment" in data

    def test_from_dict_full(self):
        """Config can be created from full dict."""
        data = {
            "default_environment": "production",
            "history_limit": 2000,
            "timeout": 60,
            "verify_ssl": False,
            "theme": "light",
            "editor": "vim",
        }
        config = Config.from_dict(data)
        assert config.default_environment == "production"
        assert config.history_limit == 2000
        assert config.timeout == 60
        assert config.verify_ssl is False
        assert config.theme == "light"
        assert config.editor == "vim"

    def test_from_dict_partial(self):
        """Config from partial dict uses defaults."""
        data = {"timeout": 60}
        config = Config.from_dict(data)
        assert config.timeout == 60
        assert config.history_limit == 1000  # default

    def test_from_dict_unknown_keys(self):
        """Unknown keys are ignored."""
        data = {"timeout": 60, "unknown_key": "ignored"}
        config = Config.from_dict(data)
        assert config.timeout == 60
        assert not hasattr(config, "unknown_key")


class TestConfigPaths:
    """Tests for config path functions."""

    def test_get_config_dir_returns_path(self):
        """get_config_dir returns a Path."""
        result = get_config_dir()
        assert isinstance(result, Path)
        assert "vagrant" in str(result)

    def test_get_config_path_returns_yaml_path(self):
        """get_config_path returns path to config.yaml."""
        result = get_config_path()
        assert result.name == "config.yaml"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_returns_defaults_when_no_file(self, tmp_path, monkeypatch):
        """load_config returns defaults when file doesn't exist."""
        monkeypatch.setattr(
            "vagrant.core.config.get_config_path",
            lambda: tmp_path / "config.yaml"
        )
        config = load_config()
        assert config.history_limit == 1000

    def test_load_reads_existing_file(self, tmp_path, monkeypatch):
        """load_config reads existing config file."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("history_limit: 500\n")
        monkeypatch.setattr(
            "vagrant.core.config.get_config_path",
            lambda: config_path
        )
        config = load_config()
        assert config.history_limit == 500

    def test_load_raises_on_invalid_yaml(self, tmp_path, monkeypatch):
        """load_config raises ConfigError on invalid YAML."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("invalid: yaml: content:\n")
        monkeypatch.setattr(
            "vagrant.core.config.get_config_path",
            lambda: config_path
        )
        with pytest.raises(ConfigError):
            load_config()

    def test_load_raises_on_non_mapping(self, tmp_path, monkeypatch):
        """load_config raises ConfigError if file is not a mapping."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("- list\n- not mapping\n")
        monkeypatch.setattr(
            "vagrant.core.config.get_config_path",
            lambda: config_path
        )
        with pytest.raises(ConfigError):
            load_config()


class TestSaveConfig:
    """Tests for save_config function."""

    def test_save_creates_file(self, tmp_path, monkeypatch):
        """save_config creates config file."""
        config_path = tmp_path / "config.yaml"
        monkeypatch.setattr(
            "vagrant.core.config.get_config_path",
            lambda: config_path
        )
        config = Config(history_limit=750)
        save_config(config)
        assert config_path.exists()
        content = config_path.read_text()
        assert "750" in content

    def test_save_overwrites_existing(self, tmp_path, monkeypatch):
        """save_config overwrites existing file."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("history_limit: 100\n")
        monkeypatch.setattr(
            "vagrant.core.config.get_config_path",
            lambda: config_path
        )
        config = Config(history_limit=999)
        save_config(config)
        content = config_path.read_text()
        assert "999" in content


class TestGetSetConfigValue:
    """Tests for get_config_value and set_config_value."""

    def test_get_valid_key(self, tmp_path, monkeypatch):
        """get_config_value returns value for valid key."""
        config_path = tmp_path / "config.yaml"
        config_path.write_text("timeout: 45\n")
        monkeypatch.setattr(
            "vagrant.core.config.get_config_path",
            lambda: config_path
        )
        assert get_config_value("timeout") == 45

    def test_get_invalid_key(self, tmp_path, monkeypatch):
        """get_config_value raises ConfigError for invalid key."""
        monkeypatch.setattr(
            "vagrant.core.config.get_config_path",
            lambda: tmp_path / "config.yaml"
        )
        with pytest.raises(ConfigError) as exc_info:
            get_config_value("nonexistent")
        assert "Unknown config key" in str(exc_info.value)

    def test_set_valid_key(self, tmp_path, monkeypatch):
        """set_config_value sets and saves value."""
        config_path = tmp_path / "config.yaml"
        monkeypatch.setattr(
            "vagrant.core.config.get_config_path",
            lambda: config_path
        )
        set_config_value("timeout", 90)
        assert get_config_value("timeout") == 90

    def test_set_invalid_key(self, tmp_path, monkeypatch):
        """set_config_value raises ConfigError for invalid key."""
        monkeypatch.setattr(
            "vagrant.core.config.get_config_path",
            lambda: tmp_path / "config.yaml"
        )
        with pytest.raises(ConfigError):
            set_config_value("nonexistent", "value")

    def test_set_bool_from_string(self, tmp_path, monkeypatch):
        """set_config_value coerces string to bool."""
        config_path = tmp_path / "config.yaml"
        monkeypatch.setattr(
            "vagrant.core.config.get_config_path",
            lambda: config_path
        )
        set_config_value("verify_ssl", "false")
        assert get_config_value("verify_ssl") is False

    def test_set_int_from_string(self, tmp_path, monkeypatch):
        """set_config_value coerces string to int."""
        config_path = tmp_path / "config.yaml"
        monkeypatch.setattr(
            "vagrant.core.config.get_config_path",
            lambda: config_path
        )
        set_config_value("timeout", "120")
        assert get_config_value("timeout") == 120

    def test_set_int_invalid_string(self, tmp_path, monkeypatch):
        """set_config_value raises on invalid int string."""
        config_path = tmp_path / "config.yaml"
        monkeypatch.setattr(
            "vagrant.core.config.get_config_path",
            lambda: config_path
        )
        with pytest.raises(ConfigError):
            set_config_value("timeout", "not a number")
