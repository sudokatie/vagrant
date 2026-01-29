"""Tests for OpenAPI parser."""

from pathlib import Path

import pytest

from vagrant.core.errors import SpecParseError
from vagrant.parser.openapi import OpenAPIParser, parse_spec


class TestOpenAPIParserFile:
    """Tests for parsing from files."""

    def test_parse_minimal_json(self, specs_dir: Path):
        """Parse minimal JSON spec."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "minimal.json")
        assert spec.title == "Minimal API"
        assert spec.version == "1.0.0"

    def test_parse_petstore_yaml(self, specs_dir: Path):
        """Parse petstore YAML spec."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        assert spec.title == "Petstore API"
        assert spec.version == "1.0.0"
        assert spec.description == "A sample API for testing the parser"

    def test_parse_nonexistent_file(self, specs_dir: Path):
        """Raise error for nonexistent file."""
        parser = OpenAPIParser()
        with pytest.raises(SpecParseError) as exc_info:
            parser.parse_file(specs_dir / "nonexistent.yaml")
        assert "not found" in str(exc_info.value).lower()


class TestOpenAPIParserString:
    """Tests for parsing from strings."""

    def test_parse_yaml_string(self):
        """Parse YAML content string."""
        content = """
openapi: "3.0.0"
info:
  title: Test API
  version: "2.0.0"
paths: {}
"""
        parser = OpenAPIParser()
        spec = parser.parse_string(content)
        assert spec.title == "Test API"
        assert spec.version == "2.0.0"

    def test_parse_json_string(self):
        """Parse JSON content string."""
        content = '{"openapi": "3.0.0", "info": {"title": "JSON API", "version": "1.0.0"}, "paths": {}}'
        parser = OpenAPIParser()
        spec = parser.parse_string(content, format="json")
        assert spec.title == "JSON API"

    def test_invalid_yaml(self):
        """Raise error for invalid YAML."""
        parser = OpenAPIParser()
        with pytest.raises(SpecParseError):
            parser.parse_string("invalid: yaml: content:")

    def test_non_object_content(self):
        """Raise error for non-object content."""
        parser = OpenAPIParser()
        with pytest.raises(SpecParseError):
            parser.parse_string("- list\n- not object")

    def test_missing_title(self):
        """Raise error for missing title."""
        content = """
openapi: "3.0.0"
info:
  version: "1.0.0"
paths: {}
"""
        parser = OpenAPIParser()
        with pytest.raises(SpecParseError) as exc_info:
            parser.parse_string(content)
        assert "title" in str(exc_info.value).lower()

    def test_missing_version(self):
        """Raise error for missing version."""
        content = """
openapi: "3.0.0"
info:
  title: Test API
paths: {}
"""
        parser = OpenAPIParser()
        with pytest.raises(SpecParseError) as exc_info:
            parser.parse_string(content)
        assert "version" in str(exc_info.value).lower()


class TestOpenAPIParserServers:
    """Tests for server parsing."""

    def test_parse_servers(self, specs_dir: Path):
        """Parse server list."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        assert len(spec.servers) == 2
        assert spec.servers[0].url == "https://api.petstore.com/v1"
        assert spec.servers[0].description == "Production server"

    def test_base_url(self, specs_dir: Path):
        """base_url returns first server."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        assert spec.base_url == "https://api.petstore.com/v1"


class TestOpenAPIParserOperations:
    """Tests for operation parsing."""

    def test_parse_operations(self, specs_dir: Path):
        """Parse all operations."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        # listPets, createPet, getPet, updatePet, deletePet
        assert len(spec.operations) == 5

    def test_operation_method_and_path(self, specs_dir: Path):
        """Operations have correct method and path."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("GET", "/pets")
        assert op is not None
        assert op.method == "GET"
        assert op.path == "/pets"

    def test_operation_id(self, specs_dir: Path):
        """Operations have operation ID."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("GET", "/pets")
        assert op.operation_id == "listPets"

    def test_operation_summary(self, specs_dir: Path):
        """Operations have summary."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("GET", "/pets")
        assert op.summary == "List all pets"

    def test_operation_tags(self, specs_dir: Path):
        """Operations have tags."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("GET", "/pets")
        assert "pets" in op.tags

    def test_deprecated_operation(self, specs_dir: Path):
        """Parse deprecated flag."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("DELETE", "/pets/{petId}")
        assert op is not None
        assert op.deprecated is True


