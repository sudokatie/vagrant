"""Tests for HTTP client."""

import pytest
import respx
from httpx import Response

from vagrant.core.errors import NetworkError
from vagrant.http.auth import AuthConfig
from vagrant.http.client import HttpClient, HttpRequest, HttpResponse


class TestHttpRequest:
    """Tests for HttpRequest dataclass."""

    def test_minimal_request(self):
        """Request with just method and URL."""
        req = HttpRequest(method="GET", url="https://api.example.com/users")
        assert req.method == "GET"
        assert req.url == "https://api.example.com/users"
        assert req.headers == {}
        assert req.params == {}
        assert req.body is None

    def test_request_with_all_fields(self):
        """Request with all fields."""
        req = HttpRequest(
            method="POST",
            url="https://api.example.com/users",
            headers={"Content-Type": "application/json"},
            params={"include": "profile"},
            body={"name": "Test User"},
        )
        assert req.headers == {"Content-Type": "application/json"}
        assert req.params == {"include": "profile"}
        assert req.body == {"name": "Test User"}


class TestHttpResponse:
    """Tests for HttpResponse dataclass."""

    def test_success_response(self):
        """Response with 2xx status."""
        resp = HttpResponse(
            status_code=200,
            status_text="OK",
            headers={"Content-Type": "application/json"},
            body={"id": 1},
            elapsed_ms=50.0,
            size_bytes=100,
        )
        assert resp.is_success is True
        assert resp.is_error is False

    def test_error_response(self):
        """Response with 4xx/5xx status."""
        resp = HttpResponse(
            status_code=404,
            status_text="Not Found",
            headers={},
            body={"error": "Not found"},
            elapsed_ms=30.0,
            size_bytes=50,
        )
        assert resp.is_success is False
        assert resp.is_error is True


class TestHttpClientInit:
    """Tests for HttpClient initialization."""

    def test_default_settings(self):
        """Client has sensible defaults."""
        client = HttpClient()
        assert client.timeout == 30
        assert client.verify_ssl is True
        assert client.base_url is None

    def test_custom_settings(self):
        """Client accepts custom settings."""
        client = HttpClient(timeout=60, verify_ssl=False, base_url="https://api.test.com")
        assert client.timeout == 60
        assert client.verify_ssl is False
        assert client.base_url == "https://api.test.com"


class TestHttpClientAuth:
    """Tests for HttpClient authentication."""

    @respx.mock
    async def test_bearer_auth(self):
        """Client applies bearer auth."""
        respx.get("https://api.example.com/test").mock(
            return_value=Response(200, json={"ok": True})
        )

        client = HttpClient()
        client.set_auth(AuthConfig(type="bearer", credentials={"token": "secret"}))

        resp = await client.get("https://api.example.com/test")

        assert resp.status_code == 200
        # Check that auth header was sent
        request = respx.calls.last.request
        assert request.headers["Authorization"] == "Bearer secret"


