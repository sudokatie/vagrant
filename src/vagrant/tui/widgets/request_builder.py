"""Request builder widget for TUI."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Input, Select, Static, Switch, TextArea

from vagrant.http.auth import AuthConfig
from vagrant.http.client import HttpRequest
from vagrant.parser.models import Operation, Parameter


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

        # Authentication section (spec 4.3)
        container.mount(Static("Authentication", classes="section-title"))
        auth_options = [
            ("none", "None"),
            ("bearer", "Bearer Token"),
            ("basic", "Basic Auth"),
            ("apikey", "API Key"),
        ]
        auth_select = Select(auth_options, id="auth-type", classes="param-input", value="none")
        auth_row = Horizontal(classes="param-row")
        auth_row.compose_add_child(Static("Type", classes="param-label"))
        auth_row.compose_add_child(auth_select)
        container.mount(auth_row)

        # Auth value input (token, user:pass, or key)
        auth_value_row = Horizontal(classes="param-row")
        auth_value_row.compose_add_child(Static("Credentials", classes="param-label"))
        auth_input = Input(placeholder="Token, user:pass, or API key", id="auth-value", classes="param-input", password=True)
        auth_value_row.compose_add_child(auth_input)
        container.mount(auth_value_row)

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
        """Create input row for a parameter with type-aware widgets.
        
        Uses appropriate input widgets based on parameter schema:
        - Boolean: Switch widget
        - Enum: Select dropdown
        - Date/DateTime: Input with format hint
        - Number/Integer: Input with type hint
        - Default: Text input
        """
        required_mark = "[required]*[/required]" if param.required else ""
        label_text = f"{param.name}{required_mark}"

        row = Horizontal(classes="param-row")
        label = Static(label_text, classes="param-label")

        input_id = f"param-{location}-{param.name}"
        schema = param.schema

        # Type-aware input selection (spec 4.3)
        if schema.type == "boolean":
            # Boolean: use Switch widget
            switch = Switch(id=input_id, classes="param-input")
            self._param_inputs[input_id] = switch
            row.compose_add_child(label)
            row.compose_add_child(switch)
            return row

        elif schema.enum:
            # Enum: use Select dropdown
            options = [(str(v), str(v)) for v in schema.enum]
            if not param.required:
                options = [("", "(none)")] + options
            select = Select(options, id=input_id, classes="param-input")
            self._param_inputs[input_id] = select
            row.compose_add_child(label)
            row.compose_add_child(select)
            return row

        # Default: Input widget with type-aware placeholder
        placeholder = param.description or ""

        # Add type-specific hints
        if schema.type == "integer":
            type_hint = "integer"
        elif schema.type == "number":
            type_hint = "number"
        elif schema.format == "date":
            type_hint = "YYYY-MM-DD"
        elif schema.format == "date-time":
            type_hint = "ISO 8601 datetime"
        elif schema.format == "email":
            type_hint = "email"
        elif schema.format == "uuid":
            type_hint = "UUID"
        elif schema.format == "uri":
            type_hint = "URL"
        else:
            type_hint = schema.type

        if placeholder:
            placeholder = f"{placeholder} ({type_hint})"
        else:
            placeholder = type_hint

        if schema.default is not None:
            placeholder = f"{placeholder} [default: {schema.default}]"

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

        # Collect parameter values from type-aware widgets
        path_params: dict[str, str] = {}
        query_params: dict[str, str] = {}
        headers: dict[str, str] = {}

        for param in op.parameters:
            input_id = f"param-{param.location}-{param.name}"
            widget = self._param_inputs.get(input_id)

            if widget:
                # Get value based on widget type
                if isinstance(widget, Switch):
                    # Boolean switch - always has a value
                    value = "true" if widget.value else "false"
                elif isinstance(widget, Select):
                    # Select dropdown
                    value = str(widget.value) if widget.value else ""
                else:
                    # Input widget
                    value = widget.value.strip() if hasattr(widget, 'value') else ""

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

    def get_auth(self) -> AuthConfig | None:
        """Get authentication config from form.
        
        Returns:
            AuthConfig if auth is configured, None otherwise.
        """
        try:
            auth_type_select = self.query_one("#auth-type", Select)
            auth_value_input = self.query_one("#auth-value", Input)

            auth_type = str(auth_type_select.value) if auth_type_select.value else "none"
            auth_value = auth_value_input.value.strip() if auth_value_input.value else ""

            if auth_type == "none" or not auth_value:
                return None

            if auth_type == "bearer":
                return AuthConfig(type="bearer", credentials={"token": auth_value})
            elif auth_type == "basic":
                # Expect user:pass format
                if ":" in auth_value:
                    user, password = auth_value.split(":", 1)
                else:
                    user, password = auth_value, ""
                return AuthConfig(type="basic", credentials={"username": user, "password": password})
            elif auth_type == "apikey":
                return AuthConfig(type="apikey", credentials={"key": auth_value})

            return None
        except Exception:
            return None

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
