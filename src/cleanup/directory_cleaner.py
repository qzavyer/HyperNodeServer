"""
Module for cleaning directories with logs.
Integrates the functionality from clean.py into the application architecture.
"""

import os
import re
import shutil
import asyncio
from pathlib import Path
from typing import Tuple, Optional

from src.utils.logger import setup_logger


class DirectoryCleaner:
    """Class for cleaning directories with logs."""
    
    def __init__(self, base_dir: str = "/app/node_logs", hyperliquid_data_dir: str = "/app/hyperliquid_data", single_file_watcher=None):
        """Initialization of the directory cleaner.
        
        Args:
            base_dir: Base directory for cleanup
            single_file_watcher: Link to SingleFileTailWatcher for protection of the current file
        """
        self.base_dir = Path(base_dir).expanduser().resolve()
        self.hyperliquid_data_dir = Path(hyperliquid_data_dir).expanduser().resolve()
        # Directory with numeric files for cleanup
        self.target_cleanup_path = self.base_dir / "node_order_statuses" / "hourly"
        self.replica_path = self.base_dir / "replica_cmds"
        self.checkpoints_path = self.hyperliquid_data_dir / "evm_db_hub_slow" / "checkpoint"
        self.max_replica_dirs = 5  # Maximum number of replica_cmds directories to keep
        self.max_checkpoints_dirs = 10  # Maximum number of checkpoints directories to keep
        self.logger = setup_logger(__name__)
        self.single_file_watcher = single_file_watcher
        
        # Regular expression for finding directories with date format yyyyMMdd
        self.date_pattern = re.compile(r"^\d{8}$")
        
        # Cleanup settings
        self.cleanup_interval_hours = 1  # Cleanup every hour
        self.file_retention_hours = 1    # Files older than 1 hour are deleted
        
    async def cleanup_async(self) -> Tuple[int, int]:
        """Async cleanup of directories.
        
        Returns:
            Tuple[int, int]: (number of removed directories, number of removed files)
        """
        try:
            removed_files = 0
            
            removed_dirs, latest_directory = await self._cleanup_orders_async()

            if latest_directory:
                # Clean up old numeric files in the latest directory
                files_removed = await self._cleanup_numeric_files_async(latest_directory)
                removed_files += files_removed

            removed_dirs += await self._cleanup_replica_cmds_async()
            removed_dirs += await self._cleanup_checkpoints_async()

            self.logger.info(f"✅ Cleanup completed: removed {removed_dirs} directories, {removed_files} files")
            return removed_dirs, removed_files
            
        except Exception as e:
            self.logger.error(f"❌ Error cleaning directories: {e}")
            raise

    async def _cleanup_orders_async(self) -> Tuple[int, Optional[Path]]:
        """Async cleanup of the node_order_statuses directory.
    
        Returns:
            Tuple[int, Optional[Path]]: (number of removed directories, latest directory or None)
        """
        try:
            self.logger.info(f"🧹 Starting cleanup in: {self.target_cleanup_path}")
            
            if not self.target_cleanup_path.exists():
                self.logger.warning(f"Target cleanup path does not exist: {self.target_cleanup_path}")
                return 0, None
            
            # Find all directories with dates in target_cleanup_path
            date_directories = []
            for item in self.target_cleanup_path.iterdir():
                if item.is_dir() and self.date_pattern.match(item.name):
                    date_directories.append(item)
            
            if not date_directories:
                self.logger.info("No date directories found")
                return 0, None
            
            # Sort by name (format yyyyMMdd)
            date_directories.sort(key=lambda p: p.name, reverse=True)
            
            self.logger.info(f"Found {len(date_directories)} date directories in {self.target_cleanup_path}")
            
            # Keep the latest directory
            latest_directory = date_directories[0]
            directories_to_remove = date_directories[1:]
            
            self.logger.info(f"Keeping latest directory: {latest_directory.name}")
            
            removed_dirs = 0
            # Delete old directories
            for dir_path in directories_to_remove:
                self.logger.info(f"🗑️ Deleting old directory: {dir_path.name}")
                await self._remove_directory_async(dir_path)
                removed_dirs += 1

            return removed_dirs, latest_directory

        except Exception as e:
            self.logger.error(f"❌ Error cleaning directories: {e}")
            raise

    async def _cleanup_replica_cmds_async(self) -> int:
        """Async cleanup of the replica_cmds directory.
    
        Returns:
            int: Number of removed directories
        """
        try:
            self.logger.info(f"🧹 Starting cleanup in: {self.replica_path}")
            if not self.replica_path.exists():
                self.logger.warning(f"Target cleanup path does not exist: {self.replica_path}")
                return 0
            
            # Find all directories with dates in replica_path
            directories = []
            for item in self.replica_path.iterdir():
                if item.is_dir() and self.date_pattern.match(item.name):
                    directories.append(item)
            
            if not directories:
                self.logger.info("No date directories found")
                return 0
            
            # Sort by name
            directories.sort(key=lambda p: p.name, reverse=True)
            
            self.logger.info(f"Found {len(directories)} directories in {self.replica_path}")
            

            directories_to_remove = directories[self.max_replica_dirs:]
            removed_dirs = 0
            # Delete old directories
            for dir_path in directories_to_remove:
                self.logger.info(f"🗑️ Deleting old directory: {dir_path.name}")
                await self._remove_directory_async(dir_path)
                removed_dirs += 1

            return removed_dirs
        except Exception as e:
            self.logger.error(f"❌ Error cleaning directories: {e}")
            raise
    
    async def _cleanup_checkpoints_async(self) -> int:
        """Async cleanup of the checkpoints directory.
    
        Returns:
            int: Number of removed directories
        """
        try:
            self.logger.info(f"🧹 Starting cleanup in: {self.checkpoints_path}")
            if not self.checkpoints_path.exists():
                self.logger.warning(f"Target cleanup path does not exist: {self.checkpoints_path}")
                return 0
            
            # Find all directories with dates in checkpoints_path
            directories = []
            for item in self.checkpoints_path.iterdir():
                if item.is_dir() and self.date_pattern.match(item.name):
                    directories.append(item)
            
            if not directories:
                self.logger.info("No date directories found")
                return 0
            
            # Sort by name
            directories.sort(key=lambda p: p.name, reverse=True)
            
            self.logger.info(f"Found {len(directories)} directories in {self.checkpoints_path}")
            

            directories_to_remove = directories[self.max_checkpoints_dirs:]
            removed_dirs = 0
            # Delete old directories
            for dir_path in directories_to_remove:
                self.logger.info(f"🗑️ Deleting old directory: {dir_path.name}")
                await self._remove_directory_async(dir_path)
                removed_dirs += 1

            return removed_dirs
        except Exception as e:
            self.logger.error(f"❌ Error cleaning directories: {e}")
            raise
    
    async def _remove_directory_async(self, dir_path: Path) -> None:
        """Async remove directory."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.rmtree, str(dir_path))
        except OSError as e:
            self.logger.error(f"Error removing directory {dir_path}: {e}")
    
    async def _cleanup_numeric_files_async(self, dir_path: Path) -> int:
        """Cleanup numeric files in directory, keeping only the last 3 files.
        
        Args:
            dir_path: Path to date directory (e.g., /app/node_logs/node_order_statuses/hourly/20251009)
            
        Returns:
            Number of files removed
        """
        removed_files = 0
        
        try:
            # Find all numeric files in directory
            numeric_files = []
            for file_path in dir_path.iterdir():
                if file_path.is_file() and file_path.name.isdigit():
                    numeric_files.append(file_path)
            
            if not numeric_files:
                self.logger.debug(f"No numeric files found in {dir_path}")
                return 0
            
            # Sort by numeric name (descending = newest first)
            numeric_files.sort(key=lambda f: int(f.name), reverse=True)
            
            self.logger.info(f"Found {len(numeric_files)} numeric files in {dir_path.name}, keeping last 3")
            
            # Keep last 3, delete the rest
            files_to_delete = numeric_files[3:]
            
            for file_path in files_to_delete:
                try:
                    self.logger.info(f"🗑️ Deleting old file: {file_path.name}")
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, file_path.unlink)
                    removed_files += 1
                except OSError as e:
                    self.logger.warning(f"Failed to delete file {file_path}: {e}")
            
            if removed_files > 0:
                self.logger.info(f"✅ Deleted {removed_files} old files from {dir_path.name}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up numeric files in {dir_path}: {e}")
        
        return removed_files
    
    async def start_periodic_cleanup_async(self) -> None:
        """Start periodic cleanup every N hours."""
        self.logger.info(f"🔄 Starting periodic cleanup every {self.cleanup_interval_hours} hours")
        
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_hours * 3600)  # Convert hours to seconds
                await self.cleanup_async()
            except asyncio.CancelledError:
                self.logger.info("🛑 Periodic cleanup stopped")
                break
            except Exception as e:
                self.logger.error(f"❌ Error in periodic cleanup: {e}")
                # Continue working even with an error
                await asyncio.sleep(60)  # Wait 1 minute before trying again
    
    def get_cleanup_stats(self) -> dict:
        """Get cleanup statistics."""
        return {
            "base_directory": str(self.base_dir),
            "cleanup_interval_hours": self.cleanup_interval_hours,
            "file_retention_hours": self.file_retention_hours,
            "directory_exists": self.base_dir.exists(),
            "directory_size_mb": self._get_directory_size_mb() if self.base_dir.exists() else 0
        }
    
    def _get_directory_size_mb(self) -> float:
        """Get directory size in megabytes."""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(self.base_dir):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)
            return total_size / (1024 * 1024)  # Convert to MB
        except Exception:
            return 0.0
