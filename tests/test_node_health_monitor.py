"""Tests for NodeHealthMonitor."""

import pytest
import tempfile
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, mock_open
from src.monitoring.node_health_monitor import NodeHealthMonitor, NodeHealthStatus


class TestNodeHealthStatus:
    """Tests for NodeHealthStatus class."""
    
    def test_node_health_status_creation(self):
        """Test creating NodeHealthStatus object."""
        now = datetime.now(timezone.utc)
        status = NodeHealthStatus(
            status="healthy",
            last_log_update=now,
            log_directory_accessible=True,
            threshold_minutes=5,
            check_timestamp=now
        )
        
        assert status.status == "healthy"
        assert status.last_log_update == now
        assert status.log_directory_accessible is True
        assert status.threshold_minutes == 5
        assert status.check_timestamp == now
    
    def test_to_dict_conversion(self):
        """Test converting NodeHealthStatus to dictionary."""
        now = datetime.now(timezone.utc)
        status = NodeHealthStatus(
            status="unhealthy",
            last_log_update=now,
            log_directory_accessible=True,
            threshold_minutes=10,
            check_timestamp=now
        )
        
        result = status.to_dict()
        
        assert result["status"] == "unhealthy"
        assert result["last_log_update"] == now.isoformat()
        assert result["log_directory_accessible"] is True
        assert result["threshold_minutes"] == 10
        assert result["check_timestamp"] == now.isoformat()
    
    def test_to_dict_with_none_timestamp(self):
        """Test to_dict with None last_log_update."""
        now = datetime.now(timezone.utc)
        status = NodeHealthStatus(
            status="server_unavailable",
            last_log_update=None,
            log_directory_accessible=False,
            threshold_minutes=5,
            check_timestamp=now
        )
        
        result = status.to_dict()
        
        assert result["last_log_update"] is None


