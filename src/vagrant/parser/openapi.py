"""OpenAPI 3.x specification parser."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from vagrant.core.errors import SpecParseError
from vagrant.parser.models import (
    ApiSpec,
    Operation,
    Parameter,
    RequestBody,
    Response,
    Schema,
    Server,
)


class OpenAPIParser:
    """Parser for OpenAPI 3.x specifications.
    
    Supports JSON and YAML formats. Handles $ref resolution for local references.
    Lenient parsing - logs warnings for non-critical issues, fails only on
    truly broken specs.
    """

    def __init__(self) -> None:
        """Initialize parser."""
        self._raw: dict[str, Any] = {}
        self._file_path: str | None = None

    def parse_file(self, path: Path | str) -> ApiSpec:
        """Parse specification from file.
        
        Detects JSON or YAML format from file extension and content.
        
        Args:
            path: Path to the spec file.
            
        Returns:
            Parsed ApiSpec.
            
        Raises:
            SpecParseError: If file cannot be read or parsed.
        """
        path = Path(path)
        self._file_path = str(path)
        
        if not path.exists():
            raise SpecParseError(f"File not found: {path}", file_path=str(path))
        
        try:
            content = path.read_text()
        except OSError as e:
            raise SpecParseError(f"Cannot read file: {e}", file_path=str(path))
        
        # Detect format from extension or content
        if path.suffix in (".json",) or content.strip().startswith("{"):
            return self.parse_string(content, format="json")
        else:
            return self.parse_string(content, format="yaml")

    def parse_string(self, content: str, format: str = "yaml") -> ApiSpec:
        """Parse specification from string content.
        
        Args:
            content: Spec content as string.
            format: Content format ("yaml" or "json").
            
        Returns:
            Parsed ApiSpec.
            
        Raises:
            SpecParseError: If content cannot be parsed.
        """
        try:
            # YAML parser handles both YAML and JSON
            self._raw = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise SpecParseError(f"Invalid {format.upper()}: {e}")
        
        if not isinstance(self._raw, dict):
            raise SpecParseError("Spec must be a YAML/JSON object")
        
        return self._parse_spec()

    def _parse_spec(self) -> ApiSpec:
        """Parse the loaded raw data into an ApiSpec."""
        # Required fields
        info = self._raw.get("info", {})
        title = info.get("title")
        version = info.get("version")
        
        if not title:
            raise SpecParseError("Missing required field: info.title")
        if not version:
            raise SpecParseError("Missing required field: info.version")
        
        # Optional fields
        description = info.get("description")
        
        # Servers
        servers = tuple(
            self._parse_server(s)
            for s in self._raw.get("servers", [])
        )
        
        # Operations from paths
        operations = self._parse_paths()
        
        # Component schemas
        schemas = self._parse_component_schemas()
        
        return ApiSpec(
            title=title,
            version=version,
            description=description,
            servers=servers,
            operations=operations,
            schemas=schemas,
        )

    def _parse_server(self, data: dict[str, Any]) -> Server:
        """Parse a server definition."""
        return Server(
            url=data.get("url", ""),
            description=data.get("description"),
        )

    def _parse_paths(self) -> tuple[Operation, ...]:
        """Parse all paths and operations."""
        operations: list[Operation] = []
        paths = self._raw.get("paths", {})
        
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            
            # Collect path-level parameters
            path_params = tuple(
                self._parse_parameter(p)
                for p in path_item.get("parameters", [])
            )
            
            # Parse each HTTP method
            for method in ("get", "post", "put", "patch", "delete", "options", "head"):
                if method not in path_item:
                    continue
                
                op_data = path_item[method]
                if not isinstance(op_data, dict):
                    continue
                
                operations.append(
                    self._parse_operation(method.upper(), path, op_data, path_params)
                )
        
        return tuple(operations)

    def _parse_operation(
        self,
        method: str,
        path: str,
        data: dict[str, Any],
        path_params: tuple[Parameter, ...],
    ) -> Operation:
        """Parse a single operation."""
        # Merge path-level and operation-level parameters
        op_params = tuple(
            self._parse_parameter(p)
            for p in data.get("parameters", [])
        )
        all_params = path_params + op_params
        
        # Parse request body
        request_body = None
        if "requestBody" in data:
            request_body = self._parse_request_body(data["requestBody"])
        
        # Parse responses
        responses = {}
        for status, resp_data in data.get("responses", {}).items():
            if isinstance(resp_data, dict):
                responses[str(status)] = self._parse_response(str(status), resp_data)
        
        return Operation(
            method=method,  # type: ignore
            path=path,
            operation_id=data.get("operationId"),
            summary=data.get("summary"),
            description=data.get("description"),
            tags=tuple(data.get("tags", [])),
            parameters=all_params,
            request_body=request_body,
            responses=responses,
            deprecated=data.get("deprecated", False),
        )

    def _parse_parameter(self, data: dict[str, Any]) -> Parameter:
        """Parse a parameter definition."""
        # Handle $ref
        data = self._resolve_ref(data)
        
        return Parameter(
            name=data.get("name", ""),
            location=data.get("in", "query"),  # type: ignore
            required=data.get("required", False),
            schema=self._parse_schema(data.get("schema", {})),
            description=data.get("description"),
            example=data.get("example"),
        )

    def _parse_request_body(self, data: dict[str, Any]) -> RequestBody:
        """Parse a request body definition."""
        data = self._resolve_ref(data)
        
        content = data.get("content", {})
        
        # Prefer application/json, fall back to first content type
        if "application/json" in content:
            content_type = "application/json"
            media = content["application/json"]
        elif content:
            content_type = next(iter(content))
            media = content[content_type]
        else:
            content_type = "application/json"
            media = {}
        
        return RequestBody(
            content_type=content_type,
            schema=self._parse_schema(media.get("schema", {})),
            required=data.get("required", False),
            description=data.get("description"),
        )

    def _parse_response(self, status_code: str, data: dict[str, Any]) -> Response:
        """Parse a response definition."""
        data = self._resolve_ref(data)
        
        content = data.get("content", {})
        schema = None
        content_type = "application/json"
        
        if "application/json" in content:
            media = content["application/json"]
            schema = self._parse_schema(media.get("schema", {}))
        elif content:
            content_type = next(iter(content))
            media = content[content_type]
            if "schema" in media:
                schema = self._parse_schema(media["schema"])
        
        return Response(
            status_code=status_code,
            description=data.get("description", ""),
            schema=schema,
            content_type=content_type,
        )

    def _parse_schema(self, data: dict[str, Any]) -> Schema:
        """Parse a schema definition."""
        if not data:
            return Schema()
        
        data = self._resolve_ref(data)
        
        # Handle allOf, oneOf, anyOf by taking first item
        for combo in ("allOf", "oneOf", "anyOf"):
            if combo in data and data[combo]:
                data = self._resolve_ref(data[combo][0])
                break
        
        schema_type = data.get("type", "string")
        
        # Parse properties for objects
        properties = None
        if "properties" in data:
            properties = {
                name: self._parse_schema(prop_data)
                for name, prop_data in data["properties"].items()
            }
        
        # Parse items for arrays
        items = None
        if "items" in data:
            items = self._parse_schema(data["items"])
        
        # Parse enum
        enum = None
        if "enum" in data:
            enum = tuple(data["enum"])
        
        return Schema(
            type=schema_type,
            format=data.get("format"),
            properties=properties,
            items=items,
            required=tuple(data.get("required", [])),
            enum=enum,
            default=data.get("default"),
            description=data.get("description"),
            nullable=data.get("nullable", False),
        )

    def _parse_component_schemas(self) -> dict[str, Schema]:
        """Parse component schemas."""
        components = self._raw.get("components", {})
        schemas_data = components.get("schemas", {})
        
        return {
            name: self._parse_schema(schema_data)
            for name, schema_data in schemas_data.items()
        }

    def _resolve_ref(self, data: dict[str, Any]) -> dict[str, Any]:
        """Resolve $ref pointer to actual data.
        
        Only handles local references (#/...).
        """
        if not isinstance(data, dict) or "$ref" not in data:
            return data
        
        ref = data["$ref"]
        if not ref.startswith("#/"):
            # External refs not supported yet
            return data
        
        # Navigate to referenced data
        parts = ref[2:].split("/")
        current = self._raw
        
        for part in parts:
            # Handle JSON pointer escaping
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                # Reference not found, return empty
                return {}
        
        return current if isinstance(current, dict) else {}


def parse_spec(source: str | Path) -> ApiSpec:
    """Convenience function to parse a spec from file or URL.
    
    Args:
        source: Path to spec file.
        
    Returns:
        Parsed ApiSpec.
    """
    parser = OpenAPIParser()
    return parser.parse_file(source)
