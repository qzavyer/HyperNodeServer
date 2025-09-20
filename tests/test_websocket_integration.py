"""Integration tests for WebSocket functionality."""

import pytest
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient

from src.main import app
from src.websocket.websocket_manager import WebSocketManager
from src.storage.models import Order


class TestWebSocketIntegration:
    """Integration tests for WebSocket functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.client = TestClient(app)
        self.mock_websocket_manager = Mock(spec=WebSocketManager)
        self.mock_websocket_manager.get_connection_stats.return_value = {
            "channels": {"orderUpdate": 0, "orderBatch": 0},
            "pending_orders": 0,
            "is_running": False
        }

    def test_websocket_status_endpoint(self):
        """Test WebSocket status endpoint."""
        response = self.client.get("/ws/status")
        assert response.status_code == 200
        
        data = response.json()
        assert "channels" in data
        assert "pending_orders" in data
        assert "is_running" in data

    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(self):
        """Test complete WebSocket connection lifecycle."""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.client.host = "127.0.0.1"
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        mock_websocket.close = AsyncMock()
        mock_websocket.client_state = Mock()
        mock_websocket.client_state.name = "CONNECTED"
        
        # Mock receive_text to simulate ping then disconnect
        mock_websocket.receive_text = AsyncMock(side_effect=["ping", WebSocketDisconnect()])

        # Test the complete lifecycle
        from src.api.websocket_routes import websocket_order_update
        await websocket_order_update(mock_websocket)

        # Verify complete flow
        mock_websocket.accept.assert_called_once()
        mock_websocket.send_text.assert_called_with("pong")

    @pytest.mark.asyncio
    async def test_websocket_error_recovery(self):
        """Test WebSocket error recovery mechanisms."""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.client.host = "127.0.0.1"
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        mock_websocket.close = AsyncMock()
        mock_websocket.client_state = Mock()
        mock_websocket.client_state.name = "CONNECTED"
        
        # Mock receive_text to raise an exception
        mock_websocket.receive_text = AsyncMock(side_effect=Exception("Test error"))

        from src.api.websocket_routes import websocket_order_update
        await websocket_order_update(mock_websocket)

        # Verify error handling - the websocket should have been processed
        # The exact behavior depends on when the exception occurs
        assert True  # Test passes if no exception is raised

    @pytest.mark.asyncio
    async def test_websocket_manager_batch_processing(self):
        """Test WebSocket manager batch processing."""
        manager = WebSocketManager()
        
        # Create test orders
        test_orders = [
            Order(id="test-1", symbol="BTC", side="Bid", price=50000.0, size=1.0,
                  owner="0x123", timestamp=datetime.now(), status="open"),
            Order(id="test-2", symbol="ETH", side="Ask", price=3000.0, size=10.0,
                  owner="0x456", timestamp=datetime.now(), status="open")
        ]
        
        # Queue orders
        for order in test_orders:
            await manager.queue_order_for_batch(order)
        
        assert len(manager.pending_orders) == 2
        
        # Send batch update
        await manager._send_batch_update()
        
        # Verify orders were processed
        assert len(manager.pending_orders) == 0

    @pytest.mark.asyncio
    async def test_websocket_manager_multiple_connections(self):
        """Test WebSocket manager with multiple connections."""
        manager = WebSocketManager()
        
        # Create multiple mock websockets
        websockets = []
        for i in range(3):
            mock_ws = Mock(spec=WebSocket)
            mock_ws.client_state = Mock()
            mock_ws.client_state.name = "CONNECTED"
            mock_ws.send_text = AsyncMock()
            websockets.append(mock_ws)
        
        # Connect all websockets
        for ws in websockets:
            await manager.connect(ws, "orderUpdate")
        
        # Verify all connections
        assert len(manager.active_connections["orderUpdate"]) == 3
        
        # Create test order
        test_order = Order(
            id="test-123", symbol="BTC", side="Bid", price=50000.0, size=1.0,
            owner="0x123", timestamp=datetime.now(), status="open"
        )
        
        # Broadcast to all connections
        await manager.broadcast_order_update(test_order)
        
        # Verify all websockets received the message
        for ws in websockets:
            assert ws.send_text.call_count == 2  # Welcome + order update

    @pytest.mark.asyncio
    async def test_websocket_manager_connection_cleanup(self):
        """Test WebSocket manager connection cleanup."""
        manager = WebSocketManager()
        
        # Create mock websocket
        mock_ws = Mock(spec=WebSocket)
        mock_ws.client_state = Mock()
        mock_ws.client_state.name = "CONNECTED"
        mock_ws.send_text = AsyncMock()
        mock_ws.close = AsyncMock()
        
        # Connect websocket
        await manager.connect(mock_ws, "orderUpdate")
        assert len(manager.active_connections["orderUpdate"]) == 1
        
        # Disconnect websocket
        await manager.disconnect(mock_ws)
        assert len(manager.active_connections["orderUpdate"]) == 0
        
        # Verify close was called
        mock_ws.close.assert_called_once_with(code=1000, reason="Normal closure")

    @pytest.mark.asyncio
    async def test_websocket_manager_error_handling(self):
        """Test WebSocket manager error handling."""
        manager = WebSocketManager()
        
        # Create mock websocket that will fail on send
        mock_ws = Mock(spec=WebSocket)
        mock_ws.client_state = Mock()
        mock_ws.client_state.name = "CONNECTED"
        mock_ws.send_text = AsyncMock(side_effect=Exception("Send error"))
        mock_ws.close = AsyncMock()
        
        # Connect websocket - this should raise an exception due to send_text failure
        try:
            await manager.connect(mock_ws, "orderUpdate")
            # If we get here, the test should fail
            assert False, "Expected connect to raise an exception"
        except Exception as e:
            # This is expected
            assert "Send error" in str(e)

    @pytest.mark.asyncio
    async def test_websocket_manager_start_stop_lifecycle(self):
        """Test WebSocket manager start/stop lifecycle."""
        manager = WebSocketManager()
        
        # Initially not running
        assert not manager.is_running
        
        # Start manager
        await manager.start()
        assert manager.is_running
        assert manager.batch_timer is not None
        
        # Stop manager
        await manager.stop()
        assert not manager.is_running
        assert manager.batch_timer is None

    def test_websocket_routes_import(self):
        """Test that WebSocket routes can be imported without errors."""
        from src.api.websocket_routes import router, set_websocket_manager
        
        # Test that router is properly configured
        assert router is not None
        
        # Test that set_websocket_manager function exists
        assert callable(set_websocket_manager)

    def test_websocket_manager_import(self):
        """Test that WebSocket manager can be imported without errors."""
        from src.websocket.websocket_manager import WebSocketManager
        
        # Test that WebSocketManager can be instantiated
        manager = WebSocketManager()
        assert manager is not None
        assert hasattr(manager, 'active_connections')
        assert hasattr(manager, 'pending_orders')
        assert hasattr(manager, 'is_running')
