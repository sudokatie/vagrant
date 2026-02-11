"""Parser module for API specifications."""

from vagrant.parser.models import (
    ApiSpec,
    Operation,
    Parameter,
    RequestBody,
    Response,
    Schema,
    Server,
)
from vagrant.parser.openapi import OpenAPIParser, parse_spec
from vagrant.parser.graphql import (
    GraphQLArg,
    GraphQLDirective,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputField,
    GraphQLOperation,
    GraphQLParser,
    GraphQLSpec,
    GraphQLType,
    GraphQLTypeRef,
    build_query,
)

__all__ = [
    # Models
    "ApiSpec",
    "Server",
    "Operation",
    "Parameter",
    "RequestBody",
    "Response",
    "Schema",
    # OpenAPI Parser
    "OpenAPIParser",
    "parse_spec",
    # GraphQL Models
    "GraphQLArg",
    "GraphQLDirective",
    "GraphQLEnumValue",
    "GraphQLField",
    "GraphQLInputField",
    "GraphQLOperation",
    "GraphQLSpec",
    "GraphQLType",
    "GraphQLTypeRef",
    # GraphQL Parser
    "GraphQLParser",
    "build_query",
]
