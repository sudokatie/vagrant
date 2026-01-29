"""Main Textual application for Vagrant."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Static, Tree, Button, Input, Label

from vagrant.parser.models import ApiSpec, Operation
from vagrant.storage.environments import Environment


class VagrantApp(App):
    """API Explorer TUI application.
    
    Interactive terminal interface for exploring and testing APIs.
    """

    CSS = """
    #main-container {
        layout: horizontal;
    }
    
    #left-panel {
        width: 30%;
        min-width: 30;
        border: solid $primary;
    }
    
    #right-panel {
        width: 70%;
        border: solid $secondary;
    }
    
    #endpoint-tree {
        height: 1fr;
    }
    
    #request-panel {
        height: 40%;
        border-bottom: solid $primary;
    }
    
    #response-panel {
        height: 60%;
    }
    
    .panel-title {
        background: $surface;
        padding: 0 1;
        text-style: bold;
    }
    
    .method-get {
        color: $success;
    }
    
    .method-post {
        color: $primary;
    }
    
    .method-put {
        color: $warning;
    }
    
    .method-delete {
        color: $error;
    }
    
    #send-button {
        margin: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("r", "reload", "Reload"),
        Binding("tab", "focus_next", "Next", show=False),
        Binding("shift+tab", "focus_previous", "Previous", show=False),
    ]

    def __init__(
        self,
        spec: ApiSpec,
        env: Environment | None = None,
        **kwargs,
    ) -> None:
        """Initialize the app.
        
        Args:
            spec: Parsed API specification.
            env: Environment configuration, if any.
        """
        super().__init__(**kwargs)
        self.spec = spec
        self.env = env
        self.selected_operation: Operation | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        
        with Container(id="main-container"):
            # Left panel - endpoint browser
            with Vertical(id="left-panel"):
                yield Static("Endpoints", classes="panel-title")
                yield self._build_endpoint_tree()
            
            # Right panel - request/response
            with Vertical(id="right-panel"):
                # Request section
                with Container(id="request-panel"):
                    yield Static("Request", classes="panel-title")
                    yield Static("Select an endpoint from the list", id="request-info")
                    yield Button("Send Request", id="send-button", disabled=True)
                
                # Response section
                with Container(id="response-panel"):
                    yield Static("Response", classes="panel-title")
                    yield Static("", id="response-content")
        
        yield Footer()

    def _build_endpoint_tree(self) -> Tree:
        """Build the endpoint tree widget."""
        tree: Tree[Operation] = Tree(self.spec.title, id="endpoint-tree")
        tree.root.expand()
        
        # Group operations by tag
        tags: dict[str, list[Operation]] = {}
        for op in self.spec.operations:
            tag = op.tags[0] if op.tags else "default"
            if tag not in tags:
                tags[tag] = []
            tags[tag].append(op)
        
        # Build tree structure
        for tag, ops in sorted(tags.items()):
            tag_node = tree.root.add(tag)
            for op in ops:
                method_class = f"method-{op.method.lower()}"
                label = f"[{method_class}]{op.method}[/] {op.path}"
                tag_node.add_leaf(label, data=op)
        
        return tree

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle endpoint selection."""
        if event.node.data is None:
            return
        
        op = event.node.data
        if not isinstance(op, Operation):
            return
        
        self.selected_operation = op
        self._update_request_panel(op)

    def _update_request_panel(self, op: Operation) -> None:
        """Update request panel with operation details."""
        info = self.query_one("#request-info", Static)
        
        lines = [
            f"[bold]{op.method}[/bold] {op.path}",
            "",
        ]
        
        if op.summary:
            lines.append(op.summary)
            lines.append("")
        
        if op.parameters:
            lines.append("[bold]Parameters:[/bold]")
            for param in op.parameters:
                required = " *" if param.required else ""
                lines.append(f"  {param.name}{required} ({param.location})")
            lines.append("")
        
        if op.request_body:
            lines.append("[bold]Request Body:[/bold] required" if op.request_body.required else "[bold]Request Body:[/bold] optional")
            lines.append("")
        
        info.update("\n".join(lines))
        
        # Enable send button
        send_btn = self.query_one("#send-button", Button)
        send_btn.disabled = False

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "send-button" and self.selected_operation:
            await self._send_request()

    async def _send_request(self) -> None:
        """Send the current request."""
        if not self.selected_operation:
            return
        
        response_widget = self.query_one("#response-content", Static)
        response_widget.update("[dim]Sending request...[/dim]")
        
        # TODO: Actually send the request using HttpClient
        # For now, show placeholder
        response_widget.update(
            "[yellow]Request execution not yet implemented.[/yellow]\n\n"
            f"Would send: {self.selected_operation.method} {self.selected_operation.path}"
        )

    def action_help(self) -> None:
        """Show help."""
        self.notify("Use Tab to navigate, Enter to select, q to quit")

    def action_reload(self) -> None:
        """Reload the spec."""
        self.notify("Reload not yet implemented")


def run_app(spec: ApiSpec, env: Environment | None = None) -> None:
    """Run the TUI application.
    
    Args:
        spec: Parsed API specification.
        env: Environment configuration, if any.
    """
    app = VagrantApp(spec, env)
    app.run()