class TestHttpClientRequests:
    """Tests for making HTTP requests."""

    @respx.mock
    async def test_get_request(self):
        """GET request works."""
        respx.get("https://api.example.com/users").mock(
            return_value=Response(200, json=[{"id": 1, "name": "Test"}])
        )

        client = HttpClient()
        resp = await client.get("https://api.example.com/users")

        assert resp.status_code == 200
        assert resp.body == [{"id": 1, "name": "Test"}]

    @respx.mock
    async def test_post_request(self):
        """POST request with JSON body."""
        respx.post("https://api.example.com/users").mock(
            return_value=Response(201, json={"id": 2, "name": "New User"})
        )

        client = HttpClient()
        resp = await client.post(
            "https://api.example.com/users",
            body={"name": "New User"},
        )

        assert resp.status_code == 201
        assert resp.body["id"] == 2

    @respx.mock
    async def test_put_request(self):
        """PUT request works."""
        respx.put("https://api.example.com/users/1").mock(
            return_value=Response(200, json={"id": 1, "name": "Updated"})
        )

        client = HttpClient()
        resp = await client.put(
            "https://api.example.com/users/1",
            body={"name": "Updated"},
        )

        assert resp.status_code == 200

    @respx.mock
    async def test_delete_request(self):
        """DELETE request works."""
        respx.delete("https://api.example.com/users/1").mock(
            return_value=Response(204)
        )

        client = HttpClient()
        resp = await client.delete("https://api.example.com/users/1")

        assert resp.status_code == 204

    @respx.mock
    async def test_query_params(self):
        """Query parameters are included."""
        respx.get("https://api.example.com/users").mock(
            return_value=Response(200, json=[])
        )

        client = HttpClient()
        await client.get("https://api.example.com/users", params={"page": "2"})

        request = respx.calls.last.request
        assert "page=2" in str(request.url)

    @respx.mock
    async def test_custom_headers(self):
        """Custom headers are sent."""
        respx.get("https://api.example.com/test").mock(
            return_value=Response(200, json={})
        )

        client = HttpClient()
        await client.get(
            "https://api.example.com/test",
            headers={"X-Custom": "value"},
        )

        request = respx.calls.last.request
        assert request.headers["X-Custom"] == "value"

    @respx.mock
    async def test_base_url(self):
        """Base URL is prepended to relative paths."""
        respx.get("https://api.example.com/v1/users").mock(
            return_value=Response(200, json=[])
        )

        client = HttpClient(base_url="https://api.example.com/v1")
        await client.get("/users")

        request = respx.calls.last.request
        assert str(request.url) == "https://api.example.com/v1/users"

    @respx.mock
    async def test_elapsed_time(self):
        """Response includes elapsed time."""
        respx.get("https://api.example.com/test").mock(
            return_value=Response(200, json={})
        )

        client = HttpClient()
        resp = await client.get("https://api.example.com/test")

        assert resp.elapsed_ms >= 0

    @respx.mock
    async def test_response_size(self):
        """Response includes body size."""
        respx.get("https://api.example.com/test").mock(
            return_value=Response(200, json={"data": "value"})
        )

        client = HttpClient()
        resp = await client.get("https://api.example.com/test")

        assert resp.size_bytes > 0

    @respx.mock
    async def test_non_json_response(self):
        """Non-JSON response is returned as text."""
        respx.get("https://api.example.com/test").mock(
            return_value=Response(200, text="Hello, World!")
        )

        client = HttpClient()
        resp = await client.get("https://api.example.com/test")

        assert resp.body == "Hello, World!"


class TestHttpClientErrors:
    """Tests for error handling."""

    @respx.mock
    async def test_connection_error(self):
        """Connection error raises NetworkError."""
        import httpx
        respx.get("https://api.example.com/test").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        client = HttpClient()
        with pytest.raises(NetworkError) as exc_info:
            await client.get("https://api.example.com/test")

        assert "Connection failed" in str(exc_info.value)

    @respx.mock
    async def test_timeout_error(self):
        """Timeout raises NetworkError."""
        import httpx
        respx.get("https://api.example.com/test").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )

        client = HttpClient()
        with pytest.raises(NetworkError) as exc_info:
            await client.get("https://api.example.com/test")

        assert "timed out" in str(exc_info.value).lower()


class TestHttpClientSend:
    """Tests for the low-level send method."""

    @respx.mock
    async def test_send_request(self):
        """send() executes HttpRequest."""
        respx.get("https://api.example.com/test").mock(
            return_value=Response(200, json={"ok": True})
        )

        client = HttpClient()
        request = HttpRequest(method="GET", url="https://api.example.com/test")
        resp = await client.send(request)

        assert resp.status_code == 200
        assert resp.body == {"ok": True}

    @respx.mock
    async def test_send_with_dict_body(self):
        """send() JSON-encodes dict body."""
        respx.post("https://api.example.com/test").mock(
            return_value=Response(200, json={})
        )

        client = HttpClient()
        request = HttpRequest(
            method="POST",
            url="https://api.example.com/test",
            body={"key": "value"},
        )
        await client.send(request)

        req = respx.calls.last.request
        assert req.headers["Content-Type"] == "application/json"

    @respx.mock
    async def test_send_with_string_body(self):
        """send() sends string body as-is."""
        respx.post("https://api.example.com/test").mock(
            return_value=Response(200, json={})
        )

        client = HttpClient()
        request = HttpRequest(
            method="POST",
            url="https://api.example.com/test",
            body="raw string data",
        )
        await client.send(request)

        req = respx.calls.last.request
        assert req.content == b"raw string data"
