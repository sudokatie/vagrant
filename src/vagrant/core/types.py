"""Shared type definitions for Vagrant.

These type aliases provide consistent typing across the codebase
and serve as documentation for valid values.
"""

from typing import Literal

# HTTP methods supported by Vagrant
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]

# Where parameters can appear in OpenAPI specs
ParamLocation = Literal["path", "query", "header", "cookie"]

# Authentication types Vagrant supports
AuthType = Literal["bearer", "basic", "apikey"]

# Output formats for CLI commands
OutputFormat = Literal["json", "yaml", "raw"]

# Theme options
Theme = Literal["dark", "light", "auto"]