class TestOpenAPIParserParameters:
    """Tests for parameter parsing."""

    def test_query_parameters(self, specs_dir: Path):
        """Parse query parameters."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("GET", "/pets")

        limit_param = next((p for p in op.parameters if p.name == "limit"), None)
        assert limit_param is not None
        assert limit_param.location == "query"
        assert limit_param.required is False
        assert limit_param.schema.type == "integer"

    def test_path_parameters(self, specs_dir: Path):
        """Parse path parameters."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("GET", "/pets/{petId}")

        id_param = next((p for p in op.parameters if p.name == "petId"), None)
        assert id_param is not None
        assert id_param.location == "path"
        assert id_param.required is True

    def test_path_level_parameters(self, specs_dir: Path):
        """Path-level parameters inherited by operations."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")

        # Both GET and PUT on /pets/{petId} should have petId parameter
        get_op = spec.find_operation("GET", "/pets/{petId}")
        put_op = spec.find_operation("PUT", "/pets/{petId}")

        assert any(p.name == "petId" for p in get_op.parameters)
        assert any(p.name == "petId" for p in put_op.parameters)

    def test_parameter_enum(self, specs_dir: Path):
        """Parse parameter with enum."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("GET", "/pets")

        status_param = next((p for p in op.parameters if p.name == "status"), None)
        assert status_param is not None
        assert status_param.schema.enum == ("available", "pending", "sold")


class TestOpenAPIParserRequestBody:
    """Tests for request body parsing."""

    def test_request_body(self, specs_dir: Path):
        """Parse request body."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("POST", "/pets")

        assert op.request_body is not None
        assert op.request_body.required is True
        assert op.request_body.content_type == "application/json"

    def test_request_body_schema(self, specs_dir: Path):
        """Request body has schema."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("POST", "/pets")

        assert op.request_body.schema.type == "object"


class TestOpenAPIParserResponses:
    """Tests for response parsing."""

    def test_responses(self, specs_dir: Path):
        """Parse responses."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("GET", "/pets")

        assert "200" in op.responses
        assert "500" in op.responses

    def test_response_description(self, specs_dir: Path):
        """Response has description."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("GET", "/pets")

        assert op.responses["200"].description == "A list of pets"

    def test_response_schema(self, specs_dir: Path):
        """Response has schema."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("GET", "/pets")

        assert op.responses["200"].schema is not None
        assert op.responses["200"].schema.type == "array"


class TestOpenAPIParserSchemas:
    """Tests for component schema parsing."""

    def test_component_schemas(self, specs_dir: Path):
        """Parse component schemas."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")

        assert "Pet" in spec.schemas
        assert "NewPet" in spec.schemas

    def test_schema_properties(self, specs_dir: Path):
        """Schema has properties."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")

        pet_schema = spec.schemas["Pet"]
        assert pet_schema.type == "object"
        assert "id" in pet_schema.properties
        assert "name" in pet_schema.properties

    def test_schema_required(self, specs_dir: Path):
        """Schema has required fields."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")

        pet_schema = spec.schemas["Pet"]
        assert "id" in pet_schema.required
        assert "name" in pet_schema.required

    def test_schema_array_items(self, specs_dir: Path):
        """Array schema has items type."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")

        pet_schema = spec.schemas["Pet"]
        tags_schema = pet_schema.properties["tags"]
        assert tags_schema.type == "array"
        assert tags_schema.items.type == "string"


class TestOpenAPIParserRefResolution:
    """Tests for $ref resolution."""

    def test_ref_in_response_schema(self, specs_dir: Path):
        """Resolve $ref in response schema."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("GET", "/pets/{petId}")

        # Response references Pet schema
        response_schema = op.responses["200"].schema
        assert response_schema.type == "object"
        assert "id" in response_schema.properties

    def test_ref_in_request_body(self, specs_dir: Path):
        """Resolve $ref in request body schema."""
        parser = OpenAPIParser()
        spec = parser.parse_file(specs_dir / "petstore.yaml")
        op = spec.find_operation("POST", "/pets")

        # Request body references NewPet schema
        body_schema = op.request_body.schema
        assert body_schema.type == "object"
        assert "name" in body_schema.properties


class TestConvenienceFunction:
    """Tests for parse_spec convenience function."""

    def test_parse_spec(self, specs_dir: Path):
        """parse_spec function works."""
        spec = parse_spec(specs_dir / "petstore.yaml")
        assert spec.title == "Petstore API"
