"""WebSocket client for interactive API exploration."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

try:
    import websockets
    from websockets.exceptions import (
        ConnectionClosed,
        InvalidURI,
        WebSocketException,
    )

    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    websockets = None
    ConnectionClosed = Exception
    InvalidURI = Exception
    WebSocketException = Exception

from vagrant.core.errors import NetworkError


class MessageDirection(Enum):
    """Direction of a WebSocket message."""

    SENT = "sent"
    RECEIVED = "received"
    SYSTEM = "system"


@dataclass
class WebSocketMessage:
    """A WebSocket message with metadata.

    Attributes:
        direction: Whether message was sent, received, or system.
        content: Message content (parsed JSON if applicable).
        raw: Raw message string.
        timestamp: When the message was sent/received.
        elapsed_ms: Time since connection opened.
    """

    direction: MessageDirection
    content: Any
    raw: str
    timestamp: datetime = field(default_factory=datetime.now)
    elapsed_ms: float = 0.0

    @property
    def is_json(self) -> bool:
        """True if content is parsed JSON."""
        return self.content != self.raw


@dataclass
class WebSocketConnection:
    """WebSocket connection state.

    Attributes:
        url: WebSocket URL.
        connected: Whether currently connected.
        connect_time: When connection was established.
        messages: Message history.
        reconnect_attempts: Number of reconnection attempts.
    """

    url: str
    connected: bool = False
    connect_time: datetime | None = None
    messages: list[WebSocketMessage] = field(default_factory=list)
    reconnect_attempts: int = 0

    @property
    def elapsed_ms(self) -> float:
        """Milliseconds since connection opened."""
        if self.connect_time:
            return (datetime.now() - self.connect_time).total_seconds() * 1000
        return 0.0

    def add_message(
        self,
        direction: MessageDirection,
        raw: str,
    ) -> WebSocketMessage:
        """Add a message to history.

        Args:
            direction: Message direction.
            raw: Raw message string.

        Returns:
            The created WebSocketMessage.
        """
        # Try to parse as JSON
        try:
            content = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            content = raw

        msg = WebSocketMessage(
            direction=direction,
            content=content,
            raw=raw,
            elapsed_ms=self.elapsed_ms,
        )
        self.messages.append(msg)
        return msg

    def filter_messages(
        self,
        direction: MessageDirection | None = None,
        pattern: str | None = None,
    ) -> list[WebSocketMessage]:
        """Filter messages by criteria.

        Args:
            direction: Filter by direction.
            pattern: Filter by content containing pattern.

        Returns:
            Filtered list of messages.
        """
        result = self.messages

        if direction:
            result = [m for m in result if m.direction == direction]

        if pattern:
            pattern_lower = pattern.lower()
            result = [m for m in result if pattern_lower in m.raw.lower()]

        return result


class WebSocketClient:
    """WebSocket client for interactive exploration.

    Provides async WebSocket connection with message history,
    auto-reconnect, and filtering capabilities.
    """

    def __init__(
        self,
        url: str,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 5,
        reconnect_delay: float = 1.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize WebSocket client.

        Args:
            url: WebSocket URL (ws:// or wss://).
            auto_reconnect: Whether to automatically reconnect.
            max_reconnect_attempts: Maximum reconnection attempts.
            reconnect_delay: Base delay between reconnects (exponential backoff).
            headers: Additional headers for connection.
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError(
                "websockets package not installed. "
                "Install with: pip install websockets"
            )

        self.url = url
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.headers = headers or {}

        self._connection = WebSocketConnection(url=url)
        self._websocket: Any = None
        self._receive_task: asyncio.Task | None = None
        self._on_message: Callable[[WebSocketMessage], None] | None = None
        self._on_connect: Callable[[], None] | None = None
        self._on_disconnect: Callable[[str], None] | None = None

    @property
    def connection(self) -> WebSocketConnection:
        """Get current connection state."""
        return self._connection

    @property
    def connected(self) -> bool:
        """True if currently connected."""
        return self._connection.connected

    @property
    def messages(self) -> list[WebSocketMessage]:
        """Get message history."""
        return self._connection.messages

    def on_message(self, callback: Callable[[WebSocketMessage], None]) -> None:
        """Set callback for received messages.

        Args:
            callback: Function called with each received message.
        """
        self._on_message = callback

    def on_connect(self, callback: Callable[[], None]) -> None:
        """Set callback for connection established.

        Args:
            callback: Function called when connected.
        """
        self._on_connect = callback

    def on_disconnect(self, callback: Callable[[str], None]) -> None:
        """Set callback for connection closed.

        Args:
            callback: Function called with reason when disconnected.
        """
        self._on_disconnect = callback

    async def connect(self) -> None:
        """Open WebSocket connection.

        Raises:
            NetworkError: If connection fails.
        """
        try:
            self._websocket = await websockets.connect(
                self.url,
                additional_headers=self.headers,
            )
            self._connection.connected = True
            self._connection.connect_time = datetime.now()
            self._connection.reconnect_attempts = 0

            # Add system message
            self._connection.add_message(
                MessageDirection.SYSTEM,
                f"Connected to {self.url}",
            )

            if self._on_connect:
                self._on_connect()

            # Start receiving messages
            self._receive_task = asyncio.create_task(self._receive_loop())

        except InvalidURI as e:
            raise NetworkError(f"Invalid WebSocket URL: {e}", url=self.url)
        except WebSocketException as e:
            raise NetworkError(f"WebSocket connection failed: {e}", url=self.url)
        except Exception as e:
            raise NetworkError(f"Connection failed: {e}", url=self.url)

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        if self._websocket:
            await self._websocket.close()
            self._websocket = None

        self._connection.connected = False
        self._connection.add_message(
            MessageDirection.SYSTEM,
            "Disconnected",
        )

    async def send(self, message: str) -> WebSocketMessage:
        """Send a message.

        Args:
            message: Message to send (string or JSON-encodable).

        Returns:
            The sent WebSocketMessage.

        Raises:
            NetworkError: If not connected or send fails.
        """
        if not self.connected or not self._websocket:
            raise NetworkError("Not connected", url=self.url)

        try:
            await self._websocket.send(message)
            return self._connection.add_message(
                MessageDirection.SENT,
                message,
            )
        except ConnectionClosed as e:
            await self._handle_disconnect(f"Connection closed: {e}")
            raise NetworkError("Connection closed", url=self.url)
        except WebSocketException as e:
            raise NetworkError(f"Send failed: {e}", url=self.url)

    async def send_json(self, data: Any) -> WebSocketMessage:
        """Send JSON-encoded data.

        Args:
            data: Data to JSON-encode and send.

        Returns:
            The sent WebSocketMessage.
        """
        return await self.send(json.dumps(data))

    async def _receive_loop(self) -> None:
        """Background task to receive messages."""
        try:
            async for message in self._websocket:
                msg = self._connection.add_message(
                    MessageDirection.RECEIVED,
                    message,
                )
                if self._on_message:
                    self._on_message(msg)

        except ConnectionClosed as e:
            await self._handle_disconnect(f"Connection closed: {e}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._handle_disconnect(f"Error: {e}")

    async def _handle_disconnect(self, reason: str) -> None:
        """Handle disconnection, attempting reconnect if enabled."""
        self._connection.connected = False
        self._connection.add_message(
            MessageDirection.SYSTEM,
            reason,
        )

        if self._on_disconnect:
            self._on_disconnect(reason)

        if self.auto_reconnect:
            await self._attempt_reconnect()

    async def _attempt_reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        while self._connection.reconnect_attempts < self.max_reconnect_attempts:
            self._connection.reconnect_attempts += 1
            delay = self.reconnect_delay * (2 ** (self._connection.reconnect_attempts - 1))

            self._connection.add_message(
                MessageDirection.SYSTEM,
                f"Reconnecting in {delay:.1f}s (attempt {self._connection.reconnect_attempts})",
            )

            await asyncio.sleep(delay)

            try:
                await self.connect()
                return  # Success
            except NetworkError:
                continue

        self._connection.add_message(
            MessageDirection.SYSTEM,
            f"Reconnection failed after {self.max_reconnect_attempts} attempts",
        )

    def clear_messages(self) -> None:
        """Clear message history."""
        self._connection.messages.clear()
