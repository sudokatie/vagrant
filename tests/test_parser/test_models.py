"""Tests for parser models."""

import pytest

from vagrant.parser.models import (
    ApiSpec,
    Operation,
    Parameter,
    RequestBody,
    Response,
    Schema,
    SecurityScheme,
    Server,
    ServerVariable,
)


class TestSchema:
    """Tests for Schema model."""

    def test_default_is_string(self):
        """Default schema is string type."""
        schema = Schema()
        assert schema.type == "string"

    def test_frozen(self):
        """Schema is immutable."""
        schema = Schema()
        with pytest.raises(AttributeError):
            schema.type = "integer"

    def test_string_factory(self):
        """String factory creates string schema."""
        schema = Schema.string(format="email")
        assert schema.type == "string"
        assert schema.format == "email"

    def test_integer_factory(self):
        """Integer factory creates integer schema."""
        schema = Schema.integer(format="int64")
        assert schema.type == "integer"
        assert schema.format == "int64"

    def test_number_factory(self):
        """Number factory creates number schema."""
        schema = Schema.number(format="double")
        assert schema.type == "number"
        assert schema.format == "double"

    def test_boolean_factory(self):
        """Boolean factory creates boolean schema."""
        schema = Schema.boolean()
        assert schema.type == "boolean"

    def test_array_factory(self):
        """Array factory creates array with item schema."""
        items = Schema.string()
        schema = Schema.array(items)
        assert schema.type == "array"
        assert schema.items == items

    def test_object_factory(self):
        """Object factory creates object schema."""
        props = {"name": Schema.string(), "age": Schema.integer()}
        schema = Schema.object(properties=props, required=("name",))
        assert schema.type == "object"
        assert schema.properties == props
        assert schema.required == ("name",)

    def test_nested_schema(self):
        """Schemas can be nested."""
        address = Schema.object(
            properties={
                "street": Schema.string(),
                "city": Schema.string(),
            }
        )
        person = Schema.object(
            properties={
                "name": Schema.string(),
                "address": address,
            }
        )
        assert person.properties["address"].type == "object"

    def test_enum_values(self):
        """Schema can have enum values."""
        schema = Schema(type="string", enum=("active", "inactive", "pending"))
        assert schema.enum == ("active", "inactive", "pending")

    def test_default_value(self):
        """Schema can have default value."""
        schema = Schema(type="integer", default=10)
        assert schema.default == 10


class TestParameter:
    """Tests for Parameter model."""

    def test_minimal_parameter(self):
        """Parameter with just name and location."""
        param = Parameter(name="id", location="path")
        assert param.name == "id"
        assert param.location == "path"
        assert param.required is False

    def test_required_parameter(self):
        """Required parameter."""
        param = Parameter(name="id", location="path", required=True)
        assert param.required is True

    def test_parameter_with_schema(self):
        """Parameter with custom schema."""
        param = Parameter(
            name="page",
            location="query",
            schema=Schema.integer(),
        )
        assert param.schema.type == "integer"

    def test_parameter_frozen(self):
        """Parameter is immutable."""
        param = Parameter(name="id", location="path")
        with pytest.raises(AttributeError):
            param.name = "new_name"


class TestRequestBody:
    """Tests for RequestBody model."""

    def test_default_content_type(self):
        """Default content type is application/json."""
        body = RequestBody()
        assert body.content_type == "application/json"

    def test_custom_schema(self):
        """Request body with custom schema."""
        schema = Schema.object(
            properties={"name": Schema.string()},
            required=("name",),
        )
        body = RequestBody(schema=schema, required=True)
        assert body.required is True
        assert body.schema.type == "object"


class TestResponse:
    """Tests for Response model."""

    def test_minimal_response(self):
        """Response with just status code."""
        resp = Response(status_code="200")
        assert resp.status_code == "200"
        assert resp.description == ""

    def test_response_with_schema(self):
        """Response with body schema."""
        schema = Schema.object(
            properties={"id": Schema.integer(), "name": Schema.string()}
        )
        resp = Response(
            status_code="200",
            description="Successful response",
            schema=schema,
        )
        assert resp.schema.type == "object"


