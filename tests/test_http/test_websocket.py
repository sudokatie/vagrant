"""Tests for WebSocket client."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vagrant.http.websocket import (
    MessageDirection,
    WebSocketClient,
    WebSocketConnection,
    WebSocketMessage,
    WEBSOCKETS_AVAILABLE,
)


class TestWebSocketMessage:
    """Tests for WebSocketMessage."""

    def test_create_message(self):
        """Test creating a WebSocket message."""
        msg = WebSocketMessage(
            direction=MessageDirection.SENT,
            content="hello",
            raw="hello",
        )
        assert msg.direction == MessageDirection.SENT
        assert msg.content == "hello"
        assert msg.raw == "hello"
        assert isinstance(msg.timestamp, datetime)

    def test_is_json_false_for_plain_text(self):
        """Test is_json is False for plain text."""
        msg = WebSocketMessage(
            direction=MessageDirection.RECEIVED,
            content="hello",
            raw="hello",
        )
        assert msg.is_json is False

    def test_is_json_true_for_parsed_json(self):
        """Test is_json is True for parsed JSON."""
        msg = WebSocketMessage(
            direction=MessageDirection.RECEIVED,
            content={"key": "value"},
            raw='{"key": "value"}',
        )
        assert msg.is_json is True


class TestWebSocketConnection:
    """Tests for WebSocketConnection."""

    def test_create_connection(self):
        """Test creating a connection."""
        conn = WebSocketConnection(url="ws://example.com")
        assert conn.url == "ws://example.com"
        assert conn.connected is False
        assert conn.connect_time is None
        assert conn.messages == []

    def test_add_message(self):
        """Test adding a message."""
        conn = WebSocketConnection(url="ws://example.com")
        msg = conn.add_message(MessageDirection.SENT, "hello")

        assert len(conn.messages) == 1
        assert msg.direction == MessageDirection.SENT
        assert msg.raw == "hello"

    def test_add_message_parses_json(self):
        """Test that add_message parses JSON."""
        conn = WebSocketConnection(url="ws://example.com")
        msg = conn.add_message(MessageDirection.RECEIVED, '{"key": "value"}')

        assert msg.content == {"key": "value"}
        assert msg.is_json is True

    def test_add_message_plain_text(self):
        """Test that add_message handles plain text."""
        conn = WebSocketConnection(url="ws://example.com")
        msg = conn.add_message(MessageDirection.RECEIVED, "not json")

        assert msg.content == "not json"
        assert msg.is_json is False

    def test_elapsed_ms_zero_when_not_connected(self):
        """Test elapsed_ms is 0 when not connected."""
        conn = WebSocketConnection(url="ws://example.com")
        assert conn.elapsed_ms == 0.0

    def test_elapsed_ms_when_connected(self):
        """Test elapsed_ms when connected."""
        conn = WebSocketConnection(url="ws://example.com")
        conn.connect_time = datetime.now()

        # Should be > 0 (small positive value)
        assert conn.elapsed_ms >= 0

    def test_filter_messages_by_direction(self):
        """Test filtering messages by direction."""
        conn = WebSocketConnection(url="ws://example.com")
        conn.add_message(MessageDirection.SENT, "out")
        conn.add_message(MessageDirection.RECEIVED, "in")
        conn.add_message(MessageDirection.SENT, "out2")

        sent = conn.filter_messages(direction=MessageDirection.SENT)
        assert len(sent) == 2

        received = conn.filter_messages(direction=MessageDirection.RECEIVED)
        assert len(received) == 1

    def test_filter_messages_by_pattern(self):
        """Test filtering messages by pattern."""
        conn = WebSocketConnection(url="ws://example.com")
        conn.add_message(MessageDirection.SENT, "hello world")
        conn.add_message(MessageDirection.RECEIVED, "goodbye")
        conn.add_message(MessageDirection.SENT, "hello again")

        matches = conn.filter_messages(pattern="hello")
        assert len(matches) == 2

    def test_filter_messages_case_insensitive(self):
        """Test filtering is case insensitive."""
        conn = WebSocketConnection(url="ws://example.com")
        conn.add_message(MessageDirection.SENT, "Hello World")

        matches = conn.filter_messages(pattern="hello")
        assert len(matches) == 1


@pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets not installed")
class TestWebSocketClient:
    """Tests for WebSocketClient."""

    def test_create_client(self):
        """Test creating a client."""
        client = WebSocketClient("ws://example.com")
        assert client.url == "ws://example.com"
        assert client.connected is False
        assert client.auto_reconnect is True

    def test_create_client_with_options(self):
        """Test creating client with options."""
        client = WebSocketClient(
            "ws://example.com",
            auto_reconnect=False,
            max_reconnect_attempts=3,
            reconnect_delay=0.5,
            headers={"Auth": "token"},
        )
        assert client.auto_reconnect is False
        assert client.max_reconnect_attempts == 3
        assert client.reconnect_delay == 0.5
        assert client.headers == {"Auth": "token"}

    def test_connection_property(self):
        """Test connection property."""
        client = WebSocketClient("ws://example.com")
        assert isinstance(client.connection, WebSocketConnection)

    def test_messages_property(self):
        """Test messages property."""
        client = WebSocketClient("ws://example.com")
        assert client.messages == []

    def test_on_message_callback(self):
        """Test setting message callback."""
        client = WebSocketClient("ws://example.com")
        callback = MagicMock()
        client.on_message(callback)
        assert client._on_message == callback

    def test_on_connect_callback(self):
        """Test setting connect callback."""
        client = WebSocketClient("ws://example.com")
        callback = MagicMock()
        client.on_connect(callback)
        assert client._on_connect == callback

    def test_on_disconnect_callback(self):
        """Test setting disconnect callback."""
        client = WebSocketClient("ws://example.com")
        callback = MagicMock()
        client.on_disconnect(callback)
        assert client._on_disconnect == callback

    def test_clear_messages(self):
        """Test clearing messages."""
        client = WebSocketClient("ws://example.com")
        client._connection.add_message(MessageDirection.SENT, "test")
        assert len(client.messages) == 1

        client.clear_messages()
        assert len(client.messages) == 0


@pytest.mark.skipif(not WEBSOCKETS_AVAILABLE, reason="websockets not installed")
class TestWebSocketClientAsync:
    """Async tests for WebSocketClient."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection."""
        with patch("vagrant.http.websocket.websockets") as mock_ws:
            mock_connection = AsyncMock()
            mock_ws.connect = AsyncMock(return_value=mock_connection)

            client = WebSocketClient("ws://example.com")
            await client.connect()

            assert client.connected is True
            assert client._connection.connect_time is not None
            mock_ws.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_calls_callback(self):
        """Test connect calls on_connect callback."""
        with patch("vagrant.http.websocket.websockets") as mock_ws:
            mock_ws.connect = AsyncMock(return_value=AsyncMock())

            client = WebSocketClient("ws://example.com")
            callback = MagicMock()
            client.on_connect(callback)

            await client.connect()
            callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnection."""
        with patch("vagrant.http.websocket.websockets") as mock_ws:
            mock_connection = AsyncMock()
            mock_ws.connect = AsyncMock(return_value=mock_connection)

            client = WebSocketClient("ws://example.com")
            await client.connect()
            await client.disconnect()

            assert client.connected is False
            mock_connection.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message(self):
        """Test sending a message."""
        with patch("vagrant.http.websocket.websockets") as mock_ws:
            mock_connection = AsyncMock()
            mock_ws.connect = AsyncMock(return_value=mock_connection)

            client = WebSocketClient("ws://example.com")
            await client.connect()

            msg = await client.send("hello")

            assert msg.direction == MessageDirection.SENT
            assert msg.raw == "hello"
            mock_connection.send.assert_called_with("hello")

    @pytest.mark.asyncio
    async def test_send_json(self):
        """Test sending JSON data."""
        with patch("vagrant.http.websocket.websockets") as mock_ws:
            mock_connection = AsyncMock()
            mock_ws.connect = AsyncMock(return_value=mock_connection)

            client = WebSocketClient("ws://example.com")
            await client.connect()

            await client.send_json({"key": "value"})

            mock_connection.send.assert_called_with('{"key": "value"}')


class TestMessageDirection:
    """Tests for MessageDirection enum."""

    def test_sent_value(self):
        """Test SENT value."""
        assert MessageDirection.SENT.value == "sent"

    def test_received_value(self):
        """Test RECEIVED value."""
        assert MessageDirection.RECEIVED.value == "received"

    def test_system_value(self):
        """Test SYSTEM value."""
        assert MessageDirection.SYSTEM.value == "system"
