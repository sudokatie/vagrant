"""Core module - configuration, errors, and shared types."""

from vagrant.core.config import (
    Config,
    get_config_dir,
    get_config_path,
    load_config,
    save_config,
    get_config_value,
    set_config_value,
)
from vagrant.core.errors import (
    VagrantError,
    SpecParseError,
    NetworkError,
    AuthError,
    ConfigError,
)
from vagrant.core.types import (
    HttpMethod,
    ParamLocation,
    AuthType,
    OutputFormat,
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