class TestOperation:
    """Tests for Operation model."""

    def test_minimal_operation(self):
        """Operation with just method and path."""
        op = Operation(method="GET", path="/users")
        assert op.method == "GET"
        assert op.path == "/users"

    def test_operation_with_parameters(self):
        """Operation with parameters."""
        params = (
            Parameter(name="id", location="path", required=True),
            Parameter(name="include", location="query"),
        )
        op = Operation(method="GET", path="/users/{id}", parameters=params)
        assert len(op.parameters) == 2

    def test_operation_with_request_body(self):
        """Operation with request body."""
        body = RequestBody(
            schema=Schema.object(properties={"name": Schema.string()})
        )
        op = Operation(method="POST", path="/users", request_body=body)
        assert op.request_body is not None

    def test_operation_with_responses(self):
        """Operation with responses."""
        responses = {
            "200": Response(status_code="200", description="Success"),
            "404": Response(status_code="404", description="Not found"),
        }
        op = Operation(method="GET", path="/users/{id}", responses=responses)
        assert "200" in op.responses
        assert "404" in op.responses

    def test_display_name_with_summary(self):
        """Display name uses summary when available."""
        op = Operation(method="GET", path="/users", summary="List all users")
        assert op.display_name == "List all users"

    def test_display_name_with_operation_id(self):
        """Display name uses operation_id when no summary."""
        op = Operation(method="GET", path="/users", operation_id="listUsers")
        assert op.display_name == "listUsers"

    def test_display_name_fallback(self):
        """Display name falls back to method + path."""
        op = Operation(method="GET", path="/users")
        assert op.display_name == "GET /users"

    def test_operation_frozen(self):
        """Operation is immutable."""
        op = Operation(method="GET", path="/users")
        with pytest.raises(AttributeError):
            op.method = "POST"

    def test_operation_with_security(self):
        """Operation with security requirements (spec 3.4)."""
        security = (
            {"bearerAuth": ()},
            {"apiKey": ()},
        )
        op = Operation(method="GET", path="/users", security=security)
        assert len(op.security) == 2
        assert "bearerAuth" in op.security[0]

    def test_operation_with_oauth_scopes(self):
        """Operation with OAuth scopes."""
        security = ({"oauth2": ("read:users", "write:users")},)
        op = Operation(method="POST", path="/users", security=security)
        assert op.security[0]["oauth2"] == ("read:users", "write:users")


class TestServerVariable:
    """Tests for ServerVariable model (spec 3.4)."""

    def test_server_variable_with_default(self):
        """Server variable with just default."""
        var = ServerVariable(default="v1")
        assert var.default == "v1"
        assert var.enum == ()

    def test_server_variable_with_enum(self):
        """Server variable with enum values."""
        var = ServerVariable(default="v1", enum=("v1", "v2", "v3"))
        assert var.enum == ("v1", "v2", "v3")

    def test_server_variable_with_description(self):
        """Server variable with description."""
        var = ServerVariable(default="v1", description="API version")
        assert var.description == "API version"


class TestSecurityScheme:
    """Tests for SecurityScheme model (spec 3.4)."""

    def test_apikey_scheme(self):
        """API key security scheme."""
        scheme = SecurityScheme(
            type="apiKey",
            name="X-API-Key",
            location="header",
        )
        assert scheme.type == "apiKey"
        assert scheme.name == "X-API-Key"
        assert scheme.location == "header"

    def test_bearer_scheme(self):
        """HTTP bearer security scheme."""
        scheme = SecurityScheme(
            type="http",
            scheme="bearer",
            bearer_format="JWT",
        )
        assert scheme.type == "http"
        assert scheme.scheme == "bearer"
        assert scheme.bearer_format == "JWT"

    def test_basic_scheme(self):
        """HTTP basic security scheme."""
        scheme = SecurityScheme(
            type="http",
            scheme="basic",
            description="Basic auth",
        )
        assert scheme.type == "http"
        assert scheme.scheme == "basic"

    def test_scheme_frozen(self):
        """Security scheme is immutable."""
        scheme = SecurityScheme(type="apiKey")
        with pytest.raises(AttributeError):
            scheme.type = "http"


class TestServer:
    """Tests for Server model."""

    def test_minimal_server(self):
        """Server with just URL."""
        server = Server(url="https://api.example.com")
        assert server.url == "https://api.example.com"
        assert server.description is None

    def test_server_with_description(self):
        """Server with description."""
        server = Server(
            url="https://api.example.com",
            description="Production server",
        )
        assert server.description == "Production server"

    def test_server_with_variables(self):
        """Server with URL variables (spec 3.4)."""
        variables = {
            "version": ServerVariable(default="v1", enum=("v1", "v2")),
            "environment": ServerVariable(default="production"),
        }
        server = Server(
            url="https://{environment}.api.example.com/{version}",
            variables=variables,
        )
        assert len(server.variables) == 2
        assert server.variables["version"].default == "v1"
        assert server.variables["environment"].default == "production"


