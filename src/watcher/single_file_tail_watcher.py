"""Single file tail watcher for real-time log monitoring."""

import asyncio
import aiofiles
from pathlib import Path
from typing import Optional, Dict, Set
import time
import re
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from src.parser.log_parser import LogParser
from src.storage.order_manager import OrderManager
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class SingleFileEventHandler(FileSystemEventHandler):
    """Handles file system events for single file monitoring."""
    
    def __init__(self, watcher: 'SingleFileTailWatcher'):
        self.watcher = watcher
    
    def on_created(self, event):
        """Called when a new file is created."""
        if not event.is_directory:
            file_path = Path(event.src_path)
            # Check if it's a numeric file in the hourly directory
            if file_path.name.isdigit():
                logger.info(f"New file created: {file_path}")
                # Schedule file switch in the main event loop
                asyncio.run_coroutine_threadsafe(
                    self.watcher._switch_to_new_file(file_path), 
                    self.watcher._main_loop
                )


class SingleFileTailWatcher:
    """Real-time single file tail watcher using readline approach."""
    
    def __init__(self, order_manager: OrderManager):
        self.order_manager = order_manager
        self.logs_path = Path(settings.NODE_LOGS_PATH).expanduser()
        self.parser = LogParser(chunk_size=settings.CHUNK_SIZE_BYTES, batch_size=settings.BATCH_SIZE)
        self.is_running = False
        
        # Current file tracking
        self.current_file_path: Optional[Path] = None
        self.current_file_handle: Optional[aiofiles.threadpool.AsyncTextIOWrapper] = None
        self.current_file_position = 0
        
        # Watchdog setup
        self.observer = Observer()
        self.handler = SingleFileEventHandler(self)
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Performance settings
        self.tail_interval = settings.TAIL_READLINE_INTERVAL_MS / 1000.0  # Convert to seconds
        self.fallback_interval = settings.FALLBACK_SCAN_INTERVAL_SEC
        
    async def start_async(self) -> None:
        """Starts single file tail monitoring."""
        logger.info(f"Starting single file tail watcher for {self.logs_path}")
        
        # Save reference to main event loop
        self._main_loop = asyncio.get_running_loop()
        
        # Ensure logs directory exists
        self.logs_path.mkdir(parents=True, exist_ok=True)
        
        # Find and start tailing current file
        await self._find_and_start_current_file()
        
        # Start watchdog for new file detection
        await self._start_watchdog()
        
        # Start fallback scanner
        fallback_task = asyncio.create_task(self._fallback_scanner())
        
        # Start main tail loop
        self.is_running = True
        tail_task = asyncio.create_task(self._tail_loop())
        
        logger.info("✅ Single file tail watcher started successfully")
    
    async def stop_async(self) -> None:
        """Stops tail monitoring."""
        logger.info("Stopping single file tail watcher")
        self.is_running = False
        
        # Stop observer
        self.observer.stop()
        self.observer.join()
        
        # Close current file handle
        if self.current_file_handle:
            try:
                await self.current_file_handle.close()
                logger.debug(f"Closed file handle: {self.current_file_path}")
            except Exception as e:
                logger.warning(f"Error closing file {self.current_file_path}: {e}")
        
        self.current_file_handle = None
        self.current_file_path = None
        self._main_loop = None
        
        logger.info("Single file tail watcher stopped")
    
    async def _find_and_start_current_file(self) -> None:
        """Finds the current file (max date + max hour) and starts tailing it."""
        try:
            current_file = self._find_current_file()
            if current_file:
                logger.info(f"Found current file: {current_file}")
                await self._start_tailing_file(current_file)
            else:
                logger.warning("No current file found, will monitor for new files")
        except Exception as e:
            logger.error(f"Error finding current file: {e}")
    
    def _find_current_file(self) -> Optional[Path]:
        """Finds the current file using max date + max hour algorithm."""
        try:
            hourly_path = self.logs_path / "node_order_statuses" / "hourly"
            logger.debug(f"Looking for current file in: {hourly_path}")
            
            if not hourly_path.exists():
                logger.warning(f"Hourly directory not found: {hourly_path}")
                return None
            
            # Find all date directories (yyyyMMdd format)
            date_dirs = []
            for item in hourly_path.iterdir():
                if item.is_dir() and re.match(r'^\d{8}$', item.name):
                    try:
                        # Validate date format
                        datetime.strptime(item.name, '%Y%m%d')
                        date_dirs.append(item)
                    except ValueError:
                        logger.debug(f"Invalid date directory: {item.name}")
                        continue
            
            if not date_dirs:
                logger.warning(f"No valid date directories found in {hourly_path}")
                return None
            
            # Find directory with maximum date
            max_date_dir = max(date_dirs, key=lambda d: d.name)
            logger.debug(f"Found max date directory: {max_date_dir}")
            
            # Find all numeric files in the max date directory
            numeric_files = []
            for item in max_date_dir.iterdir():
                if item.is_file() and item.name.isdigit():
                    try:
                        hour = int(item.name)
                        if 0 <= hour <= 23:  # Valid hour range
                            numeric_files.append(item)
                    except ValueError:
                        logger.debug(f"Invalid hour file: {item.name}")
                        continue
            
            if not numeric_files:
                logger.warning(f"No valid hour files found in {max_date_dir}")
                return None
            
            # Find file with maximum hour
            max_hour_file = max(numeric_files, key=lambda f: int(f.name))
            logger.info(f"Found current file: {max_hour_file} (date: {max_date_dir.name}, hour: {max_hour_file.name})")
            
            return max_hour_file
            
        except Exception as e:
            logger.error(f"Error finding current file: {e}")
            return None
    
    async def _start_tailing_file(self, file_path: Path) -> None:
        """Starts tailing a specific file."""
        try:
            # Close previous file if open
            if self.current_file_handle:
                await self.current_file_handle.close()
            
            # Open new file
            self.current_file_handle = await aiofiles.open(file_path, 'r')
            self.current_file_path = file_path
            
            # Seek to end of file (like tail -f)
            await self.current_file_handle.seek(0, 2)
            self.current_file_position = await self.current_file_handle.tell()
            
            logger.info(f"Started tailing {file_path} (position: {self.current_file_position})")
            
        except Exception as e:
            logger.error(f"Error starting to tail file {file_path}: {e}")
            self.current_file_handle = None
            self.current_file_path = None
    
    async def _tail_loop(self) -> None:
        """Main tail monitoring loop using readline approach."""
        logger.info("Tail loop started")
        
        while self.is_running:
            try:
                if self.current_file_handle:
                    await self._read_new_lines()
                else:
                    # No file to tail, try to find one
                    await self._find_and_start_current_file()
                
                await asyncio.sleep(self.tail_interval)
                
            except Exception as e:
                logger.error(f"Error in tail loop: {e}")
                # If file disappeared, rescan
                if "No such file" in str(e) or "file not found" in str(e).lower():
                    logger.warning("Current file disappeared, rescanning...")
                    await self._find_and_start_current_file()
                await asyncio.sleep(1)
        
        logger.info("Tail loop stopped")
    
    async def _read_new_lines(self) -> None:
        """Reads new lines from current file using readline approach."""
        try:
            if not self.current_file_handle:
                return
            
            # Read lines until EOF
            while True:
                line = await self.current_file_handle.readline()
                if not line:  # EOF
                    break
                
                line = line.strip()
                if line:
                    await self._process_line(line)
                    
        except Exception as e:
            logger.error(f"Error reading lines from {self.current_file_path}: {e}")
            raise
    
    async def _process_line(self, line: str) -> None:
        """Processes a single line from the file."""
        try:
            # Parse the line as an order
            orders = self.parser.parse_line(line)
            
            if orders:
                # Process valid orders
                await self.order_manager.update_orders_batch_async(orders)
                logger.debug(f"Processed {len(orders)} orders from line")
            else:
                # Invalid order, log as error and skip
                logger.error(f"Invalid order format, skipping line: {line[:100]}...")
                
        except Exception as e:
            logger.error(f"Error processing line: {e}, line: {line[:100]}...")
    
    async def _start_watchdog(self) -> None:
        """Starts watchdog for monitoring new file creation."""
        try:
            hourly_path = self.logs_path / "node_order_statuses" / "hourly"
            if hourly_path.exists():
                self.observer.schedule(self.handler, str(hourly_path), recursive=True)
                self.observer.start()
                logger.info(f"Started watchdog monitoring: {hourly_path}")
            else:
                logger.warning(f"Cannot start watchdog, directory not found: {hourly_path}")
        except Exception as e:
            logger.error(f"Error starting watchdog: {e}")
    
    async def _switch_to_new_file(self, new_file_path: Path) -> None:
        """Switches to a new file when it's created."""
        try:
            logger.info(f"Switching to new file: {new_file_path}")
            
            # Validate that this is indeed the new current file
            current_file = self._find_current_file()
            if current_file and current_file == new_file_path:
                await self._start_tailing_file(new_file_path)
                logger.info(f"Successfully switched to new file: {new_file_path}")
            else:
                logger.warning(f"New file {new_file_path} is not the current max file, ignoring")
                
        except Exception as e:
            logger.error(f"Error switching to new file {new_file_path}: {e}")
    
    async def _fallback_scanner(self) -> None:
        """Fallback scanner that runs periodically to ensure we're following the right file."""
        logger.info("Fallback scanner started")
        
        while self.is_running:
            try:
                await asyncio.sleep(self.fallback_interval)
                
                if not self.is_running:
                    break
                
                # Find what should be the current file
                expected_current_file = self._find_current_file()
                
                if expected_current_file:
                    # Check if we're following the right file
                    if self.current_file_path != expected_current_file:
                        logger.warning(f"Current file mismatch! Following: {self.current_file_path}, Should be: {expected_current_file}")
                        await self._start_tailing_file(expected_current_file)
                    else:
                        logger.debug("Fallback scan: following correct file")
                else:
                    logger.warning("Fallback scan: no current file found")
                
            except Exception as e:
                logger.error(f"Error in fallback scanner: {e}")
                await asyncio.sleep(60)  # Wait before retrying
        
        logger.info("Fallback scanner stopped")
    
    def get_status(self) -> dict:
        """Returns current status for monitoring."""
        return {
            "is_running": self.is_running,
            "current_file": str(self.current_file_path) if self.current_file_path else None,
            "current_position": self.current_file_position,
            "tail_interval_ms": self.tail_interval * 1000,
            "fallback_interval_sec": self.fallback_interval,
            "watchdog_active": self.observer.is_alive() if self.observer else False
        }
