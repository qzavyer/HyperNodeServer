"""Tests for centralized logging system."""

import pytest
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime, timedelta
import os

from src.utils.logger import setup_logger, cleanup_old_logs, get_logger


class TestLogger:
    """Tests for logger functionality."""
    
    def setup_method(self):
        """Setup before each test."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.logs_dir = self.temp_dir / "logs"
        self.logs_dir.mkdir()
    
    def teardown_method(self):
        """Cleanup after each test."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_setup_logger_creates_logs_directory(self):
        """Test that setup_logger creates logs directory."""
        with patch('src.utils.logger.Path') as mock_path:
            mock_path.return_value = self.logs_dir
            
            logger = setup_logger("test_logger")
            
            assert logger is not None
            assert self.logs_dir.exists()
    
    def test_setup_logger_creates_timestamped_filename(self):
        """Test that logger creates timestamped log files."""
        with patch('src.utils.logger.Path') as mock_path, \
             patch('src.utils.logger.datetime') as mock_datetime:
            
            mock_path.return_value = self.logs_dir
            mock_now = Mock()
            mock_now.strftime.return_value = "20240101_120000"
            mock_datetime.now.return_value = mock_now
            
            logger = setup_logger("test_logger")
            
            # Check that timestamped filename was created
            expected_filename = "app_20240101_120000.log"
            assert (self.logs_dir / expected_filename).exists()
    
    def test_setup_logger_fallback_to_stdout_on_file_error(self):
        """Test that logger falls back to stdout when file logging fails."""
        with patch('src.utils.logger.Path') as mock_path, \
             patch('src.utils.logger.logging.handlers.RotatingFileHandler') as mock_handler:
            
            mock_path.return_value = self.logs_dir
            mock_handler.side_effect = Exception("File permission denied")
            
            logger = setup_logger("test_logger")
            
            # Should have stdout handler
            handlers = logger.handlers
            assert len(handlers) == 1
            assert hasattr(handlers[0], 'stream')  # StreamHandler has stream attribute
    
    def test_setup_logger_caches_loggers(self):
        """Test that setup_logger caches logger instances."""
        with patch('src.utils.logger.Path') as mock_path:
            mock_path.return_value = self.logs_dir
            
            logger1 = setup_logger("test_logger")
            logger2 = setup_logger("test_logger")
            
            assert logger1 is logger2
    
    def test_get_logger_returns_existing_logger(self):
        """Test that get_logger returns existing logger."""
        with patch('src.utils.logger.Path') as mock_path:
            mock_path.return_value = self.logs_dir
            
            logger1 = setup_logger("test_logger")
            logger2 = get_logger("test_logger")
            
            assert logger1 is logger2
    
    def test_get_logger_creates_new_logger_if_not_exists(self):
        """Test that get_logger creates new logger if not exists."""
        with patch('src.utils.logger.Path') as mock_path, \
             patch('src.utils.logger.setup_logger') as mock_setup:
            
            mock_path.return_value = self.logs_dir
            mock_logger = Mock()
            mock_setup.return_value = mock_logger
            
            result = get_logger("new_logger")
            
            mock_setup.assert_called_once_with("new_logger")
            assert result is mock_logger
    
    def test_cleanup_old_logs_removes_old_files(self):
        """Test that cleanup_old_logs removes old log files."""
        # Create old log file
        old_file = self.logs_dir / "app_20240101_120000.log"
        old_file.touch()
        
        # Set old modification time (31 days ago)
        old_time = time.time() - (31 * 24 * 3600)
        os.utime(old_file, (old_time, old_time))
        
        # Create recent log file
        recent_file = self.logs_dir / "app_20241201_120000.log"
        recent_file.touch()
        
        # Cleanup old logs (30 days retention)
        cleanup_old_logs(self.logs_dir, 30)
        
        # Old file should be removed, recent file should remain
        assert not old_file.exists()
        assert recent_file.exists()
    
    def test_cleanup_old_logs_handles_errors_gracefully(self):
        """Test that cleanup_old_logs handles errors gracefully."""
        with patch('builtins.print') as mock_print:
            # Create invalid path
            invalid_dir = Path("/invalid/path")
            
            cleanup_old_logs(invalid_dir, 30)
            
            # Should print error message
            mock_print.assert_called()
    
    def test_logger_formatter_includes_timestamp_and_level(self):
        """Test that logger formatter includes timestamp and level."""
        with patch('src.utils.logger.Path') as mock_path:
            mock_path.return_value = self.logs_dir
            
            logger = setup_logger("test_logger")
            
            # Check formatter
            handler = logger.handlers[0]
            formatter = handler.formatter
            
            # Test format
            record = Mock()
            record.asctime = "2024-01-01T12:00:00.000000Z"
            record.levelname = "INFO"
            record.name = "test_logger"
            record.getMessage.return_value = "Test message"
            
            formatted = formatter.format(record)
            
            assert "2024-01-01T12:00:00.000000Z" in formatted
            assert "[INFO]" in formatted
            assert "[test_logger]" in formatted
            assert "Test message" in formatted
    
    def test_logger_rotation_settings(self):
        """Test that logger uses correct rotation settings."""
        with patch('src.utils.logger.Path') as mock_path, \
             patch('src.utils.logger.logging.handlers.RotatingFileHandler') as mock_handler:
            
            mock_path.return_value = self.logs_dir
            mock_handler_instance = Mock()
            mock_handler.return_value = mock_handler_instance
            
            setup_logger("test_logger", max_size_mb=50, retention_days=7)
            
            # Check that RotatingFileHandler was called with correct parameters
            mock_handler.assert_called_once()
            args, kwargs = mock_handler.call_args
            
            assert kwargs['maxBytes'] == 50 * 1024 * 1024  # 50 MB in bytes
            assert kwargs['backupCount'] == 5
            assert kwargs['encoding'] == 'utf-8'
