"""Request history storage using SQLite."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from vagrant.core.config import get_config_dir

# Headers that contain sensitive data and should be redacted
SENSITIVE_HEADERS = {
    "authorization",
    "x-api-key",
    "api-key",
    "apikey",
    "x-auth-token",
    "x-access-token",
    "cookie",
    "set-cookie",
}

# Pattern to detect headers that might contain secrets
SECRET_PATTERN = re.compile(r"(secret|token|password|key|auth)", re.IGNORECASE)

REDACTED = "[REDACTED]"


def redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Redact sensitive values from headers before storing in history.
    
    Redacts:
    - Known sensitive headers (Authorization, X-API-Key, etc.)
    - Any header whose name matches secret/token/password/key/auth
    
    Args:
        headers: Original headers dict.
        
    Returns:
        New dict with sensitive values replaced with [REDACTED].
    """
    redacted = {}
    for key, value in headers.items():
        key_lower = key.lower()
        if key_lower in SENSITIVE_HEADERS or SECRET_PATTERN.search(key):
            redacted[key] = REDACTED
        else:
            redacted[key] = value
    return redacted


@dataclass
class HistoryEntry:
    """A single request/response in history.
    
    Attributes:
        id: Unique identifier (assigned by storage).
        timestamp: When the request was made.
        method: HTTP method.
        url: Request URL.
        headers: Request headers.
        params: Query parameters.
        body: Request body (JSON string or None).
        status_code: Response status code.
        response_body: Response body (JSON string).
        elapsed_ms: Request duration in milliseconds.
        environment: Environment name used, if any.
    """

    id: int | None
    timestamp: datetime
    method: str
    url: str
    headers: dict[str, str]
    params: dict[str, str]
    body: str | None
    status_code: int
    response_body: str
    elapsed_ms: float
    environment: str | None = None


class HistoryStorage:
    """SQLite-backed request history storage.
    
    Stores request/response pairs for replay and analysis.
    Automatically creates database and table on first use.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize history storage.
        
        Args:
            db_path: Path to SQLite database file.
                     Defaults to ~/.config/vagrant/history.db
        """
        if db_path is None:
            db_path = get_config_dir() / "history.db"

        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Create database and table if needed."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    method TEXT NOT NULL,
                    url TEXT NOT NULL,
                    headers TEXT,
                    params TEXT,
                    body TEXT,
                    status_code INTEGER NOT NULL,
                    response_body TEXT,
                    elapsed_ms REAL,
                    environment TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_requests_timestamp 
                ON requests(timestamp DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_requests_url 
                ON requests(url)
            """)

    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        return sqlite3.connect(self.db_path)

    def add(self, entry: HistoryEntry) -> int:
        """Add entry to history.
        
        Args:
            entry: History entry to add.
            
        Returns:
            ID of the inserted entry.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO requests 
                (timestamp, method, url, headers, params, body, 
                 status_code, response_body, elapsed_ms, environment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.timestamp.isoformat(),
                    entry.method,
                    entry.url,
                    json.dumps(entry.headers),
                    json.dumps(entry.params),
                    entry.body,
                    entry.status_code,
                    entry.response_body,
                    entry.elapsed_ms,
                    entry.environment,
                ),
            )
            return cursor.lastrowid or 0

    def get(self, entry_id: int) -> HistoryEntry | None:
        """Get entry by ID.
        
        Args:
            entry_id: Entry ID to retrieve.
            
        Returns:
            History entry or None if not found.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM requests WHERE id = ?",
                (entry_id,),
            )
            row = cursor.fetchone()

            if row is None:
                return None

            return self._row_to_entry(row)

    def list(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[HistoryEntry]:
        """List recent history entries.
        
        Args:
            limit: Maximum number of entries to return.
            offset: Number of entries to skip.
            
        Returns:
            List of history entries, newest first.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM requests 
                ORDER BY timestamp DESC 
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def search(self, query: str) -> list[HistoryEntry]:
        """Search history by URL or method.
        
        Args:
            query: Search string to match against URL or method.
            
        Returns:
            List of matching entries, newest first.
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            search_pattern = f"%{query}%"
            cursor = conn.execute(
                """
                SELECT * FROM requests 
                WHERE url LIKE ? OR method LIKE ?
                ORDER BY timestamp DESC
                LIMIT 100
                """,
                (search_pattern, search_pattern),
            )
            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def clear(self) -> None:
        """Delete all history entries."""
        with self._connect() as conn:
            conn.execute("DELETE FROM requests")

    def cleanup(self, max_entries: int) -> int:
        """Remove old entries exceeding the limit.
        
        Args:
            max_entries: Maximum number of entries to keep.
            
        Returns:
            Number of entries deleted.
        """
        with self._connect() as conn:
            # Count current entries
            cursor = conn.execute("SELECT COUNT(*) FROM requests")
            count = cursor.fetchone()[0]

            if count <= max_entries:
                return 0

            to_delete = count - max_entries

            # Delete oldest entries
            conn.execute(
                """
                DELETE FROM requests WHERE id IN (
                    SELECT id FROM requests 
                    ORDER BY timestamp ASC 
                    LIMIT ?
                )
                """,
                (to_delete,),
            )

            return to_delete

    def count(self) -> int:
        """Return total number of entries."""
        with self._connect() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM requests")
            return cursor.fetchone()[0]

    def _row_to_entry(self, row: sqlite3.Row) -> HistoryEntry:
        """Convert database row to HistoryEntry."""
        return HistoryEntry(
            id=row["id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            method=row["method"],
            url=row["url"],
            headers=json.loads(row["headers"] or "{}"),
            params=json.loads(row["params"] or "{}"),
            body=row["body"],
            status_code=row["status_code"],
            response_body=row["response_body"] or "",
            elapsed_ms=row["elapsed_ms"] or 0.0,
            environment=row["environment"],
        )
