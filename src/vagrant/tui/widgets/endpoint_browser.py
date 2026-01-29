"""Endpoint browser widget for TUI."""

from __future__ import annotations

from textual.message import Message
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from vagrant.parser.models import ApiSpec, Operation


class EndpointSelected(Message):
    """Message sent when an endpoint is selected."""

    def __init__(self, operation: Operation) -> None:
        self.operation = operation
        super().__init__()


class EndpointBrowser(Tree[Operation]):
    """Tree view of API endpoints.
    
    Displays endpoints grouped by tag, with method badges.
    Emits EndpointSelected message when an endpoint is clicked.
    """

    DEFAULT_CSS = """
    EndpointBrowser {
        height: 100%;
    }
    
    EndpointBrowser > .tree--label {
        padding: 0 1;
    }
    
    EndpointBrowser .method-get {
        color: $success;
    }
    
    EndpointBrowser .method-post {
        color: $primary;
    }
    
    EndpointBrowser .method-put {
        color: $warning;
    }
    
    EndpointBrowser .method-patch {
        color: $warning;
    }
    
    EndpointBrowser .method-delete {
        color: $error;
    }
    """

    def __init__(
        self,
        spec: ApiSpec,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the endpoint browser.
        
        Args:
            spec: API specification to display.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(spec.title, id=id, classes=classes)
        self.spec = spec
        self._filter_query: str = ""
        self._build_tree()

    def _build_tree(self) -> None:
        """Build the endpoint tree from spec."""
        self.clear()
        self.root.expand()

        # Group operations by tag
        tags: dict[str, list[Operation]] = {}
        for op in self.spec.operations:
            tag = op.tags[0] if op.tags else "default"
            if tag not in tags:
                tags[tag] = []
            tags[tag].append(op)

        # Build tree structure
        for tag, ops in sorted(tags.items()):
            # Filter if query is set
            if self._filter_query:
                ops = [
                    op for op in ops
                    if self._matches_filter(op)
                ]
                if not ops:
                    continue

            tag_node = self.root.add(f"[bold]{tag}[/bold]")
            tag_node.expand()

            for op in ops:
                label = self._format_operation(op)
                tag_node.add_leaf(label, data=op)

    def _format_operation(self, op: Operation) -> str:
        """Format operation for display."""
        method_class = f"method-{op.method.lower()}"
        method_badge = f"[{method_class}]{op.method:7}[/{method_class}]"

        path = op.path
        if len(path) > 40:
            path = path[:37] + "..."

        deprecated = " [dim](deprecated)[/dim]" if op.deprecated else ""

        return f"{method_badge} {path}{deprecated}"

    def _matches_filter(self, op: Operation) -> bool:
        """Check if operation matches current filter."""
        query = self._filter_query.lower()

        # Match against method, path, summary, operation_id
        if query in op.method.lower():
            return True
        if query in op.path.lower():
            return True
        if op.summary and query in op.summary.lower():
            return True
        if op.operation_id and query in op.operation_id.lower():
            return True

        return False

    def filter(self, query: str) -> None:
        """Filter endpoints by search query.
        
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
    def selected_operation(self) -> Operation | None:
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
        if isinstance(op, Operation):
            self.post_message(EndpointSelected(op))

    def get_operations_by_tag(self, tag: str) -> list[Operation]:
        """Return all operations with the given tag."""
        return self.spec.get_operations_by_tag(tag)

    def get_all_operations(self) -> list[Operation]:
        """Return all operations."""
        return list(self.spec.operations)

    def select_operation(self, op: Operation) -> None:
        """Programmatically select an operation.
        
        Args:
            op: Operation to select.
        """
        # Find the node with this operation
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
