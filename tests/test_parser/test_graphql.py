"""Tests for GraphQL parser."""

import pytest

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
    _parse_type_ref,
    _parse_arg,
    _parse_field,
    _parse_type,
)
from vagrant.core.errors import SpecParseError


# Sample introspection response for testing
SAMPLE_INTROSPECTION = {
    "data": {
        "__schema": {
            "queryType": {"name": "Query"},
            "mutationType": {"name": "Mutation"},
            "subscriptionType": None,
            "types": [
                {
                    "kind": "OBJECT",
                    "name": "Query",
                    "description": "Root query type",
                    "fields": [
                        {
                            "name": "user",
                            "description": "Get user by ID",
                            "args": [
                                {
                                    "name": "id",
                                    "description": "User ID",
                                    "type": {
                                        "kind": "NON_NULL",
                                        "name": None,
                                        "ofType": {"kind": "SCALAR", "name": "ID", "ofType": None},
                                    },
                                    "defaultValue": None,
                                }
                            ],
                            "type": {"kind": "OBJECT", "name": "User", "ofType": None},
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                        {
                            "name": "users",
                            "description": "List all users",
                            "args": [
                                {
                                    "name": "limit",
                                    "description": "Max results",
                                    "type": {"kind": "SCALAR", "name": "Int", "ofType": None},
                                    "defaultValue": "10",
                                }
                            ],
                            "type": {
                                "kind": "NON_NULL",
                                "name": None,
                                "ofType": {
                                    "kind": "LIST",
                                    "name": None,
                                    "ofType": {"kind": "OBJECT", "name": "User", "ofType": None},
                                },
                            },
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                    ],
                    "inputFields": None,
                    "interfaces": [],
                    "enumValues": None,
                    "possibleTypes": None,
                },
                {
                    "kind": "OBJECT",
                    "name": "Mutation",
                    "description": "Root mutation type",
                    "fields": [
                        {
                            "name": "createUser",
                            "description": "Create a new user",
                            "args": [
                                {
                                    "name": "input",
                                    "description": "User data",
                                    "type": {
                                        "kind": "NON_NULL",
                                        "name": None,
                                        "ofType": {"kind": "INPUT_OBJECT", "name": "CreateUserInput", "ofType": None},
                                    },
                                    "defaultValue": None,
                                }
                            ],
                            "type": {"kind": "OBJECT", "name": "User", "ofType": None},
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                    ],
                    "inputFields": None,
                    "interfaces": [],
                    "enumValues": None,
                    "possibleTypes": None,
                },
                {
                    "kind": "OBJECT",
                    "name": "User",
                    "description": "A user account",
                    "fields": [
                        {
                            "name": "id",
                            "description": None,
                            "args": [],
                            "type": {
                                "kind": "NON_NULL",
                                "name": None,
                                "ofType": {"kind": "SCALAR", "name": "ID", "ofType": None},
                            },
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                        {
                            "name": "name",
                            "description": "User display name",
                            "args": [],
                            "type": {"kind": "SCALAR", "name": "String", "ofType": None},
                            "isDeprecated": False,
                            "deprecationReason": None,
                        },
                        {
                            "name": "email",
                            "description": "User email",
                            "args": [],
                            "type": {"kind": "SCALAR", "name": "String", "ofType": None},
                            "isDeprecated": True,
                            "deprecationReason": "Use emailAddress instead",
                        },
                    ],
                    "inputFields": None,
                    "interfaces": [],
                    "enumValues": None,
                    "possibleTypes": None,
                },
                {
                    "kind": "INPUT_OBJECT",
                    "name": "CreateUserInput",
                    "description": "Input for creating a user",
                    "fields": None,
                    "inputFields": [
                        {
                            "name": "name",
                            "description": "User name",
                            "type": {
                                "kind": "NON_NULL",
                                "name": None,
                                "ofType": {"kind": "SCALAR", "name": "String", "ofType": None},
                            },
                            "defaultValue": None,
                        },
                        {
                            "name": "email",
                            "description": "Email address",
                            "type": {"kind": "SCALAR", "name": "String", "ofType": None},
                            "defaultValue": None,
                        },
                    ],
                    "interfaces": None,
                    "enumValues": None,
                    "possibleTypes": None,
                },
                {
                    "kind": "ENUM",
                    "name": "UserRole",
                    "description": "User roles",
                    "fields": None,
                    "inputFields": None,
                    "interfaces": None,
                    "enumValues": [
                        {"name": "ADMIN", "description": "Administrator", "isDeprecated": False, "deprecationReason": None},
                        {"name": "USER", "description": "Regular user", "isDeprecated": False, "deprecationReason": None},
                        {"name": "GUEST", "description": "Guest user", "isDeprecated": True, "deprecationReason": "Use USER"},
                    ],
                    "possibleTypes": None,
                },
                {
                    "kind": "SCALAR",
                    "name": "ID",
                    "description": "Built-in ID",
                    "fields": None,
                    "inputFields": None,
                    "interfaces": None,
                    "enumValues": None,
                    "possibleTypes": None,
                },
                {
                    "kind": "SCALAR",
                    "name": "String",
                    "description": "Built-in String",
                    "fields": None,
                    "inputFields": None,
                    "interfaces": None,
                    "enumValues": None,
                    "possibleTypes": None,
                },
                {
                    "kind": "SCALAR",
                    "name": "Int",
                    "description": "Built-in Int",
                    "fields": None,
                    "inputFields": None,
                    "interfaces": None,
                    "enumValues": None,
                    "possibleTypes": None,
                },
                {
                    "kind": "OBJECT",
                    "name": "__Schema",
                    "description": "Introspection schema",
                    "fields": [],
                    "inputFields": None,
                    "interfaces": [],
                    "enumValues": None,
                    "possibleTypes": None,
                },
            ],
            "directives": [
                {
                    "name": "skip",
                    "description": "Skip this field",
                    "locations": ["FIELD", "FRAGMENT_SPREAD"],
                    "args": [
                        {
                            "name": "if",
                            "description": "Skip when true",
                            "type": {
                                "kind": "NON_NULL",
                                "name": None,
                                "ofType": {"kind": "SCALAR", "name": "Boolean", "ofType": None},
                            },
                            "defaultValue": None,
                        }
                    ],
                }
            ],
        }
    }
}


class TestGraphQLTypeRef:
    """Tests for GraphQLTypeRef."""

    def test_scalar_type_display(self):
        """Scalar types display their name."""
        ref = GraphQLTypeRef(kind="SCALAR", name="String")
        assert ref.display_name() == "String"

    def test_non_null_type_display(self):
        """Non-null types display with !."""
        inner = GraphQLTypeRef(kind="SCALAR", name="String")
        ref = GraphQLTypeRef(kind="NON_NULL", of_type=inner)
        assert ref.display_name() == "String!"

    def test_list_type_display(self):
        """List types display with []."""
        inner = GraphQLTypeRef(kind="SCALAR", name="Int")
        ref = GraphQLTypeRef(kind="LIST", of_type=inner)
        assert ref.display_name() == "[Int]"

    def test_nested_type_display(self):
        """Nested wrappers display correctly."""
        scalar = GraphQLTypeRef(kind="SCALAR", name="User")
        list_type = GraphQLTypeRef(kind="LIST", of_type=scalar)
        non_null = GraphQLTypeRef(kind="NON_NULL", of_type=list_type)
        assert non_null.display_name() == "[User]!"

    def test_base_type_name_scalar(self):
        """Base type name for scalar."""
        ref = GraphQLTypeRef(kind="SCALAR", name="ID")
        assert ref.base_type_name() == "ID"

    def test_base_type_name_wrapped(self):
        """Base type name unwraps wrappers."""
        scalar = GraphQLTypeRef(kind="SCALAR", name="String")
        non_null = GraphQLTypeRef(kind="NON_NULL", of_type=scalar)
        assert non_null.base_type_name() == "String"


class TestParseTypeRef:
    """Tests for _parse_type_ref function."""

    def test_parse_none(self):
        """Parsing None returns None."""
        assert _parse_type_ref(None) is None

    def test_parse_scalar(self):
        """Parse scalar type."""
        data = {"kind": "SCALAR", "name": "String", "ofType": None}
        ref = _parse_type_ref(data)
        assert ref.kind == "SCALAR"
        assert ref.name == "String"
        assert ref.of_type is None

    def test_parse_non_null(self):
        """Parse non-null wrapper."""
        data = {
            "kind": "NON_NULL",
            "name": None,
            "ofType": {"kind": "SCALAR", "name": "ID", "ofType": None},
        }
        ref = _parse_type_ref(data)
        assert ref.kind == "NON_NULL"
        assert ref.of_type.kind == "SCALAR"
        assert ref.of_type.name == "ID"


class TestParseArg:
    """Tests for _parse_arg function."""

    def test_parse_basic_arg(self):
        """Parse a basic argument."""
        data = {
            "name": "id",
            "description": "The ID",
            "type": {"kind": "SCALAR", "name": "ID", "ofType": None},
            "defaultValue": None,
        }
        arg = _parse_arg(data)
        assert arg.name == "id"
        assert arg.description == "The ID"
        assert arg.type.name == "ID"
        assert arg.default_value is None

    def test_parse_arg_with_default(self):
        """Parse argument with default value."""
        data = {
            "name": "limit",
            "description": None,
            "type": {"kind": "SCALAR", "name": "Int", "ofType": None},
            "defaultValue": "10",
        }
        arg = _parse_arg(data)
        assert arg.name == "limit"
        assert arg.default_value == "10"


class TestParseField:
    """Tests for _parse_field function."""

    def test_parse_simple_field(self):
        """Parse a simple field."""
        data = {
            "name": "name",
            "description": "User name",
            "args": [],
            "type": {"kind": "SCALAR", "name": "String", "ofType": None},
            "isDeprecated": False,
            "deprecationReason": None,
        }
        field = _parse_field(data)
        assert field.name == "name"
        assert field.description == "User name"
        assert field.type.name == "String"
        assert not field.is_deprecated

    def test_parse_field_with_args(self):
        """Parse field with arguments."""
        data = {
            "name": "user",
            "description": None,
            "args": [
                {
                    "name": "id",
                    "description": None,
                    "type": {"kind": "SCALAR", "name": "ID", "ofType": None},
                    "defaultValue": None,
                }
            ],
            "type": {"kind": "OBJECT", "name": "User", "ofType": None},
            "isDeprecated": False,
            "deprecationReason": None,
        }
        field = _parse_field(data)
        assert field.name == "user"
        assert len(field.args) == 1
        assert field.args[0].name == "id"

    def test_parse_deprecated_field(self):
        """Parse deprecated field."""
        data = {
            "name": "oldField",
            "description": None,
            "args": [],
            "type": {"kind": "SCALAR", "name": "String", "ofType": None},
            "isDeprecated": True,
            "deprecationReason": "Use newField",
        }
        field = _parse_field(data)
        assert field.is_deprecated
        assert field.deprecation_reason == "Use newField"


class TestParseType:
    """Tests for _parse_type function."""

    def test_parse_object_type(self):
        """Parse object type with fields."""
        data = {
            "kind": "OBJECT",
            "name": "User",
            "description": "A user",
            "fields": [
                {
                    "name": "id",
                    "description": None,
                    "args": [],
                    "type": {"kind": "SCALAR", "name": "ID", "ofType": None},
                    "isDeprecated": False,
                    "deprecationReason": None,
                }
            ],
            "inputFields": None,
            "interfaces": [],
            "enumValues": None,
            "possibleTypes": None,
        }
        t = _parse_type(data)
        assert t.kind == "OBJECT"
        assert t.name == "User"
        assert len(t.fields) == 1
        assert t.fields[0].name == "id"

    def test_parse_enum_type(self):
        """Parse enum type with values."""
        data = {
            "kind": "ENUM",
            "name": "Status",
            "description": None,
            "fields": None,
            "inputFields": None,
            "interfaces": None,
            "enumValues": [
                {"name": "ACTIVE", "description": None, "isDeprecated": False, "deprecationReason": None},
                {"name": "INACTIVE", "description": None, "isDeprecated": False, "deprecationReason": None},
            ],
            "possibleTypes": None,
        }
        t = _parse_type(data)
        assert t.kind == "ENUM"
        assert len(t.enum_values) == 2
        assert t.enum_values[0].name == "ACTIVE"

    def test_parse_input_type(self):
        """Parse input object type."""
        data = {
            "kind": "INPUT_OBJECT",
            "name": "UserInput",
            "description": None,
            "fields": None,
            "inputFields": [
                {
                    "name": "name",
                    "description": None,
                    "type": {"kind": "SCALAR", "name": "String", "ofType": None},
                    "defaultValue": None,
                }
            ],
            "interfaces": None,
            "enumValues": None,
            "possibleTypes": None,
        }
        t = _parse_type(data)
        assert t.kind == "INPUT_OBJECT"
        assert len(t.input_fields) == 1
        assert t.input_fields[0].name == "name"


class TestGraphQLParser:
    """Tests for GraphQLParser."""

    def test_parse_introspection_result(self):
        """Parse a full introspection result."""
        parser = GraphQLParser()
        spec = parser.parse_introspection_result("http://example.com/graphql", SAMPLE_INTROSPECTION)
        
        assert spec.endpoint == "http://example.com/graphql"
        assert spec.query_type == "Query"
        assert spec.mutation_type == "Mutation"
        assert spec.subscription_type is None

    def test_parse_types(self):
        """Parsed spec contains types."""
        parser = GraphQLParser()
        spec = parser.parse_introspection_result("http://example.com/graphql", SAMPLE_INTROSPECTION)
        
        assert "User" in spec.types
        assert "Query" in spec.types
        assert "Mutation" in spec.types
        
        user_type = spec.types["User"]
        assert user_type.kind == "OBJECT"
        assert len(user_type.fields) == 3

    def test_parse_directives(self):
        """Parsed spec contains directives."""
        parser = GraphQLParser()
        spec = parser.parse_introspection_result("http://example.com/graphql", SAMPLE_INTROSPECTION)
        
        assert len(spec.directives) == 1
        assert spec.directives[0].name == "skip"
        assert "FIELD" in spec.directives[0].locations

    def test_parse_missing_schema_raises(self):
        """Missing schema data raises error."""
        parser = GraphQLParser()
        with pytest.raises(SpecParseError):
            parser.parse_introspection_result("http://example.com/graphql", {"data": {}})


class TestGraphQLSpec:
    """Tests for GraphQLSpec."""

    def test_get_operations(self):
        """get_operations returns all queries and mutations."""
        parser = GraphQLParser()
        spec = parser.parse_introspection_result("http://example.com/graphql", SAMPLE_INTROSPECTION)
        
        operations = spec.get_operations()
        assert len(operations) == 3  # 2 queries + 1 mutation
        
        op_names = [op.name for op in operations]
        assert "user" in op_names
        assert "users" in op_names
        assert "createUser" in op_names

    def test_operation_types(self):
        """Operations have correct operation_type."""
        parser = GraphQLParser()
        spec = parser.parse_introspection_result("http://example.com/graphql", SAMPLE_INTROSPECTION)
        
        operations = spec.get_operations()
        queries = [op for op in operations if op.operation_type == "query"]
        mutations = [op for op in operations if op.operation_type == "mutation"]
        
        assert len(queries) == 2
        assert len(mutations) == 1

    def test_get_user_types(self):
        """get_user_types excludes builtins."""
        parser = GraphQLParser()
        spec = parser.parse_introspection_result("http://example.com/graphql", SAMPLE_INTROSPECTION)
        
        user_types = spec.get_user_types()
        type_names = [t.name for t in user_types]
        
        assert "User" in type_names
        assert "Query" in type_names
        assert "__Schema" not in type_names

    def test_type_is_builtin(self):
        """Types starting with __ are builtin."""
        parser = GraphQLParser()
        spec = parser.parse_introspection_result("http://example.com/graphql", SAMPLE_INTROSPECTION)
        
        assert spec.types["__Schema"].is_builtin()
        assert not spec.types["User"].is_builtin()


class TestBuildQuery:
    """Tests for build_query function."""

    def test_build_simple_query(self):
        """Build query for operation without args."""
        op = GraphQLOperation(
            name="currentUser",
            type=GraphQLTypeRef(kind="OBJECT", name="User"),
            args=(),
            operation_type="query",
        )
        result = build_query(op)
        assert "query" in result
        assert "currentUser" in result["query"]
        assert result["variables"] == {}

    def test_build_query_with_args(self):
        """Build query with arguments."""
        op = GraphQLOperation(
            name="user",
            type=GraphQLTypeRef(kind="OBJECT", name="User"),
            args=(
                GraphQLArg(
                    name="id",
                    type=GraphQLTypeRef(
                        kind="NON_NULL",
                        of_type=GraphQLTypeRef(kind="SCALAR", name="ID"),
                    ),
                ),
            ),
            operation_type="query",
        )
        result = build_query(op, variables={"id": "123"})
        assert "$id: ID!" in result["query"]
        assert "id: $id" in result["query"]
        assert result["variables"]["id"] == "123"

    def test_build_mutation(self):
        """Build mutation query."""
        op = GraphQLOperation(
            name="createUser",
            type=GraphQLTypeRef(kind="OBJECT", name="User"),
            args=(
                GraphQLArg(
                    name="name",
                    type=GraphQLTypeRef(kind="SCALAR", name="String"),
                ),
            ),
            operation_type="mutation",
        )
        result = build_query(op, variables={"name": "Test"})
        assert result["query"].startswith("mutation")

    def test_build_query_with_selection(self):
        """Build query with field selection."""
        op = GraphQLOperation(
            name="user",
            type=GraphQLTypeRef(kind="OBJECT", name="User"),
            args=(
                GraphQLArg(
                    name="id",
                    type=GraphQLTypeRef(kind="SCALAR", name="ID"),
                ),
            ),
            operation_type="query",
        )
        result = build_query(op, variables={"id": "1"}, selection="id name email")
        assert "{ id name email }" in result["query"]


class TestGraphQLOperation:
    """Tests for GraphQLOperation."""

    def test_display_name_query(self):
        """Display name includes operation type prefix."""
        op = GraphQLOperation(
            name="getUser",
            type=GraphQLTypeRef(kind="OBJECT", name="User"),
            operation_type="query",
        )
        assert op.display_name == "[Q] getUser"

    def test_display_name_mutation(self):
        """Mutation display name."""
        op = GraphQLOperation(
            name="updateUser",
            type=GraphQLTypeRef(kind="OBJECT", name="User"),
            operation_type="mutation",
        )
        assert op.display_name == "[M] updateUser"
