"""History panel widget for TUI."""

from __future__ import annotations

from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView, Static

from vagrant.storage.history import HistoryEntry, HistoryStorage


class HistorySelected(Message):
    """Message sent when a history entry is selected."""

    def __init__(self, entry: HistoryEntry) -> None:
        self.entry = entry
        super().__init__()


class HistoryPanel(Widget):
    """Panel showing recent request history.
    
    Displays list of recent requests with method, URL, and status.
    Clicking an entry emits HistorySelected message.
    """

    DEFAULT_CSS = """
    HistoryPanel {
        height: 100%;
    }
    
    HistoryPanel .panel-title {
        text-style: bold;
        padding: 0 1;
        background: $surface;
    }
    
    HistoryPanel ListView {
        height: 1fr;
    }
    
    HistoryPanel .history-item {
        padding: 0 1;
    }
    
    HistoryPanel .method-get {
        color: $success;
    }
    
    HistoryPanel .method-post {
        color: $primary;
    }
    
    HistoryPanel .method-put {
        color: $warning;
    }
    
    HistoryPanel .method-delete {
        color: $error;
    }
    
    HistoryPanel .status-success {
        color: $success;
    }
    
    HistoryPanel .status-error {
        color: $error;
    }
    
    HistoryPanel .empty-message {
        color: $text-muted;
        text-align: center;
        padding: 2;
    }
    """

    def __init__(
        self,
        storage: HistoryStorage | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize history panel.
        
        Args:
            storage: History storage to use. Creates new if None.
            id: Widget ID.
            classes: CSS classes.
        """
        super().__init__(id=id, classes=classes)
        self._storage = storage or HistoryStorage()
        self._entries: list[HistoryEntry] = []

    def compose(self):
        """Create child widgets."""
        yield Static("History", classes="panel-title")
        yield ListView(id="history-list")

    def on_mount(self) -> None:
        """Refresh on mount."""
        self.refresh_list()

    def refresh_list(self, limit: int = 20) -> None:
        """Reload history from storage.
        
        Args:
            limit: Maximum number of entries to show.
        """
        self._entries = self._storage.list(limit=limit)

        list_view = self.query_one("#history-list", ListView)
        list_view.clear()

        if not self._entries:
            list_view.append(ListItem(Label("[empty-message]No history yet[/empty-message]")))
            return

        for entry in self._entries:
            item = self._create_list_item(entry)
            list_view.append(item)

    def _create_list_item(self, entry: HistoryEntry) -> ListItem:
        """Create list item for a history entry."""
        method_class = f"method-{entry.method.lower()}"
        status_class = "status-success" if 200 <= entry.status_code < 300 else "status-error"

        # Truncate URL if too long
        url = entry.url
        if len(url) > 40:
            url = url[:37] + "..."

        # Format time
        time_str = entry.timestamp.strftime("%H:%M")

        label_text = (
            f"[{method_class}]{entry.method:6}[/{method_class}] "
            f"{url} "
            f"[{status_class}]{entry.status_code}[/{status_class}] "
            f"[dim]{time_str}[/dim]"
        )

        item = ListItem(Label(label_text, classes="history-item"))
        item.data = entry  # Store entry reference
        return item

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle list item selection."""
        item = event.item
        if hasattr(item, "data") and item.data:
            entry = item.data
            if isinstance(entry, HistoryEntry):
                self.post_message(HistorySelected(entry))

    @property
    def selected_entry(self) -> HistoryEntry | None:
        """Return the currently selected entry, if any."""
        list_view = self.query_one("#history-list", ListView)
        if list_view.highlighted_child:
            item = list_view.highlighted_child
            if hasattr(item, "data"):
                return item.data
        return None

    def add_entry(self, entry: HistoryEntry) -> None:
        """Add a new entry to the top of the list.
        
        Args:
            entry: Entry to add.
        """
        self._entries.insert(0, entry)

        list_view = self.query_one("#history-list", ListView)

        # Remove empty message if present
        if list_view.children and not hasattr(list_view.children[0], "data"):
            list_view.clear()

        # Insert at top
        item = self._create_list_item(entry)
        list_view.insert(0, item)

        # Keep list size reasonable
        while len(list_view.children) > 50:
            list_view.children[-1].remove()
            self._entries.pop()

    def search(self, query: str) -> None:
        """Filter history by search query.
        
        Args:
            query: Search string.
        """
        if not query:
            self.refresh_list()
            return

        results = self._storage.search(query)
        self._entries = results[:20]

        list_view = self.query_one("#history-list", ListView)
        list_view.clear()

        if not self._entries:
            list_view.append(ListItem(Label("[empty-message]No matches found[/empty-message]")))
            return

        for entry in self._entries:
            item = self._create_list_item(entry)
            list_view.append(item)

    def clear_history(self) -> None:
        """Clear all history."""
        self._storage.clear()
        self._entries.clear()

        list_view = self.query_one("#history-list", ListView)
        list_view.clear()
        list_view.append(ListItem(Label("[empty-message]No history yet[/empty-message]")))
