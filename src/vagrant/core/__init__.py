"""Core module - configuration, errors, and shared types."""

from vagrant.core.errors import (
    VagrantError,
    SpecParseError,
    NetworkError,
    AuthError,
    ConfigError,
)

__all__ = [
    "VagrantError",
    "SpecParseError",
    "NetworkError",
    "AuthError",
    "ConfigError",
]
