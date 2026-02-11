"""HTTP client module for making API requests."""

from vagrant.http.auth import ApiKeyAuth, AuthConfig, BasicAuth, BearerAuth, get_auth
from vagrant.http.chaining import (
    ChainContext,
    ExtractRule,
    extract_from_response,
    extract_value,
    find_variables,
    has_unresolved_variables,
    interpolate_dict,
    interpolate_list,
    interpolate_string,
)
from vagrant.http.client import HttpClient, HttpRequest, HttpResponse

__all__ = [
    "HttpClient",
    "HttpRequest",
    "HttpResponse",
    "AuthConfig",
    "BearerAuth",
    "BasicAuth",
    "ApiKeyAuth",
    "get_auth",
    # Chaining
    "ChainContext",
    "ExtractRule",
    "extract_value",
    "extract_from_response",
    "interpolate_string",
    "interpolate_dict",
    "interpolate_list",
    "find_variables",
    "has_unresolved_variables",
]
