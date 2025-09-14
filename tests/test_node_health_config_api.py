"""Tests for node health configuration API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, Mock
from src.main import app
from src.storage.models import NodeHealthConfig, Config

client = TestClient(app)

class TestNodeHealthConfigAPI:
    """Test node health configuration API endpoints."""
    
    def setup_method(self):
        """Setup test environment."""
        # Mock config manager with complete Config
        self.mock_config = Config(
            node_logs_path="/app/node_logs",
            cleanup_interval_hours=2,
            api_host="0.0.0.0",
            api_port=8000,
            log_level="DEBUG",
            log_file_path="/app/logs/app.log",
            log_max_size_mb=100,
            log_retention_days=30,
            data_dir="/app/data",
            config_file_path="/app/config.json",
            max_orders_per_request=1000,
            file_read_retry_attempts=3,
            file_read_retry_delay=1.0,
            symbols_config=[],
            node_health=NodeHealthConfig(
                threshold_minutes=5,
                check_interval_seconds=30
            )
        )
    
    @patch('src.main.config_manager')
    def test_get_node_health_config_success(self, mock_config_manager):
        """Test successful retrieval of node health configuration."""
        # Setup mock
        mock_config_manager.get_config.return_value = self.mock_config
        
        # Test
        response = client.get("/api/v1/config/node-health")
        
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["threshold_minutes"] == 5
        assert data["check_interval_seconds"] == 30
    
    @patch('src.main.config_manager')
    def test_get_node_health_config_error(self, mock_config_manager):
        """Test error handling in get node health configuration."""
        # Setup mock to raise exception
        mock_config_manager.get_config.side_effect = Exception("Database error")
        
        # Test
        response = client.get("/api/v1/config/node-health")
        
        assert response.status_code == 500
        assert "Failed to get node health configuration" in response.json()["detail"]
    
    @patch('src.main.config_manager')
    def test_update_node_health_config_success(self, mock_config_manager):
        """Test successful update of node health configuration."""
        # Setup mock
        mock_config_manager.get_config.return_value = self.mock_config
        mock_config_manager.save_config_async = AsyncMock()
        
        # Test data
        config_data = {
            "threshold_minutes": 10,
            "check_interval_seconds": 60
        }
        
        # Test
        response = client.post("/api/v1/config/node-health", json=config_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["config"]["threshold_minutes"] == 10
        assert data["config"]["check_interval_seconds"] == 60
    
    def test_update_node_health_config_missing_fields(self):
        """Test validation of missing required fields."""
        # Test data with missing field
        config_data = {
            "threshold_minutes": 10
            # Missing check_interval_seconds
        }
        
        # Test
        response = client.post("/api/v1/config/node-health", json=config_data)
        
        assert response.status_code == 400
        assert "Missing required field: check_interval_seconds" in response.json()["detail"]
    
    def test_update_node_health_config_invalid_threshold(self):
        """Test validation of invalid threshold_minutes."""
        # Test data with invalid threshold
        config_data = {
            "threshold_minutes": 100,  # Invalid: > 60
            "check_interval_seconds": 30
        }
        
        # Test
        response = client.post("/api/v1/config/node-health", json=config_data)
        
        assert response.status_code == 400
        assert "threshold_minutes must be an integer between 1 and 60" in response.json()["detail"]
    
    def test_update_node_health_config_invalid_interval(self):
        """Test validation of invalid check_interval_seconds."""
        # Test data with invalid interval
        config_data = {
            "threshold_minutes": 5,
            "check_interval_seconds": 5  # Invalid: < 10
        }
        
        # Test
        response = client.post("/api/v1/config/node-health", json=config_data)
        
        assert response.status_code == 400
        assert "check_interval_seconds must be an integer between 10 and 300" in response.json()["detail"]
    
    @patch('src.main.config_manager')
    def test_update_node_health_config_save_error(self, mock_config_manager):
        """Test error handling during config save."""
        # Setup mock
        mock_config_manager.get_config.return_value = self.mock_config
        mock_config_manager.save_config_async.side_effect = Exception("Save error")
        
        # Test data
        config_data = {
            "threshold_minutes": 10,
            "check_interval_seconds": 60
        }
        
        # Test
        response = client.post("/api/v1/config/node-health", json=config_data)
        
        assert response.status_code == 500
        assert "Failed to update node health configuration" in response.json()["detail"]
