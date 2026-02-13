"""Tests for GraphQL TUI widgets."""

from __future__ import annotations

import pytest

from vagrant.parser.graphql import (
    GraphQLArg,
    GraphQLField,
    GraphQLOperation,
    GraphQLSpec,
    GraphQLType,
    GraphQLTypeRef,
    build_query,
)
from vagrant.tui.widgets.graphql_browser import GraphQLBrowser, GraphQLOperationSelected
from vagrant.tui.widgets.graphql_builder import GraphQLBuilder, GraphQLRequestSent


@pytest.fixture
def sample_spec() -> GraphQLSpec:
    """Create a sample GraphQL spec for testing."""
    # Create type references
    string_type = GraphQLTypeRef(kind="SCALAR", name="String")
    int_type = GraphQLTypeRef(kind="SCALAR", name="Int")
    user_type = GraphQLTypeRef(kind="OBJECT", name="User")
    
    # Create user type fields
    user_fields = (
        GraphQLField(name="id", type=int_type),
        GraphQLField(name="name", type=string_type),
        GraphQLField(name="email", type=string_type),
    )
    
    # Create query type fields
    query_fields = (
        GraphQLField(
            name="user",
            type=user_type,
            args=(
                GraphQLArg(name="id", type=GraphQLTypeRef(kind="NON_NULL", of_type=int_type)),
            ),
        ),
        GraphQLField(
            name="users",
            type=GraphQLTypeRef(kind="LIST", of_type=user_type),
        ),
    )
    
    # Create mutation type fields
    mutation_fields = (
        GraphQLField(
            name="createUser",
            type=user_type,
            args=(
                GraphQLArg(name="name", type=GraphQLTypeRef(kind="NON_NULL", of_type=string_type)),
                GraphQLArg(name="email", type=string_type),
            ),
        ),
    )
    
    # Create types
    types = {
        "Query": GraphQLType(kind="OBJECT", name="Query", fields=query_fields),
        "Mutation": GraphQLType(kind="OBJECT", name="Mutation", fields=mutation_fields),
        "User": GraphQLType(kind="OBJECT", name="User", fields=user_fields),
        "String": GraphQLType(kind="SCALAR", name="String"),
        "Int": GraphQLType(kind="SCALAR", name="Int"),
    }
    
    return GraphQLSpec(
        endpoint="https://api.example.com/graphql",
        query_type="Query",
        mutation_type="Mutation",
        subscription_type=None,
        types=types,
    )


class TestGraphQLBrowser:
    """Tests for GraphQLBrowser widget."""

    def test_init_with_spec(self, sample_spec):
        """Browser initializes with spec."""
        browser = GraphQLBrowser(sample_spec)
        assert browser.spec == sample_spec

    def test_get_all_operations(self, sample_spec):
        """Browser returns all operations."""
        browser = GraphQLBrowser(sample_spec)
        ops = browser.get_all_operations()
        assert len(ops) == 3  # 2 queries + 1 mutation

    def test_get_queries(self, sample_spec):
        """Browser filters queries."""
        browser = GraphQLBrowser(sample_spec)
        queries = browser.get_queries()
        assert len(queries) == 2
        assert all(op.operation_type == "query" for op in queries)

    def test_get_mutations(self, sample_spec):
        """Browser filters mutations."""
        browser = GraphQLBrowser(sample_spec)
        mutations = browser.get_mutations()
        assert len(mutations) == 1
        assert mutations[0].operation_type == "mutation"
        assert mutations[0].name == "createUser"

    def test_get_subscriptions_empty(self, sample_spec):
        """Browser returns empty for no subscriptions."""
        browser = GraphQLBrowser(sample_spec)
        subs = browser.get_subscriptions()
        assert len(subs) == 0

    def test_mark_visited(self, sample_spec):
        """Browser tracks visited operations."""
        browser = GraphQLBrowser(sample_spec)
        ops = browser.get_all_operations()
        
        assert not browser.is_visited(ops[0])
        browser.mark_visited(ops[0])
        assert browser.is_visited(ops[0])
        assert browser.get_visited_count() == 1

    def test_clear_visited(self, sample_spec):
        """Browser clears visited markers."""
        browser = GraphQLBrowser(sample_spec)
        ops = browser.get_all_operations()
        
        browser.mark_visited(ops[0])
        assert browser.get_visited_count() == 1
        
        browser.clear_visited()
        assert browser.get_visited_count() == 0

    def test_filter_operations(self, sample_spec):
        """Browser filters by search query."""
        browser = GraphQLBrowser(sample_spec)
        
        browser.filter("user")
        # Should match "user" and "users" queries
        ops = [op for op in browser.get_all_operations() if browser._matches_filter(op)]
        assert len(ops) >= 2

    def test_clear_filter(self, sample_spec):
        """Browser clears filter."""
        browser = GraphQLBrowser(sample_spec)
        
        browser.filter("xyz")
        browser.clear_filter()
        assert browser._filter_query == ""


