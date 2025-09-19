"""Tests for WebSocket manager functionality."""

import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosedError

from src.websocket.websocket_manager import WebSocketManager
from src.storage.models import Order


class TestWebSocketManager:
    """Test WebSocket manager functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.manager = WebSocketManager()
        self.mock_websocket = Mock(spec=WebSocket)
        self.mock_websocket.client_state = Mock()
        self.mock_websocket.client_state.name = "CONNECTED"
        self.mock_websocket.send_text = AsyncMock()

    @pytest.mark.asyncio
    async def test_websocket_manager_initialization(self):
        """Test WebSocket manager initialization."""
        assert self.manager.active_connections == {
            "orderUpdate": set(),
            "orderBatch": set()
        }
        assert self.manager.pending_orders == []
        assert self.manager.is_running is False

    @pytest.mark.asyncio
    async def test_connect_websocket_success(self):
        """Test successful WebSocket connection."""
        await self.manager.connect(self.mock_websocket, "orderUpdate")
        
        assert self.mock_websocket in self.manager.active_connections["orderUpdate"]
        self.mock_websocket.send_text.assert_called_once()
        
        # Verify welcome message
        call_args = self.mock_websocket.send_text.call_args[0][0]
        message = json.loads(call_args)
        assert message["type"] == "connected"
        assert message["channel"] == "orderUpdate"

    @pytest.mark.asyncio
    async def test_connect_websocket_invalid_channel(self):
        """Test WebSocket connection with invalid channel."""
        with pytest.raises(ValueError, match="Unknown channel: invalid"):
            await self.manager.connect(self.mock_websocket, "invalid")

    @pytest.mark.asyncio
    async def test_disconnect_websocket_success(self):
        """Test successful WebSocket disconnection."""
        # First connect the websocket
        await self.manager.connect(self.mock_websocket, "orderUpdate")
        assert self.mock_websocket in self.manager.active_connections["orderUpdate"]
        
        # Then disconnect
        await self.manager.disconnect(self.mock_websocket)
        assert self.mock_websocket not in self.manager.active_connections["orderUpdate"]

    @pytest.mark.asyncio
    async def test_disconnect_websocket_with_close(self):
        """Test WebSocket disconnection with proper close."""
        self.mock_websocket.close = AsyncMock()
        
        # Connect and disconnect
        await self.manager.connect(self.mock_websocket, "orderUpdate")
        await self.manager.disconnect(self.mock_websocket)
        
        # Verify close was called
        self.mock_websocket.close.assert_called_once_with(code=1000, reason="Normal closure")

    @pytest.mark.asyncio
    async def test_broadcast_order_update_success(self):
        """Test successful order update broadcast."""
        # Connect websocket
        await self.manager.connect(self.mock_websocket, "orderUpdate")
        
        # Create test order
        test_order = Order(
            id="test-123",
            symbol="BTC",
            side="buy",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        # Broadcast order update
        await self.manager.broadcast_order_update(test_order)
        
        # Verify message was sent
        assert self.mock_websocket.send_text.call_count == 2  # Welcome + order update
        
        # Verify order update message
        call_args = self.mock_websocket.send_text.call_args_list[1][0][0]
        message = json.loads(call_args)
        assert message["type"] == "orderUpdate"
        assert message["channel"] == "orderUpdate"
        assert message["data"]["id"] == "test-123"

    @pytest.mark.asyncio
    async def test_broadcast_order_update_websocket_disconnect(self):
        """Test order update broadcast with WebSocket disconnect."""
        # Connect websocket
        await self.manager.connect(self.mock_websocket, "orderUpdate")
        
        # Mock send_text to raise WebSocketDisconnect
        self.mock_websocket.send_text = AsyncMock(side_effect=WebSocketDisconnect())
        
        # Create test order
        test_order = Order(
            id="test-123",
            symbol="BTC",
            side="buy",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        # Broadcast should handle disconnect gracefully
        await self.manager.broadcast_order_update(test_order)
        
        # Verify websocket was removed from connections
        assert self.mock_websocket not in self.manager.active_connections["orderUpdate"]

    @pytest.mark.asyncio
    async def test_broadcast_order_update_connection_closed(self):
        """Test order update broadcast with connection closed error."""
        # Connect websocket
        await self.manager.connect(self.mock_websocket, "orderUpdate")
        
        # Mock send_text to raise ConnectionClosedError
        self.mock_websocket.send_text = AsyncMock(side_effect=ConnectionClosedError(None, None))
        
        # Create test order
        test_order = Order(
            id="test-123",
            symbol="BTC",
            side="buy",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        # Broadcast should handle connection closed gracefully
        await self.manager.broadcast_order_update(test_order)
        
        # Verify websocket was removed from connections
        assert self.mock_websocket not in self.manager.active_connections["orderUpdate"]

    @pytest.mark.asyncio
    async def test_broadcast_order_update_no_close_frame_error(self):
        """Test order update broadcast with 'no close frame' error."""
        # Connect websocket
        await self.manager.connect(self.mock_websocket, "orderUpdate")
        
        # Mock send_text to raise 'no close frame' error
        self.mock_websocket.send_text = AsyncMock(side_effect=Exception("no close frame received or sent"))
        
        # Create test order
        test_order = Order(
            id="test-123",
            symbol="BTC",
            side="buy",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        # Broadcast should handle 'no close frame' error gracefully
        await self.manager.broadcast_order_update(test_order)
        
        # Verify websocket was removed from connections
        assert self.mock_websocket not in self.manager.active_connections["orderUpdate"]

    @pytest.mark.asyncio
    async def test_queue_order_for_batch(self):
        """Test queuing order for batch processing."""
        test_order = Order(
            id="test-123",
            symbol="BTC",
            side="buy",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        # Queue order
        await self.manager.queue_order_for_batch(test_order)
        
        assert len(self.manager.pending_orders) == 1
        assert self.manager.pending_orders[0] == test_order

    @pytest.mark.asyncio
    async def test_send_batch_update_success(self):
        """Test successful batch update sending."""
        # Connect websocket to orderBatch channel
        await self.manager.connect(self.mock_websocket, "orderBatch")
        
        # Add orders to pending
        test_orders = [
            Order(id="test-1", symbol="BTC", side="buy", price=50000.0, size=1.0, 
                  owner="0x123", timestamp=datetime.now(), status="open"),
            Order(id="test-2", symbol="ETH", side="sell", price=3000.0, size=10.0,
                  owner="0x456", timestamp=datetime.now(), status="open")
        ]
        self.manager.pending_orders.extend(test_orders)
        
        # Send batch update
        await self.manager._send_batch_update()
        
        # Verify message was sent
        assert self.mock_websocket.send_text.call_count == 2  # Welcome + batch update
        
        # Verify batch update message
        call_args = self.mock_websocket.send_text.call_args_list[1][0][0]
        message = json.loads(call_args)
        assert message["type"] == "orderBatch"
        assert message["channel"] == "orderBatch"
        assert message["data"]["count"] == 2
        assert len(message["data"]["orders"]) == 2
        
        # Verify pending orders were cleared
        assert len(self.manager.pending_orders) == 0

    @pytest.mark.asyncio
    async def test_get_connection_stats(self):
        """Test getting connection statistics."""
        # Connect websockets
        await self.manager.connect(self.mock_websocket, "orderUpdate")
        
        # Add some pending orders
        test_order = Order(
            id="test-123", symbol="BTC", side="buy", price=50000.0, size=1.0,
            owner="0x123", timestamp=datetime.now(), status="open"
        )
        self.manager.pending_orders.append(test_order)
        
        # Get stats
        stats = self.manager.get_connection_stats()
        
        assert stats["channels"]["orderUpdate"] == 1
        assert stats["channels"]["orderBatch"] == 0
        assert stats["pending_orders"] == 1
        assert stats["is_running"] is False

    @pytest.mark.asyncio
    async def test_start_stop_manager(self):
        """Test starting and stopping the manager."""
        # Start manager
        await self.manager.start()
        assert self.manager.is_running is True
        assert self.manager.batch_timer is not None
        
        # Stop manager
        await self.manager.stop()
        assert self.manager.is_running is False
        assert self.manager.batch_timer is None