"""Secure secret storage using system keychain.

Provides abstraction over system keychains (macOS Keychain, Windows Credential
Manager, Linux Secret Service) via the keyring library.
"""

from __future__ import annotations

import logging

try:
    import keyring
    from keyring.errors import KeyringError
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    KeyringError = Exception  # type: ignore

logger = logging.getLogger(__name__)

# Service name used for all Vagrant secrets in keychain
SERVICE_NAME = "vagrant"


class SecretStorage:
    """Secure storage for secrets using system keychain.
    
    Uses the system's native credential storage:
    - macOS: Keychain
    - Windows: Credential Manager
    - Linux: Secret Service (GNOME Keyring, KWallet, etc.)
    
    Secrets are stored with a service name of "vagrant" and the
    key format: "{environment}:{variable_name}"
    """

    def __init__(self, service_name: str = SERVICE_NAME) -> None:
        """Initialize secret storage.
        
        Args:
            service_name: Service identifier in keychain (default: "vagrant").
        """
        self.service_name = service_name

    @staticmethod
    def is_available() -> bool:
        """Check if keychain storage is available.
        
        Returns:
            True if keyring library is installed and a backend is available.
        """
        if not KEYRING_AVAILABLE:
            return False

        try:
            # Try to get the current backend - this will fail if none available
            backend = keyring.get_keyring()
            # Check it's not the fail backend
            return "fail" not in backend.__class__.__name__.lower()
        except Exception:
            return False

    def _make_key(self, environment: str, name: str) -> str:
        """Create keychain key from environment and variable name.
        
        Args:
            environment: Environment name.
            name: Variable name (with or without secret_ prefix).
            
        Returns:
            Key in format "environment:name".
        """
        return f"{environment}:{name}"

    def get(self, environment: str, name: str) -> str | None:
        """Retrieve a secret from keychain.
        
        Args:
            environment: Environment name.
            name: Secret variable name.
            
        Returns:
            Secret value or None if not found.
        """
        if not KEYRING_AVAILABLE:
            logger.warning("Keyring not available, cannot retrieve secret")
            return None

        key = self._make_key(environment, name)

        try:
            return keyring.get_password(self.service_name, key)
        except KeyringError as e:
            logger.warning(f"Failed to retrieve secret from keychain: {e}")
            return None

    def set(self, environment: str, name: str, value: str) -> bool:
        """Store a secret in keychain.
        
        Args:
            environment: Environment name.
            name: Secret variable name.
            value: Secret value to store.
            
        Returns:
            True if stored successfully, False otherwise.
        """
        if not KEYRING_AVAILABLE:
            logger.warning("Keyring not available, cannot store secret")
            return False

        key = self._make_key(environment, name)

        try:
            keyring.set_password(self.service_name, key, value)
            return True
        except KeyringError as e:
            logger.warning(f"Failed to store secret in keychain: {e}")
            return False

    def delete(self, environment: str, name: str) -> bool:
        """Delete a secret from keychain.
        
        Args:
            environment: Environment name.
            name: Secret variable name.
            
        Returns:
            True if deleted successfully, False otherwise.
        """
        if not KEYRING_AVAILABLE:
            logger.warning("Keyring not available, cannot delete secret")
            return False

        key = self._make_key(environment, name)

        try:
            keyring.delete_password(self.service_name, key)
            return True
        except KeyringError as e:
            # May fail if secret doesn't exist, which is fine
            logger.debug(f"Failed to delete secret from keychain: {e}")
            return False

    def delete_environment(self, environment: str, secret_names: list[str]) -> int:
        """Delete all secrets for an environment.
        
        Args:
            environment: Environment name.
            secret_names: List of secret variable names to delete.
            
        Returns:
            Number of secrets deleted.
        """
        deleted = 0
        for name in secret_names:
            if self.delete(environment, name):
                deleted += 1
        return deleted


def is_secret_variable(name: str) -> bool:
    """Check if a variable name is a secret (prefixed with secret_).
    
    Args:
        name: Variable name.
        
    Returns:
        True if name starts with "secret_".
    """
    return name.startswith("secret_")
