"""GraphQL request builder widget for TUI."""

from __future__ import annotations

import json
from typing import Any

from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Input, Static, TextArea

from vagrant.parser.graphql import GraphQLArg, GraphQLOperation, build_query


class GraphQLRequestSent(Message):
    """Message sent when GraphQL request is submitted."""

    def __init__(self, query: str, variables: dict[str, Any]) -> None:
        self.query = query
        self.variables = variables
        super().__init__()


class GraphQLBuilder(Widget):
    """Form widget for building GraphQL requests.
    
    Displays operation details, argument inputs,
    field selection editor, and variable management.
    """

    DEFAULT_CSS = """
    GraphQLBuilder {
        height: auto;
        padding: 1;
    }
    
    GraphQLBuilder .operation-header {
        text-style: bold;
        margin-bottom: 1;
    }
    
    GraphQLBuilder .section-title {
        text-style: bold;
        margin-top: 1;
    }
    
    GraphQLBuilder .arg-row {
        layout: horizontal;
        height: 3;
    }
    
    GraphQLBuilder .arg-label {
        width: 20;
        padding-right: 1;
    }
    
    GraphQLBuilder .arg-input {
        width: 1fr;
    }
    
    GraphQLBuilder .required {
        color: $error;
    }
    
    GraphQLBuilder .type-hint {
        color: $text-muted;
    }
    
    GraphQLBuilder #send-button {
        margin-top: 1;
    }
    
    GraphQLBuilder #query-area {
        height: 10;
        margin-top: 1;
    }
    
    GraphQLBuilder #selection-area {
        height: 6;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize GraphQL builder."""
        super().__init__(id=id, classes=classes)
        self._operation: GraphQLOperation | None = None
        self._arg_inputs: dict[str, Input] = {}

    def compose(self):
        """Create child widgets."""
        yield Static("Select an operation", id="operation-header", classes="operation-header")
        yield Vertical(id="args-container")
        yield Static("Field Selection [dim](comma-separated)[/dim]", classes="section-title")
        yield TextArea(id="selection-area")
        yield Static("Generated Query", classes="section-title")
        yield TextArea(id="query-area", read_only=True)
        yield Button("Send Request", id="send-button", variant="primary", disabled=True)

    def set_operation(self, op: GraphQLOperation) -> None:
        """Configure form for the given operation.
        
        Args:
            op: GraphQL operation to build request for.
        """
        self._operation = op
        self._arg_inputs.clear()

        # Update header
        header = self.query_one("#operation-header", Static)
        op_type = op.operation_type.upper()
        header.update(f"[bold]{op_type}[/bold] {op.name} [dim]-> {op.type.display_name()}[/dim]")

        # Show description if available
        if op.description:
            header.update(f"[bold]{op_type}[/bold] {op.name}\n[dim]{op.description}[/dim]")

        # Rebuild args container
        container = self.query_one("#args-container", Vertical)
        container.remove_children()

        if op.args:
            container.mount(Static("Arguments", classes="section-title"))
            for arg in op.args:
                container.mount(self._create_arg_row(arg))

        # Set default field selection based on return type
        selection_area = self.query_one("#selection-area", TextArea)
        selection_area.text = self._get_default_selection(op)

        # Update generated query
        self._update_query()

        # Enable send button
        send_btn = self.query_one("#send-button", Button)
        send_btn.disabled = False

    def _create_arg_row(self, arg: GraphQLArg) -> Horizontal:
        """Create input row for a GraphQL argument."""
        is_required = arg.type.kind == "NON_NULL"
        required_mark = "[required]*[/required]" if is_required else ""
        type_display = arg.type.display_name()
        label_text = f"{arg.name}{required_mark} [type-hint]{type_display}[/type-hint]"

        row = Horizontal(classes="arg-row")
        label = Static(label_text, classes="arg-label")

        placeholder = arg.description or f"Enter {type_display}"
        if arg.default_value:
            placeholder = f"{placeholder} [default: {arg.default_value}]"

        input_id = f"arg-{arg.name}"
        input_widget = Input(placeholder=placeholder, id=input_id, classes="arg-input")
        self._arg_inputs[input_id] = input_widget

        row.compose_add_child(label)
        row.compose_add_child(input_widget)

        return row

    def _get_default_selection(self, op: GraphQLOperation) -> str:
        """Generate default field selection for an operation.
        
        For scalar types, returns empty.
        For object types, suggests common fields.
        """
        base_type = op.type.base_type_name()
        if not base_type:
            return ""

        # Common scalar types don't need selection
        scalars = {"String", "Int", "Float", "Boolean", "ID"}
        if base_type in scalars:
            return ""

        # For objects, suggest common fields
        return "id, name"

    def _update_query(self) -> None:
        """Update the generated query preview."""
        if not self._operation:
            return

        variables = self._get_variables()
        selection = self._get_selection()

        query_data = build_query(self._operation, variables, selection)
        query_text = query_data["query"]

        # Format for display
        formatted = self._format_query(query_text)

        query_area = self.query_one("#query-area", TextArea)
        query_area.text = formatted

    def _format_query(self, query: str) -> str:
        """Format a GraphQL query for readability."""
        # Simple formatting - add newlines after { and before }
        result = query.replace("{ ", "{\n  ").replace(" }", "\n}")
        return result

    def _get_variables(self) -> dict[str, Any]:
        """Collect variable values from inputs."""
        variables: dict[str, Any] = {}

        if not self._operation:
            return variables

        for arg in self._operation.args:
            input_id = f"arg-{arg.name}"
            widget = self._arg_inputs.get(input_id)

            if widget and widget.value.strip():
                value = widget.value.strip()

                # Try to parse as JSON for complex types
                try:
                    parsed = json.loads(value)
                    variables[arg.name] = parsed
                except json.JSONDecodeError:
                    # Use as string
                    variables[arg.name] = value

        return variables

    def _get_selection(self) -> str:
        """Get field selection from input."""
        selection_area = self.query_one("#selection-area", TextArea)
        return selection_area.text.strip()

    def get_request_data(self) -> tuple[str, dict[str, Any]] | None:
        """Build GraphQL query data from current form values.
        
        Returns:
            Tuple of (query_string, variables) if valid, None otherwise.
        """
        if not self._operation:
            return None

        variables = self._get_variables()
        selection = self._get_selection()

        query_data = build_query(self._operation, variables, selection)

        return query_data["query"], query_data["variables"]

    def clear(self) -> None:
        """Clear all form fields."""
        self._operation = None
        self._arg_inputs.clear()

        header = self.query_one("#operation-header", Static)
        header.update("Select an operation")

        container = self.query_one("#args-container", Vertical)
        container.remove_children()

        selection_area = self.query_one("#selection-area", TextArea)
        selection_area.text = ""

        query_area = self.query_one("#query-area", TextArea)
        query_area.text = ""

        send_btn = self.query_one("#send-button", Button)
        send_btn.disabled = True

    def on_input_changed(self, event: Input.Changed) -> None:
        """Update query preview when arguments change."""
        if event.input.id and event.input.id.startswith("arg-"):
            self._update_query()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Update query preview when selection changes."""
        if event.text_area.id == "selection-area":
            self._update_query()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle send button press."""
        if event.button.id == "send-button":
            data = self.get_request_data()
            if data:
                query, variables = data
                self.post_message(GraphQLRequestSent(query, variables))
