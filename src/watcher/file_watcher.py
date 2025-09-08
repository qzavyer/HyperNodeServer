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
        logger.debug(f"File modified event: {event.src_path} (is_directory: {event.is_directory})")
        if not event.is_directory:
            # Проверяем что это файл лога (цифровые имена или .json)
            file_name = Path(event.src_path).name
            if file_name.isdigit() or file_name.endswith('.json'):
                logger.info(f"Log file modified, scheduling processing: {event.src_path}")
                # Запускаем обработку в фоне, не блокируя event loop
                asyncio.create_task(self.file_watcher._schedule_file_processing(Path(event.src_path)))
            else:
                logger.debug(f"Ignoring non-log file: {event.src_path} (name: {file_name})")
        else:
            logger.debug(f"Ignoring directory: {event.src_path}")
    
    def on_created(self, event):
        """Called when a new file is created."""
        logger.debug(f"File created event: {event.src_path} (is_directory: {event.is_directory})")
        if not event.is_directory:
            # Проверяем что это файл лога (цифровые имена или .json)
            file_name = Path(event.src_path).name
            if file_name.isdigit() or file_name.endswith('.json'):
                logger.info(f"Log file created, scheduling processing: {event.src_path}")
                # Запускаем обработку в фоне, не блокируя event loop
                asyncio.create_task(self.file_watcher._schedule_file_processing(Path(event.src_path)))
            else:
                logger.debug(f"Ignoring non-log file: {event.src_path} (name: {file_name})")
        else:
            logger.debug(f"Ignoring directory: {event.src_path}")


