"""Tests for health API endpoints."""

import pytest
import tempfile
import os
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from src.main import app
from src.monitoring.node_health_monitor import NodeHealthStatus, NodeHealthMonitor

# Create temp directory for tests
temp_dir = tempfile.mkdtemp()
os.environ['NODE_LOGS_PATH'] = temp_dir

client = TestClient(app)

class TestHealthAPI:
    """Tests for health API endpoints."""
    
    def setup_method(self):
        """Setup for each test method."""
        # Initialize node health monitor for tests
        from src.main import node_health_monitor
        from src.storage.config_manager import ConfigManager
        
        # Create a mock config manager and initialize monitor
        config_manager = ConfigManager()
        config = config_manager._create_default_config()
        
        # Set the global monitor instance
        import src.main
        src.main.node_health_monitor = NodeHealthMonitor(
            node_logs_path=temp_dir,
            threshold_minutes=config.node_health.threshold_minutes
        )
    
    def test_basic_health_check(self):
        """Test enhanced health check endpoint."""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "data" in data
        assert "timestamp" in data
        
        # Check data structure
        health_data = data["data"]
        assert "nodeStatus" in health_data
        assert "lastUpdate" in health_data
        assert "errorCount" in health_data
        assert "responseTime" in health_data
        assert "uptime" in health_data
        assert "criticalAlerts" in health_data
    
    @patch('src.main.node_health_monitor')
    def test_node_health_status_success(self, mock_monitor):
        """Test successful node health status retrieval."""
        # Mock the health status
        mock_status = NodeHealthStatus(
            status="online",
            last_log_update=datetime.now(timezone.utc),
            log_directory_accessible=True,
            threshold_minutes=5,
            check_timestamp=datetime.now(timezone.utc)
        )
        mock_monitor.get_health_status.return_value = mock_status
        
        response = client.get("/api/v1/node-health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["nodeStatus"] == "online"
        assert data["log_directory_accessible"] is True
        assert data["threshold_minutes"] == 5
        assert "lastUpdate" in data
        assert "check_timestamp" in data
    
    @patch('src.main.node_health_monitor')
    def test_node_health_status_unhealthy(self, mock_monitor):
        """Test node health status when unhealthy."""
        # Mock unhealthy status
        mock_status = NodeHealthStatus(
            status="degraded",
            last_log_update=datetime.now(timezone.utc),
            log_directory_accessible=True,
            threshold_minutes=5,
            check_timestamp=datetime.now(timezone.utc)
        )
        mock_monitor.get_health_status.return_value = mock_status
        
        response = client.get("/api/v1/node-health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["nodeStatus"] == "degraded"
        assert data["log_directory_accessible"] is True
    
    @patch('src.main.node_health_monitor')
    def test_node_health_status_server_unavailable(self, mock_monitor):
        """Test node health status when server is unavailable."""
        # Mock server unavailable status
        mock_status = NodeHealthStatus(
            status="offline",
            last_log_update=None,
            log_directory_accessible=False,
            threshold_minutes=5,
            check_timestamp=datetime.now(timezone.utc)
        )
        mock_monitor.get_health_status.return_value = mock_status
        
        response = client.get("/api/v1/node-health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["nodeStatus"] == "offline"
        assert data["log_directory_accessible"] is False
        assert data["lastUpdate"] is None
    
    @patch('src.main.node_health_monitor')
    def test_node_health_status_monitor_not_initialized(self, mock_monitor):
        """Test node health status when monitor is not initialized."""
        # Set monitor to None to simulate not initialized state
        mock_monitor = None
        
        with patch('src.api.health_routes.src.main.node_health_monitor', None):
            response = client.get("/api/v1/node-health")
            
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "not initialized" in data["detail"]
    
    @patch('src.main.node_health_monitor')
    def test_node_health_status_exception(self, mock_monitor):
        """Test node health status when monitor raises exception."""
        # Mock monitor to raise exception
        mock_monitor.get_health_status.side_effect = Exception("Test exception")
        
        response = client.get("/api/v1/node-health")
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Unable to retrieve node health status" in data["detail"]
    
    @patch('src.main.node_health_monitor')
    def test_node_health_status_response_format(self, mock_monitor):
        """Test that node health status response has correct format."""
        # Mock status with specific values
        test_time = datetime(2025, 1, 13, 20, 30, 0, tzinfo=timezone.utc)
        mock_status = NodeHealthStatus(
            status="online",
            last_log_update=test_time,
            log_directory_accessible=True,
            threshold_minutes=10,
            check_timestamp=test_time
        )
        mock_monitor.get_health_status.return_value = mock_status
        
        response = client.get("/api/v1/node-health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields are present
        required_fields = [
            "nodeStatus", "lastUpdate", "log_directory_accessible", 
            "threshold_minutes", "check_timestamp"
        ]
        for field in required_fields:
            assert field in data
        
        # Check field types
        assert isinstance(data["nodeStatus"], str)
        assert isinstance(data["log_directory_accessible"], bool)
        assert isinstance(data["threshold_minutes"], int)
        
        # Check timestamp format
        assert data["lastUpdate"] == test_time.isoformat()
        assert data["check_timestamp"] == test_time.isoformat()
    
    @patch('src.main.node_health_monitor')
    def test_node_health_status_different_thresholds(self, mock_monitor):
        """Test node health status with different threshold values."""
        test_cases = [
            (1, "healthy"),
            (5, "healthy"), 
            (10, "unhealthy"),
            (60, "unhealthy")
        ]
        
        for threshold, expected_status in test_cases:
            mock_status = NodeHealthStatus(
                status=expected_status,
                last_log_update=datetime.now(timezone.utc),
                log_directory_accessible=True,
                threshold_minutes=threshold,
                check_timestamp=datetime.now(timezone.utc)
            )
            mock_monitor.get_health_status.return_value = mock_status
            
            response = client.get("/api/v1/node-health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["nodeStatus"] == expected_status
            assert data["threshold_minutes"] == threshold
    
    def test_health_endpoint_metrics(self):
        """Test health endpoint returns correct metrics structure."""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert data["status"] == "success"
        assert "data" in data
        assert "timestamp" in data
        
        # Check data metrics
        health_data = data["data"]
        required_fields = [
            "nodeStatus", "lastUpdate", "errorCount", 
            "responseTime", "uptime", "criticalAlerts"
        ]
        
        for field in required_fields:
            assert field in health_data, f"Missing field: {field}"
        
        # Check field types
        assert isinstance(health_data["nodeStatus"], str)
        assert isinstance(health_data["errorCount"], int)
        assert isinstance(health_data["responseTime"], (int, float))
        assert isinstance(health_data["uptime"], (int, float))
        assert isinstance(health_data["criticalAlerts"], list)
        
        # Check nodeStatus values
        assert health_data["nodeStatus"] in ["online", "offline", "degraded"]
