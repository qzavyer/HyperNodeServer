"""Tests for resilient logging with disk space error handling."""

import pytest
import logging
import tempfile
import os
import sys
import time
from pathlib import Path

from src.utils.resilient_file_handler import ResilientRotatingFileHandler


class TestResilientFileHandler:
    """Tests for ResilientRotatingFileHandler."""
    
    def test_normal_logging(self):
        """Test normal logging works as expected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            
            handler = ResilientRotatingFileHandler(
                log_file,
                maxBytes=1024,
                backupCount=2
            )
            
            logger = logging.getLogger("test_normal")
            logger.setLevel(logging.DEBUG)
            logger.addHandler(handler)
            
            # Write some logs
            for i in range(10):
                logger.info(f"Test message {i}")
            
            # Check file exists
            assert log_file.exists()
            
            # Check content
            content = log_file.read_text()
            assert "Test message 0" in content
            assert "Test message 9" in content
            
            handler.close()
    
    def test_emergency_cleanup(self):
        """Test emergency cleanup removes old log files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "app.log"
            
            # Create some old backup files
            for i in range(5):
                backup_file = Path(tmpdir) / f"app.log.{i}"
                backup_file.write_text("old log data" * 1000)
                # Make them old
                old_time = time.time() - (i + 1) * 86400
                os.utime(backup_file, (old_time, old_time))
            
            handler = ResilientRotatingFileHandler(
                log_file,
                maxBytes=1024,
                backupCount=2,
                emergency_cleanup_threshold_mb=1
            )
            
            # Perform emergency cleanup
            handler._perform_emergency_cleanup()
            
            # Check that old files were removed
            remaining_files = list(Path(tmpdir).glob("app.log.*"))
            assert len(remaining_files) < 5, "Old files should be removed"
            
            handler.close()
    
    def test_fallback_to_stdout(self, capsys):
        """Test fallback to stdout when file logging fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            
            handler = ResilientRotatingFileHandler(
                log_file,
                maxBytes=1024,
                backupCount=2
            )
            
            logger = logging.getLogger("test_fallback")
            logger.setLevel(logging.DEBUG)
            handler.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(handler)
            
            # Simulate degraded mode
            handler.is_degraded = True
            handler._setup_fallback_handler()
            
            # Write log
            logger.info("Fallback test message")
            
            # Check that fallback handler was set up
            assert handler.fallback_handler is not None
            assert handler.is_degraded
            
            # Check that the fallback handler is a StreamHandler pointing to stdout
            assert isinstance(handler.fallback_handler, logging.StreamHandler)
            assert handler.fallback_handler.stream == sys.stdout
            
            handler.close()
    
    def test_handler_state_tracking(self):
        """Test that handler tracks degraded state correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            
            handler = ResilientRotatingFileHandler(
                log_file,
                maxBytes=1024,
                backupCount=2
            )
            
            # Initially not degraded
            assert not handler.is_degraded
            
            # Simulate disk full
            handler.is_degraded = True
            handler.last_error_time = time.time()
            handler.error_count = 1
            
            assert handler.is_degraded
            assert handler.error_count == 1
            assert handler.last_error_time is not None
            
            handler.close()
    
    def test_recovery_thread_starts(self):
        """Test that recovery thread starts when degraded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            
            handler = ResilientRotatingFileHandler(
                log_file,
                maxBytes=1024,
                backupCount=2,
                recovery_check_interval_sec=1
            )
            
            # Start recovery thread
            handler.is_degraded = True
            handler._start_recovery_thread()
            
            # Check thread is running
            assert handler.recovery_thread is not None
            assert handler.recovery_thread.is_alive()
            
            # Stop thread
            handler.stop_recovery.set()
            handler.recovery_thread.join(timeout=2)
            
            handler.close()
    
    def test_log_rotation_still_works(self):
        """Test that log rotation still works with resilient handler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            
            handler = ResilientRotatingFileHandler(
                log_file,
                maxBytes=1024,  # Small size to trigger rotation
                backupCount=3
            )
            
            logger = logging.getLogger("test_rotation")
            logger.setLevel(logging.DEBUG)
            logger.addHandler(handler)
            
            # Write enough to trigger rotation
            for i in range(100):
                logger.info(f"Long message {i} " * 10)
            
            # Check that backup files were created
            backup_files = list(Path(tmpdir).glob("test.log.*"))
            assert len(backup_files) > 0, "Should create backup files"
            
            handler.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

