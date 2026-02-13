"""GraphQL TUI application for Vagrant."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header, Input, Static

from vagrant.core.errors import NetworkError, VagrantError
from vagrant.http.client import HttpClient, HttpRequest, HttpResponse
from vagrant.parser.graphql import GraphQLOperation, GraphQLSpec
from vagrant.storage.environments import Environment, EnvironmentManager
from vagrant.storage.history import HistoryEntry, HistoryStorage, redact_headers
from vagrant.tui.widgets.graphql_browser import GraphQLBrowser, GraphQLOperationSelected
from vagrant.tui.widgets.graphql_builder import GraphQLBuilder, GraphQLRequestSent
from vagrant.tui.widgets.history_panel import HistoryPanel, HistorySelected
from vagrant.tui.widgets.response_viewer import ResponseViewer


class GraphQLApp(App):
    """GraphQL Explorer TUI application.
    
    Interactive terminal interface for exploring and testing GraphQL APIs.
    Integrates operation browsing, query building, response viewing,
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
        spec: GraphQLSpec,
        env: Environment | None = None,
        **kwargs,
    ) -> None:
        """Initialize the GraphQL app.
        
        Args:
            spec: Parsed GraphQL specification.
            env: Environment configuration, if any.
        """
        super().__init__(**kwargs)
        self.spec = spec
        self.env = env
        self.selected_operation: GraphQLOperation | None = None
        self._last_query: str | None = None
        self._last_variables: dict[str, Any] | None = None
        self._history_visible = True

        # Initialize services
        self._http_client = HttpClient()
        self._history = HistoryStorage()
        self._env_mgr = EnvironmentManager()

        # Configure endpoint
        self._http_client.set_base_url(spec.endpoint)
        if env and env.base_url:
            self._http_client.set_base_url(env.base_url)

        # Configure auth from environment
        if env and env.auth:
            self._http_client.set_auth(env.auth)

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()

        with Container(id="main-container"):
            # Left panel - operation browser
            with Vertical(id="left-panel"):
                yield Static("Operations", classes="panel-title")
                yield Input(placeholder="Search operations...", id="search-input")
                yield GraphQLBrowser(self.spec, id="graphql-browser")

            # Center panel - request/response
            with Vertical(id="right-panel"):
                # Request section
                with Container(id="request-builder"):
                    yield GraphQLBuilder(id="graphql-form")

                # Response section
                with Container(id="response-viewer"):
                    yield ResponseViewer(id="response-view")

            # Right panel - history
            with Vertical(id="history-panel"):
                yield HistoryPanel(self._history, id="history-list")

        yield Static("Ready", id="status-bar")
        yield Footer()

    def on_graphql_operation_selected(self, event: GraphQLOperationSelected) -> None:
        """Handle operation selection from browser."""
        self.selected_operation = event.operation

        # Update request builder
        graphql_builder = self.query_one("#graphql-form", GraphQLBuilder)
        graphql_builder.set_operation(event.operation)

        # Update status
        self._set_status(f"Selected: {event.operation.operation_type} {event.operation.name}")

    def on_graphql_request_sent(self, event: GraphQLRequestSent) -> None:
        """Handle request submission from builder."""
        self._last_query = event.query
        self._last_variables = event.variables
        self._execute_graphql(event.query, event.variables)

    def _execute_graphql(self, query: str, variables: dict[str, Any]) -> None:
        """Execute GraphQL request in background."""
        # Show loading state
        response_viewer = self.query_one("#response-view", ResponseViewer)
        response_viewer.set_loading()
        self._set_status("Sending GraphQL request...")

        # Run async request in worker
        self.run_worker(self._do_graphql_request(query, variables), exclusive=True)

    async def _do_graphql_request(self, query: str, variables: dict[str, Any]) -> None:
        """Async GraphQL request execution."""
        try:
            # Build GraphQL POST body
            body = {
                "query": query,
                "variables": variables,
            }

            # Construct request
            endpoint = self.spec.endpoint
            if self.env and self.env.base_url:
                endpoint = self.env.base_url

            request = HttpRequest(
                method="POST",
                url=endpoint,
                headers={"Content-Type": "application/json"},
                params={},
                body=body,
            )

            # Send request
            response = await self._http_client.send(request)

            # Store response for variable substitution
            self._env_mgr.set_last_response(response.body)

            # Update UI
            self._handle_response(request, response, query, variables)

        except NetworkError as e:
            self._handle_error(str(e))
        except VagrantError as e:
            self._handle_error(str(e))
        except Exception as e:
            self._handle_error(f"Unexpected error: {e}")

    def _handle_response(
        self,
        request: HttpRequest,
        response: HttpResponse,
        query: str,
        variables: dict[str, Any],
    ) -> None:
        """Handle successful response."""
        # Update response viewer
        response_viewer = self.query_one("#response-view", ResponseViewer)
        response_viewer.set_response(response)

        # Check for GraphQL errors in response
        if isinstance(response.body, dict) and "errors" in response.body:
            errors = response.body["errors"]
            if errors:
                first_error = errors[0].get("message", "GraphQL error")
                self._set_status(f"GraphQL error: {first_error}")
                return

        # Add to history
        entry = HistoryEntry(
            id=None,
            timestamp=datetime.now(),
            method="POST",
            url=request.url,
            headers=redact_headers(request.headers),
            params={},
            body=json.dumps({"query": query, "variables": variables}),
            status_code=response.status_code,
            response_body=json.dumps(response.body) if isinstance(response.body, (dict, list)) else str(response.body),
            elapsed_ms=response.elapsed_ms,
            environment=self.env.name if self.env else None,
        )

        self._history.add(entry)

        # Update history panel
        history_panel = self.query_one("#history-list", HistoryPanel)
        history_panel.refresh_entries()

        # Mark operation as visited
        if self.selected_operation:
            browser = self.query_one("#graphql-browser", GraphQLBrowser)
            browser.mark_visited(self.selected_operation)

        # Update status
        op_name = self.selected_operation.name if self.selected_operation else "query"
        self._set_status(
            f"200 OK {op_name} ({response.elapsed_ms:.0f}ms)"
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
            browser = self.query_one("#graphql-browser", GraphQLBrowser)
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
        if self._last_query:
            self._execute_graphql(self._last_query, self._last_variables or {})
            self.notify("Replaying last query")
        else:
            self.notify("No query to replay", severity="warning")

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
        browser = self.query_one("#graphql-browser", GraphQLBrowser)
        browser.clear_filter()

    def action_clear_history(self) -> None:
        """Clear all history."""
        self._history.clear()
        history_panel = self.query_one("#history-list", HistoryPanel)
        history_panel.refresh_entries()
        self.notify("History cleared")


def run_graphql_app(spec: GraphQLSpec, env: Environment | None = None) -> None:
    """Run the GraphQL TUI application.
    
    Args:
        spec: Parsed GraphQL specification.
        env: Environment configuration, if any.
    """
    app = GraphQLApp(spec, env)
    app.run()