class TestApiSpec:
    """Tests for ApiSpec model."""

    def test_minimal_spec(self):
        """Spec with just title and version."""
        spec = ApiSpec(title="My API", version="1.0.0")
        assert spec.title == "My API"
        assert spec.version == "1.0.0"

    def test_spec_with_servers(self):
        """Spec with server list."""
        servers = (
            Server(url="https://api.example.com", description="Production"),
            Server(url="https://staging.example.com", description="Staging"),
        )
        spec = ApiSpec(title="My API", version="1.0.0", servers=servers)
        assert len(spec.servers) == 2

    def test_base_url_property(self):
        """base_url returns first server URL."""
        servers = (Server(url="https://api.example.com"),)
        spec = ApiSpec(title="My API", version="1.0.0", servers=servers)
        assert spec.base_url == "https://api.example.com"

    def test_base_url_empty(self):
        """base_url returns None when no servers."""
        spec = ApiSpec(title="My API", version="1.0.0")
        assert spec.base_url is None

    def test_spec_with_operations(self):
        """Spec with operations."""
        ops = (
            Operation(method="GET", path="/users", tags=("users",)),
            Operation(method="POST", path="/users", tags=("users",)),
            Operation(method="GET", path="/posts", tags=("posts",)),
        )
        spec = ApiSpec(title="My API", version="1.0.0", operations=ops)
        assert len(spec.operations) == 3

    def test_get_operations_by_tag(self):
        """Filter operations by tag."""
        ops = (
            Operation(method="GET", path="/users", tags=("users",)),
            Operation(method="POST", path="/users", tags=("users",)),
            Operation(method="GET", path="/posts", tags=("posts",)),
        )
        spec = ApiSpec(title="My API", version="1.0.0", operations=ops)
        user_ops = spec.get_operations_by_tag("users")
        assert len(user_ops) == 2

    def test_get_operations_by_path(self):
        """Filter operations by path prefix."""
        ops = (
            Operation(method="GET", path="/users"),
            Operation(method="GET", path="/users/{id}"),
            Operation(method="GET", path="/posts"),
        )
        spec = ApiSpec(title="My API", version="1.0.0", operations=ops)
        user_ops = spec.get_operations_by_path("/users")
        assert len(user_ops) == 2

    def test_find_operation(self):
        """Find operation by method and path."""
        ops = (
            Operation(method="GET", path="/users"),
            Operation(method="POST", path="/users"),
        )
        spec = ApiSpec(title="My API", version="1.0.0", operations=ops)
        op = spec.find_operation("POST", "/users")
        assert op is not None
        assert op.method == "POST"

    def test_find_operation_not_found(self):
        """find_operation returns None when not found."""
        ops = (Operation(method="GET", path="/users"),)
        spec = ApiSpec(title="My API", version="1.0.0", operations=ops)
        op = spec.find_operation("DELETE", "/users")
        assert op is None

    def test_spec_with_schemas(self):
        """Spec with component schemas."""
        schemas = {
            "User": Schema.object(
                properties={"id": Schema.integer(), "name": Schema.string()}
            ),
            "Post": Schema.object(
                properties={"id": Schema.integer(), "title": Schema.string()}
            ),
        }
        spec = ApiSpec(title="My API", version="1.0.0", schemas=schemas)
        assert "User" in spec.schemas
        assert "Post" in spec.schemas

    def test_spec_with_security_schemes(self):
        """Spec with security schemes (spec 3.4)."""
        security_schemes = {
            "bearerAuth": SecurityScheme(type="http", scheme="bearer"),
            "apiKey": SecurityScheme(type="apiKey", name="X-API-Key", location="header"),
        }
        spec = ApiSpec(
            title="My API",
            version="1.0.0",
            security_schemes=security_schemes,
        )
        assert "bearerAuth" in spec.security_schemes
        assert "apiKey" in spec.security_schemes
        assert spec.security_schemes["bearerAuth"].scheme == "bearer"
