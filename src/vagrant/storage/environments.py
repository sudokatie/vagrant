"""Environment management for API configurations."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from vagrant.core.config import get_config_dir
from vagrant.http.auth import AuthConfig


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
    """

    # Pattern for variable substitution: {{variable}} or {{env.VAR}}
    VAR_PATTERN = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")

    def __init__(self, config_dir: Path | None = None) -> None:
        """Initialize environment manager.
        
        Args:
            config_dir: Config directory. Defaults to ~/.config/vagrant/
        """
        if config_dir is None:
            config_dir = get_config_dir()

        self.env_dir = config_dir / "environments"
        self.env_dir.mkdir(parents=True, exist_ok=True)

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

        return Environment.from_dict(data)

    def save(self, env: Environment) -> None:
        """Save environment to file.
        
        Args:
            env: Environment to save.
        """
        path = self.env_dir / f"{env.name}.yaml"

        with open(path, "w") as f:
            yaml.safe_dump(env.to_dict(), f, default_flow_style=False)

    def delete(self, name: str) -> None:
        """Delete environment.
        
        Args:
            name: Environment name to delete.
            
        Raises:
            FileNotFoundError: If environment doesn't exist.
        """
        yaml_path = self.env_dir / f"{name}.yaml"
        yml_path = self.env_dir / f"{name}.yml"

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
