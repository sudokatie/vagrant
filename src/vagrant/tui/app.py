"""Main Textual application for Vagrant."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header, Input, Static
from textual.worker import Worker, WorkerState

from vagrant.core.errors import NetworkError, VagrantError
from vagrant.http.client import HttpClient, HttpRequest, HttpResponse
from vagrant.parser.models import ApiSpec, Operation
from vagrant.storage.environments import Environment, EnvironmentManager
from vagrant.storage.history import HistoryEntry, HistoryStorage, redact_headers
from vagrant.tui.widgets.endpoint_browser import EndpointBrowser, EndpointSelected
from vagrant.tui.widgets.history_panel import HistoryPanel, HistorySelected
from vagrant.tui.widgets.request_builder import RequestBuilder, RequestSent
from vagrant.tui.widgets.response_viewer import ResponseViewer


# Load CSS from external file
CSS_PATH = Path(__file__).parent / "styles.tcss"


class VagrantApp(App):
    """API Explorer TUI application.
    
    Interactive terminal interface for exploring and testing APIs.
    Integrates endpoint browsing, request building, response viewing,
    and history tracking.
    """

    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("?", "help", "Help"),
        Binding("r", "replay", "Replay"),
        Binding("e", "edit_env", "Edit Env"),
        Binding("h", "toggle_history", "History"),
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
        self._last_request: HttpRequest | None = None
        self._history_visible = True

        # Initialize services
        self._http_client = HttpClient()
        self._history = HistoryStorage()
        self._env_mgr = EnvironmentManager()

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
        self._last_request = event.request
        self._execute_request(event.request)

    def _execute_request(self, request: HttpRequest) -> None:
        """Execute HTTP request in background."""
        # Show loading state
        response_viewer = self.query_one("#response-view", ResponseViewer)
        response_viewer.set_loading()
        self._set_status("Sending request...")

        # Run async request in worker
        self.run_worker(self._do_request(request), exclusive=True)

    async def _do_request(self, request: HttpRequest) -> None:
        """Async request execution."""
        try:
            # Substitute environment variables in URL
            url = request.url
            if self.env:
                url = self._env_mgr.substitute(url, self.env)

            # Create modified request with substituted URL
            final_request = HttpRequest(
                method=request.method,
                url=url,
                headers=request.headers,
                params=request.params,
                body=request.body,
            )

            # Check for request-level auth from builder (spec 4.3)
            request_builder = self.query_one("#request-form", RequestBuilder)
            request_auth = request_builder.get_auth()
            if request_auth:
                # Apply request-specific auth (overrides env auth for this request)
                self._http_client.set_auth(request_auth)
            elif self.env and self.env.auth:
                # Restore env auth
                self._http_client.set_auth(self.env.auth)

            # Send request
            response = await self._http_client.send(final_request)
            
            # Store response for {{response.field.path}} substitution
            self._env_mgr.set_last_response(response.body)

            # Update UI
            self._handle_response(final_request, response)

        except NetworkError as e:
            self._handle_error(str(e))
        except VagrantError as e:
            self._handle_error(str(e))
        except Exception as e:
            self._handle_error(f"Unexpected error: {e}")

    def _handle_response(self, request: HttpRequest, response: HttpResponse) -> None:
        """Handle successful response."""
        # Update response viewer
        response_viewer = self.query_one("#response-view", ResponseViewer)
        response_viewer.set_response(response)

        # Add to history (redact sensitive headers per spec 6.3)
        entry = HistoryEntry(
            id=None,
            timestamp=datetime.now(),
            method=request.method,
            url=request.url,
            headers=redact_headers(request.headers),
            params=request.params,
            body=json.dumps(request.body) if request.body else None,
            status_code=response.status_code,
            response_body=json.dumps(response.body) if isinstance(response.body, (dict, list)) else str(response.body),
            elapsed_ms=response.elapsed_ms,
            environment=self.env.name if self.env else None,
        )

        entry_id = self._history.add(entry)

        # Update history panel
        history_panel = self.query_one("#history-list", HistoryPanel)
        history_panel.refresh_entries()

        # Mark endpoint as visited (spec 4.3)
        if self.selected_operation:
            endpoint_browser = self.query_one("#endpoint-browser", EndpointBrowser)
            endpoint_browser.mark_visited(self.selected_operation)

        # Update status
        status_style = "success" if response.is_success else "error"
        self._set_status(
            f"{response.status_code} "
            f"{request.method} {request.url} ({response.elapsed_ms:.0f}ms)"
        )

    def _handle_error(self, error: str) -> None:
        """Handle request error."""
        response_viewer = self.query_one("#response-view", ResponseViewer)
        response_viewer.set_error(error)
        self._set_status(f"Error: {error}")

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
            "Tab: Navigate | Enter: Select | /: Search | r: Replay | h: History | q: Quit",
            title="Help",
        )

    def action_replay(self) -> None:
        """Replay the last request."""
        if self._last_request:
            self._execute_request(self._last_request)
            self.notify("Replaying last request")
        else:
            self.notify("No request to replay", severity="warning")

    def action_edit_env(self) -> None:
        """Open environment editor."""
        if self.env:
            self.notify(f"Environment: {self.env.name}\nEdit in ~/.config/vagrant/environments/")
        else:
            self.notify("No environment configured", severity="warning")

    def action_toggle_history(self) -> None:
        """Toggle history panel visibility."""
        history_panel = self.query_one("#history-panel")
        self._history_visible = not self._history_visible
        history_panel.display = self._history_visible
        self.notify("History " + ("shown" if self._history_visible else "hidden"))

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
        self._history.clear()
        history_panel = self.query_one("#history-list", HistoryPanel)
        history_panel.refresh_entries()
        self.notify("History cleared")


def run_app(spec: ApiSpec, env: Environment | None = None) -> None:
    """Run the TUI application.
    
    Args:
        spec: Parsed API specification.
        env: Environment configuration, if any.
    """
    app = VagrantApp(spec, env)
    app.run()
