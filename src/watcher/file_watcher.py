"""File watcher for monitoring HyperLiquid node logs."""

import asyncio
from pathlib import Path
from typing import List, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent
import aiofiles

from src.parser.log_parser import LogParser
from src.storage.order_manager import OrderManager
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class LogFileHandler(FileSystemEventHandler):
    """Handles file system events for log files."""
    
    def __init__(self, file_watcher: 'FileWatcher'):
        self.file_watcher = file_watcher
    
    def on_modified(self, event):
        """Called when a file is modified."""
        if not event.is_directory and event.src_path.endswith('.json'):
            asyncio.create_task(self.file_watcher._process_file_async(Path(event.src_path)))
    
    def on_created(self, event):
        """Called when a new file is created."""
        if not event.is_directory and event.src_path.endswith('.json'):
            asyncio.create_task(self.file_watcher._process_file_async(Path(event.src_path)))


class FileWatcher:
    """Monitors log directories for file changes."""
    
    def __init__(self, order_manager: OrderManager):
        self.order_manager = order_manager
        self.logs_path = Path(settings.NODE_LOGS_PATH).expanduser()
        self.observer = Observer()
        self.handler = LogFileHandler(self)
        self.parser = LogParser(chunk_size=8192, batch_size=1000)
        self.is_running = False
        self.processing_files: set = set()  # Track files being processed
        
    async def start_async(self) -> None:
        """Starts file monitoring."""
        logger.info(f"Starting file watcher for {self.logs_path}")
        
        # Ensure logs directory exists
        self.logs_path.mkdir(parents=True, exist_ok=True)
        
        # Schedule initial scan of latest file
        asyncio.create_task(self.scan_latest_file_async())
        
        # Schedule periodic cleanup
        asyncio.create_task(self._cleanup_loop_async())
        
        # Start file system monitoring
        self.observer.schedule(self.handler, str(self.logs_path), recursive=True)
        self.observer.start()
        self.is_running = True
        
        logger.info("File watcher started successfully")
    
    async def stop_async(self) -> None:
        """Stops file monitoring."""
        logger.info("Stopping file watcher")
        self.is_running = False
        self.observer.stop()
        self.observer.join()
        logger.info("File watcher stopped")
    
    async def scan_latest_file_async(self) -> None:
        """Scans only the latest file on startup."""
        try:
            latest_file = self._find_latest_file()
            if latest_file:
                logger.info(f"Scanning latest file: {latest_file}")
                await self._process_file_async(latest_file)
            else:
                logger.debug(f"No log files found for initial scan\n{self.logs_path}")
                logger.info(f"No log files found for initial scan")
        except Exception as e:
            logger.error(f"Error during initial file scan: {e}")
    
    async def _process_file_async(self, file_path: Path) -> None:
        """Processes a single log file asynchronously with timeout protection."""
        # Prevent concurrent processing of the same file
        if file_path in self.processing_files:
            logger.debug(f"File {file_path} is already being processed, skipping")
            return
        
        self.processing_files.add(file_path)
        
        try:
            logger.debug(f"Processing file: {file_path}")
            
            # Check file size and apply limits
            file_size = file_path.stat().st_size
            file_size_gb = file_size / (1024**3)
            
            if file_size_gb > settings.MAX_FILE_SIZE_GB:
                logger.warning(f"File {file_path} too large ({file_size_gb:.2f} GB), skipping")
                return
            
            # Use timeout parsing for large files
            timeout_seconds = min(60, max(10, int(file_size_gb * 5)))  # 5s per GB, min 10s, max 60s
            max_orders = settings.MAX_ORDERS_PER_FILE if hasattr(settings, 'MAX_ORDERS_PER_FILE') else None
            
            logger.info(f"Processing {file_path} ({file_size_gb:.2f} GB) with {timeout_seconds}s timeout")
            
            # Parse file with timeout and batching
            orders = await self.parser.parse_file_with_timeout_async(
                str(file_path), 
                timeout_seconds=timeout_seconds,
                max_orders=max_orders
            )
            
            if orders:
                # Process orders in batches to prevent blocking
                batch_size = 500
                for i in range(0, len(orders), batch_size):
                    batch = orders[i:i + batch_size]
                    await self.order_manager.update_orders_batch_async(batch)
                    
                    # Small delay between batches to prevent blocking
                    if i + batch_size < len(orders):
                        await asyncio.sleep(0.01)
                
                logger.info(f"Processed {len(orders)} orders from {file_path}")
            else:
                logger.debug(f"No orders found in {file_path}")
                
        except asyncio.TimeoutError:
            logger.warning(f"Processing timeout for {file_path}")
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
        finally:
            self.processing_files.discard(file_path)
    
    async def _read_file_with_retry_async(self, file_path: Path) -> List[str]:
        """Reads file with retry logic."""
        for attempt in range(settings.FILE_READ_RETRY_ATTEMPTS):
            try:
                async with aiofiles.open(file_path, 'r') as f:
                    return await f.readlines()
            except (IOError, OSError) as e:
                if attempt < settings.FILE_READ_RETRY_ATTEMPTS - 1:
                    await asyncio.sleep(settings.FILE_READ_RETRY_DELAY)
                else:
                    logger.error(f"Failed to read file after {settings.FILE_READ_RETRY_ATTEMPTS} attempts: {file_path}")
                    raise
    
    def _find_latest_file(self) -> Optional[Path]:
        """Finds the most recent log file."""
        try:
            json_files = list(self.logs_path.rglob("*"))
            if not json_files:
                return None
            
            # Sort by modification time, newest first
            latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
            return latest_file
        except Exception as e:
            logger.error(f"Error finding latest file: {e}")
            return None
    
    async def _cleanup_loop_async(self) -> None:
        """Periodic cleanup loop."""
        while self.is_running:
            try:
                await asyncio.sleep(settings.CLEANUP_INTERVAL_HOURS * 3600)  # Convert hours to seconds
                if self.is_running:
                    await self.cleanup_old_data_async()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def cleanup_old_data_async(self) -> None:
        """Removes data older than configured hours."""
        try:
            cleaned_count = self.order_manager.cleanup_old_orders(settings.CLEANUP_INTERVAL_HOURS)
            logger.info(f"Cleaned up {cleaned_count} old orders")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
