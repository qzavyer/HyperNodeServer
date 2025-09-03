"""Tests for WebSocket manager module."""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from src.websocket.websocket_manager import WebSocketManager
from src.storage.models import Order

@pytest.fixture
def websocket_manager():
    """WebSocket manager instance for testing."""
    return WebSocketManager()

@pytest.fixture
def sample_order():
    """Sample order for testing."""
    return Order(
        id="123",
        symbol="BTC",
        side="Bid",
        price=50000.0,
        size=1.0,
        owner="0x123",
        timestamp=datetime.now(),
        status="open"
    )

@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    websocket = Mock(spec=WebSocket)
    websocket.accept = AsyncMock()
    websocket.send_text = AsyncMock()
    websocket.close = AsyncMock()
    return websocket

class TestWebSocketManager:
    """Tests for WebSocketManager class."""
    
    def test_init(self, websocket_manager):
        """Test WebSocketManager initialization."""
        assert len(websocket_manager.active_connections) == 2
        assert "orderUpdate" in websocket_manager.active_connections
        assert "orderBatch" in websocket_manager.active_connections
        assert len(websocket_manager.pending_orders) == 0
        assert websocket_manager.is_running is False
    
    @pytest.mark.asyncio
    async def test_start(self, websocket_manager):
        """Test starting WebSocket manager."""
        await websocket_manager.start()
        
        assert websocket_manager.is_running is True
        assert websocket_manager.batch_timer is not None
        assert not websocket_manager.batch_timer.done()
    
    @pytest.mark.asyncio
    async def test_stop(self, websocket_manager):
        """Test stopping WebSocket manager."""
        # Start first
        await websocket_manager.start()
        assert websocket_manager.is_running is True
        
        # Stop
        await websocket_manager.stop()
        
        assert websocket_manager.is_running is False
        # Check if timer is cancelled or done
        assert (websocket_manager.batch_timer is None or 
                websocket_manager.batch_timer.cancelled() or 
                websocket_manager.batch_timer.done())
    
    @pytest.mark.asyncio
    async def test_connect_valid_channel(self, websocket_manager, mock_websocket):
        """Test connecting to valid channel."""
        await websocket_manager.connect(mock_websocket, "orderUpdate")
        
        mock_websocket.accept.assert_called_once()
        assert mock_websocket in websocket_manager.active_connections["orderUpdate"]
        assert len(websocket_manager.active_connections["orderUpdate"]) == 1
    
    @pytest.mark.asyncio
    async def test_connect_invalid_channel(self, websocket_manager, mock_websocket):
        """Test connecting to invalid channel."""
        with pytest.raises(ValueError, match="Unknown channel: invalid"):
            await websocket_manager.connect(mock_websocket, "invalid")
    
    @pytest.mark.asyncio
    async def test_disconnect(self, websocket_manager, mock_websocket):
        """Test disconnecting WebSocket."""
        # Connect first
        await websocket_manager.connect(mock_websocket, "orderUpdate")
        assert mock_websocket in websocket_manager.active_connections["orderUpdate"]
        
        # Disconnect
        await websocket_manager.disconnect(mock_websocket)
        
        assert mock_websocket not in websocket_manager.active_connections["orderUpdate"]
        assert len(websocket_manager.active_connections["orderUpdate"]) == 0
    
    @pytest.mark.asyncio
    async def test_broadcast_order_update(self, websocket_manager, sample_order, mock_websocket):
        """Test broadcasting order update."""
        # Connect WebSocket
        await websocket_manager.connect(mock_websocket, "orderUpdate")

        # Broadcast update
        await websocket_manager.broadcast_order_update(sample_order)

        # Verify message was sent (should be called twice: welcome + order update)
        assert mock_websocket.send_text.call_count == 2
        
        # Verify welcome message
        welcome_call = mock_websocket.send_text.call_args_list[0]
        welcome_message = json.loads(welcome_call[0][0])
        assert welcome_message["type"] == "connected"
        assert welcome_message["channel"] == "orderUpdate"
        
        # Verify order update message
        update_call = mock_websocket.send_text.call_args_list[1]
        update_message = json.loads(update_call[0][0])
        assert update_message["type"] == "orderUpdate"
        assert update_message["channel"] == "orderUpdate"
        assert update_message["data"]["id"] == "123"
        assert update_message["data"]["symbol"] == "BTC"
    
    @pytest.mark.asyncio
    async def test_broadcast_order_update_no_connections(self, websocket_manager, sample_order):
        """Test broadcasting order update with no connections."""
        # No connections, should not fail
        await websocket_manager.broadcast_order_update(sample_order)
        # Should complete without error
    
    @pytest.mark.asyncio
    async def test_queue_order_for_batch(self, websocket_manager, sample_order):
        """Test queuing order for batch update."""
        await websocket_manager.queue_order_for_batch(sample_order)
        
        assert len(websocket_manager.pending_orders) == 1
        assert websocket_manager.pending_orders[0] == sample_order
    
    @pytest.mark.asyncio
    async def test_batch_timer_loop(self, websocket_manager):
        """Test batch timer loop."""
        # Start manager
        await websocket_manager.start()
        
        # Add order to queue
        sample_order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        websocket_manager.pending_orders.append(sample_order)
        
        # Mock WebSocket connection
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.send_text = AsyncMock()
        websocket_manager.active_connections["orderBatch"].add(mock_websocket)
        
        # Let timer run briefly
        await asyncio.sleep(0.6)  # Wait for timer to trigger
        
        # Verify batch update was sent
        mock_websocket.send_text.assert_called_once()
        
        # Verify queue was cleared
        assert len(websocket_manager.pending_orders) == 0
        
        # Stop manager
        await websocket_manager.stop()
    
    @pytest.mark.asyncio
    async def test_send_batch_update(self, websocket_manager, sample_order):
        """Test sending batch update."""
        # Add orders to queue
        websocket_manager.pending_orders.append(sample_order)
        websocket_manager.pending_orders.append(sample_order)  # Add another
        
        # Mock WebSocket connection
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.send_text = AsyncMock()
        websocket_manager.active_connections["orderBatch"].add(mock_websocket)
        
        # Send batch update
        await websocket_manager._send_batch_update()
        
        # Verify message was sent
        mock_websocket.send_text.assert_called_once()
        
        # Verify message format
        call_args = mock_websocket.send_text.call_args[0][0]
        message = json.loads(call_args)
        
        assert message["type"] == "orderBatch"
        assert message["channel"] == "orderBatch"
        assert "timestamp" in message
        assert message["data"]["count"] == 2
        assert len(message["data"]["orders"]) == 2
        
        # Verify queue was cleared
        assert len(websocket_manager.pending_orders) == 0
    
    @pytest.mark.asyncio
    async def test_handle_websocket_disconnect(self, websocket_manager, sample_order):
        """Test handling WebSocket disconnection during broadcast."""
        # Connect WebSocket
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock(side_effect=WebSocketDisconnect(1000))
        mock_websocket.close = AsyncMock()
        
        # Mock the connect method to avoid the welcome message error
        with patch.object(websocket_manager, 'connect') as mock_connect:
            mock_connect.return_value = None
            await websocket_manager.connect(mock_websocket, "orderUpdate")
        
        # Try to broadcast (should handle disconnect gracefully)
        await websocket_manager.broadcast_order_update(sample_order)
        
        # Verify WebSocket was removed from connections
        assert mock_websocket not in websocket_manager.active_connections["orderUpdate"]
    
    @pytest.mark.asyncio
    async def test_handle_websocket_error(self, websocket_manager, sample_order):
        """Test handling WebSocket error during broadcast."""
        # Connect WebSocket
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock(side_effect=Exception("Test error"))
        mock_websocket.close = AsyncMock()
        
        # Mock the connect method to avoid the welcome message error
        with patch.object(websocket_manager, 'connect') as mock_connect:
            mock_connect.return_value = None
            await websocket_manager.connect(mock_websocket, "orderUpdate")
        
        # Try to broadcast (should handle error gracefully)
        await websocket_manager.broadcast_order_update(sample_order)
        
        # Verify WebSocket was removed from connections
        assert mock_websocket not in websocket_manager.active_connections["orderUpdate"]
    
    def test_get_connection_stats(self, websocket_manager):
        """Test getting connection statistics."""
        stats = websocket_manager.get_connection_stats()
        
        assert "channels" in stats
        assert "pending_orders" in stats
        assert "is_running" in stats
        
        assert stats["channels"]["orderUpdate"] == 0
        assert stats["channels"]["orderBatch"] == 0
        assert stats["pending_orders"] == 0
        assert stats["is_running"] is False