class TestNodeHealthMonitor:
    """Tests for NodeHealthMonitor class."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.monitor = NodeHealthMonitor(self.temp_dir, threshold_minutes=5)
    
    def teardown_method(self):
        """Cleanup test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init(self):
        """Test NodeHealthMonitor initialization."""
        monitor = NodeHealthMonitor("/test/path", threshold_minutes=10)
        
        assert monitor.node_logs_path == Path("/test/path")
        assert monitor.threshold_minutes == 10
    
    def test_get_last_log_update_time_no_directory(self):
        """Test get_last_log_update_time when directory doesn't exist."""
        monitor = NodeHealthMonitor("/nonexistent/path")
        
        result = monitor.get_last_log_update_time()
        
        assert result is None
    
    def test_get_last_log_update_time_empty_directory(self):
        """Test get_last_log_update_time with empty directory."""
        result = self.monitor.get_last_log_update_time()
        
        assert result is None
    
    def test_get_last_log_update_time_with_files(self):
        """Test get_last_log_update_time with log files."""
        # Create test files with different timestamps
        file1 = Path(self.temp_dir) / "log1.txt"
        file2 = Path(self.temp_dir) / "log2.txt"
        
        # Create files
        file1.write_text("test log 1")
        file2.write_text("test log 2")
        
        # Set different modification times
        old_time = datetime.now(timezone.utc) - timedelta(hours=1)
        new_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        os.utime(file1, (old_time.timestamp(), old_time.timestamp()))
        os.utime(file2, (new_time.timestamp(), new_time.timestamp()))
        
        result = self.monitor.get_last_log_update_time()
        
        assert result is not None
        # Should return the newer timestamp
        assert abs((result - new_time).total_seconds()) < 1
    
    def test_check_log_directory_access_existing_directory(self):
        """Test check_log_directory_access with existing directory."""
        result = self.monitor.check_log_directory_access()
        
        assert result is True
    
    def test_check_log_directory_access_nonexistent_directory(self):
        """Test check_log_directory_access with nonexistent directory."""
        monitor = NodeHealthMonitor("/nonexistent/path")
        
        result = monitor.check_log_directory_access()
        
        assert result is False
    
    def test_check_log_directory_access_file_instead_of_directory(self):
        """Test check_log_directory_access with file instead of directory."""
        # Create a file
        test_file = Path(self.temp_dir) / "test_file.txt"
        test_file.write_text("test")
        
        monitor = NodeHealthMonitor(str(test_file))
        
        result = monitor.check_log_directory_access()
        
        assert result is False
    
    def test_get_health_status_directory_not_accessible(self):
        """Test get_health_status when directory is not accessible."""
        monitor = NodeHealthMonitor("/nonexistent/path")
        
        status = monitor.get_health_status()
        
        assert status.status == "server_unavailable"
        assert status.log_directory_accessible is False
        assert status.last_log_update is None
    
    def test_get_health_status_no_log_files(self):
        """Test get_health_status with no log files."""
        status = self.monitor.get_health_status()
        
        assert status.status == "unhealthy"
        assert status.log_directory_accessible is True
        assert status.last_log_update is None
    
    def test_get_health_status_healthy(self):
        """Test get_health_status with recent log files."""
        # Create a recent log file
        log_file = Path(self.temp_dir) / "recent_log.txt"
        log_file.write_text("recent log")
        
        # Set modification time to 2 minutes ago (within threshold)
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=2)
        os.utime(log_file, (recent_time.timestamp(), recent_time.timestamp()))
        
        status = self.monitor.get_health_status()
        
        assert status.status == "healthy"
        assert status.log_directory_accessible is True
        assert status.last_log_update is not None
    
    def test_get_health_status_unhealthy(self):
        """Test get_health_status with old log files."""
        # Create an old log file
        log_file = Path(self.temp_dir) / "old_log.txt"
        log_file.write_text("old log")
        
        # Set modification time to 10 minutes ago (beyond threshold)
        old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        os.utime(log_file, (old_time.timestamp(), old_time.timestamp()))
        
        status = self.monitor.get_health_status()
        
        assert status.status == "unhealthy"
        assert status.log_directory_accessible is True
        assert status.last_log_update is not None
    
    def test_get_health_status_exact_threshold(self):
        """Test get_health_status with log file exactly at threshold."""
        # Create a log file
        log_file = Path(self.temp_dir) / "threshold_log.txt"
        log_file.write_text("threshold log")
        
        # Set modification time to slightly less than threshold (4.9 minutes ago)
        threshold_time = datetime.now(timezone.utc) - timedelta(minutes=4, seconds=54)
        os.utime(log_file, (threshold_time.timestamp(), threshold_time.timestamp()))
        
        status = self.monitor.get_health_status()
        
        assert status.status == "healthy"  # Should be healthy (< threshold)
    
    def test_get_health_status_subdirectories(self):
        """Test get_health_status with files in subdirectories."""
        # Create subdirectory with log file
        subdir = Path(self.temp_dir) / "subdir"
        subdir.mkdir()
        
        log_file = subdir / "sub_log.txt"
        log_file.write_text("sub log")
        
        # Set recent modification time
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        os.utime(log_file, (recent_time.timestamp(), recent_time.timestamp()))
        
        status = self.monitor.get_health_status()
        
        assert status.status == "healthy"
        assert status.last_log_update is not None
    
    @patch('src.monitoring.node_health_monitor.logger')
    def test_get_last_log_update_time_exception(self, mock_logger):
        """Test get_last_log_update_time handles exceptions gracefully."""
        with patch.object(Path, 'rglob', side_effect=Exception("Test exception")):
            result = self.monitor.get_last_log_update_time()
            
            assert result is None
            mock_logger.error.assert_called_once()
    
    @patch('src.monitoring.node_health_monitor.logger')
    def test_check_log_directory_access_exception(self, mock_logger):
        """Test check_log_directory_access handles exceptions gracefully."""
        with patch.object(Path, 'exists', side_effect=Exception("Test exception")):
            result = self.monitor.check_log_directory_access()
            
            assert result is False
            mock_logger.error.assert_called_once()
