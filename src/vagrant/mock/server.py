"""Mock server that generates responses from OpenAPI specs.

Serves mock responses based on examples and schemas defined in the spec.
Useful for testing without a real API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from http import HTTPStatus

from aiohttp import web

from vagrant.parser import ApiSpec, Operation, Schema
from vagrant.parser.openapi import parse_spec

logger = logging.getLogger(__name__)


@dataclass
class RequestLog:
    """Log entry for a mock server request."""
    timestamp: datetime
    method: str
    path: str
    query: dict[str, str]
    headers: dict[str, str]
    body: Any
    status: int
    response: Any


@dataclass
class MockServer:
    """Mock HTTP server based on an OpenAPI spec.
    
    Generates responses from spec examples or schema defaults.
    Logs all requests for inspection.
    """
    spec: ApiSpec
    host: str = "127.0.0.1"
    port: int = 8080
    delay_ms: int = 0
    logs: list[RequestLog] = field(default_factory=list)
    _app: web.Application | None = field(default=None, repr=False)
    _runner: web.AppRunner | None = field(default=None, repr=False)

    def __post_init__(self):
        self._app = web.Application()
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Set up routes from the spec."""
        for op in self.spec.operations:
            # Convert OpenAPI path params {id} to aiohttp format {id}
            aiohttp_path = op.path
            
            handler = self._create_handler(op)
            method = op.method.lower()
            
            if method == "get":
                self._app.router.add_get(aiohttp_path, handler)
            elif method == "post":
                self._app.router.add_post(aiohttp_path, handler)
            elif method == "put":
                self._app.router.add_put(aiohttp_path, handler)
            elif method == "patch":
                self._app.router.add_patch(aiohttp_path, handler)
            elif method == "delete":
                self._app.router.add_delete(aiohttp_path, handler)

    def _create_handler(self, op: Operation):
        """Create a request handler for an operation."""
        async def handler(request: web.Request) -> web.Response:
            # Add delay if configured
            if self.delay_ms > 0:
                await asyncio.sleep(self.delay_ms / 1000)
            
            # Parse request
            body = None
            if request.body_exists:
                try:
                    body = await request.json()
                except json.JSONDecodeError:
                    body = await request.text()
            
            # Generate response
            status, response_body = self._generate_response(op, request)
            
            # Log request
            log_entry = RequestLog(
                timestamp=datetime.now(),
                method=op.method,
                path=request.path,
                query=dict(request.query),
                headers=dict(request.headers),
                body=body,
                status=status,
                response=response_body,
            )
            self.logs.append(log_entry)
            logger.info(f"{op.method} {request.path} -> {status}")
            
            # Return response
            return web.json_response(
                response_body,
                status=status,
                headers={"X-Mock-Server": "vagrant"},
            )
        
        return handler

    def _generate_response(
        self,
        op: Operation,
        request: web.Request,
    ) -> tuple[int, Any]:
        """Generate a mock response for an operation.
        
        Priority:
        1. Example from response definition
        2. Generated from schema
        3. Empty response
        """
        # Find success response (200, 201, or first 2xx)
        success_codes = ["200", "201", "204"]
        response = None
        status_code = 200
        
        for code in success_codes:
            if code in op.responses:
                response = op.responses[code]
                status_code = int(code)
                break
        
        if not response:
            # Find any 2xx response
            for code, resp in op.responses.items():
                if code.startswith("2"):
                    response = resp
                    status_code = int(code)
                    break
        
        if not response:
            return 200, {"message": "OK"}
        
        if status_code == 204:
            return 204, None
        
        # Generate from schema if available
        if response.schema:
            return status_code, self._generate_from_schema(response.schema)
        
        return status_code, {"message": response.description or "OK"}

    def _generate_from_schema(self, schema: Schema) -> Any:
        """Generate mock data from a schema."""
        if schema.default is not None:
            return schema.default
        
        if schema.enum:
            return schema.enum[0]
        
        if schema.type == "string":
            return self._generate_string(schema)
        elif schema.type == "integer":
            return self._generate_integer(schema)
        elif schema.type == "number":
            return self._generate_number(schema)
        elif schema.type == "boolean":
            return False
        elif schema.type == "array":
            if schema.items:
                return [self._generate_from_schema(schema.items)]
            return []
        elif schema.type == "object":
            if not schema.properties:
                return {}
            result = {}
            for name, prop_schema in schema.properties.items():
                result[name] = self._generate_from_schema(prop_schema)
            return result
        
        return None

    def _generate_string(self, schema: Schema) -> str:
        """Generate a mock string value."""
        fmt = schema.format
        if fmt == "date":
            return "2024-01-15"
        elif fmt == "date-time":
            return "2024-01-15T10:30:00Z"
        elif fmt == "email":
            return "user@example.com"
        elif fmt == "uuid":
            return "550e8400-e29b-41d4-a716-446655440000"
        elif fmt == "uri" or fmt == "url":
            return "https://example.com"
        elif fmt == "hostname":
            return "example.com"
        elif fmt == "ipv4":
            return "192.168.1.1"
        elif fmt == "ipv6":
            return "2001:db8::1"
        return "string"

    def _generate_integer(self, schema: Schema) -> int:
        """Generate a mock integer value."""
        fmt = schema.format
        if fmt == "int32":
            return 42
        elif fmt == "int64":
            return 9007199254740991
        return 0

    def _generate_number(self, schema: Schema) -> float:
        """Generate a mock number value."""
        fmt = schema.format
        if fmt == "float":
            return 3.14
        elif fmt == "double":
            return 3.141592653589793
        return 0.0

    async def start(self) -> None:
        """Start the mock server."""
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self.host, self.port)
        await site.start()
        logger.info(f"Mock server running at http://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Stop the mock server."""
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        logger.info("Mock server stopped")

    def get_logs(self, limit: int = 100) -> list[RequestLog]:
        """Get recent request logs."""
        return self.logs[-limit:]

    def clear_logs(self) -> None:
        """Clear request logs."""
        self.logs.clear()


async def run_mock_server(
    spec_path: str,
    host: str = "127.0.0.1",
    port: int = 8080,
    delay_ms: int = 0,
) -> None:
    """Run a mock server for an OpenAPI spec.
    
    Args:
        spec_path: Path to OpenAPI spec file.
        host: Host to bind to.
        port: Port to listen on.
        delay_ms: Artificial delay for responses.
    """
    spec = parse_spec(spec_path)
    server = MockServer(spec=spec, host=host, port=port, delay_ms=delay_ms)
    
    await server.start()
    
    print(f"Mock server running at http://{host}:{port}")
    print(f"Serving {len(spec.operations)} endpoints from {spec.title}")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await server.stop()
