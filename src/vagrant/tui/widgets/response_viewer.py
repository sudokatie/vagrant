"""Response viewer widget for TUI."""

from __future__ import annotations

import json

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from vagrant.http.client import HttpResponse


class ResponseViewer(Widget):
    """Widget for displaying HTTP responses.
    
    Shows status, timing, headers, and body with syntax highlighting.
    Supports toggling between formatted and raw view.
    """

    DEFAULT_CSS = """
    ResponseViewer {
        height: 100%;
    }
    
    ResponseViewer .status-success {
        color: $success;
        text-style: bold;
    }
    
    ResponseViewer .status-error {
        color: $error;
        text-style: bold;
    }
    
    ResponseViewer .status-redirect {
        color: $warning;
        text-style: bold;
    }
    
    ResponseViewer .meta {
        color: $text-muted;
    }
    
    ResponseViewer .headers-title {
        text-style: bold;
        margin-top: 1;
    }
    
    ResponseViewer .header-row {
        color: $text-muted;
    }
    
    ResponseViewer .body-title {
        text-style: bold;
        margin-top: 1;
    }
    
    ResponseViewer #body-content {
        margin-top: 1;
        padding: 1;
        background: $surface;
    }
    
    ResponseViewer #placeholder {
        color: $text-muted;
        text-align: center;
        padding: 2;
    }
    """

    def __init__(
        self,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize response viewer."""
        super().__init__(id=id, classes=classes)
        self._response: HttpResponse | None = None
        self._show_raw: bool = False

    def compose(self):
        """Create child widgets."""
        yield Static("Send a request to see the response", id="placeholder")
        yield Vertical(id="response-container")

    def set_response(self, response: HttpResponse) -> None:
        """Display a response.
        
        Args:
            response: HTTP response to display.
        """
        self._response = response

        # Hide placeholder
        placeholder = self.query_one("#placeholder", Static)
        placeholder.display = False

        # Build response display
        container = self.query_one("#response-container", Vertical)
        container.remove_children()

        # Status line
        status_class = self._get_status_class(response.status_code)
        status_line = (
            f"[{status_class}]{response.status_code} {response.status_text}[/{status_class}] "
            f"[meta]({response.elapsed_ms:.0f}ms, {self._format_size(response.size_bytes)})[/meta]"
        )
        container.mount(Static(status_line, id="status-line"))

        # Headers (collapsible)
        if response.headers:
            container.mount(Static("Headers", classes="headers-title"))
            headers_text = "\n".join(
                f"  [header-row]{k}: {v}[/header-row]"
                for k, v in list(response.headers.items())[:10]
            )
            if len(response.headers) > 10:
                headers_text += f"\n  [meta]... and {len(response.headers) - 10} more[/meta]"
            container.mount(Static(headers_text, id="headers-content"))

        # Body
        container.mount(Static("Body", classes="body-title"))
        body_content = self._format_body(response.body)
        container.mount(Static(body_content, id="body-content"))

    def _get_status_class(self, status_code: int) -> str:
        """Get CSS class for status code."""
        if 200 <= status_code < 300:
            return "status-success"
        elif 300 <= status_code < 400:
            return "status-redirect"
        else:
            return "status-error"

    def _format_size(self, size_bytes: int) -> str:
        """Format byte size for display."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"

    def _format_body(self, body) -> str:
        """Format response body for display."""
        if body is None:
            return "[meta](empty)[/meta]"

        if isinstance(body, (dict, list)):
            try:
                formatted = json.dumps(body, indent=2)
                # Truncate if very long
                lines = formatted.split("\n")
                if len(lines) > 50:
                    formatted = "\n".join(lines[:50])
                    formatted += f"\n... ({len(lines) - 50} more lines)"
                return formatted
            except (TypeError, ValueError):
                return str(body)

        # String body
        text = str(body)
        if len(text) > 5000:
            text = text[:5000] + f"\n... ({len(text) - 5000} more characters)"
        return text

    def clear(self) -> None:
        """Clear the response display."""
        self._response = None

        placeholder = self.query_one("#placeholder", Static)
        placeholder.display = True

        container = self.query_one("#response-container", Vertical)
        container.remove_children()

    def toggle_format(self) -> None:
        """Toggle between formatted and raw view."""
        self._show_raw = not self._show_raw
        if self._response:
            self.set_response(self._response)

    def set_loading(self) -> None:
        """Show loading state."""
        placeholder = self.query_one("#placeholder", Static)
        placeholder.update("[dim]Sending request...[/dim]")
        placeholder.display = True

        container = self.query_one("#response-container", Vertical)
        container.remove_children()

    def set_error(self, error: str) -> None:
        """Show error state.
        
        Args:
            error: Error message to display.
        """
        placeholder = self.query_one("#placeholder", Static)
        placeholder.update(f"[status-error]Error: {error}[/status-error]")
        placeholder.display = True

        container = self.query_one("#response-container", Vertical)
        container.remove_children()

    @property
    def response(self) -> HttpResponse | None:
        """Return the current response, if any."""
        return self._response

    def copy_body(self) -> str | None:
        """Return the body content for copying."""
        if not self._response:
            return None

        body = self._response.body
        if isinstance(body, (dict, list)):
            return json.dumps(body, indent=2)
        return str(body) if body else None
