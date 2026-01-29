"""Core module - configuration, errors, and shared types."""

from vagrant.core.config import (
    Config,
    get_config_dir,
    get_config_path,
    get_config_value,
    load_config,
    save_config,
    set_config_value,
)
from vagrant.core.errors import (
    AuthError,
    ConfigError,
    NetworkError,
    SpecParseError,
    VagrantError,
)
from vagrant.core.types import (
    AuthType,
    HttpMethod,
    OutputFormat,
    ParamLocation,
    Theme,
)

__all__ = [
    # Config
    "Config",
    "get_config_dir",
    "get_config_path",
    "load_config",
    "save_config",
    "get_config_value",
    "set_config_value",
    # Errors
    "VagrantError",
    "SpecParseError",
    "NetworkError",
    "AuthError",
    "ConfigError",
    # Types
    "HttpMethod",
    "ParamLocation",
    "AuthType",
    "OutputFormat",
    "Theme",
]
