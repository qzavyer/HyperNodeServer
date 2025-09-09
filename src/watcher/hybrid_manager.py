"""Hybrid manager for coordinating legacy FileWatcher and new RealtimeWatcher."""

import asyncio
from typing import Set, Dict, Optional, List
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.storage.models import Order
from src.storage.order_manager import OrderManager
from src.watcher.file_watcher import FileWatcher
from src.watcher.realtime_watcher import RealtimeWatcher
from src.parser.log_parser import LogParser
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class HybridManager:
    """Manages both legacy FileWatcher and new RealtimeWatcher to avoid duplicates."""
    
    def __init__(
        self, 
        file_watcher: FileWatcher, 
        order_manager: OrderManager,
        dedup_window_seconds: int = 60
    ):
        """Initialize hybrid manager.
        
        Args:
            file_watcher: Existing legacy file watcher
            order_manager: Order manager for processing orders
            dedup_window_seconds: Time window for deduplication
        """
        self.logger = setup_logger(__name__)
        self.file_watcher = file_watcher
        self.order_manager = order_manager
        self.realtime_watcher = RealtimeWatcher()
        self.parser = LogParser()
        
        # Deduplication tracking
        self.processed_orders: Dict[str, datetime] = {}  # order_id -> timestamp
        self.dedup_window = timedelta(seconds=dedup_window_seconds)
        
        # Configuration
        self.realtime_enabled = True
        self.legacy_enabled = True
        self.running = False
        
        # Statistics
        self.stats = {
            "realtime_orders_processed": 0,
            "legacy_orders_processed": 0,
            "duplicate_orders_filtered": 0,
            "total_orders_processed": 0
        }
        
    async def start_async(self) -> None:
        """Start hybrid processing with both watchers."""
        self.running = True
        self.logger.info("🚀 Starting HybridManager with dual processing streams")
        
        # Start legacy file watcher
        if self.legacy_enabled:
            await self.file_watcher.start_async()
            self.logger.info("✅ Legacy FileWatcher started")
            
        # Start realtime watcher
        if self.realtime_enabled:
            await self.realtime_watcher.start_async()
            self.logger.info("✅ RealtimeWatcher started")
            
            # Start realtime processing task
            asyncio.create_task(self._realtime_processing_loop())
            
        self.logger.info("🎯 HybridManager fully operational")
        
    async def stop_async(self) -> None:
        """Stop both watchers and cleanup."""
        self.running = False
        self.logger.info("🛑 Stopping HybridManager")
        
        if self.legacy_enabled:
            await self.file_watcher.stop_async()
            
        if self.realtime_enabled:
            await self.realtime_watcher.stop_async()
            
        self.logger.info("✅ HybridManager stopped")
        
    async def _realtime_processing_loop(self) -> None:
        """Main loop for processing realtime file changes."""
        while self.running:
            try:
                # Get the current active file path
                current_file = self._get_current_active_file()
                if not current_file:
                    await asyncio.sleep(5)  # Wait before retry
                    continue
                    
                self.logger.info(f"🔄 Starting realtime processing of: {current_file}")
                
                # Process new lines from current file
                async for line in self.realtime_watcher.watch_current_file(current_file):
                    if not self.running:
                        break
                        
                    await self._process_realtime_line(line, "realtime")
                    
            except Exception as e:
                self.logger.error(f"Error in realtime processing loop: {e}")
                await asyncio.sleep(5)  # Wait before retry
                
    def _get_current_active_file(self) -> Optional[str]:
        """Get the path to the currently active log file."""
        try:
            # Use the same logic as FileWatcher to find current file
            base_path = Path(self.file_watcher.logs_path) / "node_order_statuses/hourly"
            
            # Look for current hour file pattern (like 20250909/8)
            # Use UTC time as logs are typically in UTC
            utc_now = datetime.now(timezone.utc)
            current_date = utc_now.strftime("%Y%m%d")
            current_hour = utc_now.hour
            
            date_dir = base_path / current_date
            self.logger.debug(f"Looking for date dir: {date_dir}")
            
            if date_dir.exists():
                current_file = date_dir / str(current_hour)
                self.logger.debug(f"Looking for current hour file: {current_file}")
                if current_file.exists():
                    self.logger.info(f"Found current active file: {current_file}")
                    return str(current_file)
                else:
                    self.logger.warning(f"Current hour file not found: {current_file}")
            else:
                self.logger.warning(f"Date directory not found: {date_dir}")
                    
            # Fallback: find the latest file
            self.logger.info("Falling back to latest file search")
            latest_file = self._find_latest_file(base_path)
            if latest_file:
                self.logger.info(f"Found latest file: {latest_file}")
            else:
                self.logger.error("No files found in fallback search")
            return latest_file
            
        except Exception as e:
            self.logger.error(f"Error finding current active file: {e}")
            return None
            
    def _find_latest_file(self, base_path: Path) -> Optional[str]:
        """Find the latest log file."""
        try:
            latest_time = datetime.min
            latest_file = None
            
            for date_dir in base_path.iterdir():
                if date_dir.is_dir() and date_dir.name.isdigit():
                    for hour_file in date_dir.iterdir():
                        if hour_file.is_file() and hour_file.name.isdigit():
                            file_time = hour_file.stat().st_mtime
                            file_datetime = datetime.fromtimestamp(file_time)
                            if file_datetime > latest_time:
                                latest_time = file_datetime
                                latest_file = str(hour_file)
                                
            return latest_file
            
        except Exception as e:
            self.logger.error(f"Error finding latest file: {e}")
            return None
            
    async def _process_realtime_line(self, line: str, source: str) -> None:
        """Process a single line from realtime stream."""
        try:
            # Parse the line to extract order
            order = self.parser._parse_line(line)
            if not order:
                return
                
            # Check for duplicates
            if self._is_duplicate_order(order, source):
                self.stats["duplicate_orders_filtered"] += 1
                return
                
            # Process the order
            await self.order_manager.update_order(order)
            
            # Update statistics
            if source == "realtime":
                self.stats["realtime_orders_processed"] += 1
            else:
                self.stats["legacy_orders_processed"] += 1
                
            self.stats["total_orders_processed"] += 1
            
            # Track for deduplication
            self.processed_orders[order.id] = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error processing realtime line: {e}")
            
    def _is_duplicate_order(self, order: Order, source: str) -> bool:
        """Check if order is a duplicate within the dedup window."""
        order_id = order.id
        now = datetime.now()
        
        # Check if we've seen this order recently
        if order_id in self.processed_orders:
            last_seen = self.processed_orders[order_id]
            if now - last_seen < self.dedup_window:
                self.logger.debug(f"Duplicate order filtered: {order_id} from {source}")
                return True
                
        # Cleanup old entries periodically
        if len(self.processed_orders) > 10000:  # Cleanup every 10k orders
            self._cleanup_old_entries(now)
            
        return False
        
    def _cleanup_old_entries(self, now: datetime) -> None:
        """Remove old entries from deduplication cache."""
        cutoff_time = now - self.dedup_window * 2  # Keep double the window
        old_keys = [
            order_id for order_id, timestamp in self.processed_orders.items()
            if timestamp < cutoff_time
        ]
        
        for key in old_keys:
            del self.processed_orders[key]
            
        if old_keys:
            self.logger.debug(f"Cleaned up {len(old_keys)} old dedup entries")
            
    def get_stats(self) -> dict:
        """Get processing statistics."""
        return {
            **self.stats,
            "running": self.running,
            "realtime_enabled": self.realtime_enabled,
            "legacy_enabled": self.legacy_enabled,
            "dedup_cache_size": len(self.processed_orders),
            "realtime_watcher_stats": self.realtime_watcher.get_stats(),
            "file_watcher_stats": {
                "is_running": self.file_watcher.is_running,
                "processing_status": self.file_watcher.get_processing_status()
            }
        }
