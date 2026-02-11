"""Tests for secrets storage module."""

import pytest

from vagrant.storage.secrets import (
    SERVICE_NAME,
    SecretStorage,
    is_secret_variable,
)


class TestIsSecretVariable:
    """Tests for is_secret_variable function."""

    def test_secret_prefix(self):
        """Variables starting with secret_ are secrets."""
        assert is_secret_variable("secret_api_key") is True
        assert is_secret_variable("secret_token") is True
        assert is_secret_variable("secret_") is True

    def test_non_secret_prefix(self):
        """Variables not starting with secret_ are not secrets."""
        assert is_secret_variable("api_key") is False
        assert is_secret_variable("token") is False
        assert is_secret_variable("SECRET_KEY") is False  # Case sensitive
        assert is_secret_variable("my_secret_value") is False
        assert is_secret_variable("") is False


class TestSecretStorage:
    """Tests for SecretStorage class."""

    def test_init_default_service_name(self):
        """Storage uses default service name."""
        storage = SecretStorage()
        assert storage.service_name == SERVICE_NAME

    def test_init_custom_service_name(self):
        """Storage accepts custom service name."""
        storage = SecretStorage(service_name="test-service")
        assert storage.service_name == "test-service"

    def test_make_key(self):
        """Key format is environment:name."""
        storage = SecretStorage()
        assert storage._make_key("prod", "secret_token") == "prod:secret_token"
        assert storage._make_key("dev", "api_key") == "dev:api_key"

    def test_is_available_returns_bool(self):
        """is_available returns a boolean."""
        result = SecretStorage.is_available()
        assert isinstance(result, bool)


class TestSecretStorageWithMock:
    """Tests for SecretStorage with mocked keyring.
    
    These tests mock the keyring module to test the storage logic
    without requiring actual system keychain access.
    """

    @pytest.fixture
    def mock_keyring(self, monkeypatch):
        """Mock keyring module."""
        stored = {}

        def mock_get_password(service, key):
            return stored.get(f"{service}:{key}")

        def mock_set_password(service, key, value):
            stored[f"{service}:{key}"] = value

        def mock_delete_password(service, key):
            stored_key = f"{service}:{key}"
            if stored_key in stored:
                del stored[stored_key]
            else:
                from keyring.errors import PasswordDeleteError
                raise PasswordDeleteError()

        # Import keyring and patch it
        import vagrant.storage.secrets as secrets_module
        monkeypatch.setattr(secrets_module, "KEYRING_AVAILABLE", True)

        import keyring
        monkeypatch.setattr(keyring, "get_password", mock_get_password)
        monkeypatch.setattr(keyring, "set_password", mock_set_password)
        monkeypatch.setattr(keyring, "delete_password", mock_delete_password)

        return stored

    def test_set_and_get(self, mock_keyring):
        """Can store and retrieve a secret."""
        storage = SecretStorage()

        result = storage.set("production", "secret_token", "my-secret-value")
        assert result is True

        value = storage.get("production", "secret_token")
        assert value == "my-secret-value"

    def test_get_nonexistent(self, mock_keyring):
        """Getting nonexistent secret returns None."""
        storage = SecretStorage()
        value = storage.get("production", "nonexistent")
        assert value is None

    def test_delete_existing(self, mock_keyring):
        """Can delete an existing secret."""
        storage = SecretStorage()
        storage.set("production", "secret_key", "value")

        result = storage.delete("production", "secret_key")
        assert result is True

        # Verify it's gone
        value = storage.get("production", "secret_key")
        assert value is None

    def test_delete_nonexistent(self, mock_keyring):
        """Deleting nonexistent secret returns False."""
        storage = SecretStorage()
        result = storage.delete("production", "nonexistent")
        assert result is False

    def test_delete_environment(self, mock_keyring):
        """Can delete all secrets for an environment."""
        storage = SecretStorage()

        # Store multiple secrets
        storage.set("staging", "secret_a", "value_a")
        storage.set("staging", "secret_b", "value_b")
        storage.set("staging", "secret_c", "value_c")

        # Delete all
        deleted = storage.delete_environment("staging", ["secret_a", "secret_b", "secret_c"])
        assert deleted == 3

        # Verify they're gone
        assert storage.get("staging", "secret_a") is None
        assert storage.get("staging", "secret_b") is None
        assert storage.get("staging", "secret_c") is None

    def test_delete_environment_partial(self, mock_keyring):
        """delete_environment handles partial deletion."""
        storage = SecretStorage()

        # Store only one
        storage.set("staging", "secret_a", "value_a")

        # Try to delete three (two don't exist)
        deleted = storage.delete_environment("staging", ["secret_a", "secret_b", "secret_c"])
        assert deleted == 1


class TestSecretStorageUnavailable:
    """Tests for when keyring is not available."""

    @pytest.fixture
    def disable_keyring(self, monkeypatch):
        """Disable keyring module."""
        import vagrant.storage.secrets as secrets_module
        monkeypatch.setattr(secrets_module, "KEYRING_AVAILABLE", False)

    def test_get_returns_none(self, disable_keyring):
        """get returns None when keyring unavailable."""
        storage = SecretStorage()
        assert storage.get("env", "key") is None

    def test_set_returns_false(self, disable_keyring):
        """set returns False when keyring unavailable."""
        storage = SecretStorage()
        assert storage.set("env", "key", "value") is False

    def test_delete_returns_false(self, disable_keyring):
        """delete returns False when keyring unavailable."""
        storage = SecretStorage()
        assert storage.delete("env", "key") is False
