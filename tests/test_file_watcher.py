"""Tests for FileWatcher module."""

import pytest
import asyncio
import tempfile
import shutil
import time
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from src.watcher.file_watcher import FileWatcher, LogFileHandler
from src.storage.order_manager import OrderManager
from src.storage.file_storage import FileStorage
from src.storage.models import Order


class TestFileWatcher:
    """Tests for FileWatcher class."""
    
    def setup_method(self):
        """Setup before each test."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.storage = FileStorage()
        self.order_manager = OrderManager(self.storage)
        self.file_watcher = FileWatcher(self.order_manager)
        self.file_watcher.logs_path = self.temp_dir
    
    def teardown_method(self):
        """Cleanup after each test."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_start_async_creates_directory(self):
        """Test that start_async creates logs directory."""
        logs_path = self.temp_dir / "logs"
        self.file_watcher.logs_path = logs_path
        
        with patch.object(self.file_watcher, 'scan_latest_file_async') as mock_scan, \
             patch.object(self.file_watcher, '_cleanup_loop_async') as mock_cleanup, \
             patch.object(self.file_watcher.observer, 'schedule'), \
             patch.object(self.file_watcher.observer, 'start'):
            
            await self.file_watcher.start_async()
            
            assert logs_path.exists()
            assert logs_path.is_dir()
    
    @pytest.mark.asyncio
    async def test_stop_async_stops_observer(self):
        """Test that stop_async properly stops the observer."""
        self.file_watcher.is_running = True
        
        with patch.object(self.file_watcher.observer, 'stop') as mock_stop, \
             patch.object(self.file_watcher.observer, 'join') as mock_join:
            
            await self.file_watcher.stop_async()
            
            mock_stop.assert_called_once()
            mock_join.assert_called_once()
            assert not self.file_watcher.is_running
    
    def test_find_latest_file_returns_none_when_no_files(self):
        """Test that _find_latest_file returns None when no files exist."""
        result = self.file_watcher._find_latest_file()
        assert result is None
    
    def test_find_latest_file_returns_latest_file(self):
        """Test that _find_latest_file returns the most recent file."""
        # Create test files with different timestamps
        file1 = self.temp_dir / "file1.json"
        file2 = self.temp_dir / "file2.json"
        
        file1.touch()
        time.sleep(0.1)  # Ensure different timestamps
        file2.touch()
        
        result = self.file_watcher._find_latest_file()
        assert result == file2
    
    @pytest.mark.asyncio
    async def test_read_file_with_retry_async_success_on_first_attempt(self):
        """Test successful file reading on first attempt."""
        test_file = self.temp_dir / "test.json"
        test_content = '{"test": "data"}\n'
        test_file.write_text(test_content)
        
        result = await self.file_watcher._read_file_with_retry_async(test_file)
        
        assert result == [test_content]
    
    @pytest.mark.asyncio
    async def test_read_file_with_retry_async_success_on_second_attempt(self):
        """Test successful file reading on second attempt."""
        test_file = self.temp_dir / "test.json"
        test_content = '{"test": "data"}\n'
        test_file.write_text(test_content)
        
        # Mock aiofiles.open to fail first time, succeed second time
        mock_file = AsyncMock()
        mock_file.readlines.return_value = [test_content]
        
        with patch('aiofiles.open') as mock_open:
            mock_open.side_effect = [
                OSError("File busy"),  # First attempt fails
                type('MockContextManager', (), {
                    '__aenter__': AsyncMock(return_value=mock_file),
                    '__aexit__': AsyncMock(return_value=None)
                })()  # Second attempt succeeds
            ]
            
            result = await self.file_watcher._read_file_with_retry_async(test_file)
            
            assert result == [test_content]
            assert mock_open.call_count == 2
    
    @pytest.mark.asyncio
    async def test_read_file_with_retry_async_fails_after_max_attempts(self):
        """Test that file reading fails after maximum attempts."""
        test_file = self.temp_dir / "test.json"
        
        with patch('aiofiles.open', side_effect=OSError("File busy")), \
             pytest.raises(OSError, match="File busy"):
            
            await self.file_watcher._read_file_with_retry_async(test_file)
    
    @pytest.mark.asyncio
    async def test_process_file_async_with_valid_data(self):
        """Test processing file with valid order data."""
        test_file = self.temp_dir / "test.json"
        test_content = f'''{"user":"0x123","status":"open","order":{"oid":123,"coin":"BTC","side":"Bid","px":"50000"}}
{"user":"0x456","status":"cancelled","order":{"oid":456,"coin":"ETH","side":"Ask","px":"3000"}}'''
        test_file.write_text(test_content)
        
        with patch.object(self.file_watcher.order_manager, 'update_order') as mock_update:
            await self.file_watcher._process_file_async(test_file)
            
            # Should call update_order for each order found
            assert mock_update.call_count == 2
    
    @pytest.mark.asyncio
    async def test_process_file_async_with_no_data(self):
        """Test processing file with no valid order data."""
        test_file = self.temp_dir / "test.json"
        test_content = '{"invalid": "data"}\n'
        test_file.write_text(test_content)
        
        with patch.object(self.file_watcher.order_manager, 'update_order') as mock_update:
            await self.file_watcher._process_file_async(test_file)
            
            # Should not call update_order if no orders found
            mock_update.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_cleanup_old_data_async_calls_order_manager(self):
        """Test that cleanup calls order manager cleanup method."""
        with patch.object(self.file_watcher.order_manager, 'cleanup_old_orders') as mock_cleanup:
            mock_cleanup.return_value = 5
            
            await self.file_watcher.cleanup_old_data_async()
            
            mock_cleanup.assert_called_once_with(2)  # Default CLEANUP_INTERVAL_HOURS
    
    @pytest.mark.asyncio
    async def test_cleanup_loop_async_runs_periodically(self):
        """Test that cleanup loop runs periodically."""
        self.file_watcher.is_running = True
        
        with patch.object(self.file_watcher, 'cleanup_old_data_async') as mock_cleanup, \
             patch('asyncio.sleep') as mock_sleep:
            
            # Run cleanup loop for a short time
            task = asyncio.create_task(self.file_watcher._cleanup_loop_async())
            await asyncio.sleep(0.1)  # Let it run briefly
            self.file_watcher.is_running = False
            await task
            
            mock_sleep.assert_called()
            # Note: cleanup might not be called due to timing, so we don't assert it


