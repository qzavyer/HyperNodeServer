"""Real-time tail watcher for streaming log file processing."""

import asyncio
import aiofiles
from pathlib import Path
from typing import AsyncGenerator, Optional, Set
from datetime import datetime
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class RealtimeWatcher:
    """Real-time file tail watcher for immediate order processing."""
    
    def __init__(self, poll_interval_ms: int = 100):
        """Initialize realtime watcher.
        
        Args:
            poll_interval_ms: Polling interval in milliseconds for tail reading
        """
        self.logger = setup_logger(__name__)
        self.poll_interval = poll_interval_ms / 1000.0  # Convert to seconds
        self.running = False
        self._current_file: Optional[str] = None
        self._file_handle = None
        self._last_position = 0
        
    async def start_async(self) -> None:
        """Start the realtime watcher."""
        self.running = True
        self.logger.info("✅ RealtimeWatcher started")
        
    async def stop_async(self) -> None:
        """Stop the realtime watcher and cleanup resources."""
        self.running = False
        if self._file_handle:
            await self._file_handle.close()
            self._file_handle = None
        self.logger.info("🛑 RealtimeWatcher stopped")
        
    async def tail_file(self, file_path: str) -> AsyncGenerator[str, None]:
        """Stream new lines from file as they are written (like 'tail -f').
        
        Args:
            file_path: Path to the file to tail
            
        Yields:
            New lines as they are written to the file
        """
        path = Path(file_path)
        if not path.exists():
            self.logger.warning(f"File does not exist for tailing: {file_path}")
            return
            
        self.logger.info(f"🔄 Starting tail of file: {file_path}")
        
        try:
            # Open file and seek to end for real-time streaming
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                # Move to end of file to start reading only new content
                await f.seek(0, 2)  # 2 = SEEK_END
                current_size = await f.tell()
                self.logger.debug(f"Starting tail from position: {current_size}")
                
                lines_yielded = 0
                while self.running:
                    # Try to read new line
                    line = await f.readline()
                    
                    if line:
                        # Strip line ending but keep content
                        clean_line = line.rstrip('\n\r')
                        if clean_line:  # Skip empty lines
                            lines_yielded += 1
                            self.logger.debug(f"Tail yielded line {lines_yielded}: {clean_line[:100]}...")
                            yield clean_line
                    else:
                        # No new content, wait before polling again
                        await asyncio.sleep(self.poll_interval)
                        
        except Exception as e:
            self.logger.error(f"Error tailing file {file_path}: {e}")
            raise
            
    async def watch_current_file(self, current_file_path: str) -> AsyncGenerator[str, None]:
        """Watch the current active log file for new orders.
        
        Args:
            current_file_path: Path to the currently active log file
            
        Yields:
            New log lines as they are written
        """
        if not self.running:
            await self.start_async()
            
        self._current_file = current_file_path
        self.logger.info(f"👀 Watching current file: {current_file_path}")
        
        try:
            async for line in self.tail_file(current_file_path):
                yield line
                
        except Exception as e:
            self.logger.error(f"Error watching current file {current_file_path}: {e}")
            raise
    
    def get_stats(self) -> dict:
        """Get current watcher statistics."""
        return {
            "running": self.running,
            "current_file": self._current_file,
            "poll_interval_ms": self.poll_interval * 1000,
            "last_position": self._last_position
        }
