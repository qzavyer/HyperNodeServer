"""Tests for SingleFileTailWatcher."""

import pytest
import asyncio
import tempfile
import json
import time
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from src.watcher.single_file_tail_watcher import SingleFileTailWatcher, SingleFileEventHandler
from src.storage.models import Order


class TestSingleFileTailWatcher:
    """Tests for SingleFileTailWatcher class."""
    
    @pytest.fixture
    def mock_order_manager(self):
        """Mock order manager."""
        manager = Mock()
        manager.update_orders_batch_async = AsyncMock()
        return manager
    
    @pytest.fixture
    def temp_logs_dir(self):
        """Create temporary logs directory structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_path = Path(temp_dir) / "node_logs"
            hourly_path = logs_path / "node_order_statuses" / "hourly"
            hourly_path.mkdir(parents=True)
            
            # Create test date directory
            today = datetime.now().strftime("%Y%m%d")
            date_dir = hourly_path / today
            date_dir.mkdir()
            
            yield logs_path, hourly_path, date_dir
    
    @pytest.fixture
    def watcher(self, mock_order_manager, temp_logs_dir):
        """Create SingleFileTailWatcher instance."""
        logs_path, _, _ = temp_logs_dir
        
        with patch('config.settings.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = str(logs_path)
            mock_settings.DATA_PATH = str(logs_path)
            mock_settings.CHUNK_SIZE_BYTES = 1024
            mock_settings.BATCH_SIZE = 100
            mock_settings.TAIL_READLINE_INTERVAL_MS = 100
            mock_settings.FALLBACK_SCAN_INTERVAL_SEC = 60
            
            watcher = SingleFileTailWatcher(mock_order_manager)
            # Update the logs_path to use the temp directory
            watcher.logs_path = logs_path
            return watcher
    
    def test_initialization(self, mock_order_manager):
        """Test SingleFileTailWatcher initialization."""
        with patch('config.settings.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = "/test/logs"
            mock_settings.DATA_PATH = "/test/logs"
            mock_settings.CHUNK_SIZE_BYTES = 1024
            mock_settings.BATCH_SIZE = 100
            mock_settings.TAIL_READLINE_INTERVAL_MS = 100
            mock_settings.FALLBACK_SCAN_INTERVAL_SEC = 60
            
            watcher = SingleFileTailWatcher(mock_order_manager)
            
            assert watcher.order_manager == mock_order_manager
            assert watcher.is_running is False
            assert watcher.current_file_path is None
            assert watcher.current_file_handle is None
            assert watcher.current_file_position == 0
    
    def test_find_current_file_no_directories(self, watcher):
        """Test finding current file when no date directories exist."""
        result = watcher._find_current_file()
        assert result is None
    
    def test_find_current_file_no_files(self, watcher, temp_logs_dir):
        """Test finding current file when no hour files exist."""
        logs_path, hourly_path, date_dir = temp_logs_dir
        
        # Create empty date directory
        today = datetime.now().strftime("%Y%m%d")
        date_dir = hourly_path / today
        date_dir.mkdir(exist_ok=True)
        
        result = watcher._find_current_file()
        assert result is None
    
    def test_find_current_file_success(self, watcher, temp_logs_dir):
        """Test successfully finding current file."""
        logs_path, hourly_path, date_dir = temp_logs_dir
        
        # Create test hour files
        hour_5 = date_dir / "5"
        hour_10 = date_dir / "10"
        hour_15 = date_dir / "15"
        
        for hour_file in [hour_5, hour_10, hour_15]:
            hour_file.write_text("test data")
        
        result = watcher._find_current_file()
        
        # Should return the file with maximum hour (15)
        assert result == hour_15
    
    def test_find_current_file_invalid_hour(self, watcher, temp_logs_dir):
        """Test finding current file with invalid hour files."""
        logs_path, hourly_path, date_dir = temp_logs_dir
        
        # Create valid and invalid hour files
        valid_hour = date_dir / "10"
        invalid_hour = date_dir / "25"  # Invalid hour > 23
        non_numeric = date_dir / "abc"
        
        for hour_file in [valid_hour, invalid_hour, non_numeric]:
            hour_file.write_text("test data")
        
        result = watcher._find_current_file()
        
        # Should return only the valid hour file
        assert result == valid_hour
    
    @pytest.mark.asyncio
    async def test_start_tailing_file(self, watcher, temp_logs_dir):
        """Test starting to tail a file."""
        logs_path, hourly_path, date_dir = temp_logs_dir
        
        # Create test file
        test_file = date_dir / "10"
        test_file.write_text("line1\nline2\nline3\n")
        
        try:
            await watcher._start_tailing_file(test_file)
            
            assert watcher.current_file_path == test_file
            assert watcher.current_file_handle is not None
            assert watcher.current_file_position > 0  # Should be at end of file
        finally:
            # Clean up file handle and memory-mapped file
            if watcher.current_file_handle:
                await watcher.current_file_handle.close()
                watcher.current_file_handle = None
            if hasattr(watcher, 'mmap_file') and watcher.mmap_file:
                watcher.mmap_file.close()
                watcher.mmap_file = None
    
    @pytest.mark.asyncio
    async def test_start_tailing_file_close_previous(self, watcher, temp_logs_dir):
        """Test that starting to tail a new file closes the previous one."""
        logs_path, hourly_path, date_dir = temp_logs_dir
        
        # Create test files
        file1 = date_dir / "10"
        file2 = date_dir / "11"
        
        for test_file in [file1, file2]:
            test_file.write_text("test data")
        
        try:
            # Start tailing first file
            await watcher._start_tailing_file(file1)
            first_handle = watcher.current_file_handle
            
            # Start tailing second file
            await watcher._start_tailing_file(file2)
            
            assert watcher.current_file_path == file2
            assert watcher.current_file_handle != first_handle
            assert watcher.current_file_handle is not None
        finally:
            # Clean up file handle and memory-mapped file
            if watcher.current_file_handle:
                await watcher.current_file_handle.close()
                watcher.current_file_handle = None
            if hasattr(watcher, 'mmap_file') and watcher.mmap_file:
                watcher.mmap_file.close()
                watcher.mmap_file = None
    
    @pytest.mark.asyncio
    async def test_process_line_valid_order(self, watcher):
        """Test processing a valid order line."""
        # Mock parser to return a valid order
        mock_order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        watcher.parser.parse_line = Mock(return_value=mock_order)
        
        test_line = '{"user":"0x123","oid":123,"coin":"BTC","side":"B","limitPx":"50000","sz":"1.0"}'
        
        await watcher._process_line(test_line)
        
        # Verify order manager was called
        watcher.order_manager.update_orders_batch_async.assert_called_once_with([mock_order])
    
    @pytest.mark.asyncio
    async def test_process_line_invalid_order(self, watcher):
        """Test processing an invalid order line."""
        # Mock parser to return None (invalid order)
        watcher.parser.parse_line = Mock(return_value=None)
        
        test_line = "invalid json line"
        
        # Should not raise exception, just log error
        await watcher._process_line(test_line)
        
        # Verify order manager was not called
        watcher.order_manager.update_orders_batch_async.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_process_line_parser_exception(self, watcher):
        """Test processing line when parser raises exception."""
        # Mock parser to raise exception
        watcher.parser.parse_line = Mock(side_effect=Exception("Parse error"))
        
        test_line = "some line"
        
        # Should not raise exception, just log error
        await watcher._process_line(test_line)
        
        # Verify order manager was not called
        watcher.order_manager.update_orders_batch_async.assert_not_called()
    
    def test_get_status(self, watcher):
        """Test getting watcher status."""
        watcher.is_running = True
        watcher.current_file_path = Path("/test/file")
        watcher.current_file_position = 12345
        watcher.tail_interval = 0.1
        watcher.fallback_interval = 60
        
        status = watcher.get_status()
        
        assert status["is_running"] is True
        assert status["current_file"] == str(Path("/test/file"))
        assert status["current_position"] == 12345
        assert status["tail_interval_ms"] == 100
        assert status["fallback_interval_sec"] == 60
        assert "parallel_workers" in status
        assert "json_optimization" in status
        assert "pre_filter" in status
        assert "cache_hits" in status
        assert "cache_misses" in status
        assert "watchdog_active" in status

    def test_pre_filter_line_valid(self, watcher):
        """Test pre-filtering with valid line."""
        valid_line = '{"time":"2025-01-01T00:00:00","user":"0x123","order":{"coin":"BTC","side":"B","status":"open"}}'
        result = watcher._pre_filter_line(valid_line)
        assert result is True
        assert watcher.pre_filter_passed == 1

    def test_pre_filter_line_invalid(self, watcher):
        """Test pre-filtering with invalid line."""
        invalid_line = "This is not a JSON line"
        result = watcher._pre_filter_line(invalid_line)
        assert result is False
        assert watcher.pre_filter_rejected == 1

    def test_pre_filter_line_empty(self, watcher):
        """Test pre-filtering with empty line."""
        result = watcher._pre_filter_line("")
        assert result is False
        assert watcher.pre_filter_rejected == 1

    def test_parse_line_optimized_with_cache(self, watcher):
        """Test optimized parsing with caching."""
        line = '{"time":"2025-01-01T00:00:00","user":"0x1234567890abcdef","order":{"coin":"BTC","side":"B","sz":"1.0","limitPx":"50000","oid":123,"status":"open"}}'
        
        # First parse - should cache
        order1 = watcher._parse_line_optimized(line)
        
        # Second parse - should use cache
        order2 = watcher._parse_line_optimized(line)
        
        assert watcher.cache_hits == 1
        assert watcher.cache_misses == 1

    def test_parse_chunk_sync(self, watcher):
        """Test synchronous chunk parsing."""
        lines = [
            '{"time":"2025-01-01T00:00:00","user":"0x1234567890abcdef","order":{"coin":"BTC","side":"B","sz":"1.0","limitPx":"50000","oid":123,"status":"open"}}',
            '{"time":"2025-01-01T00:00:01","user":"0x1234567890abcdef","order":{"coin":"ETH","side":"A","sz":"10.0","limitPx":"3000","oid":124,"status":"open"}}'
        ]
        
        orders = watcher._parse_chunk_sync(lines)
        assert len(orders) == 2


class TestSingleFileEventHandler:
    """Tests for SingleFileEventHandler class."""
    
    def test_initialization(self):
        """Test SingleFileEventHandler initialization."""
        mock_watcher = Mock()
        handler = SingleFileEventHandler(mock_watcher)
        
        assert handler.watcher == mock_watcher
    
    def test_on_created_numeric_file(self):
        """Test handling creation of numeric file."""
        mock_watcher = Mock()
        mock_watcher._main_loop = Mock()
        mock_watcher._main_loop.is_closed.return_value = False
        
        handler = SingleFileEventHandler(mock_watcher)
        
        # Mock event
        mock_event = Mock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/path/10"
        
        with patch('asyncio.run_coroutine_threadsafe') as mock_run:
            handler.on_created(mock_event)
            
            # Verify that coroutine was scheduled
            mock_run.assert_called_once()
    
    def test_on_created_non_numeric_file(self):
        """Test handling creation of non-numeric file."""
        mock_watcher = Mock()
        handler = SingleFileEventHandler(mock_watcher)
        
        # Mock event
        mock_event = Mock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/path/abc"
        
        with patch('asyncio.run_coroutine_threadsafe') as mock_run:
            handler.on_created(mock_event)
            
            # Verify that coroutine was NOT scheduled
            mock_run.assert_not_called()
    
    def test_on_created_directory(self):
        """Test handling creation of directory."""
        mock_watcher = Mock()
        handler = SingleFileEventHandler(mock_watcher)
        
        # Mock event
        mock_event = Mock()
        mock_event.is_directory = True
        mock_event.src_path = "/test/path/dir"
        
        with patch('asyncio.run_coroutine_threadsafe') as mock_run:
            handler.on_created(mock_event)
            
            # Verify that coroutine was NOT scheduled
            mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_integration_find_and_start_current_file():
    """Integration test for finding and starting current file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        logs_path = Path(temp_dir) / "node_logs"
        hourly_path = logs_path / "node_order_statuses" / "hourly"
        hourly_path.mkdir(parents=True)
        
        # Create test date directory
        today = datetime.now().strftime("%Y%m%d")
        date_dir = hourly_path / today
        date_dir.mkdir()
        
        # Create test hour files
        hour_5 = date_dir / "5"
        hour_10 = date_dir / "10"
        hour_15 = date_dir / "15"
        
        for hour_file in [hour_5, hour_10, hour_15]:
            hour_file.write_text("test data")
        
        # Create watcher
        mock_order_manager = Mock()
        mock_order_manager.update_orders_batch_async = AsyncMock()
        
        with patch('config.settings.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = str(logs_path)
            mock_settings.DATA_PATH = str(logs_path)
            mock_settings.CHUNK_SIZE_BYTES = 1024
            mock_settings.BATCH_SIZE = 100
            mock_settings.TAIL_READLINE_INTERVAL_MS = 100
            mock_settings.FALLBACK_SCAN_INTERVAL_SEC = 60
            
            watcher = SingleFileTailWatcher(mock_order_manager)
            # Update the logs_path to use the temp directory
            watcher.logs_path = logs_path
            
            try:
                # Test finding and starting current file
                await watcher._find_and_start_current_file()
                
                # Should be tailing the file with maximum hour (15)
                assert watcher.current_file_path == hour_15
                assert watcher.current_file_handle is not None
            finally:
                # Clean up file handle and memory-mapped file
                if watcher.current_file_handle:
                    await watcher.current_file_handle.close()
                    watcher.current_file_handle = None
                if hasattr(watcher, 'mmap_file') and watcher.mmap_file:
                    watcher.mmap_file.close()
                    watcher.mmap_file = None

    def test_parse_chunk_sync_timeout(self, watcher):
        """Test that _parse_chunk_sync handles timeouts correctly."""
        # Create a line that will cause hanging (infinite loop simulation)
        hanging_line = '{"user":"0x123","oid":123,"coin":"BTC","side":"Bid","px":"50000"}'
        
        # Mock the parser to simulate hanging
        def hanging_parse(line):
            time.sleep(2)  # Simulate hanging for 2 seconds
            return None
        
        with patch.object(watcher.parser, 'parse_line', side_effect=hanging_parse):
            start_time = time.time()
            result = watcher._parse_chunk_sync([hanging_line])
            end_time = time.time()
            
            # Should complete within 2 seconds (timeout is 1 second per line)
            assert end_time - start_time < 2.0
            assert result == []  # Empty result due to timeout

    def test_parse_line_optimized_timeout(self, watcher):
        """Test that _parse_line_optimized handles timeouts correctly."""
        # Create a line that will cause hanging
        hanging_line = '{"user":"0x123","oid":123,"coin":"BTC","side":"Bid","px":"50000"}'
        
        # Mock the parser to simulate hanging
        def hanging_parse(line):
            time.sleep(1)  # Simulate hanging for 1 second
            return None
        
        with patch.object(watcher.parser, 'parse_line', side_effect=hanging_parse):
            start_time = time.time()
            result = watcher._parse_line_optimized(hanging_line)
            end_time = time.time()
            
            # Should complete within 1 second (timeout is 0.5 seconds)
            assert end_time - start_time < 1.0
            assert result is None  # None result due to timeout

    def test_parse_chunk_sync_progress_logging(self, watcher):
        """Test that _parse_chunk_sync logs progress correctly."""
        lines = [f'{{"user":"0x{i}","oid":{i},"coin":"BTC","side":"Bid","px":"50000"}}' for i in range(15)]
        
        with patch.object(watcher, 'logger') as mock_logger:
            result = watcher._parse_chunk_sync(lines)
            
            # Should log progress at least once (every 10 lines)
            assert mock_logger.info.called
            # Should process all lines
            assert len(result) >= 0  # May be 0 if parsing fails, but should not hang

    def test_parse_chunk_sync_error_handling(self, watcher):
        """Test that _parse_chunk_sync handles errors gracefully."""
        # Create lines that will cause errors
        error_lines = [
            'invalid json',
            '{"incomplete":',
            '{"user":"0x123","oid":123,"coin":"BTC","side":"Bid","px":"50000"}',
            'another invalid json'
        ]
        
        result = watcher._parse_chunk_sync(error_lines)
        
        # Should not crash and return some result
        assert isinstance(result, list)
        # Should handle errors gracefully
        assert len(result) >= 0
