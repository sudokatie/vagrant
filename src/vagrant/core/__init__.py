"""Core module - configuration, errors, and shared types."""

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
