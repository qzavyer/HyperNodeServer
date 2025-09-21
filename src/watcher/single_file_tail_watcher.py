"""Single file tail watcher for real-time log monitoring."""

import asyncio
import aiofiles
from pathlib import Path
from typing import Optional, Dict, Set, List
import time
import re
import json
import concurrent.futures
import mmap
import threading
import os
import psutil
from functools import lru_cache
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from src.parser.log_parser import LogParser
from src.storage.order_manager import OrderManager
from src.monitoring.resource_monitor import ResourceMonitor
from src.cleanup.directory_cleaner import DirectoryCleaner
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
        self.batch_size = settings.TAIL_BATCH_SIZE
        self.buffer_size = settings.TAIL_BUFFER_SIZE
        self.aggressive_polling = settings.TAIL_AGGRESSIVE_POLLING
        
        # Parallel processing settings - conservative for HyperLiquid node coexistence
        if settings.MAX_WORKERS_AUTO:
            # Use only 1/4 of available CPU cores to leave resources for HyperLiquid node
            available_cores = os.cpu_count() or 4
            self.parallel_workers = max(1, min(settings.TAIL_PARALLEL_WORKERS, available_cores // 4))
        else:
            self.parallel_workers = settings.TAIL_PARALLEL_WORKERS
        self.parallel_batch_size = settings.TAIL_PARALLEL_BATCH_SIZE
        self.json_optimization = settings.TAIL_JSON_OPTIMIZATION
        self.pre_filter = settings.TAIL_PRE_FILTER
        
        # Revolutionary memory-mapped processing
        self.memory_mapped = settings.TAIL_MEMORY_MAPPED
        self.mmap_chunk_size = settings.TAIL_MMAP_CHUNK_SIZE
        self.zero_copy = settings.TAIL_ZERO_COPY
        self.lock_free = settings.TAIL_LOCK_FREE
        
        # Streaming processing
        self.streaming = settings.TAIL_STREAMING
        self.stream_buffer_size = settings.TAIL_STREAM_BUFFER_SIZE
        self.stream_chunk_size = settings.TAIL_STREAM_CHUNK_SIZE
        self.stream_processing_delay = settings.TAIL_STREAM_PROCESSING_DELAY_MS / 1000.0
        
        # Thread pool for parallel processing
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.parallel_workers)
        
        # Memory-mapped file state
        self.mmap_file = None
        self.mmap_data = None
        self.mmap_position = 0
        self.mmap_lock = threading.RLock() if not self.lock_free else None
        
        # Streaming state
        self.stream_buffer = bytearray()
        self.stream_position = 0
        
        # Directory cleaner for automatic cleanup on disk space issues
        self.directory_cleaner = DirectoryCleaner(base_dir=str(self.logs_path), single_file_watcher=self)
        self.last_cleanup_time = 0
        self.cleanup_cooldown = 300  # 5 minutes cooldown between cleanups
        
        # Pre-filtering patterns for fast line validation (compiled once)
        self.valid_line_patterns = [
            re.compile(r'^\s*\{.*\}\s*$'),  # JSON object
            re.compile(r'"order"'),  # Contains order field
            re.compile(r'"status"'),  # Contains status field
        ]
        
        # Cache for compiled regex patterns
        self._pattern_cache = {}
        
        # Resource monitoring for HyperLiquid node coexistence
        self.resource_monitor = ResourceMonitor()
        
        # Batch processing
        self.line_buffer = []
        self.last_batch_time = 0
        self.batch_timeout_ms = 5  # Process batch after 5ms or when full
        
        # Aggressive mode settings
        if self.aggressive_polling:
            self.tail_interval = 0.0001  # 0.1ms polling in aggressive mode
            self.batch_timeout_ms = 0.1   # 0.1ms batch timeout in aggressive mode
        
        # Ultra-fast mode settings
        if settings.TAIL_ULTRA_FAST_MODE:
            self.tail_interval = 0.00001  # 0.01ms polling in ultra-fast mode
            self.batch_timeout_ms = 0.01   # 0.01ms batch timeout in ultra-fast mode
            self.batch_size = settings.TAIL_MAX_BATCH_SIZE  # Use max batch size
        
        # Emergency mode settings (maximum speed)
        if settings.TAIL_EMERGENCY_MODE:
            self.tail_interval = 0.000001  # 0.001ms polling in emergency mode
            self.batch_timeout_ms = 0.001   # 0.001ms batch timeout in emergency mode
            self.batch_size = settings.TAIL_MAX_BATCH_SIZE  # Use max batch size
            self.parallel_workers = 16  # Maximum parallel workers
            self.parallel_batch_size = 500  # Maximum parallel batch size
        
        # Performance counters
        self.total_lines_processed = 0
        self.total_orders_processed = 0
        self.last_performance_log = 0
        self.last_orders_log = 0
        self.global_lines_processed = 0
        
        # JSON optimization cache with size limit
        self.json_cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.max_cache_size = 10000  # Limit cache size to prevent memory issues
        
        # Pre-filtering counters
        self.pre_filter_passed = 0
        self.pre_filter_rejected = 0
        
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
        
        # Process any remaining lines in buffer
        if self.line_buffer:
            await self._process_batch()
        
        # Close current file handle
        if self.current_file_handle:
            try:
                await self.current_file_handle.close()
                logger.debug(f"Closed file handle: {self.current_file_path}")
            except Exception as e:
                logger.warning(f"Error closing file {self.current_file_path}: {e}")
        
        # Close memory-mapped file
        if self.mmap_file:
            try:
                self.mmap_file.close()
                logger.debug("Closed memory-mapped file")
            except Exception as e:
                logger.warning(f"Error closing memory-mapped file: {e}")
        
        # Shutdown thread pool
        self.executor.shutdown(wait=True)
        
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
            logger.info(f"Found max date directory: {max_date_dir}")
            
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
            
            # Log detailed file info
            try:
                file_stat = max_hour_file.stat()
                logger.info(f"Found current file: {max_hour_file.name} (date: {max_date_dir.name}, hour: {max_hour_file.name})")
                logger.info(f"File size: {file_stat.st_size} bytes, modified: {file_stat.st_mtime}")
            except Exception as e:
                logger.warning(f"Could not get file stats for {max_hour_file}: {e}")
            
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
            
            # Open new file with optimized buffer size
            self.current_file_handle = await aiofiles.open(file_path, 'r', buffering=self.buffer_size)
            self.current_file_path = file_path
            
            # Seek to end of file (like tail -f)
            await self.current_file_handle.seek(0, 2)
            self.current_file_position = await self.current_file_handle.tell()
            
            # Initialize memory-mapped file if enabled
            if self.memory_mapped:
                await self._init_memory_mapped_file(file_path)
            
            logger.info(f"Started tailing {file_path} (position: {self.current_file_position})")
            
        except Exception as e:
            logger.error(f"Error starting to tail file {file_path}: {e}")
            self.current_file_handle = None
            self.current_file_path = None
    
    async def _tail_loop(self) -> None:
        """Main tail monitoring loop using readline approach."""
        logger.info("Tail loop started")
        loop_count = 0
        
        # Use asyncio.create_task for concurrent operations
        tasks = []
        
        while self.is_running:
            try:
                loop_count += 1
                if loop_count % 100 == 0:  # Log every 100 iterations
                    logger.info(f"Tail loop iteration {loop_count}, running: {self.is_running}")
                
                # Create concurrent tasks
                if self.current_file_handle:
                    # Process file reading and order processing concurrently
                    read_task = asyncio.create_task(self._read_new_lines())
                    tasks.append(read_task)
                else:
                    # Find new file
                    find_task = asyncio.create_task(self._find_and_start_current_file())
                    tasks.append(find_task)
                
                # Wait for tasks with timeout to prevent blocking
                if tasks:
                    done, pending = await asyncio.wait(tasks, timeout=0.01, return_when=asyncio.FIRST_COMPLETED)
                    
                    # Cancel pending tasks
                    for task in pending:
                        task.cancel()
                    
                    # Clear completed tasks
                    tasks = list(pending)
                
                # Check resource usage and throttle if necessary
                throttle_factor = self.resource_monitor.get_throttle_factor()
                await asyncio.sleep(self.tail_interval * throttle_factor)
                
            except OSError as e:
                if e.errno == 28:  # No space left on device
                    logger.error("🚨 No space left on device detected in tail loop! Starting emergency cleanup...")
                    cleanup_performed = await self._emergency_cleanup_if_needed()
                    if cleanup_performed:
                        logger.info("✅ Emergency cleanup completed, continuing...")
                    else:
                        logger.error("❌ Emergency cleanup failed or not needed")
                else:
                    logger.error(f"OSError in tail loop: {e}")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error in tail loop: {e}")
                # If file disappeared, rescan
                if "No such file" in str(e) or "file not found" in str(e).lower():
                    logger.warning("Current file disappeared, rescanning...")
                    await self._find_and_start_current_file()
                await asyncio.sleep(1)
        
        logger.info("Tail loop stopped")
    
    async def _read_new_lines(self) -> None:
        """Reads new lines using revolutionary memory-mapped approach."""
        try:
            if not self.current_file_handle:
                logger.info("No file handle available for reading")
                return
            
            # Log current file info
            if self.current_file_path:
                try:
                    file_stat = self.current_file_path.stat()
                    logger.info(f"Reading file: {self.current_file_path.name}, size: {file_stat.st_size} bytes, modified: {file_stat.st_mtime}")
                except OSError as e:
                    if e.errno == 28:  # No space left on device
                        logger.error("🚨 No space left on device detected! Starting emergency cleanup...")
                        cleanup_performed = await self._emergency_cleanup_if_needed()
                        if cleanup_performed:
                            logger.info("✅ Emergency cleanup completed, continuing...")
                        else:
                            logger.error("❌ Emergency cleanup failed or not needed")
                    else:
                        logger.warning(f"Could not get file stats: {e}")
                except Exception as e:
                    logger.warning(f"Could not get file stats: {e}")
            
            # Use revolutionary approach based on settings
            if self.streaming:
                logger.info("Reading lines using streaming approach")
                await self._read_streaming_lines()
            elif self.memory_mapped and self.mmap_data:
                logger.info("Reading lines using memory-mapped approach")
                await self._read_memory_mapped_lines()
            else:
                logger.info("Reading lines using traditional approach")
                await self._read_traditional_lines()
                        
        except OSError as e:
            if e.errno == 28:  # No space left on device
                logger.error("🚨 No space left on device detected in _read_new_lines! Starting emergency cleanup...")
                cleanup_performed = await self._emergency_cleanup_if_needed()
                if cleanup_performed:
                    logger.info("✅ Emergency cleanup completed, continuing...")
                else:
                    logger.error("❌ Emergency cleanup failed or not needed")
            else:
                logger.error(f"OSError reading lines from {self.current_file_path}: {e}")
        except Exception as e:
            logger.error(f"Error reading lines from {self.current_file_path}: {e}")
            raise
    
    async def _read_traditional_lines(self) -> None:
        """Traditional readline approach (fallback)."""
        lines_read = 0
        
        # Check if file handle is valid
        if not self.current_file_handle:
            logger.error("No file handle available in _read_traditional_lines")
            return
        
        try:
            # Use non-blocking approach - get file size from filesystem
            import os
            file_stat = os.stat(self.current_file_path)
            file_size = file_stat.st_size
            logger.info(f"File size check: {file_size} bytes")
            
            # Get current position from our internal tracking
            if not hasattr(self, 'file_position') or not hasattr(self, 'last_file_path') or self.last_file_path != self.current_file_path:
                # New file or first time - start from end
                self.file_position = file_size
                self.last_file_path = self.current_file_path
                logger.info(f"New file detected, initialized file position to: {self.file_position}")
                return  # No new data on first read
            
            current_pos = self.file_position
            new_data_bytes = file_size - current_pos
            logger.info(f"Position check: current={current_pos}, file_size={file_size}, new_bytes={new_data_bytes}")
        except Exception as e:
            logger.error(f"Error checking file position: {e}")
            return
        
        self.file_position = file_size
        
        if new_data_bytes == 0:
            logger.info("No new data available, file not growing")
            return
        
        # Read new data using regular file operations (non-blocking)
        if new_data_bytes > 0:
            logger.info(f"About to read {new_data_bytes} bytes from file")
            try:
                # Open file in binary mode for precise positioning
                with open(self.current_file_path, 'rb') as f:
                    f.seek(current_pos)  # Seek to our last position
                    new_data = f.read(new_data_bytes)  # Read only new data
                    
                    # Convert to text and split into lines
                    new_text = new_data.decode('utf-8', errors='ignore')
                    new_lines = new_text.split('\n')
                    logger.info(f"Decoded {len(new_data)} bytes to {len(new_lines)} lines")
                    
                    # Process each line
                    for line_idx, line in enumerate(new_lines):
                        line = line.strip()
                        if line:
                            self.line_buffer.append(line)
                            lines_read += 1
                            
                            # Log every 1000 lines added to buffer
                            if lines_read % 1000 == 0:
                                logger.info(f"Added {lines_read} lines to buffer, buffer size: {len(self.line_buffer)}")
                                print(f"Added {lines_read} lines to buffer, buffer size: {len(self.line_buffer)}")
                            
                            # Process batch when full or timeout reached
                            if (len(self.line_buffer) >= self.batch_size or 
                                self._should_process_batch()):
                                await self._process_batch()

            except Exception as e:
                logger.error(f"Error reading new data: {e}")
                return
        
        # Process remaining lines in buffer
        if self.line_buffer and self._should_process_batch():
            await self._process_batch()
    
    async def _read_memory_mapped_lines(self) -> None:
        """Revolutionary memory-mapped line reading."""
        try:
            # Get current file size
            current_size = self.current_file_handle.tell()
            
            # If file grew, read new data
            if current_size > self.mmap_position:
                # Read new chunk
                new_data_size = current_size - self.mmap_position
                new_data = self.mmap_data[self.mmap_position:current_size]
                
                # Process new data in chunks
                await self._process_memory_mapped_chunk(new_data)
                
                # Update position
                self.mmap_position = current_size
                
        except Exception as e:
            logger.error(f"Error in memory-mapped reading: {e}")
            # Fallback to traditional approach
            await self._read_traditional_lines()
    
    async def _init_memory_mapped_file(self, file_path: Path) -> None:
        """Initialize memory-mapped file for ultra-fast reading."""
        try:
            # Close previous mmap if exists
            if self.mmap_file:
                self.mmap_file.close()
            
            # Open file for memory mapping
            with open(file_path, 'rb') as f:
                # Get file size
                f.seek(0, 2)
                file_size = f.tell()
                
                if file_size > 0:
                    # Create memory map
                    self.mmap_file = mmap.mmap(f.fileno(), file_size, access=mmap.ACCESS_READ)
                    self.mmap_data = self.mmap_file
                    self.mmap_position = file_size  # Start from end
                    
                    logger.info(f"Initialized memory-mapped file: {file_size} bytes")
                else:
                    logger.warning("File is empty, skipping memory mapping")
                    
        except Exception as e:
            logger.error(f"Error initializing memory-mapped file: {e}")
            self.mmap_file = None
            self.mmap_data = None
    
    async def _process_memory_mapped_chunk(self, data: bytes) -> None:
        """Process memory-mapped chunk with zero-copy string operations."""
        try:
            # Convert bytes to string (zero-copy if possible)
            if self.zero_copy:
                # Use memoryview for zero-copy operations
                text = data.decode('utf-8', errors='ignore')
            else:
                text = data.decode('utf-8', errors='ignore')
            
            # Split into lines and process
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if line:
                    self.line_buffer.append(line)
                    
                    # Process batch when full or timeout reached
                    if (len(self.line_buffer) >= self.batch_size or 
                        self._should_process_batch()):
                        await self._process_batch()
                        
        except Exception as e:
            logger.error(f"Error processing memory-mapped chunk: {e}")
    
    async def _read_streaming_lines(self) -> None:
        """Revolutionary streaming processing for maximum speed."""
        try:
            # Get current file size
            current_size = self.current_file_handle.tell()
            
            # If file grew, read new data in streaming chunks
            if current_size > self.stream_position:
                # Read new data in chunks
                while self.stream_position < current_size:
                    # Calculate chunk size
                    chunk_size = min(self.stream_chunk_size, current_size - self.stream_position)
                    
                    # Read chunk
                    await self.current_file_handle.seek(self.stream_position)
                    chunk_data = await self.current_file_handle.read(chunk_size)
                    
                    if chunk_data:
                        # Add to stream buffer
                        self.stream_buffer.extend(chunk_data)
                        
                        # Process complete lines from buffer
                        await self._process_stream_buffer()
                        
                        # Update position
                        self.stream_position += len(chunk_data)
                    
                    # Small delay to prevent overwhelming the system
                    if self.stream_processing_delay > 0:
                        if settings.TAIL_NO_SLEEP_MODE:
                            # Yield control to event loop without delay
                            await asyncio.sleep(0)  # Yield to event loop
                        else:
                            await asyncio.sleep(self.stream_processing_delay)
                        
        except Exception as e:
            logger.error(f"Error in streaming reading: {e}")
            # Fallback to traditional approach
            await self._read_traditional_lines()
    
    async def _process_stream_buffer(self) -> None:
        """Process streaming buffer for complete lines."""
        try:
            # Find complete lines in buffer
            while b'\n' in self.stream_buffer:
                # Find first newline
                newline_pos = self.stream_buffer.find(b'\n')
                
                # Extract line
                line_bytes = self.stream_buffer[:newline_pos]
                self.stream_buffer = self.stream_buffer[newline_pos + 1:]
                
                # Convert to string
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                
                if line:
                    self.line_buffer.append(line)
                    
                    # Process batch when full or timeout reached
                    if (len(self.line_buffer) >= self.batch_size or 
                        self._should_process_batch()):
                        await self._process_batch()
                        
        except Exception as e:
            logger.error(f"Error processing stream buffer: {e}")
    
    def _should_process_batch(self) -> bool:
        """Check if batch should be processed due to timeout."""
        if not self.line_buffer:
            return False
            
        current_time = time.time() * 1000  # Convert to milliseconds
        return (current_time - self.last_batch_time) >= self.batch_timeout_ms
    
    async def _process_batch(self) -> None:
        """Process a batch of lines for maximum performance with parallel processing."""
        if not self.line_buffer:
            return
            
        logger.info(f"Processing batch of {len(self.line_buffer)} lines")
        print(f"Processing batch of {len(self.line_buffer)} lines")
            
        try:
            # Use parallel processing for large batches
            if len(self.line_buffer) >= self.parallel_batch_size:
                orders = await self._process_batch_parallel(self.line_buffer)
            else:
                orders = await self._process_batch_sequential(self.line_buffer)
            
            logger.info(f"Processed batch of {len(orders)} orders")

            # Process all orders at once
            if orders:
                await self.order_manager.update_orders_batch_async(orders)
                self.total_orders_processed += len(orders)
                
                # Log every 1000 orders with timestamp of last order
                if self.total_orders_processed - self.last_orders_log >= 1000:
                    last_order_timestamp = orders[-1].timestamp if orders else None
                    timestamp_str = last_order_timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] if last_order_timestamp else "N/A"
                    logger.info(f"Processed {self.total_orders_processed} orders total, last order timestamp: {timestamp_str}")
                    self.last_orders_log = self.total_orders_processed
            
            # Update counters
            self.total_lines_processed += len(self.line_buffer)
            
            # Log performance every 1000 lines
            if self.total_lines_processed - self.last_performance_log >= 1000:
                cache_hit_rate = (self.cache_hits / (self.cache_hits + self.cache_misses) * 100) if (self.cache_hits + self.cache_misses) > 0 else 0
                pre_filter_rate = (self.pre_filter_passed / (self.pre_filter_passed + self.pre_filter_rejected) * 100) if (self.pre_filter_passed + self.pre_filter_rejected) > 0 else 0
                logger.info(f"Performance: {self.total_lines_processed} lines, {self.total_orders_processed} orders processed, cache hit rate: {cache_hit_rate:.1f}%, pre-filter pass rate: {pre_filter_rate:.1f}%")
                self.last_performance_log = self.total_lines_processed
            
            # Clear buffer and update timestamp
            self.line_buffer.clear()
            self.last_batch_time = time.time() * 1000
            
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            self.line_buffer.clear()  # Clear buffer on error
    
    async def _process_batch_sequential(self, lines: List[str]) -> List:
        """Process batch sequentially for small batches."""
        orders = []
        for line in lines:
            order = self._parse_line_optimized(line)
            if order:
                orders.append(order)
        return orders
    
    async def _process_batch_parallel(self, lines: List[str]) -> List:
        """Process batch in parallel for large batches."""
        # Split lines into chunks for parallel processing
        chunk_size = max(1, len(lines) // self.parallel_workers)
        chunks = [lines[i:i + chunk_size] for i in range(0, len(lines), chunk_size)]
        
        logger.info(f"Parallel processing {len(lines)} lines in {len(chunks)} chunks")
        print(f"Parallel processing {len(lines)} lines in {len(chunks)} chunks")
        
        # Process chunks in parallel
        loop = asyncio.get_event_loop()
        tasks = []
        for chunk in chunks:
            task = loop.run_in_executor(self.executor, self._parse_chunk_sync, chunk)
            tasks.append(task)
        
        # Wait for all chunks to complete with individual timeouts
        try:
            logger.info(f"Starting asyncio.gather with {len(tasks)} tasks")
            print(f"Starting asyncio.gather with {len(tasks)} tasks")
            
            # Wait for each task individually with timeout
            results = []
            for i, task in enumerate(tasks):
                try:
                    result = await asyncio.wait_for(task, timeout=10.0)
                    results.append(result)
                    logger.info(f"Task {i} completed successfully")
                    print(f"Task {i} completed successfully")
                except asyncio.TimeoutError:
                    logger.error(f"Task {i} timed out after 10 seconds, cancelling")
                    print(f"Task {i} timed out after 10 seconds, cancelling")
                    task.cancel()
                    results.append(Exception(f"Task {i} timed out"))
                except Exception as e:
                    logger.error(f"Task {i} failed: {e}")
                    print(f"Task {i} failed: {e}")
                    results.append(e)
            
            logger.info(f"All tasks processed: {len(results)} results")
            print(f"All tasks processed: {len(results)} results")
        except Exception as e:
            logger.error(f"Parallel batch processing failed: {e}")
            print(f"Parallel batch processing failed: {e}")
            raise
        
        # Combine results
        orders = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error in parallel processing chunk {i}: {result}")
                print(f"Error in parallel processing chunk {i}: {result}")
            else:
                orders.extend(result)
        
        logger.info(f"Parallel processing completed: {len(orders)} total orders")
        print(f"Parallel processing completed: {len(orders)} total orders")
        
        return orders
    
    def _parse_chunk_sync(self, lines: List[str]) -> List:
        """Synchronous parsing of a chunk of lines (for thread pool)."""
        orders = []
        for line in lines:
            order = self._parse_line_optimized(line)
            if order:
                orders.append(order)
        
        # Diagnostic: log chunk processing results
        if len(lines) > 0:
            logger.info(f"Chunk processed: {len(lines)} lines -> {len(orders)} orders")
            print(f"Chunk processed: {len(lines)} lines -> {len(orders)} orders")
        
        return orders
    
    @lru_cache(maxsize=1000)
    def _pre_filter_line(self, line: str) -> bool:
        """Fast pre-filtering to reject obviously invalid lines with caching."""
        if not self.pre_filter:
            return True
            
        if not line.strip():
            self.pre_filter_rejected += 1
            return False
        
        # Check if line matches any valid pattern
        for pattern in self.valid_line_patterns:
            if pattern.search(line):
                self.pre_filter_passed += 1
                return True
        
        self.pre_filter_rejected += 1
        
        # Diagnostic: log every 100 rejected lines
        if self.pre_filter_rejected % 100 == 0:
            logger.info(f"Pre-filter rejected {self.pre_filter_rejected} lines, last: {line[:50]}...")
            print(f"Pre-filter rejected {self.pre_filter_rejected} lines, last: {line[:50]}...")
        
        return False
    
    def _check_resource_usage(self) -> bool:
        """Check if resource usage is within limits for HyperLiquid node coexistence."""
        return not self.resource_monitor.should_throttle()
    
    def _parse_line_optimized(self, line: str) -> Optional:
        """Optimized line parsing with JSON caching and pre-filtering."""
        if not line.strip():
            return None
        
        # Pre-filtering: reject obviously invalid lines
        if not self._pre_filter_line(line):
            return None
        
        # Увеличиваем глобальный счетчик для всех строк, прошедших pre-filter
        self.global_lines_processed += 1
        
        # Диагностика: логируем каждые 500 строк
        if self.global_lines_processed % 500 == 0:
            logger.info(f"Global lines processed: {self.global_lines_processed}")
            print(f"Global lines processed: {self.global_lines_processed}")
        
        # Логируем статистику OrderExtractor каждые 1000 обработанных строк
        if self.global_lines_processed > 0 and self.global_lines_processed % 1000 == 0:
            logger.info(f"Triggering OrderExtractor stats logging at {self.global_lines_processed} lines")
            print(f"Triggering OrderExtractor stats logging at {self.global_lines_processed} lines")
            if hasattr(self.parser, 'order_extractor') and hasattr(self.parser.order_extractor, '_log_detailed_stats'):
                self.parser.order_extractor._log_detailed_stats()
            else:
                logger.error("OrderExtractor does not have _log_detailed_stats method")
                print("OrderExtractor does not have _log_detailed_stats method")
        
        # Diagnostic: log every 1000 lines to see what we're processing
        if hasattr(self, '_parse_line_count'):
            self._parse_line_count += 1
        else:
            self._parse_line_count = 1
            
        if self._parse_line_count % 1000 == 0:
            logger.info(f"Parsing line {self._parse_line_count}: {line[:100]}...")
            print(f"Parsing line {self._parse_line_count}: {line[:100]}...")
            
        try:
            # JSON optimization: cache parsed JSON for identical lines
            if self.json_optimization:
                line_hash = hash(line)
                if line_hash in self.json_cache:
                    self.cache_hits += 1
                    cached_data = self.json_cache[line_hash]
                    if cached_data is not None:
                        return self.parser._create_order_from_data(cached_data)
                    return None
                else:
                    self.cache_misses += 1
            
            # Parse the line
            order = self.parser.parse_line(line)
            
            # Cache the result if JSON optimization is enabled
            if self.json_optimization and order:
                # Extract raw JSON data for caching
                try:
                    json_data = json.loads(line)
                    self.json_cache[line_hash] = json_data
                    
                    # Limit cache size to prevent memory issues
                    if len(self.json_cache) > 10000:
                        # Remove oldest entries (simple FIFO)
                        oldest_keys = list(self.json_cache.keys())[:1000]
                        for key in oldest_keys:
                            del self.json_cache[key]
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    # If JSON parsing fails, don't cache - this is expected for malformed data
                    logger.debug(f"JSON parsing failed for caching: {e}")
                    pass
            
            return order
            
        except Exception as e:
            logger.debug(f"Error parsing line: {e}")
            return None
    
    async def _process_line(self, line: str) -> None:
        """Processes a single line from the file."""
        try:
            # Parse the line as an order using public method
            order = self.parser.parse_line(line)
            
            if order:
                # Process valid order
                await self.order_manager.update_orders_batch_async([order])
                logger.info(f"Processed order from line")
                
        except Exception as e:
            logger.error(f"Error processing line: {e}, line: {line}")
    
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
            "watchdog_active": self.observer.is_alive() if self.observer else False,
            "batch_size": self.batch_size,
            "buffer_size": self.buffer_size,
            "lines_in_buffer": len(self.line_buffer),
            "batch_timeout_ms": self.batch_timeout_ms,
            "aggressive_polling": self.aggressive_polling,
            "parallel_workers": self.parallel_workers,
            "parallel_batch_size": self.parallel_batch_size,
            "json_optimization": self.json_optimization,
            "pre_filter": self.pre_filter,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_size": len(self.json_cache),
            "pre_filter_passed": self.pre_filter_passed,
            "pre_filter_rejected": self.pre_filter_rejected,
            "memory_mapped": self.memory_mapped,
            "streaming": self.streaming,
            "zero_copy": self.zero_copy,
            "lock_free": self.lock_free,
            "stream_buffer_size": len(self.stream_buffer),
            "mmap_position": self.mmap_position,
            "stream_position": self.stream_position,
            "total_lines_processed": self.total_lines_processed,
            "total_orders_processed": self.total_orders_processed,
            "resource_monitor": self.resource_monitor.get_status(),
            "resource_usage": self.resource_monitor.check_resources()
        }
    
    async def _emergency_cleanup_if_needed(self) -> bool:
        """Perform emergency cleanup if disk space is low.
        
        Returns:
            bool: True if cleanup was performed, False otherwise
        """
        try:
            current_time = time.time()
            
            # Check cooldown to avoid excessive cleanup
            if current_time - self.last_cleanup_time < self.cleanup_cooldown:
                return False
            
            # Check disk space
            disk_usage = psutil.disk_usage(self.logs_path)
            free_space_gb = disk_usage.free / (1024**3)
            
            # If less than 1GB free space, trigger cleanup
            if free_space_gb < 1.0:
                logger.warning(f"🚨 Low disk space detected: {free_space_gb:.2f}GB free. Starting emergency cleanup...")
                
                # Perform cleanup
                removed_dirs, removed_files = await self.directory_cleaner.cleanup_async()
                
                self.last_cleanup_time = current_time
                
                # Check space after cleanup
                disk_usage_after = psutil.disk_usage(self.logs_path)
                free_space_after_gb = disk_usage_after.free / (1024**3)
                
                logger.info(f"✅ Emergency cleanup completed: removed {removed_dirs} dirs, {removed_files} files. Free space: {free_space_after_gb:.2f}GB")
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error during emergency cleanup: {e}")
            return False