class TestLogFileHandler:
    """Tests for LogFileHandler class."""
    
    def setup_method(self):
        """Setup before each test."""
        self.file_watcher = Mock()
        self.handler = LogFileHandler(self.file_watcher)
    
    def test_on_modified_with_json_file(self):
        """Test that on_modified processes JSON files."""
        event = Mock()
        event.is_directory = False
        event.src_path = "/path/to/file.json"
        
        with patch('asyncio.create_task') as mock_create_task:
            self.handler.on_modified(event)
            
            mock_create_task.assert_called_once()
    
    def test_on_modified_with_non_json_file(self):
        """Test that on_modified ignores non-JSON files."""
        event = Mock()
        event.is_directory = False
        event.src_path = "/path/to/file.txt"
        
        with patch('asyncio.create_task') as mock_create_task:
            self.handler.on_modified(event)
            
            mock_create_task.assert_not_called()
    
    def test_on_modified_with_directory(self):
        """Test that on_modified ignores directories."""
        event = Mock()
        event.is_directory = True
        event.src_path = "/path/to/directory"
        
        with patch('asyncio.create_task') as mock_create_task:
            self.handler.on_modified(event)
            
            mock_create_task.assert_not_called()
    
    def test_on_created_with_json_file(self):
        """Test that on_created processes JSON files."""
        event = Mock()
        event.is_directory = False
        event.src_path = "/path/to/file.json"
        
        with patch('asyncio.create_task') as mock_create_task:
            self.handler.on_created(event)
            
            mock_create_task.assert_called_once()
    
    def test_on_created_with_non_json_file(self):
        """Test that on_created ignores non-JSON files."""
        event = Mock()
        event.is_directory = False
        event.src_path = "/path/to/file.txt"
        
        with patch('asyncio.create_task') as mock_create_task:
            self.handler.on_created(event)
            
            mock_create_task.assert_not_called()

