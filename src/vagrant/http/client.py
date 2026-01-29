"""HTTP client for making API requests."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from vagrant.core.errors import NetworkError
from vagrant.core.types import HttpMethod
from vagrant.http.auth import AuthConfig, get_auth


@dataclass
class HttpRequest:
    """HTTP request configuration.
    
    Attributes:
        method: HTTP method (GET, POST, etc.).
        url: Full URL to request.
        headers: Request headers.
        params: Query parameters.
        body: Request body (will be JSON-encoded for dict/list).
    """

    method: HttpMethod
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    body: Any = None


@dataclass
class HttpResponse:
    """HTTP response data.
    
    Attributes:
        status_code: HTTP status code.
        status_text: HTTP status text.
        headers: Response headers.
        body: Parsed response body (JSON if applicable, else raw text/bytes).
        elapsed_ms: Request duration in milliseconds.
        size_bytes: Response body size in bytes.
    """

    status_code: int
    status_text: str
    headers: dict[str, str]
    body: Any
    elapsed_ms: float
    size_bytes: int

    @property
    def is_success(self) -> bool:
        """True if status code is 2xx."""
        return 200 <= self.status_code < 300

    @property
    def is_error(self) -> bool:
        """True if status code is 4xx or 5xx."""
        return self.status_code >= 400


class HttpClient:
    """HTTP client wrapper around httpx.
    
    Provides async HTTP request execution with timing, auth, and
    automatic JSON parsing.
    """

    def __init__(
        self,
        timeout: int = 30,
        verify_ssl: bool = True,
        base_url: str | None = None,
    ) -> None:
        """Initialize HTTP client.
        
        Args:
            timeout: Request timeout in seconds.
            verify_ssl: Whether to verify SSL certificates.
            base_url: Base URL prepended to relative paths.
        """
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.base_url = base_url
        self._auth: AuthConfig | None = None
        self._default_headers: dict[str, str] = {
            "User-Agent": "Vagrant/0.1.0",
            "Accept": "application/json",
        }

    def set_auth(self, auth: AuthConfig) -> None:
        """Configure authentication for all requests.
        
        Args:
            auth: Authentication configuration.
        """
        self._auth = auth

    def set_base_url(self, url: str) -> None:
        """Set base URL for relative paths.
        
        Args:
            url: Base URL (e.g., "https://api.example.com/v1").
        """
        self.base_url = url.rstrip("/")

    async def send(self, request: HttpRequest) -> HttpResponse:
        """Send HTTP request and return response.
        
        Args:
            request: Request configuration.
            
        Returns:
            HTTP response with timing and parsed body.
            
        Raises:
            NetworkError: If request fails due to network issues.
        """
        # Build full URL
        url = request.url
        if self.base_url and not url.startswith(("http://", "https://")):
            url = f"{self.base_url}/{url.lstrip('/')}"

        # Build headers
        headers = {**self._default_headers, **request.headers}

        # Build params (copy so auth can modify)
        params = dict(request.params) if request.params else {}

        # Apply auth (may modify headers and/or params)
        if self._auth:
            auth_handler = get_auth(self._auth)
            auth_handler.apply(headers, params)

        # Prepare body
        content = None
        if request.body is not None:
            if isinstance(request.body, (dict, list)):
                content = json.dumps(request.body)
                headers.setdefault("Content-Type", "application/json")
            elif isinstance(request.body, str):
                content = request.body
            else:
                content = str(request.body)

        # Execute request
        start_time = time.monotonic()

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                verify=self.verify_ssl,
            ) as client:
                response = await client.request(
                    method=request.method,
                    url=url,
                    headers=headers,
                    params=params or None,
                    content=content,
                )
        except httpx.TimeoutException as e:
            raise NetworkError(f"Request timed out: {e}", url=url)
        except httpx.ConnectError as e:
            raise NetworkError(f"Connection failed: {e}", url=url)
        except httpx.RequestError as e:
            raise NetworkError(f"Request failed: {e}", url=url)

        elapsed_ms = (time.monotonic() - start_time) * 1000

        # Parse response body
        body: Any
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError):
            body = response.text

        return HttpResponse(
            status_code=response.status_code,
            status_text=response.reason_phrase or "",
            headers=dict(response.headers),
            body=body,
            elapsed_ms=elapsed_ms,
            size_bytes=len(response.content),
        )

    async def get(
        self,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        """Convenience method for GET requests."""
        return await self.send(
            HttpRequest(
                method="GET",
                url=url,
                params=params or {},
                headers=headers or {},
            )
        )

    async def post(
        self,
        url: str,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        """Convenience method for POST requests."""
        return await self.send(
            HttpRequest(
                method="POST",
                url=url,
                body=body,
                headers=headers or {},
            )
        )

    async def put(
        self,
        url: str,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        """Convenience method for PUT requests."""
        return await self.send(
            HttpRequest(
                method="PUT",
                url=url,
                body=body,
                headers=headers or {},
            )
        )

    async def delete(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        """Convenience method for DELETE requests."""
        return await self.send(
            HttpRequest(
                method="DELETE",
                url=url,
                headers=headers or {},
            )
        )
