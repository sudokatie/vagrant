"""Tests for error classes."""

import pytest

from vagrant.core.errors import (
    VagrantError,
    SpecParseError,
    NetworkError,
    AuthError,
    ConfigError,
)


class TestVagrantError:
    """Tests for base VagrantError."""

    def test_message_only(self):
        """Error with just a message."""
        err = VagrantError("Something went wrong")
        assert err.message == "Something went wrong"
        assert err.details is None
        assert str(err) == "Something went wrong"

    def test_message_and_details(self):
        """Error with message and details."""
        err = VagrantError("Failed", "check your input")
        assert err.message == "Failed"
        assert err.details == "check your input"
        assert str(err) == "Failed: check your input"

    def test_repr(self):
        """Error has useful repr."""
        err = VagrantError("Test", "details")
        assert "VagrantError" in repr(err)
        assert "Test" in repr(err)
        assert "details" in repr(err)

    def test_is_exception(self):
        """VagrantError is a proper exception."""
        with pytest.raises(VagrantError):
            raise VagrantError("test")


class TestSpecParseError:
    """Tests for SpecParseError."""

    def test_inherits_from_vagrant_error(self):
        """SpecParseError is a VagrantError."""
        err = SpecParseError("Invalid YAML")
        assert isinstance(err, VagrantError)

    def test_message_only(self):
        """Parse error with just message."""
        err = SpecParseError("Invalid YAML")
        assert err.message == "Invalid YAML"
        assert err.file_path is None
        assert err.line is None

    def test_with_file_path(self):
        """Parse error with file path."""
        err = SpecParseError("Missing field", file_path="spec.yaml")
        assert err.file_path == "spec.yaml"
        assert "spec.yaml" in str(err)

    def test_with_file_and_line(self):
        """Parse error with file and line."""
        err = SpecParseError("Syntax error", file_path="api.yaml", line=42)
        assert err.file_path == "api.yaml"
        assert err.line == 42
        assert "api.yaml" in str(err)
        assert "42" in str(err)


class TestNetworkError:
    """Tests for NetworkError."""

    def test_inherits_from_vagrant_error(self):
        """NetworkError is a VagrantError."""
        err = NetworkError("Connection refused")
        assert isinstance(err, VagrantError)

    def test_message_only(self):
        """Network error with just message."""
        err = NetworkError("Timeout")
        assert err.message == "Timeout"
        assert err.url is None
        assert err.status_code is None

    def test_with_url(self):
        """Network error with URL."""
        err = NetworkError("Failed", url="https://api.example.com")
        assert err.url == "https://api.example.com"
        assert "api.example.com" in str(err)

    def test_with_url_and_status(self):
        """Network error with URL and status code."""
        err = NetworkError("Failed", url="https://api.example.com", status_code=500)
        assert err.url == "https://api.example.com"
        assert err.status_code == 500
        assert "500" in str(err)


class TestAuthError:
    """Tests for AuthError."""

    def test_inherits_from_vagrant_error(self):
        """AuthError is a VagrantError."""
        err = AuthError("Invalid token")
        assert isinstance(err, VagrantError)

    def test_message_only(self):
        """Auth error with just message."""
        err = AuthError("Unauthorized")
        assert err.message == "Unauthorized"
        assert err.auth_type is None

    def test_with_auth_type(self):
        """Auth error with auth type."""
        err = AuthError("Token expired", auth_type="bearer")
        assert err.auth_type == "bearer"
        assert "bearer" in str(err)


class TestConfigError:
    """Tests for ConfigError."""

    def test_inherits_from_vagrant_error(self):
        """ConfigError is a VagrantError."""
        err = ConfigError("Invalid config")
        assert isinstance(err, VagrantError)

    def test_message_only(self):
        """Config error with just message."""
        err = ConfigError("File not found")
        assert err.message == "File not found"
        assert err.config_key is None

    def test_with_config_key(self):
        """Config error with config key."""
        err = ConfigError("Invalid value", config_key="timeout")
        assert err.config_key == "timeout"
        assert "timeout" in str(err)


class TestErrorHierarchy:
    """Test that all errors can be caught as VagrantError."""

    def test_catch_all_as_vagrant_error(self):
        """All error types caught by VagrantError."""
        errors = [
            SpecParseError("test"),
            NetworkError("test"),
            AuthError("test"),
            ConfigError("test"),
        ]
        
        for err in errors:
            try:
                raise err
            except VagrantError as caught:
                assert caught is err
