"""Tests for cleanup API endpoints."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient

from src.main import app
from src.cleanup.directory_cleaner import DirectoryCleaner


class TestCleanupAPI:
    """Test cases for cleanup API endpoints."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.client = TestClient(app)
        
    def teardown_method(self):
        """Cleanup test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_run_cleanup_dry_run(self):
        """Test cleanup endpoint in dry-run mode."""
        response = self.client.post(
            "/api/v1/cleanup/run",
            json={"dry_run": True, "force": False}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "removed_directories" in data
        assert "removed_files" in data
        assert data["dry_run"] is True
        assert "execution_time_seconds" in data
    
    def test_run_cleanup_normal_mode(self):
        """Test cleanup endpoint in normal mode."""
        response = self.client.post(
            "/api/v1/cleanup/run",
            json={"dry_run": False, "force": False}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "removed_directories" in data
        assert "removed_files" in data
        assert data["dry_run"] is False
        assert "execution_time_seconds" in data
    
    def test_run_cleanup_error(self):
        """Test cleanup endpoint with error."""
        # Mock the directory cleaner to raise an exception
        mock_cleaner = Mock(spec=DirectoryCleaner)
        mock_cleaner.cleanup_async = AsyncMock(side_effect=Exception("Test error"))
        mock_cleaner.logger = Mock()
        
        with patch('src.api.cleanup_routes.get_directory_cleaner', return_value=mock_cleaner):
            response = self.client.post(
                "/api/v1/cleanup/run",
                json={"dry_run": False, "force": False}
            )
        
        assert response.status_code == 500
        data = response.json()
        assert "Test error" in data["detail"]
    
    def test_get_cleanup_report(self):
        """Test cleanup report endpoint."""
        # Mock the directory cleaner
        mock_cleaner = Mock(spec=DirectoryCleaner)
        mock_report = {
            "timestamp": 1234567890,
            "dry_run": True,
            "summary": {
                "total_directories_to_remove": 5,
                "total_files_to_remove": 10,
                "estimated_space_to_free_mb": 100.5
            }
        }
        mock_cleaner.get_cleanup_report = Mock(return_value=mock_report)
        mock_cleaner.logger = Mock()
        
        with patch('src.api.cleanup_routes.get_directory_cleaner', return_value=mock_cleaner):
            response = self.client.get("/api/v1/cleanup/report?dry_run=true")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["dry_run"] is True
        assert data["report"] == mock_report
        
        # Verify the method was called with dry_run=True
        mock_cleaner.get_cleanup_report.assert_called_once_with(dry_run=True)
    
    def test_get_cleanup_stats(self):
        """Test cleanup stats endpoint."""
        # Mock the directory cleaner
        mock_cleaner = Mock(spec=DirectoryCleaner)
        mock_stats = {
            "total_cleanups": 10,
            "total_directories_removed": 50,
            "total_files_removed": 100
        }
        mock_cleaner.get_cleanup_stats = Mock(return_value=mock_stats)
        mock_cleaner.cleanup_interval_hours = 1
        mock_cleaner.file_retention_hours = 2
        mock_cleaner.target_cleanup_path = Path("/test/path")
        mock_cleaner.config = None
        mock_cleaner.config_path = None
        mock_cleaner.logger = Mock()
        
        with patch('src.api.cleanup_routes.get_directory_cleaner', return_value=mock_cleaner):
            response = self.client.get("/api/v1/cleanup/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "cleanup_interval_hours" in data["stats"]
        assert "file_retention_hours" in data["stats"]
        assert "target_cleanup_path" in data["stats"]
        assert "config_loaded" in data["stats"]
    
    def test_get_cleanup_config_summary_no_config(self):
        """Test config summary endpoint with no config loaded."""
        # Mock the directory cleaner
        mock_cleaner = Mock(spec=DirectoryCleaner)
        mock_cleaner.config = None
        mock_cleaner.logger = Mock()
        
        with patch('src.api.cleanup_routes.get_directory_cleaner', return_value=mock_cleaner):
            response = self.client.get("/api/v1/cleanup/config/summary")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["config_loaded"] is False
        assert "No configuration loaded" in data["message"]
    
    def test_get_cleanup_config_summary_with_config(self):
        """Test config summary endpoint with config loaded."""
        # Mock the directory cleaner
        mock_cleaner = Mock(spec=DirectoryCleaner)
        mock_cleaner.config = {"version": "1.0", "rules": []}
        mock_cleaner.get_config_summary = Mock(return_value={"version": "1.0", "rule_count": 5})
        mock_cleaner.logger = Mock()
        
        with patch('src.api.cleanup_routes.get_directory_cleaner', return_value=mock_cleaner):
            response = self.client.get("/api/v1/cleanup/config/summary")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["config_loaded"] is True
        assert "summary" in data
    
    def test_load_cleanup_config(self):
        """Test load config endpoint."""
        # Mock the directory cleaner
        mock_cleaner = Mock(spec=DirectoryCleaner)
        mock_cleaner.load_config = Mock()
        mock_cleaner.get_config_summary = Mock(return_value={"version": "1.0", "rule_count": 5})
        mock_cleaner.logger = Mock()
        
        with patch('src.api.cleanup_routes.get_directory_cleaner', return_value=mock_cleaner):
            response = self.client.post(
                "/api/v1/cleanup/config/load",
                params={"config_path": "/test/config.json"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["config_path"] == "/test/config.json"
        assert "summary" in data
        
        # Verify the method was called
        mock_cleaner.load_config.assert_called_once_with("/test/config.json")
    
    def test_load_cleanup_config_error(self):
        """Test load config endpoint with error."""
        # Mock the directory cleaner to raise an exception
        mock_cleaner = Mock(spec=DirectoryCleaner)
        mock_cleaner.load_config = Mock(side_effect=Exception("Config file not found"))
        mock_cleaner.logger = Mock()
        
        with patch('src.api.cleanup_routes.get_directory_cleaner', return_value=mock_cleaner):
            response = self.client.post(
                "/api/v1/cleanup/config/load",
                params={"config_path": "/nonexistent/config.json"}
            )
        
        assert response.status_code == 400
        data = response.json()
        assert "Config file not found" in data["detail"]
    
    def test_apply_cleanup_config_dry_run(self):
        """Test apply config endpoint in dry-run mode."""
        # Mock the directory cleaner
        mock_cleaner = Mock(spec=DirectoryCleaner)
        mock_cleaner.config = {"version": "1.0", "rules": []}
        mock_cleaner.apply_config_rules_async = AsyncMock(return_value=(3, 7))
        mock_cleaner.logger = Mock()
        
        with patch('src.api.cleanup_routes.get_directory_cleaner', return_value=mock_cleaner):
            response = self.client.post(
                "/api/v1/cleanup/config/apply?dry_run=true"
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["removed_directories"] == 3
        assert data["removed_files"] == 7
        assert data["dry_run"] is True
        
        # Verify the method was called with dry_run=True
        mock_cleaner.apply_config_rules_async.assert_called_once_with(dry_run=True)
    
    def test_apply_cleanup_config_no_config(self):
        """Test apply config endpoint with no config loaded."""
        # Mock the directory cleaner
        mock_cleaner = Mock(spec=DirectoryCleaner)
        mock_cleaner.config = None
        mock_cleaner.logger = Mock()
        
        with patch('src.api.cleanup_routes.get_directory_cleaner', return_value=mock_cleaner):
            response = self.client.post(
                "/api/v1/cleanup/config/apply?dry_run=false"
            )
        
        assert response.status_code == 400
        data = response.json()
        assert "No configuration loaded" in data["detail"]
    
    def test_get_cleanup_health(self):
        """Test cleanup health endpoint."""
        # Mock the directory cleaner
        mock_cleaner = Mock(spec=DirectoryCleaner)
        mock_cleaner.logger = Mock()
        mock_cleaner.logger.handlers = [Mock()]
        mock_cleaner.logger.handlers[0].formatter = Mock()
        mock_cleaner.logger.handlers[0].formatter.formatTime = Mock(return_value="2025-01-01T00:00:00Z")
        mock_cleaner.logger.handlers[0].formatter.converter = Mock()
        mock_cleaner.logger.handlers[0].formatter.converter.now = Mock(return_value=1234567890)
        mock_cleaner.target_cleanup_path = Path(self.temp_dir)
        mock_cleaner.target_cleanup_path.mkdir(exist_ok=True)
        mock_cleaner.cleanup_interval_hours = 1
        mock_cleaner.file_retention_hours = 2
        
        with patch('src.api.cleanup_routes.get_directory_cleaner', return_value=mock_cleaner):
            response = self.client.get("/api/v1/cleanup/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "health" in data
        assert data["health"]["status"] in ["healthy", "degraded"]
        assert "cleaner_initialized" in data["health"]
        assert "config_loaded" in data["health"]
        assert "target_path_exists" in data["health"]
    
    def test_get_cleanup_health_error(self):
        """Test cleanup health endpoint with error."""
        # Mock the directory cleaner to raise an exception
        mock_cleaner = Mock(spec=DirectoryCleaner)
        mock_cleaner.logger = Mock()
        mock_cleaner.logger.handlers = []
        mock_cleaner.target_cleanup_path = Mock()
        mock_cleaner.target_cleanup_path.exists = Mock(side_effect=Exception("Test error"))
        
        with patch('src.api.cleanup_routes.get_directory_cleaner', return_value=mock_cleaner):
            response = self.client.get("/api/v1/cleanup/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["health"]["status"] == "unhealthy"
        assert "Test error" in data["health"]["error"]
