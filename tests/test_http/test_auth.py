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
        """ApiKeyAuth uses X-API-Key by default."""
        auth = ApiKeyAuth("my-api-key")
        headers = {}
        auth.apply(headers)
        assert headers["X-API-Key"] == "my-api-key"

    def test_custom_header_name(self):
        """ApiKeyAuth uses custom header name."""
        auth = ApiKeyAuth("my-api-key", header_name="X-Custom-Auth")
        headers = {}
        auth.apply(headers)
        assert "X-API-Key" not in headers
        assert headers["X-Custom-Auth"] == "my-api-key"


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
        """get_auth creates ApiKeyAuth with custom header."""
        config = AuthConfig(
            type="apikey",
            credentials={"key": "my-key", "header": "Authorization"},
        )
        auth = get_auth(config)

        headers = {}
        auth.apply(headers)
        assert headers["Authorization"] == "my-key"

    def test_missing_credentials(self):
        """get_auth handles missing credentials gracefully."""
        config = AuthConfig(type="bearer", credentials={})
        auth = get_auth(config)

        headers = {}
        auth.apply(headers)
        # Should work but with empty token
        assert headers["Authorization"] == "Bearer "
