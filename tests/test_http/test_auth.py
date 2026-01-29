"""Tests for authentication handlers."""

import base64

from vagrant.http.auth import (
    ApiKeyAuth,
    AuthConfig,
    BasicAuth,
    BearerAuth,
    get_auth,
)


class TestBearerAuth:
    """Tests for BearerAuth handler."""

    def test_apply_adds_header(self):
        """BearerAuth adds Authorization header."""
        auth = BearerAuth("my-secret-token")
        headers = {}
        auth.apply(headers)
        assert headers["Authorization"] == "Bearer my-secret-token"

    def test_apply_overwrites_existing(self):
        """BearerAuth overwrites existing Authorization."""
        auth = BearerAuth("new-token")
        headers = {"Authorization": "old-value"}
        auth.apply(headers)
        assert headers["Authorization"] == "Bearer new-token"


class TestBasicAuth:
    """Tests for BasicAuth handler."""

    def test_apply_adds_header(self):
        """BasicAuth adds Authorization header."""
        auth = BasicAuth("user", "pass")
        headers = {}
        auth.apply(headers)

        # Decode and verify
        assert headers["Authorization"].startswith("Basic ")
        encoded = headers["Authorization"].split(" ")[1]
        decoded = base64.b64decode(encoded).decode()
        assert decoded == "user:pass"

    def test_handles_special_characters(self):
        """BasicAuth handles special characters in credentials."""
        auth = BasicAuth("user@example.com", "p@ss:word!")
        headers = {}
        auth.apply(headers)

        encoded = headers["Authorization"].split(" ")[1]
        decoded = base64.b64decode(encoded).decode()
        assert decoded == "user@example.com:p@ss:word!"


class TestApiKeyAuth:
    """Tests for ApiKeyAuth handler."""

    def test_default_header_name(self):
        """ApiKeyAuth uses X-API-Key header by default."""
        auth = ApiKeyAuth("my-api-key")
        headers = {}
        auth.apply(headers)
        assert headers["X-API-Key"] == "my-api-key"

    def test_custom_header_name(self):
        """ApiKeyAuth uses custom header name."""
        auth = ApiKeyAuth("my-api-key", name="X-Custom-Auth")
        headers = {}
        auth.apply(headers)
        assert "X-API-Key" not in headers
        assert headers["X-Custom-Auth"] == "my-api-key"

    def test_query_parameter_location(self):
        """ApiKeyAuth can add key as query parameter."""
        auth = ApiKeyAuth("my-api-key", name="api_key", location="query")
        headers = {}
        params = {}
        auth.apply(headers, params)
        assert "api_key" not in headers
        assert params["api_key"] == "my-api-key"

    def test_header_location_explicit(self):
        """ApiKeyAuth with explicit header location."""
        auth = ApiKeyAuth("my-api-key", name="Authorization", location="header")
        headers = {}
        params = {}
        auth.apply(headers, params)
        assert headers["Authorization"] == "my-api-key"
        assert "Authorization" not in params

    def test_query_with_none_params(self):
        """ApiKeyAuth handles None params gracefully for query location."""
        auth = ApiKeyAuth("my-api-key", name="api_key", location="query")
        headers = {}
        auth.apply(headers, None)
        # Should not crash, just doesn't add the key
        assert "api_key" not in headers


class TestGetAuth:
    """Tests for get_auth factory function."""

    def test_bearer_auth(self):
        """get_auth creates BearerAuth."""
        config = AuthConfig(type="bearer", credentials={"token": "test-token"})
        auth = get_auth(config)

        headers = {}
        auth.apply(headers)
        assert "Bearer test-token" in headers["Authorization"]

    def test_basic_auth(self):
        """get_auth creates BasicAuth."""
        config = AuthConfig(
            type="basic",
            credentials={"username": "user", "password": "pass"},
        )
        auth = get_auth(config)

        headers = {}
        auth.apply(headers)
        assert headers["Authorization"].startswith("Basic ")

    def test_apikey_auth(self):
        """get_auth creates ApiKeyAuth."""
        config = AuthConfig(type="apikey", credentials={"key": "my-key"})
        auth = get_auth(config)

        headers = {}
        auth.apply(headers)
        assert headers["X-API-Key"] == "my-key"

    def test_apikey_auth_custom_header(self):
        """get_auth creates ApiKeyAuth with custom header using legacy 'header' key."""
        config = AuthConfig(
            type="apikey",
            credentials={"key": "my-key", "header": "Authorization"},
        )
        auth = get_auth(config)

        headers = {}
        auth.apply(headers)
        assert headers["Authorization"] == "my-key"

    def test_apikey_auth_with_name(self):
        """get_auth creates ApiKeyAuth with 'name' key."""
        config = AuthConfig(
            type="apikey",
            credentials={"key": "my-key", "name": "X-Custom-Key"},
        )
        auth = get_auth(config)

        headers = {}
        auth.apply(headers)
        assert headers["X-Custom-Key"] == "my-key"

    def test_apikey_auth_query_location(self):
        """get_auth creates ApiKeyAuth with query location."""
        config = AuthConfig(
            type="apikey",
            credentials={"key": "my-key", "name": "api_key", "location": "query"},
        )
        auth = get_auth(config)

        headers = {}
        params = {}
        auth.apply(headers, params)
        assert "api_key" not in headers
        assert params["api_key"] == "my-key"

    def test_apikey_auth_invalid_location_defaults_to_header(self):
        """get_auth defaults to header for invalid location."""
        config = AuthConfig(
            type="apikey",
            credentials={"key": "my-key", "location": "invalid"},
        )
        auth = get_auth(config)

        headers = {}
        params = {}
        auth.apply(headers, params)
        assert headers["X-API-Key"] == "my-key"
        assert "X-API-Key" not in params

    def test_missing_credentials(self):
        """get_auth handles missing credentials gracefully."""
        config = AuthConfig(type="bearer", credentials={})
        auth = get_auth(config)

        headers = {}
        auth.apply(headers)
        # Should work but with empty token
        assert headers["Authorization"] == "Bearer "