class FileWatcher:
    """Monitors log directories for file changes with background processing."""
    
    def __init__(self, order_manager: OrderManager):
        self.order_manager = order_manager
        self.logs_path = Path(settings.NODE_LOGS_PATH).expanduser()
        self.observer = Observer()
        self.handler = LogFileHandler(self)
        self.parser = LogParser(chunk_size=8192, batch_size=1000)
        self.is_running = False
        self.processing_files: set = set()  # Track files being processed
        self.pending_files: asyncio.Queue = asyncio.Queue()  # Queue for file processing
        
    async def start_async(self) -> None:
        """Starts file monitoring with background processing."""
        logger.info(f"Starting file watcher for {self.logs_path}")
        
        # Ensure logs directory exists
        self.logs_path.mkdir(parents=True, exist_ok=True)
        
        # Schedule initial scan of latest file
        scan_task = asyncio.create_task(self.scan_latest_file_async())
        logger.info("✅ Initial file scan task created")
        
        # Start background file processor
        processor_task = asyncio.create_task(self._background_file_processor())
        logger.info("✅ Background file processor task created")
        
        # Schedule periodic cleanup
        cleanup_task = asyncio.create_task(self._cleanup_loop_async())
        logger.info("✅ Cleanup loop task created")
        
        # Start periodic scanner for active files (to catch changes missed by watchdog)
        scanner_task = asyncio.create_task(self._periodic_scanner())
        logger.info("✅ Periodic scanner task created")
        
        # Start file system monitoring for node_order_statuses/hourly/
        hourly_path = self.logs_path / "node_order_statuses" / "hourly"
        if hourly_path.exists():
            self.observer.schedule(self.handler, str(hourly_path), recursive=True)
            logger.info(f"Monitoring directory: {hourly_path}")
        else:
            # Fallback to monitoring base directory if hourly doesn't exist yet
            self.observer.schedule(self.handler, str(self.logs_path), recursive=True)
            logger.info(f"Monitoring base directory (hourly not found): {self.logs_path}")
        
        self.observer.start()
        self.is_running = True
        
        logger.info("File watcher started successfully with background processing")
    
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
            logger.info(f"Starting initial scan of logs directory: {self.logs_path}")
            latest_file = self._find_latest_file()
            if latest_file:
                logger.info(f"Scanning latest file: {latest_file}")
                await self._schedule_file_processing(latest_file)
            else:
                logger.warning(f"No log files found for initial scan in {self.logs_path}")
                # Дополнительная диагностика
                try:
                    if self.logs_path.exists():
                        logger.info(f"Directory exists, contents: {list(self.logs_path.iterdir())}")
                        hourly_path = self.logs_path / "node_order_statuses" / "hourly"
                        if hourly_path.exists():
                            logger.info(f"Hourly directory exists, contents: {list(hourly_path.rglob('*'))}")
                        else:
                            logger.warning(f"Hourly directory does not exist: {hourly_path}")
                    else:
                        logger.warning(f"Logs directory does not exist: {self.logs_path}")
                except Exception as scan_ex:
                    logger.error(f"Error during directory scan: {scan_ex}")
        except Exception as e:
            logger.error(f"Error during initial file scan: {e}")
    
    async def _schedule_file_processing(self, file_path: Path) -> None:
        """Schedules file for background processing without blocking API."""
        # Проверяем, не обрабатывается ли уже файл
        if file_path in self.processing_files:
            logger.debug(f"File {file_path} is already scheduled for processing, skipping")
            return
        
        # Проверяем размер файла
        try:
            file_size = file_path.stat().st_size
            file_size_gb = file_size / (1024**3)
            
            if file_size_gb > settings.MAX_FILE_SIZE_GB:
                logger.warning(f"File {file_path} too large ({file_size_gb:.2f} GB), skipping")
                return
                
        except Exception as e:
            logger.error(f"Error checking file size for {file_path}: {e}")
            return
        
        # Добавляем файл в очередь для фоновой обработки
        await self.pending_files.put(file_path)
        logger.info(f"Scheduled {file_path} ({file_size_gb:.2f} GB) for background processing")
    
    async def _background_file_processor(self) -> None:
        """Background processor that handles files without blocking API."""
        logger.info("Background file processor started")
        
        # Добавляем счетчик для отладки
        timeout_count = 0
        
        while self.is_running:
            try:
                # Ждем файл для обработки (неблокирующе)
                try:
                    file_path = await asyncio.wait_for(
                        self.pending_files.get(), 
                        timeout=1.0
                    )
                    timeout_count = 0  # Сбрасываем счетчик если получили файл
                    logger.info(f"Background processor received file: {file_path}")
                    
                except asyncio.TimeoutError:
                    # Таймаут - проверяем, нужно ли продолжать работу
                    timeout_count += 1
                    if timeout_count % 30 == 0:  # Логируем каждые 30 секунд
                        logger.debug(f"Background processor waiting for files... (timeout count: {timeout_count})")
                        logger.debug(f"Queue size: {self.pending_files.qsize()}, Processing files: {len(self.processing_files)}")
                    continue
                
                # Обрабатываем файл в фоне
                await self._process_file_background(file_path)
                
            except Exception as e:
                logger.error(f"Error in background file processor: {e}")
                await asyncio.sleep(1)  # Пауза перед следующей попыткой
        
        logger.info("Background file processor stopped")
    
    async def _process_file_background(self, file_path: Path) -> None:
        """Processes a single log file in background without blocking API."""
        if file_path in self.processing_files:
            logger.debug(f"File {file_path} is already being processed, skipping")
            return
        
        self.processing_files.add(file_path)
        
        try:
            logger.info(f"Starting background processing of {file_path}")
            
            # Обрабатываем файл по частям с паузами между батчами
            total_orders = 0
            async for batch in self.parser.parse_file_async(str(file_path)):
                # Обновляем ордера батчами
                await self.order_manager.update_orders_batch_async(batch)
                total_orders += len(batch)
                
                # Пауза между батчами, чтобы не блокировать API
                await asyncio.sleep(0.1)
                
                # Логируем прогресс
                if total_orders % 10000 == 0:
                    logger.info(f"Processed {total_orders} orders from {file_path}")
            
            logger.info(f"Completed background processing: {total_orders} orders from {file_path}")
            
        except Exception as e:
            logger.error(f"Error processing file {file_path} in background: {e}")
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
        """Finds the most recent log file in node_order_statuses/hourly/ subdirectories."""
        try:
            # Ищем файлы в поддиректориях node_order_statuses/hourly/
            hourly_path = self.logs_path / "node_order_statuses" / "hourly"
            logger.info(f"Looking for files in: {hourly_path}")
            
            if not hourly_path.exists():
                logger.warning(f"Hourly directory not found: {hourly_path}")
                # Fallback: проверяем основную директорию
                base_log_files = list(self.logs_path.rglob("*"))
                base_log_files = [f for f in base_log_files if f.is_file() and (f.name.isdigit() or f.name.endswith('.json'))]
                if base_log_files:
                    logger.info(f"Found {len(base_log_files)} log files in base directory")
                    latest_file = max(base_log_files, key=lambda f: f.stat().st_mtime)
                    logger.info(f"Using latest file from base directory: {latest_file}")
                    return latest_file
                else:
                    logger.warning(f"No log files found in base directory either: {self.logs_path}")
                return None
            
            # Ищем файлы логов в поддиректориях (цифровые имена или .json)
            all_files = list(hourly_path.rglob("*"))
            log_files = [f for f in all_files if f.is_file() and (f.name.isdigit() or f.name.endswith('.json'))]
            logger.info(f"Found {len(log_files)} log files in hourly directory (numeric names or .json)")
            
            if not log_files:
                logger.warning(f"No log files found in {hourly_path}")
                # Показываем что есть в директории
                logger.info(f"All files in hourly directory: {[str(f) for f in all_files[:10]]}")  # Показываем первые 10
                return None
            
            # Sort by modification time, newest first
            latest_file = max(log_files, key=lambda f: f.stat().st_mtime)
            logger.info(f"Found latest file: {latest_file} (size: {latest_file.stat().st_size} bytes)")
            return latest_file
        except Exception as e:
            logger.error(f"Error finding latest file: {e}")
            return None
    
    async def _periodic_scanner(self) -> None:
        """Periodically scans for file changes that watchdog might miss."""
        logger.info("Periodic scanner started")
        last_scan_sizes = {}  # file_path -> size
        
        while self.is_running:
            try:
                await asyncio.sleep(5)  # Scan every 30 seconds
                
                # Find current hour file
                current_file = self._find_latest_file()
                if current_file and current_file.exists():
                    current_size = current_file.stat().st_size
                    
                    # Check if file has grown since last scan
                    if str(current_file) not in last_scan_sizes:
                        last_scan_sizes[str(current_file)] = current_size
                        logger.info(f"Periodic scanner: New file detected {current_file} ({current_size} bytes)")
                        await self._schedule_file_processing(current_file)
                    elif current_size > last_scan_sizes[str(current_file)]:
                        last_scan_sizes[str(current_file)] = current_size
                        logger.info(f"Periodic scanner: File grew {current_file} ({current_size} bytes)")
                        await self._schedule_file_processing(current_file)
                    else:
                        logger.debug(f"Periodic scanner: No changes in {current_file}")
                        
            except Exception as e:
                logger.error(f"Error in periodic scanner: {e}")
                await asyncio.sleep(30)  # Wait before retrying
    
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
    
    def get_processing_status(self) -> dict:
        """Returns current processing status for monitoring."""
        return {
            "is_running": self.is_running,
            "processing_files_count": len(self.processing_files),
            "pending_files_count": self.pending_files.qsize(),
            "processing_files": list(str(f) for f in self.processing_files)
        }