class TestGraphQLBuilder:
    """Tests for GraphQLBuilder widget."""

    def test_init(self):
        """Builder initializes without operation."""
        builder = GraphQLBuilder()
        assert builder._operation is None

    def test_get_request_data_none(self):
        """Builder returns None when no operation set."""
        builder = GraphQLBuilder()
        assert builder.get_request_data() is None


class TestBuildQuery:
    """Tests for query building."""

    def test_simple_query(self):
        """Build simple query without args."""
        op = GraphQLOperation(
            name="users",
            type=GraphQLTypeRef(kind="LIST", of_type=GraphQLTypeRef(kind="OBJECT", name="User")),
            operation_type="query",
        )
        
        result = build_query(op, selection="id name")
        assert "query" in result
        assert "users" in result["query"]
        assert "id name" in result["query"]

    def test_query_with_args(self):
        """Build query with arguments."""
        op = GraphQLOperation(
            name="user",
            type=GraphQLTypeRef(kind="OBJECT", name="User"),
            args=(
                GraphQLArg(
                    name="id",
                    type=GraphQLTypeRef(kind="NON_NULL", of_type=GraphQLTypeRef(kind="SCALAR", name="Int")),
                ),
            ),
            operation_type="query",
        )
        
        result = build_query(op, variables={"id": 123}, selection="id name email")
        assert "query($id: Int!)" in result["query"]
        assert "user(id: $id)" in result["query"]
        assert result["variables"] == {"id": 123}

    def test_mutation(self):
        """Build mutation query."""
        op = GraphQLOperation(
            name="createUser",
            type=GraphQLTypeRef(kind="OBJECT", name="User"),
            args=(
                GraphQLArg(
                    name="name",
                    type=GraphQLTypeRef(kind="NON_NULL", of_type=GraphQLTypeRef(kind="SCALAR", name="String")),
                ),
            ),
            operation_type="mutation",
        )
        
        result = build_query(op, variables={"name": "John"}, selection="id name")
        assert "mutation($name: String!)" in result["query"]
        assert "createUser(name: $name)" in result["query"]

    def test_empty_selection(self):
        """Build query without selection for scalar return."""
        op = GraphQLOperation(
            name="count",
            type=GraphQLTypeRef(kind="SCALAR", name="Int"),
            operation_type="query",
        )
        
        result = build_query(op)
        assert "count" in result["query"]
        # No curly braces for scalar return
        assert "{" not in result["query"] or "{ count }" in result["query"]


class TestGraphQLTypeRef:
    """Tests for type reference display."""

    def test_scalar_display(self):
        """Scalar type displays name."""
        t = GraphQLTypeRef(kind="SCALAR", name="String")
        assert t.display_name() == "String"

    def test_non_null_display(self):
        """Non-null wraps type with !."""
        t = GraphQLTypeRef(
            kind="NON_NULL",
            of_type=GraphQLTypeRef(kind="SCALAR", name="Int"),
        )
        assert t.display_name() == "Int!"

    def test_list_display(self):
        """List wraps type with []."""
        t = GraphQLTypeRef(
            kind="LIST",
            of_type=GraphQLTypeRef(kind="OBJECT", name="User"),
        )
        assert t.display_name() == "[User]"

    def test_nested_display(self):
        """Nested types display correctly."""
        t = GraphQLTypeRef(
            kind="NON_NULL",
            of_type=GraphQLTypeRef(
                kind="LIST",
                of_type=GraphQLTypeRef(kind="OBJECT", name="User"),
            ),
        )
        assert t.display_name() == "[User]!"

    def test_base_type_name(self):
        """Base type name unwraps wrappers."""
        t = GraphQLTypeRef(
            kind="NON_NULL",
            of_type=GraphQLTypeRef(
                kind="LIST",
                of_type=GraphQLTypeRef(kind="OBJECT", name="User"),
            ),
        )
        assert t.base_type_name() == "User"


class TestGraphQLOperation:
    """Tests for GraphQL operation."""

    def test_display_name_query(self):
        """Query operation display name."""
        op = GraphQLOperation(
            name="getUser",
            type=GraphQLTypeRef(kind="OBJECT", name="User"),
            operation_type="query",
        )
        assert "[Q]" in op.display_name
        assert "getUser" in op.display_name

    def test_display_name_mutation(self):
        """Mutation operation display name."""
        op = GraphQLOperation(
            name="createUser",
            type=GraphQLTypeRef(kind="OBJECT", name="User"),
            operation_type="mutation",
        )
        assert "[M]" in op.display_name
        assert "createUser" in op.display_name
