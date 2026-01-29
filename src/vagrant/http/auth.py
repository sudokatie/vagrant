"""Authentication handlers for HTTP requests."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Protocol

from vagrant.core.types import AuthType


class AuthHandler(Protocol):
    """Protocol for auth handlers."""

    def apply(self, headers: dict[str, str]) -> None:
        """Apply authentication to request headers."""
        ...


@dataclass
class AuthConfig:
    """Authentication configuration.
    
    Attributes:
        type: Authentication type (bearer, basic, apikey).
        credentials: Type-specific credentials.
            - bearer: {"token": "..."}
            - basic: {"username": "...", "password": "..."}
            - apikey: {"key": "...", "header": "X-API-Key"} (header is optional)
    """

    type: AuthType
    credentials: dict[str, str]


class BearerAuth:
    """Bearer token authentication.
    
    Adds Authorization: Bearer <token> header.
    """

    def __init__(self, token: str) -> None:
        """Initialize with bearer token.
        
        Args:
            token: The bearer token.
        """
        self.token = token

    def apply(self, headers: dict[str, str]) -> None:
        """Add bearer token to headers."""
        headers["Authorization"] = f"Bearer {self.token}"


class BasicAuth:
    """HTTP Basic authentication.
    
    Adds Authorization: Basic <base64(username:password)> header.
    """

    def __init__(self, username: str, password: str) -> None:
        """Initialize with username and password.
        
        Args:
            username: The username.
            password: The password.
        """
        self.username = username
        self.password = password

    def apply(self, headers: dict[str, str]) -> None:
        """Add basic auth to headers."""
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"


class ApiKeyAuth:
    """API key authentication.
    
    Adds a custom header with the API key.
    """

    def __init__(self, key: str, header_name: str = "X-API-Key") -> None:
        """Initialize with API key and header name.
        
        Args:
            key: The API key.
            header_name: Name of the header to use (default: X-API-Key).
        """
        self.key = key
        self.header_name = header_name

    def apply(self, headers: dict[str, str]) -> None:
        """Add API key to headers."""
        headers[self.header_name] = self.key


def get_auth(config: AuthConfig) -> AuthHandler:
    """Create an auth handler from configuration.
    
    Args:
        config: Authentication configuration.
        
    Returns:
        Appropriate AuthHandler for the config type.
        
    Raises:
        ValueError: If auth type is not supported.
    """
    if config.type == "bearer":
        token = config.credentials.get("token", "")
        return BearerAuth(token)
    elif config.type == "basic":
        username = config.credentials.get("username", "")
        password = config.credentials.get("password", "")
        return BasicAuth(username, password)
    elif config.type == "apikey":
        key = config.credentials.get("key", "")
        header = config.credentials.get("header", "X-API-Key")
        return ApiKeyAuth(key, header)
    else:
        raise ValueError(f"Unsupported auth type: {config.type}")
