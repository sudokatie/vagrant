"""Configuration management for Vagrant."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from vagrant.core.errors import ConfigError
from vagrant.core.types import Theme


@dataclass
class Config:
    """Vagrant configuration settings.
    
    Attributes:
        default_environment: Name of the default environment to use.
        history_limit: Maximum number of history entries to keep.
        timeout: Default request timeout in seconds.
        verify_ssl: Whether to verify SSL certificates.
        theme: Color theme for TUI.
        editor: External editor command for body editing.
    """

    default_environment: str = "default"
    history_limit: int = 1000
    timeout: int = 30
    verify_ssl: bool = True
    theme: Theme = "dark"
    editor: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return {
            "default_environment": self.default_environment,
            "history_limit": self.history_limit,
            "timeout": self.timeout,
            "verify_ssl": self.verify_ssl,
            "theme": self.theme,
            "editor": self.editor,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        """Create config from dictionary.
        
        Unknown keys are ignored for forward compatibility.
        """
        return cls(
            default_environment=data.get("default_environment", "default"),
            history_limit=data.get("history_limit", 1000),
            timeout=data.get("timeout", 30),
            verify_ssl=data.get("verify_ssl", True),
            theme=data.get("theme", "dark"),
            editor=data.get("editor", ""),
        )


def get_config_dir() -> Path:
    """Return path to Vagrant config directory.
    
    Creates the directory if it doesn't exist.
    """
    config_dir = Path.home() / ".config" / "vagrant"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Return path to config file."""
    return get_config_dir() / "config.yaml"


def load_config() -> Config:
    """Load configuration from file.
    
    Returns default config if file doesn't exist.
    Merges partial config with defaults.
    
    Raises:
        ConfigError: If config file exists but cannot be parsed.
    """
    config_path = get_config_path()
    
    if not config_path.exists():
        return Config()
    
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML in config file: {e}")
    except OSError as e:
        raise ConfigError(f"Cannot read config file: {e}")
    
    if not isinstance(data, dict):
        raise ConfigError("Config file must be a YAML mapping")
    
    return Config.from_dict(data)


def save_config(config: Config) -> None:
    """Save configuration to file.
    
    Creates config directory if it doesn't exist.
    
    Raises:
        ConfigError: If config cannot be written.
    """
    config_path = get_config_path()
    
    try:
        with open(config_path, "w") as f:
            yaml.safe_dump(config.to_dict(), f, default_flow_style=False)
    except OSError as e:
        raise ConfigError(f"Cannot write config file: {e}")


def get_config_value(key: str) -> Any:
    """Get a single config value.
    
    Raises:
        ConfigError: If key is not a valid config key.
    """
    config = load_config()
    
    if not hasattr(config, key):
        raise ConfigError(f"Unknown config key: {key}", config_key=key)
    
    return getattr(config, key)


def set_config_value(key: str, value: Any) -> None:
    """Set a single config value.
    
    Raises:
        ConfigError: If key is not a valid config key.
    """
    config = load_config()
    
    if not hasattr(config, key):
        raise ConfigError(f"Unknown config key: {key}", config_key=key)
    
    # Type coercion for common cases
    current = getattr(config, key)
    if isinstance(current, bool) and isinstance(value, str):
        value = value.lower() in ("true", "yes", "1", "on")
    elif isinstance(current, int) and isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            raise ConfigError(f"Invalid integer value: {value}", config_key=key)
    
    setattr(config, key, value)
    save_config(config)
