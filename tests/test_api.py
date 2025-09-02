"""Tests for API routes."""

import pytest
import tempfile
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from typing import Set

from src.main import app
from src.storage.models import Order, Config, SymbolConfig
from datetime import datetime

client = TestClient(app)

class TestAPI:
    """Tests for API endpoints."""

    def test_root_endpoint(self):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "HyperLiquid Node Parser API"
        assert data["version"] == "1.0.0"

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    @patch('src.main.order_manager')
    def test_get_orders_endpoint(self, mock_manager):
        """Test get orders endpoint."""
        # Mock order manager
        mock_orders = [
            Order(
                id="1",
                symbol="BTC",
                side="Bid",
                price=50000.0,
                size=1.0,
                owner="0x123",
                timestamp=datetime.now(),
                status="open"
            )
        ]
        mock_manager.get_orders.return_value = mock_orders
        
        response = client.get("/api/v1/orders")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["symbol"] == "BTC"

    @patch('src.main.order_manager')
    def test_get_orders_with_filters(self, mock_manager):
        """Test get orders endpoint with filters."""
        mock_orders = []
        mock_manager.get_orders.return_value = mock_orders
        
        response = client.get("/api/v1/orders?symbol=BTC&side=Bid&min_liquidity=1000")
        assert response.status_code == 200
        
        # Verify filters were passed to manager
        mock_manager.get_orders.assert_called_with(
            symbol="BTC",
            side="Bid", 
            min_liquidity=1000.0,
            status=None
        )

    @patch('src.main.order_manager')
    def test_get_order_by_id(self, mock_manager):
        """Test get order by ID endpoint."""
        mock_order = Order(
            id="1",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        mock_manager.get_order_by_id.return_value = mock_order
        
        response = client.get("/api/v1/orders/1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "1"
        assert data["symbol"] == "BTC"

    @patch('src.main.order_manager')
    def test_get_order_by_id_not_found(self, mock_manager):
        """Test get order by ID when not found."""
        mock_manager.get_order_by_id.return_value = None
        
        response = client.get("/api/v1/orders/999")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Order not found"

    @patch('src.main.order_manager')
    def test_get_orders_summary(self, mock_manager):
        """Test get orders summary endpoint."""
        mock_manager.get_order_count.return_value = 5
        mock_manager.get_order_count_by_status.return_value = {
            "open": 3,
            "filled": 1,
            "canceled": 1
        }
        mock_manager.get_open_orders.return_value = [MagicMock(), MagicMock(), MagicMock()]
        
        response = client.get("/api/v1/orders/stats/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_orders"] == 5
        assert data["status_counts"]["open"] == 3
        assert data["open_orders_count"] == 3

    @patch('src.main.config_manager')
    def test_get_config_endpoint(self, mock_config_manager):
        """Test get config endpoint."""
        from src.storage.models import Config
        mock_config = Config(
            node_logs_path="/test/path",
            cleanup_interval_hours=2,
            api_host="0.0.0.0",
            api_port=8000,
            log_level="DEBUG",
            log_file_path="logs/app.log",
            log_max_size_mb=100,
            log_retention_days=30,
            data_dir="data",
            config_file_path="config/config.json",
            max_orders_per_request=1000,
            file_read_retry_attempts=3,
            file_read_retry_delay=1.0,
            symbols_config=[]
        )
        mock_config_manager.get_config.return_value = mock_config
        
        response = client.get("/api/v1/config")
        assert response.status_code == 200
