"""Authentication handlers for HTTP requests."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Literal, Protocol

from vagrant.core.types import AuthType

# Location for API key authentication
ApiKeyLocation = Literal["header", "query"]


class AuthHandler(Protocol):
    """Protocol for auth handlers."""

    def apply(
        self,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
    ) -> None:
        """Apply authentication to request headers and/or query params.
        
        Args:
            headers: Request headers dict to modify.
            params: Query parameters dict to modify (optional).
        """
        ...


@dataclass
class AuthConfig:
    """Authentication configuration.
    
    Attributes:
        type: Authentication type (bearer, basic, apikey).
        credentials: Type-specific credentials.
            - bearer: {"token": "..."}
            - basic: {"username": "...", "password": "..."}
            - apikey: {"key": "...", "name": "X-API-Key", "location": "header"}
              location can be "header" (default) or "query"
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

    def apply(
        self,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
    ) -> None:
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

    def apply(
        self,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
    ) -> None:
        """Add basic auth to headers."""
        credentials = f"{self.username}:{self.password}"
        encoded = base64.b64encode(credentials.encode()).decode()
        headers["Authorization"] = f"Basic {encoded}"


class ApiKeyAuth:
    """API key authentication.
    
    Adds API key to header or query parameter based on location.
    """

    def __init__(
        self,
        key: str,
        name: str = "X-API-Key",
        location: ApiKeyLocation = "header",
    ) -> None:
        """Initialize with API key, name, and location.
        
        Args:
            key: The API key value.
            name: Name of the header or query parameter (default: X-API-Key).
            location: Where to add the key - "header" or "query" (default: header).
        """
        self.key = key
        self.name = name
        self.location = location

    def apply(
        self,
        headers: dict[str, str],
        params: dict[str, str] | None = None,
    ) -> None:
        """Add API key to headers or query params based on location."""
        if self.location == "query":
            if params is not None:
                params[self.name] = self.key
        else:
            # Default to header
            headers[self.name] = self.key


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
        name = config.credentials.get("name", "X-API-Key")
        # Support legacy "header" key for backwards compatibility
        if "header" in config.credentials and "name" not in config.credentials:
            name = config.credentials["header"]
        location = config.credentials.get("location", "header")
        if location not in ("header", "query"):
            location = "header"
        return ApiKeyAuth(key, name, location)  # type: ignore
    else:
        raise ValueError(f"Unsupported auth type: {config.type}")
