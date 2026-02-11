"""GraphQL schema parser via introspection.

Fetches and parses GraphQL schemas using the standard introspection query.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx

from vagrant.core.errors import SpecParseError

# Standard GraphQL introspection query
INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    subscriptionType { name }
    types {
      kind
      name
      description
      fields(includeDeprecated: true) {
        name
        description
        args {
          name
          description
          type { ...TypeRef }
          defaultValue
        }
        type { ...TypeRef }
        isDeprecated
        deprecationReason
      }
      inputFields {
        name
        description
        type { ...TypeRef }
        defaultValue
      }
      interfaces { ...TypeRef }
      enumValues(includeDeprecated: true) {
        name
        description
        isDeprecated
        deprecationReason
      }
      possibleTypes { ...TypeRef }
    }
    directives {
      name
      description
      locations
      args {
        name
        description
        type { ...TypeRef }
        defaultValue
      }
    }
  }
}

fragment TypeRef on __Type {
  kind
  name
  ofType {
    kind
    name
    ofType {
      kind
      name
      ofType {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
            }
          }
        }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class GraphQLTypeRef:
    """Reference to a GraphQL type.
    
    Handles wrapped types (NonNull, List) via kind and of_type.
    """
    kind: str  # SCALAR, OBJECT, INTERFACE, UNION, ENUM, INPUT_OBJECT, LIST, NON_NULL
    name: str | None = None
    of_type: GraphQLTypeRef | None = None

    def display_name(self) -> str:
        """Human-readable type name."""
        if self.kind == "NON_NULL":
            return f"{self.of_type.display_name() if self.of_type else '?'}!"
        if self.kind == "LIST":
            return f"[{self.of_type.display_name() if self.of_type else '?'}]"
        return self.name or "Unknown"

    def base_type_name(self) -> str | None:
        """Get the underlying type name without wrappers."""
        if self.kind in ("NON_NULL", "LIST") and self.of_type:
            return self.of_type.base_type_name()
        return self.name


@dataclass(frozen=True)
class GraphQLArg:
    """GraphQL field argument."""
    name: str
    type: GraphQLTypeRef
    description: str | None = None
    default_value: str | None = None


@dataclass(frozen=True)
class GraphQLField:
    """GraphQL object field."""
    name: str
    type: GraphQLTypeRef
    description: str | None = None
    args: tuple[GraphQLArg, ...] = ()
    is_deprecated: bool = False
    deprecation_reason: str | None = None


@dataclass(frozen=True)
class GraphQLEnumValue:
    """GraphQL enum value."""
    name: str
    description: str | None = None
    is_deprecated: bool = False
    deprecation_reason: str | None = None


@dataclass(frozen=True)
class GraphQLInputField:
    """GraphQL input object field."""
    name: str
    type: GraphQLTypeRef
    description: str | None = None
    default_value: str | None = None


@dataclass(frozen=True)
class GraphQLType:
    """GraphQL type definition."""
    kind: str
    name: str
    description: str | None = None
    fields: tuple[GraphQLField, ...] = ()
    input_fields: tuple[GraphQLInputField, ...] = ()
    enum_values: tuple[GraphQLEnumValue, ...] = ()
    interfaces: tuple[GraphQLTypeRef, ...] = ()
    possible_types: tuple[GraphQLTypeRef, ...] = ()

    def is_builtin(self) -> bool:
        """Check if this is a built-in type (starts with __)."""
        return self.name.startswith("__") if self.name else False


@dataclass(frozen=True)
class GraphQLDirective:
    """GraphQL directive definition."""
    name: str
    description: str | None = None
    locations: tuple[str, ...] = ()
    args: tuple[GraphQLArg, ...] = ()


@dataclass(frozen=True)
class GraphQLOperation:
    """A query, mutation, or subscription field."""
    name: str
    type: GraphQLTypeRef
    description: str | None = None
    args: tuple[GraphQLArg, ...] = ()
    operation_type: str = "query"  # query, mutation, subscription
    is_deprecated: bool = False
    deprecation_reason: str | None = None

    @property
    def display_name(self) -> str:
        """Human-friendly name."""
        prefix = self.operation_type[0].upper()
        return f"[{prefix}] {self.name}"


@dataclass(frozen=True)
class GraphQLSpec:
    """Complete GraphQL schema specification."""
    endpoint: str
    query_type: str | None = None
    mutation_type: str | None = None
    subscription_type: str | None = None
    types: dict[str, GraphQLType] = field(default_factory=dict)
    directives: tuple[GraphQLDirective, ...] = ()

    def get_operations(self) -> list[GraphQLOperation]:
        """Get all queries, mutations, and subscriptions."""
        operations: list[GraphQLOperation] = []

        # Get queries
        if self.query_type and self.query_type in self.types:
            query_obj = self.types[self.query_type]
            for f in query_obj.fields:
                operations.append(GraphQLOperation(
                    name=f.name,
                    type=f.type,
                    description=f.description,
                    args=f.args,
                    operation_type="query",
                    is_deprecated=f.is_deprecated,
                    deprecation_reason=f.deprecation_reason,
                ))

        # Get mutations
        if self.mutation_type and self.mutation_type in self.types:
            mutation_obj = self.types[self.mutation_type]
            for f in mutation_obj.fields:
                operations.append(GraphQLOperation(
                    name=f.name,
                    type=f.type,
                    description=f.description,
                    args=f.args,
                    operation_type="mutation",
                    is_deprecated=f.is_deprecated,
                    deprecation_reason=f.deprecation_reason,
                ))

        # Get subscriptions
        if self.subscription_type and self.subscription_type in self.types:
            sub_obj = self.types[self.subscription_type]
            for f in sub_obj.fields:
                operations.append(GraphQLOperation(
                    name=f.name,
                    type=f.type,
                    description=f.description,
                    args=f.args,
                    operation_type="subscription",
                    is_deprecated=f.is_deprecated,
                    deprecation_reason=f.deprecation_reason,
                ))

        return operations

    def get_user_types(self) -> list[GraphQLType]:
        """Get non-builtin types."""
        return [t for t in self.types.values() if not t.is_builtin()]


def _parse_type_ref(data: dict[str, Any] | None) -> GraphQLTypeRef | None:
    """Parse a type reference from introspection data."""
    if not data:
        return None
    return GraphQLTypeRef(
        kind=data.get("kind", "SCALAR"),
        name=data.get("name"),
        of_type=_parse_type_ref(data.get("ofType")),
    )


def _parse_arg(data: dict[str, Any]) -> GraphQLArg:
    """Parse an argument from introspection data."""
    return GraphQLArg(
        name=data.get("name", ""),
        type=_parse_type_ref(data.get("type")) or GraphQLTypeRef(kind="SCALAR", name="String"),
        description=data.get("description"),
        default_value=data.get("defaultValue"),
    )


def _parse_field(data: dict[str, Any]) -> GraphQLField:
    """Parse a field from introspection data."""
    args = tuple(_parse_arg(a) for a in data.get("args", []))
    return GraphQLField(
        name=data.get("name", ""),
        type=_parse_type_ref(data.get("type")) or GraphQLTypeRef(kind="SCALAR", name="String"),
        description=data.get("description"),
        args=args,
        is_deprecated=data.get("isDeprecated", False),
        deprecation_reason=data.get("deprecationReason"),
    )


def _parse_input_field(data: dict[str, Any]) -> GraphQLInputField:
    """Parse an input field from introspection data."""
    return GraphQLInputField(
        name=data.get("name", ""),
        type=_parse_type_ref(data.get("type")) or GraphQLTypeRef(kind="SCALAR", name="String"),
        description=data.get("description"),
        default_value=data.get("defaultValue"),
    )


def _parse_enum_value(data: dict[str, Any]) -> GraphQLEnumValue:
    """Parse an enum value from introspection data."""
    return GraphQLEnumValue(
        name=data.get("name", ""),
        description=data.get("description"),
        is_deprecated=data.get("isDeprecated", False),
        deprecation_reason=data.get("deprecationReason"),
    )


def _parse_type(data: dict[str, Any]) -> GraphQLType:
    """Parse a type from introspection data."""
    fields = tuple(_parse_field(f) for f in data.get("fields") or [])
    input_fields = tuple(_parse_input_field(f) for f in data.get("inputFields") or [])
    enum_values = tuple(_parse_enum_value(v) for v in data.get("enumValues") or [])
    interfaces = tuple(_parse_type_ref(i) for i in data.get("interfaces") or [] if i)
    possible_types = tuple(_parse_type_ref(p) for p in data.get("possibleTypes") or [] if p)

    return GraphQLType(
        kind=data.get("kind", "OBJECT"),
        name=data.get("name", ""),
        description=data.get("description"),
        fields=fields,
        input_fields=input_fields,
        enum_values=enum_values,
        interfaces=tuple(i for i in interfaces if i),
        possible_types=tuple(p for p in possible_types if p),
    )


def _parse_directive(data: dict[str, Any]) -> GraphQLDirective:
    """Parse a directive from introspection data."""
    args = tuple(_parse_arg(a) for a in data.get("args", []))
    return GraphQLDirective(
        name=data.get("name", ""),
        description=data.get("description"),
        locations=tuple(data.get("locations", [])),
        args=args,
    )


class GraphQLParser:
    """Parser for GraphQL schemas via introspection."""

    def __init__(self, timeout: float = 30.0):
        """Initialize parser.
        
        Args:
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout

    async def parse_endpoint(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
    ) -> GraphQLSpec:
        """Fetch and parse a GraphQL schema via introspection.
        
        Args:
            endpoint: GraphQL endpoint URL.
            headers: Optional headers (e.g., authorization).
            
        Returns:
            Parsed GraphQL specification.
            
        Raises:
            SpecParseError: If introspection fails or response is invalid.
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    endpoint,
                    json={"query": INTROSPECTION_QUERY},
                    headers=headers or {},
                )
                response.raise_for_status()
            except httpx.HTTPError as e:
                raise SpecParseError(f"Failed to fetch GraphQL schema: {e}")

            try:
                data = response.json()
            except json.JSONDecodeError as e:
                raise SpecParseError(f"Invalid JSON response: {e}")

            if "errors" in data:
                errors = data["errors"]
                msg = errors[0].get("message", "Unknown error") if errors else "Unknown error"
                raise SpecParseError(f"GraphQL introspection failed: {msg}")

            schema_data = data.get("data", {}).get("__schema")
            if not schema_data:
                raise SpecParseError("No schema data in introspection response")

            return self._parse_schema(endpoint, schema_data)

    def parse_introspection_result(
        self,
        endpoint: str,
        data: dict[str, Any],
    ) -> GraphQLSpec:
        """Parse a pre-fetched introspection result.
        
        Args:
            endpoint: GraphQL endpoint URL (for reference).
            data: The introspection query result data.
            
        Returns:
            Parsed GraphQL specification.
        """
        schema_data = data.get("data", {}).get("__schema") or data.get("__schema")
        if not schema_data:
            raise SpecParseError("No schema data in introspection result")
        return self._parse_schema(endpoint, schema_data)

    def _parse_schema(
        self,
        endpoint: str,
        schema_data: dict[str, Any],
    ) -> GraphQLSpec:
        """Parse schema data into GraphQLSpec."""
        query_type = schema_data.get("queryType", {}).get("name")
        mutation_type = schema_data.get("mutationType", {}).get("name") if schema_data.get("mutationType") else None
        subscription_type = schema_data.get("subscriptionType", {}).get("name") if schema_data.get("subscriptionType") else None

        types_data = schema_data.get("types", [])
        types = {t["name"]: _parse_type(t) for t in types_data if t.get("name")}

        directives_data = schema_data.get("directives", [])
        directives = tuple(_parse_directive(d) for d in directives_data)

        return GraphQLSpec(
            endpoint=endpoint,
            query_type=query_type,
            mutation_type=mutation_type,
            subscription_type=subscription_type,
            types=types,
            directives=directives,
        )


def build_query(
    operation: GraphQLOperation,
    variables: dict[str, Any] | None = None,
    selection: str | None = None,
) -> dict[str, Any]:
    """Build a GraphQL query document for an operation.
    
    Args:
        operation: The operation to build a query for.
        variables: Variable values to include.
        selection: Field selection (default: all scalar fields).
        
    Returns:
        Dict with query and variables keys ready for POST.
    """
    # Build variable definitions
    var_defs = []
    for arg in operation.args:
        var_defs.append(f"${arg.name}: {arg.type.display_name()}")

    var_def_str = f"({', '.join(var_defs)})" if var_defs else ""

    # Build argument applications
    arg_apps = []
    for arg in operation.args:
        arg_apps.append(f"{arg.name}: ${arg.name}")

    arg_app_str = f"({', '.join(arg_apps)})" if arg_apps else ""

    # Default selection is just the operation (for scalar return types)
    # For objects, caller should provide selection
    field_selection = selection or ""
    if field_selection:
        field_selection = f" {{ {field_selection} }}"

    op_type = operation.operation_type
    query = f"{op_type}{var_def_str} {{ {operation.name}{arg_app_str}{field_selection} }}"

    return {
        "query": query,
        "variables": variables or {},
    }
