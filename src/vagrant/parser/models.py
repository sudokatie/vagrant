"""Data models for API specifications.

All models are frozen (immutable) dataclasses for safety and hashability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vagrant.core.types import HttpMethod, ParamLocation


@dataclass(frozen=True)
class Schema:
    """JSON Schema definition.
    
    Represents the schema for request/response bodies and parameters.
    Supports nested schemas for objects and arrays.
    
    Attributes:
        type: JSON Schema type (string, integer, number, boolean, array, object).
        format: Optional format hint (date, date-time, email, uuid, etc.).
        properties: For object types, mapping of property names to schemas.
        items: For array types, schema of array items.
        required: List of required property names for objects.
        enum: List of allowed values.
        default: Default value if not provided.
        description: Human-readable description.
        nullable: Whether null is an allowed value.
    """

    type: str = "string"
    format: str | None = None
    properties: dict[str, Schema] | None = None
    items: Schema | None = None
    required: tuple[str, ...] = ()
    enum: tuple[Any, ...] | None = None
    default: Any = None
    description: str | None = None
    nullable: bool = False

    @classmethod
    def string(cls, format: str | None = None) -> Schema:
        """Create a string schema."""
        return cls(type="string", format=format)

    @classmethod
    def integer(cls, format: str | None = None) -> Schema:
        """Create an integer schema."""
        return cls(type="integer", format=format)

    @classmethod
    def number(cls, format: str | None = None) -> Schema:
        """Create a number schema."""
        return cls(type="number", format=format)

    @classmethod
    def boolean(cls) -> Schema:
        """Create a boolean schema."""
        return cls(type="boolean")

    @classmethod
    def array(cls, items: Schema) -> Schema:
        """Create an array schema with given item type."""
        return cls(type="array", items=items)

    @classmethod
    def object(
        cls,
        properties: dict[str, Schema] | None = None,
        required: tuple[str, ...] = (),
    ) -> Schema:
        """Create an object schema."""
        return cls(type="object", properties=properties, required=required)


@dataclass(frozen=True)
class Parameter:
    """API parameter definition.
    
    Attributes:
        name: Parameter name as it appears in the request.
        location: Where the parameter appears (path, query, header, cookie).
        required: Whether the parameter is required.
        schema: Schema defining the parameter's type.
        description: Human-readable description.
        example: Example value for documentation.
    """

    name: str
    location: ParamLocation
    required: bool = False
    schema: Schema = field(default_factory=Schema.string)
    description: str | None = None
    example: Any = None


@dataclass(frozen=True)
class RequestBody:
    """Request body definition.
    
    Attributes:
        content_type: Media type (usually application/json).
        schema: Schema defining the body structure.
        required: Whether the body is required.
        description: Human-readable description.
    """

    content_type: str = "application/json"
    schema: Schema = field(default_factory=Schema.object)
    required: bool = False
    description: str | None = None


@dataclass(frozen=True)
class Response:
    """API response definition.
    
    Attributes:
        status_code: HTTP status code as string (e.g., "200", "404").
        description: Human-readable description.
        schema: Schema defining the response body, if any.
        content_type: Media type of the response.
    """

    status_code: str
    description: str = ""
    schema: Schema | None = None
    content_type: str = "application/json"


@dataclass(frozen=True)
class Operation:
    """API operation (endpoint).
    
    Represents a single API operation - the combination of an HTTP method
    and path (e.g., GET /users/{id}).
    
    Attributes:
        method: HTTP method (GET, POST, etc.).
        path: URL path with parameter placeholders.
        operation_id: Unique identifier for the operation.
        summary: Short description.
        description: Detailed description.
        tags: Categorization tags.
        parameters: Parameters for this operation.
        request_body: Request body definition, if any.
        responses: Mapping of status codes to response definitions.
        deprecated: Whether this operation is deprecated.
    """

    method: HttpMethod
    path: str
    operation_id: str | None = None
    summary: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()
    parameters: tuple[Parameter, ...] = ()
    request_body: RequestBody | None = None
    responses: dict[str, Response] = field(default_factory=dict)
    deprecated: bool = False

    @property
    def display_name(self) -> str:
        """Human-friendly name for the operation."""
        if self.summary:
            return self.summary
        if self.operation_id:
            return self.operation_id
        return f"{self.method} {self.path}"


@dataclass(frozen=True)
class Server:
    """API server definition.
    
    Attributes:
        url: Base URL for API requests.
        description: Human-readable description.
    """

    url: str
    description: str | None = None


@dataclass(frozen=True)
class ApiSpec:
    """Complete API specification.
    
    Represents a parsed OpenAPI specification with all endpoints,
    schemas, and metadata needed for exploration.
    
    Attributes:
        title: API title.
        version: API version string.
        description: API description.
        servers: List of server definitions.
        operations: All API operations.
        schemas: Named schemas from components.
    """

    title: str
    version: str
    description: str | None = None
    servers: tuple[Server, ...] = ()
    operations: tuple[Operation, ...] = ()
    schemas: dict[str, Schema] = field(default_factory=dict)

    @property
    def base_url(self) -> str | None:
        """Return the first server URL, if any."""
        return self.servers[0].url if self.servers else None

    def get_operations_by_tag(self, tag: str) -> list[Operation]:
        """Return all operations with the given tag."""
        return [op for op in self.operations if tag in op.tags]

    def get_operations_by_path(self, path_prefix: str) -> list[Operation]:
        """Return all operations whose path starts with the prefix."""
        return [op for op in self.operations if op.path.startswith(path_prefix)]

    def find_operation(
        self,
        method: HttpMethod,
        path: str,
    ) -> Operation | None:
        """Find an operation by method and exact path."""
        for op in self.operations:
            if op.method == method and op.path == path:
                return op
        return None
