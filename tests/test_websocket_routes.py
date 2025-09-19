"""Tests for WebSocket routes functionality."""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient

from src.api.websocket_routes import router, set_websocket_manager
from src.websocket.websocket_manager import WebSocketManager


class TestWebSocketRoutes:
    """Test WebSocket routes functionality."""

    def setup_method(self):
        """Setup test environment."""
        self.mock_websocket_manager = Mock(spec=WebSocketManager)
        self.mock_websocket_manager.connect = AsyncMock()
        self.mock_websocket_manager.disconnect = AsyncMock()
        set_websocket_manager(self.mock_websocket_manager)

    @pytest.mark.asyncio
    async def test_websocket_order_update_success(self):
        """Test successful WebSocket orderUpdate connection."""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.client.host = "127.0.0.1"
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
        mock_websocket.send_text = AsyncMock()

        # Test the WebSocket handler
        from src.api.websocket_routes import websocket_order_update
        await websocket_order_update(mock_websocket)

        # Verify connection was accepted and connected to manager
        mock_websocket.accept.assert_called_once()
        self.mock_websocket_manager.connect.assert_called_once_with(mock_websocket, "orderUpdate")
        self.mock_websocket_manager.disconnect.assert_called_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_websocket_order_update_no_manager(self):
        """Test WebSocket orderUpdate when manager is not initialized."""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.client.host = "127.0.0.1"

        # Set manager to None
        set_websocket_manager(None)

        from src.api.websocket_routes import websocket_order_update
        await websocket_order_update(mock_websocket)

        # Verify no connection was attempted
        mock_websocket.accept.assert_not_called()

    @pytest.mark.asyncio
    async def test_websocket_order_update_ping_pong(self):
        """Test WebSocket ping/pong mechanism."""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.client.host = "127.0.0.1"
        mock_websocket.accept = AsyncMock()
        mock_websocket.send_text = AsyncMock()
        
        # Mock receive_text to return "ping" then disconnect
        mock_websocket.receive_text = AsyncMock(side_effect=["ping", WebSocketDisconnect()])

        from src.api.websocket_routes import websocket_order_update
        await websocket_order_update(mock_websocket)

        # Verify pong was sent
        mock_websocket.send_text.assert_called_with("pong")

    @pytest.mark.asyncio
    async def test_websocket_order_update_close_command(self):
        """Test WebSocket close command handling."""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.client.host = "127.0.0.1"
        mock_websocket.accept = AsyncMock()
        mock_websocket.close = AsyncMock()
        mock_websocket.client_state = Mock()
        mock_websocket.client_state.name = "CONNECTED"
        
        # Mock receive_text to return "close"
        mock_websocket.receive_text = AsyncMock(side_effect=["close"])

        from src.api.websocket_routes import websocket_order_update
        await websocket_order_update(mock_websocket)

        # Verify close was called with correct parameters
        mock_websocket.close.assert_called_once_with(code=1000, reason="Client requested close")

    @pytest.mark.asyncio
    async def test_websocket_order_update_connection_error(self):
        """Test WebSocket orderUpdate connection error handling."""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.client.host = "127.0.0.1"
        mock_websocket.accept = AsyncMock(side_effect=Exception("Connection error"))
        mock_websocket.close = AsyncMock()
        mock_websocket.client_state = Mock()
        mock_websocket.client_state.name = "CONNECTED"

        from src.api.websocket_routes import websocket_order_update
        await websocket_order_update(mock_websocket)

        # Verify error handling
        mock_websocket.close.assert_called_once_with(code=1000, reason="Server error")
        self.mock_websocket_manager.disconnect.assert_called_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_websocket_order_batch_success(self):
        """Test successful WebSocket orderBatch connection."""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.client.host = "127.0.0.1"
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
        mock_websocket.send_text = AsyncMock()

        from src.api.websocket_routes import websocket_order_batch
        await websocket_order_batch(mock_websocket)

        # Verify connection was accepted and connected to manager
        mock_websocket.accept.assert_called_once()
        self.mock_websocket_manager.connect.assert_called_once_with(mock_websocket, "orderBatch")
        self.mock_websocket_manager.disconnect.assert_called_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_websocket_order_batch_message_loop_error(self):
        """Test WebSocket orderBatch message loop error handling."""
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.client.host = "127.0.0.1"
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_text = AsyncMock(side_effect=Exception("Message loop error"))
        mock_websocket.send_text = AsyncMock()

        from src.api.websocket_routes import websocket_order_batch
        await websocket_order_batch(mock_websocket)

        # Verify error handling and cleanup
        self.mock_websocket_manager.disconnect.assert_called_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_websocket_status_no_manager(self):
        """Test WebSocket status when manager is not initialized."""
        set_websocket_manager(None)
        
        from src.api.websocket_routes import websocket_status
        result = await websocket_status()
        
        assert result == {"error": "WebSocket manager not initialized"}

    @pytest.mark.asyncio
    async def test_websocket_status_with_manager(self):
        """Test WebSocket status with initialized manager."""
        mock_stats = {"channels": {"orderUpdate": 2, "orderBatch": 1}, "pending_orders": 5, "is_running": True}
        self.mock_websocket_manager.get_connection_stats.return_value = mock_stats
        
        from src.api.websocket_routes import websocket_status
        result = await websocket_status()
        
        assert result == mock_stats
        self.mock_websocket_manager.get_connection_stats.assert_called_once()
