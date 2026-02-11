"""Tests for mock server."""

import pytest
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from vagrant.mock.server import MockServer, RequestLog
from vagrant.parser.models import (
    ApiSpec,
    Operation,
    Parameter,
    RequestBody,
    Response,
    Schema,
    Server,
)


def create_test_spec() -> ApiSpec:
    """Create a test API spec."""
    return ApiSpec(
        title="Test API",
        version="1.0.0",
        servers=(Server(url="http://localhost:8080"),),
        operations=(
            Operation(
                method="GET",
                path="/users",
                operation_id="listUsers",
                summary="List users",
                responses={
                    "200": Response(
                        status_code="200",
                        description="Success",
                        schema=Schema.array(
                            Schema.object(
                                properties={
                                    "id": Schema.integer(),
                                    "name": Schema.string(),
                                    "email": Schema.string(format="email"),
                                },
                            )
                        ),
                    ),
                },
            ),
            Operation(
                method="GET",
                path="/users/{id}",
                operation_id="getUser",
                summary="Get user by ID",
                parameters=(
                    Parameter(name="id", location="path", required=True, schema=Schema.integer()),
                ),
                responses={
                    "200": Response(
                        status_code="200",
                        description="Success",
                        schema=Schema.object(
                            properties={
                                "id": Schema.integer(),
                                "name": Schema.string(),
                                "email": Schema.string(format="email"),
                            },
                        ),
                    ),
                    "404": Response(status_code="404", description="Not found"),
                },
            ),
            Operation(
                method="POST",
                path="/users",
                operation_id="createUser",
                summary="Create user",
                request_body=RequestBody(
                    content_type="application/json",
                    schema=Schema.object(
                        properties={
                            "name": Schema.string(),
                            "email": Schema.string(format="email"),
                        },
                        required=("name",),
                    ),
                    required=True,
                ),
                responses={
                    "201": Response(
                        status_code="201",
                        description="Created",
                        schema=Schema.object(
                            properties={
                                "id": Schema.integer(),
                                "name": Schema.string(),
                            },
                        ),
                    ),
                },
            ),
            Operation(
                method="DELETE",
                path="/users/{id}",
                operation_id="deleteUser",
                summary="Delete user",
                responses={
                    "204": Response(status_code="204", description="Deleted"),
                },
            ),
        ),
    )


class TestMockServer:
    """Tests for MockServer class."""

    def test_create_server(self):
        """Can create a mock server from spec."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        assert server.spec == spec
        assert server.host == "127.0.0.1"
        assert server.port == 8080
        assert server.logs == []

    def test_custom_host_port(self):
        """Can specify custom host and port."""
        spec = create_test_spec()
        server = MockServer(spec=spec, host="0.0.0.0", port=3000)
        assert server.host == "0.0.0.0"
        assert server.port == 3000

    def test_generate_string(self):
        """Generate mock string values."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        assert server._generate_string(Schema.string()) == "string"
        assert server._generate_string(Schema.string(format="email")) == "user@example.com"
        assert server._generate_string(Schema.string(format="date")) == "2024-01-15"
        assert server._generate_string(Schema.string(format="uuid")).startswith("550e8400")

    def test_generate_integer(self):
        """Generate mock integer values."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        assert server._generate_integer(Schema.integer()) == 0
        assert server._generate_integer(Schema.integer(format="int32")) == 42

    def test_generate_number(self):
        """Generate mock number values."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        assert server._generate_number(Schema.number()) == 0.0
        assert server._generate_number(Schema.number(format="float")) == 3.14

    def test_generate_boolean(self):
        """Generate mock boolean values."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        assert server._generate_from_schema(Schema.boolean()) is False

    def test_generate_array(self):
        """Generate mock array values."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        result = server._generate_from_schema(Schema.array(Schema.string()))
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0] == "string"

    def test_generate_object(self):
        """Generate mock object values."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        schema = Schema.object(
            properties={
                "id": Schema.integer(format="int32"),
                "name": Schema.string(),
            }
        )
        result = server._generate_from_schema(schema)
        assert isinstance(result, dict)
        assert result["id"] == 42
        assert result["name"] == "string"

    def test_generate_with_default(self):
        """Use default value if available."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        schema = Schema(type="string", default="hello")
        assert server._generate_from_schema(schema) == "hello"

    def test_generate_with_enum(self):
        """Use first enum value."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        schema = Schema(type="string", enum=("active", "inactive", "pending"))
        assert server._generate_from_schema(schema) == "active"

    def test_get_logs(self):
        """Can get request logs."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        # Add some mock logs
        from datetime import datetime
        log = RequestLog(
            timestamp=datetime.now(),
            method="GET",
            path="/users",
            query={},
            headers={},
            body=None,
            status=200,
            response=[],
        )
        server.logs.append(log)
        
        logs = server.get_logs()
        assert len(logs) == 1
        assert logs[0].method == "GET"

    def test_clear_logs(self):
        """Can clear request logs."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        from datetime import datetime
        log = RequestLog(
            timestamp=datetime.now(),
            method="GET",
            path="/users",
            query={},
            headers={},
            body=None,
            status=200,
            response=[],
        )
        server.logs.append(log)
        
        server.clear_logs()
        assert server.logs == []


@pytest.mark.asyncio
class TestMockServerIntegration:
    """Integration tests for mock server HTTP handling."""

    async def test_get_users(self):
        """GET /users returns array response."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        await server.start()
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://{server.host}:{server.port}/users")
                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)
                assert len(data) == 1
                assert "id" in data[0]
                assert "email" in data[0]
                assert data[0]["email"] == "user@example.com"
        finally:
            await server.stop()

    async def test_get_user_by_id(self):
        """GET /users/{id} returns object response."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        await server.start()
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://{server.host}:{server.port}/users/123")
                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, dict)
                assert "id" in data
        finally:
            await server.stop()

    async def test_post_user(self):
        """POST /users returns 201 created."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        await server.start()
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"http://{server.host}:{server.port}/users",
                    json={"name": "Test User", "email": "test@example.com"},
                )
                assert response.status_code == 201
                data = response.json()
                assert "id" in data
        finally:
            await server.stop()

    async def test_delete_user(self):
        """DELETE /users/{id} returns 204."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        await server.start()
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.delete(f"http://{server.host}:{server.port}/users/123")
                assert response.status_code == 204
        finally:
            await server.stop()

    async def test_request_logging(self):
        """Requests are logged."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        await server.start()
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.get(f"http://{server.host}:{server.port}/users")
            
            logs = server.get_logs()
            assert len(logs) == 1
            assert logs[0].method == "GET"
            assert logs[0].path == "/users"
            assert logs[0].status == 200
        finally:
            await server.stop()

    async def test_mock_header(self):
        """Response includes X-Mock-Server header."""
        spec = create_test_spec()
        server = MockServer(spec=spec)
        
        await server.start()
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://{server.host}:{server.port}/users")
                assert response.headers.get("X-Mock-Server") == "vagrant"
        finally:
            await server.stop()
