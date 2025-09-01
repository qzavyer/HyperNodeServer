"""Tests for API routes."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from datetime import datetime

from src.main import app
from src.storage.models import Order, Config
from src.storage.order_manager import OrderManager
from src.storage.config_manager import ConfigManager

client = TestClient(app)

class TestAPIRoutes:
    """Tests for API routes."""
    
    def setup_method(self):
        """Setup before each test."""
        # Create mock order
        self.mock_order = Order(
            id="test_order_1",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x1234567890abcdef",
            timestamp=datetime.now(),
            status="open"
        )
        
        # Create mock config
        self.mock_config = Config(
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
            min_liquidity_by_symbol={},
            supported_symbols=[]
        )
    
    @patch('src.api.routes.src.main.order_manager')
    def test_get_orders_success(self, mock_order_manager):
        """Test successful GET /orders request."""
        # Setup mock
        mock_order_manager.get_orders.return_value = [self.mock_order]
        
        response = client.get("/api/v1/orders")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "test_order_1"
        assert data[0]["symbol"] == "BTC"
        assert data[0]["side"] == "Bid"
        assert data[0]["price"] == 50000.0
        assert data[0]["size"] == 1.0
        assert data[0]["owner"] == "0x1234567890abcdef"
        assert data[0]["status"] == "open"
    
    @patch('src.api.routes.src.main.order_manager')
    def test_get_orders_with_filters(self, mock_order_manager):
        """Test GET /orders with query parameters."""
        # Setup mock
        mock_order_manager.get_orders.return_value = [self.mock_order]
        
        response = client.get("/api/v1/orders?symbol=BTC&side=Bid&min_liquidity=1000&status=open")
        
        assert response.status_code == 200
        mock_order_manager.get_orders.assert_called_once_with(
            symbol="BTC",
            side="Bid", 
            min_liquidity=1000.0,
            status="open"
        )
    
    @patch('src.api.routes.src.main.order_manager')
    def test_get_orders_error(self, mock_order_manager):
        """Test GET /orders error handling."""
        # Setup mock to raise exception
        mock_order_manager.get_orders.side_effect = Exception("Database error")
        
        response = client.get("/api/v1/orders")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to get orders" in data["detail"]
    
    @patch('src.api.routes.src.main.order_manager')
    def test_get_order_by_id_success(self, mock_order_manager):
        """Test successful GET /orders/{order_id} request."""
        # Setup mock
        mock_order_manager.get_order_by_id.return_value = self.mock_order
        
        response = client.get("/api/v1/orders/test_order_1")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test_order_1"
        assert data["symbol"] == "BTC"
        assert data["side"] == "Bid"
        assert data["price"] == 50000.0
        assert data["size"] == 1.0
        assert data["owner"] == "0x1234567890abcdef"
        assert data["status"] == "open"
    
    @patch('src.api.routes.src.main.order_manager')
    def test_get_order_by_id_not_found(self, mock_order_manager):
        """Test GET /orders/{order_id} when order not found."""
        # Setup mock
        mock_order_manager.get_order_by_id.return_value = None
        
        response = client.get("/api/v1/orders/nonexistent_order")
        
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Order not found"
    
    @patch('src.api.routes.src.main.order_manager')
    def test_get_orders_summary_success(self, mock_order_manager):
        """Test successful GET /orders/stats/summary request."""
        # Setup mock
        mock_order_manager.get_order_count.return_value = 100
        mock_order_manager.get_order_count_by_status.return_value = {
            "open": 50,
            "filled": 30,
            "cancelled": 15,
            "triggered": 5
        }
        mock_order_manager.get_open_orders.return_value = [self.mock_order] * 50
        
        response = client.get("/api/v1/orders/stats/summary")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_orders"] == 100
        assert data["status_counts"]["open"] == 50
        assert data["status_counts"]["filled"] == 30
        assert data["status_counts"]["cancelled"] == 15
        assert data["status_counts"]["triggered"] == 5
        assert data["open_orders_count"] == 50
    
    @patch('src.api.routes.src.main.order_manager')
    def test_get_orders_summary_error(self, mock_order_manager):
        """Test GET /orders/stats/summary error handling."""
        # Setup mock to raise exception
        mock_order_manager.get_order_count.side_effect = Exception("Database error")
        
        response = client.get("/api/v1/orders/stats/summary")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to get summary" in data["detail"]
    
    @patch('src.api.routes.src.main.config_manager')
    def test_get_config_success(self, mock_config_manager):
        """Test successful GET /config request."""
        # Setup mock
        mock_config_manager.get_config.return_value = self.mock_config
        
        response = client.get("/api/v1/config")
        
        assert response.status_code == 200
        data = response.json()
        assert data["node_logs_path"] == "/test/path"
        assert data["cleanup_interval_hours"] == 2
        assert data["api_host"] == "0.0.0.0"
        assert data["api_port"] == 8000
        assert data["log_level"] == "DEBUG"
        assert data["log_file_path"] == "logs/app.log"
        assert data["log_max_size_mb"] == 100
        assert data["log_retention_days"] == 30
        assert data["data_dir"] == "data"
        assert data["config_file_path"] == "config/config.json"
        assert data["max_orders_per_request"] == 1000
        assert data["file_read_retry_attempts"] == 3
        assert data["file_read_retry_delay"] == 1.0
        assert data["min_liquidity_by_symbol"] == {}
        assert data["supported_symbols"] == []
    
    @patch('src.api.routes.src.main.config_manager')
    def test_get_config_error(self, mock_config_manager):
        """Test GET /config error handling."""
        # Setup mock to raise exception
        mock_config_manager.get_config.side_effect = Exception("Config error")
        
        response = client.get("/api/v1/config")
        
        assert response.status_code == 500
        data = response.json()
        assert "Failed to get config" in data["detail"]
    
    @patch('src.api.routes.src.main.config_manager')
    def test_update_config_success(self, mock_config_manager):
        """Test successful PUT /config request."""
        # Setup mock
        updated_config = Config(
            node_logs_path="/new/path",
            cleanup_interval_hours=5,
            api_host="127.0.0.1",
            api_port=9000,
            log_level="INFO",
            log_file_path="logs/new.log",
            log_max_size_mb=200,
            log_retention_days=60,
            data_dir="new_data",
            config_file_path="config/new.json",
            max_orders_per_request=2000,
            file_read_retry_attempts=5,
            file_read_retry_delay=2.0,
            min_liquidity_by_symbol={"BTC": 1000.0},
            supported_symbols=["BTC", "ETH"]
        )
        mock_config_manager.update_config_async.return_value = updated_config
        
        updates = {
            "api_port": 9000,
            "log_level": "INFO",
            "min_liquidity_by_symbol": {"BTC": 1000.0}
        }
        
        response = client.put("/api/v1/config", json=updates)
        
        assert response.status_code == 200
        data = response.json()
        assert data["api_port"] == 9000
        assert data["log_level"] == "INFO"
        assert data["min_liquidity_by_symbol"] == {"BTC": 1000.0}
        
        # Verify the update method was called
        mock_config_manager.update_config_async.assert_called_once_with(updates)
    
    @patch('src.api.routes.src.main.config_manager')
    def test_update_config_error(self, mock_config_manager):
        """Test PUT /config error handling."""
        # Setup mock to raise exception
        mock_config_manager.update_config_async.side_effect = Exception("Update error")
        
        updates = {"api_port": 99999}  # Invalid port
        
        response = client.put("/api/v1/config", json=updates)
        
        assert response.status_code == 400
        data = response.json()
        assert "Failed to update config" in data["detail"]
    
    def test_root_endpoint(self):
        """Test GET / root endpoint."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "HyperLiquid Node Parser API"
        assert data["version"] == "1.0.0"
    
    @patch('src.api.routes.src.main.order_manager')
    def test_health_check_endpoint(self, mock_order_manager):
        """Test GET /health health check endpoint."""
        # Setup mock
        mock_order_manager.get_order_count.return_value = 100
        mock_order_manager.get_order_count_by_status.return_value = {
            "open": 50,
            "filled": 30,
            "cancelled": 15,
            "triggered": 5
        }
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["order_count"] == 100
        assert data["order_manager_stats"]["open"] == 50
        assert data["order_manager_stats"]["filled"] == 30
        assert data["order_manager_stats"]["cancelled"] == 15
        assert data["order_manager_stats"]["triggered"] == 5
