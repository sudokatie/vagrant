"""Main Textual application for Vagrant."""

from __future__ import annotations

import json
from datetime import datetime

from textual.app import App, ComposeResult, work
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header, Input, Static

from vagrant.core.errors import NetworkError, VagrantError
from vagrant.http.client import HttpClient, HttpRequest, HttpResponse
from vagrant.parser.models import ApiSpec, Operation
from vagrant.storage.environments import Environment
from vagrant.storage.history import HistoryEntry, HistoryStorage
from vagrant.tui.widgets.endpoint_browser import EndpointBrowser, EndpointSelected
from vagrant.tui.widgets.history_panel import HistoryPanel, HistorySelected
from vagrant.tui.widgets.request_builder import RequestBuilder, RequestSent
from vagrant.tui.widgets.response_viewer import ResponseViewer


class VagrantApp(App):
    """API Explorer TUI application.
    
    Interactive terminal interface for exploring and testing APIs.
    Integrates endpoint browsing, request building, response viewing,
    and history tracking.
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
        width: 50%;
        border: solid $secondary;
    }
    
    #history-panel {
        width: 20%;
        min-width: 20;
        border: solid $accent;
    }
    
    #search-input {
        dock: top;
        margin: 0 1;
    }
    
    #endpoint-browser {
        height: 1fr;
    }
    
    #request-builder {
        height: 40%;
        border-bottom: solid $primary;
        overflow-y: auto;
    }
    
    #response-viewer {
        height: 60%;
        overflow-y: auto;
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
    
    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("r", "reload", "Reload Spec"),
        Binding("ctrl+l", "clear_history", "Clear History"),
        Binding("/", "focus_search", "Search"),
        Binding("escape", "clear_search", "Clear Search", show=False),
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

        # Initialize services
        self._http_client = HttpClient()
        self._history = HistoryStorage()

        # Configure base URL from spec or environment
        if spec.servers:
            self._http_client.set_base_url(spec.servers[0].url)
        if env and env.base_url:
            self._http_client.set_base_url(env.base_url)

        # Configure auth from environment
        if env and env.auth:
            self._http_client.set_auth(env.auth)

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()

        with Container(id="main-container"):
            # Left panel - endpoint browser
            with Vertical(id="left-panel"):
                yield Static("Endpoints", classes="panel-title")
                yield Input(placeholder="Search endpoints...", id="search-input")
                yield EndpointBrowser(self.spec, id="endpoint-browser")

            # Center panel - request/response
            with Vertical(id="right-panel"):
                # Request section
                with Container(id="request-builder"):
                    yield RequestBuilder(id="request-form")

                # Response section
                with Container(id="response-viewer"):
                    yield ResponseViewer(id="response-view")

            # Right panel - history
            with Vertical(id="history-panel"):
                yield HistoryPanel(self._history, id="history-list")

        yield Static("Ready", id="status-bar")
        yield Footer()

    def on_endpoint_selected(self, event: EndpointSelected) -> None:
        """Handle endpoint selection from browser."""
        self.selected_operation = event.operation

        # Update request builder
        request_builder = self.query_one("#request-form", RequestBuilder)
        request_builder.set_operation(event.operation)

        # Update status
        self._set_status(f"Selected: {event.operation.method} {event.operation.path}")

    def on_request_sent(self, event: RequestSent) -> None:
        """Handle request submission from builder."""
        self._execute_request(event.request)

    @work(exclusive=True, thread=True)
    async def _execute_request(self, request: HttpRequest) -> None:
        """Execute HTTP request in background.
        
        Uses Textual's work decorator for async execution without
        blocking the UI.
        """
        # Show loading state
        response_viewer = self.query_one("#response-view", ResponseViewer)
        self.call_from_thread(response_viewer.set_loading)
        self.call_from_thread(self._set_status, "Sending request...")

        try:
            # Substitute environment variables in URL
            url = request.url
            if self.env:
                from vagrant.storage.environments import EnvironmentManager
                mgr = EnvironmentManager()
                url = mgr.substitute(url, self.env)

            # Create modified request with substituted URL
            final_request = HttpRequest(
                method=request.method,
                url=url,
                headers=request.headers,
                params=request.params,
                body=request.body,
            )

            # Send request
            response = await self._http_client.send(final_request)

            # Update UI on main thread
            self.call_from_thread(self._handle_response, final_request, response)

        except NetworkError as e:
            self.call_from_thread(self._handle_error, str(e))
        except VagrantError as e:
            self.call_from_thread(self._handle_error, str(e))
        except Exception as e:
            self.call_from_thread(self._handle_error, f"Unexpected error: {e}")

    def _handle_response(self, request: HttpRequest, response: HttpResponse) -> None:
        """Handle successful response on main thread."""
        # Update response viewer
        response_viewer = self.query_one("#response-view", ResponseViewer)
        response_viewer.set_response(response)

        # Add to history
        entry = HistoryEntry(
            id=None,
            timestamp=datetime.now(),
            method=request.method,
            url=request.url,
            headers=request.headers,
            params=request.params,
            body=json.dumps(request.body) if request.body else None,
            status_code=response.status_code,
            response_body=json.dumps(response.body) if isinstance(response.body, (dict, list)) else str(response.body),
            elapsed_ms=response.elapsed_ms,
            environment=self.env.name if self.env else None,
        )

        entry_id = self._history.add(entry)
        entry.id = entry_id

        # Update history panel
        history_panel = self.query_one("#history-list", HistoryPanel)
        history_panel.add_entry(entry)

        # Update status
        status_class = "success" if response.is_success else "error"
        self._set_status(
            f"[{status_class}]{response.status_code}[/{status_class}] "
            f"{request.method} {request.url} ({response.elapsed_ms:.0f}ms)"
        )

    def _handle_error(self, error: str) -> None:
        """Handle request error on main thread."""
        response_viewer = self.query_one("#response-view", ResponseViewer)
        response_viewer.set_error(error)
        self._set_status(f"[error]Error: {error}[/error]")

    def on_history_selected(self, event: HistorySelected) -> None:
        """Handle history entry selection."""
        entry = event.entry

        # Reconstruct response for display
        try:
            body = json.loads(entry.response_body) if entry.response_body else None
        except (json.JSONDecodeError, ValueError):
            body = entry.response_body

        response = HttpResponse(
            status_code=entry.status_code,
            status_text="",
            headers={},
            body=body,
            elapsed_ms=entry.elapsed_ms,
            size_bytes=len(entry.response_body) if entry.response_body else 0,
        )

        response_viewer = self.query_one("#response-view", ResponseViewer)
        response_viewer.set_response(response)

        self._set_status(f"Viewing history: {entry.method} {entry.url}")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-input":
            browser = self.query_one("#endpoint-browser", EndpointBrowser)
            browser.filter(event.value)

    def _set_status(self, message: str) -> None:
        """Update status bar."""
        status = self.query_one("#status-bar", Static)
        status.update(message)

    def action_help(self) -> None:
        """Show help."""
        self.notify(
            "Tab: Navigate | Enter: Select | /: Search | q: Quit",
            title="Help",
        )

    def action_reload(self) -> None:
        """Reload the spec."""
        browser = self.query_one("#endpoint-browser", EndpointBrowser)
        browser.clear_filter()
        self.notify("Spec reloaded")

    def action_focus_search(self) -> None:
        """Focus the search input."""
        search = self.query_one("#search-input", Input)
        search.focus()

    def action_clear_search(self) -> None:
        """Clear search and filter."""
        search = self.query_one("#search-input", Input)
        search.value = ""
        browser = self.query_one("#endpoint-browser", EndpointBrowser)
        browser.clear_filter()

    def action_clear_history(self) -> None:
        """Clear all history."""
        history_panel = self.query_one("#history-list", HistoryPanel)
        history_panel.clear_history()
        self.notify("History cleared")


def run_app(spec: ApiSpec, env: Environment | None = None) -> None:
    """Run the TUI application.
    
    Args:
        spec: Parsed API specification.
        env: Environment configuration, if any.
    """
    app = VagrantApp(spec, env)
    app.run()
