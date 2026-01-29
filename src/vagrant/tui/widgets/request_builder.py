"""Request builder widget for TUI."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from textual.containers import Vertical, Horizontal
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static, Input, Button, TextArea

from vagrant.parser.models import Operation, Parameter
from vagrant.http.client import HttpRequest


class RequestSent(Message):
    """Message sent when request is submitted."""

    def __init__(self, request: HttpRequest) -> None:
        self.request = request
        super().__init__()


@dataclass
class FormData:
    """Collected form data for request building."""
    path_params: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, str] = field(default_factory=dict)
    header_params: dict[str, str] = field(default_factory=dict)
    body: str = ""


class RequestBuilder(Widget):
    """Form widget for building HTTP requests.
    
    Displays operation details and provides input fields
    for parameters and request body.
    """

    DEFAULT_CSS = """
    RequestBuilder {
        height: auto;
        padding: 1;
    }
    
    RequestBuilder .operation-header {
        text-style: bold;
        margin-bottom: 1;
    }
    
    RequestBuilder .section-title {
        text-style: bold;
        margin-top: 1;
    }
    
    RequestBuilder .param-row {
        layout: horizontal;
        height: 3;
    }
    
    RequestBuilder .param-label {
        width: 20;
        padding-right: 1;
    }
    
    RequestBuilder .param-input {
        width: 1fr;
    }
    
    RequestBuilder .required {
        color: $error;
    }
    
    RequestBuilder #send-button {
        margin-top: 1;
    }
    
    RequestBuilder #body-area {
        height: 6;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize request builder."""
        super().__init__(id=id, classes=classes)
        self._operation: Operation | None = None
        self._form_data = FormData()
        self._param_inputs: dict[str, Input] = {}

    def compose(self):
        """Create child widgets."""
        yield Static("Select an endpoint", id="operation-header", classes="operation-header")
        yield Vertical(id="params-container")
        yield Button("Send Request", id="send-button", variant="primary", disabled=True)

    def set_operation(self, op: Operation) -> None:
        """Configure form for the given operation.
        
        Args:
            op: Operation to build request for.
        """
        self._operation = op
        self._form_data = FormData()
        self._param_inputs.clear()
        
        # Update header
        header = self.query_one("#operation-header", Static)
        header.update(f"[bold]{op.method}[/bold] {op.path}")
        
        # Rebuild params container
        container = self.query_one("#params-container", Vertical)
        container.remove_children()
        
        # Group parameters by location
        path_params = [p for p in op.parameters if p.location == "path"]
        query_params = [p for p in op.parameters if p.location == "query"]
        header_params = [p for p in op.parameters if p.location == "header"]
        
        # Path parameters
        if path_params:
            container.mount(Static("Path Parameters", classes="section-title"))
            for param in path_params:
                container.mount(self._create_param_row(param, "path"))
        
        # Query parameters
        if query_params:
            container.mount(Static("Query Parameters", classes="section-title"))
            for param in query_params:
                container.mount(self._create_param_row(param, "query"))
        
        # Header parameters
        if header_params:
            container.mount(Static("Headers", classes="section-title"))
            for param in header_params:
                container.mount(self._create_param_row(param, "header"))
        
        # Request body
        if op.request_body:
            container.mount(Static("Request Body", classes="section-title"))
            body_area = TextArea(id="body-area")
            body_area.text = "{}"
            container.mount(body_area)
        
        # Enable send button
        send_btn = self.query_one("#send-button", Button)
        send_btn.disabled = False

    def _create_param_row(self, param: Parameter, location: str) -> Horizontal:
        """Create input row for a parameter."""
        required_mark = "[required]*[/required]" if param.required else ""
        label_text = f"{param.name}{required_mark}"
        
        row = Horizontal(classes="param-row")
        label = Static(label_text, classes="param-label")
        
        input_id = f"param-{location}-{param.name}"
        placeholder = param.description or f"{param.schema.type}"
        if param.schema.default is not None:
            placeholder = f"{placeholder} (default: {param.schema.default})"
        
        input_widget = Input(placeholder=placeholder, id=input_id, classes="param-input")
        self._param_inputs[input_id] = input_widget
        
        row.compose_add_child(label)
        row.compose_add_child(input_widget)
        
        return row

    def get_request(self) -> HttpRequest | None:
        """Build HttpRequest from current form values.
        
        Returns:
            HttpRequest if form is valid, None otherwise.
        """
        if not self._operation:
            return None
        
        op = self._operation
        
        # Collect parameter values
        path_params: dict[str, str] = {}
        query_params: dict[str, str] = {}
        headers: dict[str, str] = {}
        
        for param in op.parameters:
            input_id = f"param-{param.location}-{param.name}"
            input_widget = self._param_inputs.get(input_id)
            
            if input_widget:
                value = input_widget.value.strip()
                if value:
                    if param.location == "path":
                        path_params[param.name] = value
                    elif param.location == "query":
                        query_params[param.name] = value
                    elif param.location == "header":
                        headers[param.name] = value
        
        # Build URL with path params
        url = op.path
        for name, value in path_params.items():
            url = url.replace(f"{{{name}}}", value)
        
        # Get body
        body = None
        if op.request_body:
            try:
                body_area = self.query_one("#body-area", TextArea)
                body_text = body_area.text.strip()
                if body_text:
                    body = json.loads(body_text)
            except (json.JSONDecodeError, Exception):
                body = None
        
        return HttpRequest(
            method=op.method,
            url=url,
            headers=headers,
            params=query_params,
            body=body,
        )

    def clear(self) -> None:
        """Clear all form fields."""
        self._operation = None
        self._form_data = FormData()
        self._param_inputs.clear()
        
        header = self.query_one("#operation-header", Static)
        header.update("Select an endpoint")
        
        container = self.query_one("#params-container", Vertical)
        container.remove_children()
        
        send_btn = self.query_one("#send-button", Button)
        send_btn.disabled = True

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle send button press."""
        if event.button.id == "send-button":
            request = self.get_request()
            if request:
                self.post_message(RequestSent(request))
