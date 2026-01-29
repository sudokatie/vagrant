"""Environment management for API configurations."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from vagrant.core.config import get_config_dir, load_config
from vagrant.http.auth import AuthConfig
from vagrant.storage.secrets import SecretStorage, is_secret_variable


# Placeholder stored in YAML when secret is in keychain
KEYCHAIN_PLACEHOLDER = "{{keychain}}"


@dataclass
class Environment:
    """API environment configuration.
    
    Attributes:
        name: Environment name (used as filename).
        base_url: Base URL for API requests.
        auth: Authentication configuration, if any.
        variables: Custom variables for substitution.
    """

    name: str
    base_url: str = ""
    auth: AuthConfig | None = None
    variables: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data: dict[str, Any] = {
            "name": self.name,
            "base_url": self.base_url,
            "variables": self.variables,
        }
        if self.auth:
            data["auth"] = {
                "type": self.auth.type,
                "credentials": self.auth.credentials,
            }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Environment:
        """Create from dictionary."""
        auth = None
        if "auth" in data and data["auth"]:
            auth = AuthConfig(
                type=data["auth"].get("type", "bearer"),
                credentials=data["auth"].get("credentials", {}),
            )

        return cls(
            name=data.get("name", ""),
            base_url=data.get("base_url", ""),
            auth=auth,
            variables=data.get("variables", {}),
        )


class EnvironmentManager:
    """Manage environment configurations.
    
    Environments are stored as YAML files in ~/.config/vagrant/environments/
    When use_keychain is enabled, secret_ prefixed variables are stored in
    the system keychain instead of plain text in YAML files.
    """

    # Pattern for variable substitution: {{variable}} or {{env.VAR}} or {{response.path}}
    VAR_PATTERN = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")

    def __init__(
        self,
        config_dir: Path | None = None,
        use_keychain: bool | None = None,
    ) -> None:
        """Initialize environment manager.
        
        Args:
            config_dir: Config directory. Defaults to ~/.config/vagrant/
            use_keychain: Override keychain setting. If None, uses config.
        """
        if config_dir is None:
            config_dir = get_config_dir()

        self.env_dir = config_dir / "environments"
        self.env_dir.mkdir(parents=True, exist_ok=True)
        
        # Store last response for {{response.field.path}} substitution
        self._last_response: dict[str, Any] | None = None
        
        # Initialize secret storage
        self._secret_storage = SecretStorage()
        
        # Determine if keychain should be used
        if use_keychain is not None:
            self._use_keychain = use_keychain
        else:
            try:
                config = load_config()
                self._use_keychain = config.use_keychain
            except Exception:
                self._use_keychain = False
        
        # Only use keychain if it's enabled AND available
        if self._use_keychain and not SecretStorage.is_available():
            self._use_keychain = False
    
    def set_last_response(self, response_body: Any) -> None:
        """Store the last response body for variable substitution.
        
        Args:
            response_body: The response body (usually a dict or list).
        """
        if isinstance(response_body, dict):
            self._last_response = response_body
        else:
            self._last_response = None
    
    def _get_response_value(self, path: str) -> str | None:
        """Get a value from the last response using dot notation.
        
        Args:
            path: Dot-separated path like "data.user.id" or "items.0.name"
            
        Returns:
            The value as a string, or None if not found.
        """
        if self._last_response is None:
            return None
        
        parts = path.split(".")
        current: Any = self._last_response
        
        for part in parts:
            if current is None:
                return None
            
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                # Try to parse as integer index
                try:
                    index = int(part)
                    if 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None
                except ValueError:
                    return None
            else:
                return None
        
        # Convert final value to string
        if current is None:
            return None
        return str(current)

    def list(self) -> list[str]:
        """List all environment names.
        
        Returns:
            List of environment names (without .yaml extension).
        """
        names = []
        for path in self.env_dir.glob("*.yaml"):
            names.append(path.stem)
        for path in self.env_dir.glob("*.yml"):
            if path.stem not in names:
                names.append(path.stem)
        return sorted(names)

    def get(self, name: str) -> Environment:
        """Load environment by name.
        
        If keychain is enabled, secret_ variables are fetched from system
        keychain rather than the YAML file.
        
        Args:
            name: Environment name.
            
        Returns:
            Loaded environment.
            
        Raises:
            FileNotFoundError: If environment doesn't exist.
        """
        # Try .yaml first, then .yml
        yaml_path = self.env_dir / f"{name}.yaml"
        yml_path = self.env_dir / f"{name}.yml"

        if yaml_path.exists():
            path = yaml_path
        elif yml_path.exists():
            path = yml_path
        else:
            raise FileNotFoundError(f"Environment not found: {name}")

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        # Ensure name is set
        data["name"] = name

        env = Environment.from_dict(data)
        
        # If keychain enabled, fetch secret_ variables from keychain
        if self._use_keychain:
            for var_name, var_value in list(env.variables.items()):
                if is_secret_variable(var_name):
                    # Value is placeholder, fetch real value from keychain
                    if var_value == KEYCHAIN_PLACEHOLDER:
                        secret_value = self._secret_storage.get(name, var_name)
                        if secret_value is not None:
                            env.variables[var_name] = secret_value
                        else:
                            # Secret not found in keychain, remove from dict
                            del env.variables[var_name]
        
        return env

    def save(self, env: Environment) -> None:
        """Save environment to file.
        
        If keychain is enabled, secret_ variables are stored in system
        keychain and replaced with a placeholder in the YAML file.
        
        Args:
            env: Environment to save.
        """
        path = self.env_dir / f"{env.name}.yaml"
        
        # Create a copy of the environment for serialization
        data = env.to_dict()
        
        # If keychain enabled, store secrets separately
        if self._use_keychain:
            for var_name, var_value in list(data["variables"].items()):
                if is_secret_variable(var_name) and var_value != KEYCHAIN_PLACEHOLDER:
                    # Store in keychain
                    if self._secret_storage.set(env.name, var_name, var_value):
                        # Replace with placeholder in YAML
                        data["variables"][var_name] = KEYCHAIN_PLACEHOLDER

        with open(path, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False)

    def delete(self, name: str) -> None:
        """Delete environment.
        
        If keychain is enabled, also deletes any secrets stored in keychain.
        
        Args:
            name: Environment name to delete.
            
        Raises:
            FileNotFoundError: If environment doesn't exist.
        """
        yaml_path = self.env_dir / f"{name}.yaml"
        yml_path = self.env_dir / f"{name}.yml"

        # Get environment first to find secret variable names
        if self._use_keychain:
            try:
                env = self.get(name)
                secret_names = [
                    var_name for var_name in env.variables
                    if is_secret_variable(var_name)
                ]
                self._secret_storage.delete_environment(name, secret_names)
            except FileNotFoundError:
                pass  # Will raise below

        if yaml_path.exists():
            yaml_path.unlink()
        elif yml_path.exists():
            yml_path.unlink()
        else:
            raise FileNotFoundError(f"Environment not found: {name}")

    def exists(self, name: str) -> bool:
        """Check if environment exists.
        
        Args:
            name: Environment name.
            
        Returns:
            True if environment exists.
        """
        yaml_path = self.env_dir / f"{name}.yaml"
        yml_path = self.env_dir / f"{name}.yml"
        return yaml_path.exists() or yml_path.exists()

    def substitute(self, text: str, env: Environment) -> str:
        """Substitute variables in text.
        
        Supports:
        - {{variable}} - from env.variables
        - {{env.VAR}} - from OS environment variables
        - {{base_url}} - environment's base URL
        - {{response.field.path}} - from last response body
        
        Args:
            text: Text with {{variable}} placeholders.
            env: Environment to use for substitution.
            
        Returns:
            Text with variables substituted.
        """
        def replace(match: re.Match) -> str:
            key = match.group(1).strip()

            # Check for env.VAR pattern
            if key.startswith("env."):
                env_var = key[4:]
                return os.environ.get(env_var, match.group(0))

            # Check for response.field.path pattern
            if key.startswith("response."):
                response_path = key[9:]  # Remove "response." prefix
                value = self._get_response_value(response_path)
                if value is not None:
                    return value
                return match.group(0)

            # Check for base_url
            if key == "base_url":
                return env.base_url

            # Check environment variables
            if key in env.variables:
                return env.variables[key]

            # Return original if not found
            return match.group(0)

        return self.VAR_PATTERN.sub(replace, text)

    def substitute_all(
        self,
        data: dict[str, Any],
        env: Environment,
    ) -> dict[str, Any]:
        """Substitute variables in all string values of a dict.
        
        Args:
            data: Dictionary with potential variable placeholders.
            env: Environment to use for substitution.
            
        Returns:
            Dictionary with variables substituted.
        """
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.substitute(value, env)
            elif isinstance(value, dict):
                result[key] = self.substitute_all(value, env)
            else:
                result[key] = value
        return result
