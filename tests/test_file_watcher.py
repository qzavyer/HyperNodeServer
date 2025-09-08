"""Tests for file watcher module."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from src.watcher.file_watcher import FileWatcher, LogFileHandler
from src.storage.order_manager import OrderManager
from src.parser.log_parser import LogParser

@pytest.fixture
def mock_order_manager():
    """Mock order manager."""
    manager = Mock(spec=OrderManager)
    manager.update_orders_batch_async = AsyncMock()
    return manager

@pytest.fixture
def mock_parser():
    """Mock log parser."""
    parser = Mock(spec=LogParser)
    parser.parse_file_async = AsyncMock()
    return parser

@pytest.fixture
def file_watcher(mock_order_manager):
    """File watcher instance for testing."""
    watcher = FileWatcher(mock_order_manager)
    watcher.parser = Mock(spec=LogParser)
    watcher.parser.parse_file_async = AsyncMock()
    return watcher

class TestFileWatcher:
    """Tests for FileWatcher class."""
    
    def test_init(self, mock_order_manager):
        """Test FileWatcher initialization."""
        watcher = FileWatcher(mock_order_manager)
        assert watcher.order_manager == mock_order_manager
        assert watcher.is_running is False
        assert len(watcher.processing_files) == 0
        assert watcher.pending_files is not None
    
    @pytest.mark.asyncio
    async def test_start_async(self, file_watcher):
        """Test starting file watcher."""
        # Mock the internal async tasks
        with patch.object(file_watcher, 'scan_latest_file_async') as mock_scan, \
             patch.object(file_watcher, '_background_file_processor') as mock_bg, \
             patch.object(file_watcher, '_cleanup_loop_async') as mock_cleanup, \
             patch('asyncio.create_task') as mock_create_task:
            
            # Mock the observer methods
            file_watcher.observer.schedule = Mock()
            file_watcher.observer.start = Mock()
            
            await file_watcher.start_async()
            
            assert file_watcher.is_running is True
            file_watcher.observer.schedule.assert_called_once_with(file_watcher.handler, str(file_watcher.logs_path), recursive=True)
            file_watcher.observer.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_stop_async(self, file_watcher):
        """Test stopping file watcher."""
        file_watcher.is_running = True
        file_watcher.observer.stop = Mock()
        file_watcher.observer.join = Mock()
        
        await file_watcher.stop_async()
        
        assert file_watcher.is_running is False
        file_watcher.observer.stop.assert_called_once()
        file_watcher.observer.join.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_schedule_file_processing(self, file_watcher):
        """Test scheduling file for processing."""
        file_path = Path("/test/file.log")
        
        # Mock file size and settings
        with patch('pathlib.Path.stat') as mock_stat, \
             patch('src.watcher.file_watcher.settings') as mock_settings:
            mock_stat.return_value.st_size = 1024 * 1024  # 1MB
            mock_settings.MAX_FILE_SIZE_GB = 10.0  # Allow files up to 10GB
            
            await file_watcher._schedule_file_processing(file_path)
            
            # Verify file was scheduled
            assert file_watcher.pending_files.qsize() == 1
    
    @pytest.mark.asyncio
    async def test_process_file_background(self, file_watcher):
        """Test background file processing."""
        file_path = Path("/test/file.log")
        
        # Mock parser to return batches
        mock_batch = [Mock(spec='Order')]
        
        # Create proper async generator mock that matches AsyncGenerator[List[Order], None]
        class MockAsyncGenerator:
            def __init__(self, data):
                self.data = data
                self.index = 0
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                if self.index < len(self.data):
                    result = self.data[self.index]
                    self.index += 1
                    return result
                raise StopAsyncIteration
        
        # Mock parse_file_async to return our async generator
        file_watcher.parser.parse_file_async = Mock(return_value=MockAsyncGenerator([mock_batch]))
        
        # Mock order manager
        file_watcher.order_manager.update_orders_batch_async = AsyncMock()
        
        # Create a task to run the background processing
        # This allows us to check the state during processing
        task = asyncio.create_task(file_watcher._process_file_background(file_path))
        
        # Wait a bit for the processing to start
        await asyncio.sleep(0.01)
        
        # Verify file was added to processing_files during processing
        assert file_path in file_watcher.processing_files
        
        # Wait for the task to complete
        await task
        
        # Verify file was removed from processing_files after completion
        assert file_path not in file_watcher.processing_files
        
        # Verify parser was called
        file_watcher.parser.parse_file_async.assert_called_once_with(str(file_path))
        
        # Verify order manager was updated
        file_watcher.order_manager.update_orders_batch_async.assert_called_once_with(mock_batch)
    
    def test_get_processing_status(self, file_watcher):
        """Test getting processing status."""
        file_watcher.is_running = True
        file_watcher.processing_files.add(Path("/test/file1.log"))
        file_watcher.processing_files.add(Path("/test/file2.log"))
        
        # Mock queue size
        file_watcher.pending_files.qsize = Mock(return_value=3)
        
        status = file_watcher.get_processing_status()
        
        assert status["is_running"] is True
        assert status["processing_files_count"] == 2
        assert status["pending_files_count"] == 3
        assert len(status["processing_files"]) == 2

class TestLogFileHandler:
    """Tests for LogFileHandler class."""
    
    def test_init(self, mock_order_manager):
        """Test LogFileHandler initialization."""
        file_watcher = FileWatcher(mock_order_manager)
        handler = LogFileHandler(file_watcher)
        assert handler.file_watcher == file_watcher
    
    @pytest.mark.asyncio
    async def test_on_created(self, mock_order_manager):
        """Test file creation event handling for JSON files."""
        file_watcher = FileWatcher(mock_order_manager)
        file_watcher._schedule_file_processing = AsyncMock()
        handler = LogFileHandler(file_watcher)
        
        mock_event = Mock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/file.json"
        
        # Mock asyncio.create_task
        with patch('asyncio.create_task') as mock_create_task:
            handler.on_created(mock_event)
            mock_create_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_on_created_numeric_files(self, mock_order_manager):
        """Test file creation event handling for numeric log files."""
        file_watcher = FileWatcher(mock_order_manager)
        file_watcher._schedule_file_processing = AsyncMock()
        handler = LogFileHandler(file_watcher)
        
        mock_event = Mock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/logs/10"
        
        # Mock asyncio.create_task
        with patch('asyncio.create_task') as mock_create_task:
            handler.on_created(mock_event)
            mock_create_task.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_on_modified(self, mock_order_manager):
        """Test file modification event handling."""
        file_watcher = FileWatcher(mock_order_manager)
        file_watcher._schedule_file_processing = AsyncMock()
        handler = LogFileHandler(file_watcher)
        
        mock_event = Mock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/file.json"
        
        # Mock asyncio.create_task
        with patch('asyncio.create_task') as mock_create_task:
            handler.on_modified(mock_event)
            mock_create_task.assert_called_once()
    
    def test_on_created_ignores_directories(self, mock_order_manager):
        """Test that directory events are ignored."""
        file_watcher = FileWatcher(mock_order_manager)
        file_watcher._schedule_file_processing = AsyncMock()
        handler = LogFileHandler(file_watcher)
        
        mock_event = Mock()
        mock_event.is_directory = True
        mock_event.src_path = "/test/directory"
        
        with patch('asyncio.create_task') as mock_create_task:
            handler.on_created(mock_event)
            mock_create_task.assert_not_called()
    
    def test_on_created_ignores_non_log_files(self, mock_order_manager):
        """Test that non-log files are ignored."""
        file_watcher = FileWatcher(mock_order_manager)
        file_watcher._schedule_file_processing = AsyncMock()
        handler = LogFileHandler(file_watcher)
        
        mock_event = Mock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/readme.txt"
        
        with patch('asyncio.create_task') as mock_create_task:
            handler.on_created(mock_event)
            mock_create_task.assert_not_called()
    
    def test_on_modified_ignores_non_json_files(self, mock_order_manager):
        """Test that non-JSON files are ignored."""
        file_watcher = FileWatcher(mock_order_manager)
        file_watcher._schedule_file_processing = AsyncMock()
        handler = LogFileHandler(file_watcher)
        
        mock_event = Mock()
        mock_event.is_directory = False
        mock_event.src_path = "/test/file.txt"
        
        with patch('asyncio.create_task') as mock_create_task:
            handler.on_modified(mock_event)
            mock_create_task.assert_not_called()

