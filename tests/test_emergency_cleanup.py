"""
Tests for emergency cleanup functionality in SingleFileTailWatcher.
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
import os

from src.watcher.single_file_tail_watcher import SingleFileTailWatcher
from src.storage.order_manager import OrderManager


class TestEmergencyCleanup:
    """Test emergency cleanup functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def mock_order_manager(self):
        """Create mock order manager."""
        return Mock(spec=OrderManager)
    
    @pytest.fixture
    def watcher(self, temp_dir, mock_order_manager):
        """Create SingleFileTailWatcher instance for testing."""
        with patch('src.watcher.single_file_tail_watcher.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = str(temp_dir)
            mock_settings.CHUNK_SIZE_BYTES = 1024
            mock_settings.BATCH_SIZE = 100
            mock_settings.TAIL_READLINE_INTERVAL_MS = 100
            mock_settings.FALLBACK_SCAN_INTERVAL_SEC = 1
            mock_settings.TAIL_BATCH_SIZE = 10
            mock_settings.TAIL_BUFFER_SIZE = 1024
            mock_settings.TAIL_AGGRESSIVE_POLLING = False
            mock_settings.MAX_WORKERS_AUTO = False
            mock_settings.TAIL_PARALLEL_WORKERS = 1
            mock_settings.TAIL_PARALLEL_BATCH_SIZE = 10
            mock_settings.TAIL_JSON_OPTIMIZATION = True
            mock_settings.TAIL_PRE_FILTER = True
            mock_settings.TAIL_MEMORY_MAPPED = False
            mock_settings.TAIL_MMAP_CHUNK_SIZE = 1024
            mock_settings.TAIL_ZERO_COPY = False
            mock_settings.TAIL_LOCK_FREE = False
            mock_settings.TAIL_STREAMING = False
            mock_settings.TAIL_STREAM_BUFFER_SIZE = 1024
            mock_settings.TAIL_STREAM_CHUNK_SIZE = 512
            mock_settings.TAIL_STREAM_PROCESSING_DELAY_MS = 10
            
            watcher = SingleFileTailWatcher(mock_order_manager)
            return watcher
    
    @pytest.mark.asyncio
    async def test_emergency_cleanup_with_low_disk_space(self, watcher, temp_dir):
        """Test emergency cleanup when disk space is low."""
        # Create some test directories with old dates
        old_dir = temp_dir / "20250917"
        old_dir.mkdir(parents=True)
        
        # Create test file
        test_file = old_dir / "test.log"
        test_file.write_text("test content")
        
        # Mock psutil.disk_usage to return low disk space
        with patch('psutil.disk_usage') as mock_disk_usage:
            # First call - low space (0.5GB free)
            mock_disk_usage.return_value = Mock(free=0.5 * 1024**3)
            
            # Mock the cleanup_async method
            with patch.object(watcher.directory_cleaner, 'cleanup_async', new_callable=AsyncMock) as mock_cleanup:
                mock_cleanup.return_value = (1, 1)  # 1 dir, 1 file removed
                
                result = await watcher._emergency_cleanup_if_needed()
                
                # Should trigger cleanup
                assert result is True
                mock_cleanup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_emergency_cleanup_with_sufficient_disk_space(self, watcher, temp_dir):
        """Test that cleanup is not triggered when disk space is sufficient."""
        # Mock psutil.disk_usage to return sufficient disk space
        with patch('psutil.disk_usage') as mock_disk_usage:
            mock_disk_usage.return_value = Mock(free=5.0 * 1024**3)  # 5GB free
            
            result = await watcher._emergency_cleanup_if_needed()
            
            # Should not trigger cleanup
            assert result is False
    
    @pytest.mark.asyncio
    async def test_emergency_cleanup_cooldown(self, watcher, temp_dir):
        """Test that cleanup respects cooldown period."""
        # Set last cleanup time to recent time
        watcher.last_cleanup_time = 1000  # Recent timestamp
        
        # Mock current time to be within cooldown
        with patch('time.time', return_value=1000 + 60):  # 1 minute later (within 5min cooldown)
            with patch('psutil.disk_usage') as mock_disk_usage:
                mock_disk_usage.return_value = Mock(free=0.5 * 1024**3)  # Low space
                
                result = await watcher._emergency_cleanup_if_needed()
                
                # Should not trigger cleanup due to cooldown
                assert result is False
    
    @pytest.mark.asyncio
    async def test_emergency_cleanup_error_handling(self, watcher, temp_dir):
        """Test error handling in emergency cleanup."""
        # Mock psutil.disk_usage to raise an exception
        with patch('psutil.disk_usage', side_effect=Exception("Disk usage error")):
            result = await watcher._emergency_cleanup_if_needed()
            
            # Should return False on error
            assert result is False
    
    def test_oserror_no_space_left_handling(self, watcher):
        """Test that OSError with errno 28 is handled correctly."""
        # Create OSError with errno 28 (No space left on device)
        oserror = OSError("No space left on device")
        oserror.errno = 28
        
        # Test that the error is recognized
        assert oserror.errno == 28
        assert "No space left on device" in str(oserror)
    
    @pytest.mark.asyncio
    async def test_directory_cleaner_integration(self, watcher, temp_dir):
        """Test that DirectoryCleaner is properly integrated."""
        # Check that directory cleaner is initialized
        assert watcher.directory_cleaner is not None
        assert watcher.directory_cleaner.base_dir == Path(temp_dir)
        assert watcher.directory_cleaner.single_file_watcher == watcher
        
        # Check cleanup cooldown settings
        assert watcher.last_cleanup_time == 0
        assert watcher.cleanup_cooldown == 300  # 5 minutes


if __name__ == "__main__":
    pytest.main([__file__])
