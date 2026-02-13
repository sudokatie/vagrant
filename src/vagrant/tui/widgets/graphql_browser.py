"""GraphQL operation browser widget for TUI."""

from __future__ import annotations

from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from vagrant.parser.graphql import GraphQLOperation, GraphQLSpec


class GraphQLOperationSelected(Message):
    """Message sent when a GraphQL operation is selected."""

    def __init__(self, operation: GraphQLOperation) -> None:
        self.operation = operation
        super().__init__()


class GraphQLBrowser(Tree[GraphQLOperation]):
    """Tree view of GraphQL operations.
    
    Displays queries, mutations, and subscriptions grouped by type.
    Tracks which operations have been visited.
    Emits GraphQLOperationSelected message when clicked.
    """

    DEFAULT_CSS = """
    GraphQLBrowser {
        height: 100%;
    }
    
    GraphQLBrowser > .tree--label {
        padding: 0 1;
    }
    
    GraphQLBrowser .op-query {
        color: $success;
    }
    
    GraphQLBrowser .op-mutation {
        color: $warning;
    }
    
    GraphQLBrowser .op-subscription {
        color: $primary;
    }
    
    GraphQLBrowser .visited {
        text-style: dim;
    }
    
    GraphQLBrowser .deprecated {
        text-style: strike;
    }
    """

    def __init__(
        self,
        spec: GraphQLSpec,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the GraphQL browser.
        
        Args:
            spec: GraphQL specification to display.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__("GraphQL API", id=id, classes=classes)
        self.spec = spec
        self._filter_query: str = ""
        self._visited: set[tuple[str, str]] = set()  # (type, name) tuples
        self._build_tree()

    def _build_tree(self) -> None:
        """Build the operation tree from spec."""
        self.clear()
        self.root.expand()

        operations = self.spec.get_operations()

        # Group by operation type
        queries = [op for op in operations if op.operation_type == "query"]
        mutations = [op for op in operations if op.operation_type == "mutation"]
        subscriptions = [op for op in operations if op.operation_type == "subscription"]

        # Build tree structure
        if queries:
            self._add_operation_group("Queries", queries, "query")

        if mutations:
            self._add_operation_group("Mutations", mutations, "mutation")

        if subscriptions:
            self._add_operation_group("Subscriptions", subscriptions, "subscription")

    def _add_operation_group(
        self,
        title: str,
        ops: list[GraphQLOperation],
        op_type: str,
    ) -> None:
        """Add a group of operations to the tree."""
        # Filter if query is set
        if self._filter_query:
            ops = [op for op in ops if self._matches_filter(op)]
            if not ops:
                return

        group_node = self.root.add(f"[bold]{title}[/bold]")
        group_node.expand()

        for op in ops:
            label = self._format_operation(op)
            group_node.add_leaf(label, data=op)

    def _format_operation(self, op: GraphQLOperation) -> str:
        """Format operation for display."""
        op_class = f"op-{op.operation_type}"
        op_badge = f"[{op_class}]{op.operation_type[0].upper()}[/{op_class}]"

        name = op.name
        if len(name) > 35:
            name = name[:32] + "..."

        deprecated = " [dim deprecated](deprecated)[/dim deprecated]" if op.is_deprecated else ""
        visited = " [dim]✓[/dim]" if self.is_visited(op) else ""

        # Show return type hint
        return_type = f"[dim]-> {op.type.display_name()}[/dim]"

        return f"{op_badge} {name} {return_type}{deprecated}{visited}"

    def mark_visited(self, op: GraphQLOperation) -> None:
        """Mark an operation as visited.
        
        Args:
            op: Operation that was executed.
        """
        self._visited.add((op.operation_type, op.name))
        self._build_tree()

    def is_visited(self, op: GraphQLOperation) -> bool:
        """Check if an operation has been visited.
        
        Args:
            op: Operation to check.
            
        Returns:
            True if the operation has been visited.
        """
        return (op.operation_type, op.name) in self._visited

    def get_visited_count(self) -> int:
        """Return the number of visited operations."""
        return len(self._visited)

    def clear_visited(self) -> None:
        """Clear all visited markers."""
        self._visited.clear()
        self._build_tree()

    def _matches_filter(self, op: GraphQLOperation) -> bool:
        """Check if operation matches current filter."""
        query = self._filter_query.lower()

        if query in op.name.lower():
            return True
        if op.description and query in op.description.lower():
            return True
        if query in op.operation_type.lower():
            return True

        return False

    def filter(self, query: str) -> None:
        """Filter operations by search query.
        
        Args:
            query: Search string to filter by.
        """
        self._filter_query = query
        self._build_tree()

    def clear_filter(self) -> None:
        """Clear the current filter."""
        self._filter_query = ""
        self._build_tree()

    @property
    def selected_operation(self) -> GraphQLOperation | None:
        """Return the currently selected operation, if any."""
        node = self.cursor_node
        if node and node.data:
            return node.data
        return None

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle node selection."""
        if event.node.data is None:
            return

        op = event.node.data
        if isinstance(op, GraphQLOperation):
            self.post_message(GraphQLOperationSelected(op))

    def get_queries(self) -> list[GraphQLOperation]:
        """Return all query operations."""
        return [op for op in self.spec.get_operations() if op.operation_type == "query"]

    def get_mutations(self) -> list[GraphQLOperation]:
        """Return all mutation operations."""
        return [op for op in self.spec.get_operations() if op.operation_type == "mutation"]

    def get_subscriptions(self) -> list[GraphQLOperation]:
        """Return all subscription operations."""
        return [op for op in self.spec.get_operations() if op.operation_type == "subscription"]

    def get_all_operations(self) -> list[GraphQLOperation]:
        """Return all operations."""
        return self.spec.get_operations()

    def select_operation(self, op: GraphQLOperation) -> None:
        """Programmatically select an operation.
        
        Args:
            op: Operation to select.
        """
        def find_node(node: TreeNode) -> TreeNode | None:
            if node.data is op:
                return node
            for child in node.children:
                result = find_node(child)
                if result:
                    return result
            return None

        target = find_node(self.root)
        if target:
            self.select_node(target)
