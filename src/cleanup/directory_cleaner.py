"""
Module for cleaning directories with logs.
Integrates the functionality from clean.py into the application architecture.
"""

import os
import re
import shutil
import asyncio
import json
from pathlib import Path
from typing import Tuple, Optional, Dict, List, Any

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
        self.periodic_abci_path = self.base_dir / "periodic_abci_states"
        self.evm_block_receipts_path = self.base_dir / "evm_block_and_receipts" / "hourly"
        self.validator_connections_path = self.base_dir / "node_logs" / "validator_connections" / "hourly"
        self.node_fast_block_times_path = self.base_dir / "node_fast_block_times"
        self.checkpoints_path = self.hyperliquid_data_dir / "evm_db_hub_slow" / "checkpoint"
        self.max_replica_dirs = 1  # Maximum number of replica_cmds directories to keep
        self.max_checkpoints_dirs = 5  # Maximum number of checkpoints directories to keep
        self.logger = setup_logger(__name__)
        self.single_file_watcher = single_file_watcher
        
        # Regular expression for finding directories with date format yyyyMMdd
        self.date_pattern = re.compile(r"^\d{8}$")
        # Regular expression for ISO 8601 format (2025-10-10T23:11:09Z or 2025-10-10T23-11-09Z for Windows)
        self.iso_datetime_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}[:\-]\d{2}[:\-]\d{2}Z$")
        # Regular expression for numeric checkpoint directories (any length numeric ID)
        self.numeric_pattern = re.compile(r"^\d+$")
        # Regular expression for temporary files with date format YYYY-MM-DD_HH:MM:SS.*
        self.temp_file_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{2}:\d{2}:\d{2}\.")
        
        # Cleanup settings
        self.cleanup_interval_hours = 1  # Cleanup every hour
        self.file_retention_hours = 1    # Files older than 1 hour are deleted
        
        # Configuration
        self.config = None
        self.config_path = None
        
    async def cleanup_async(self, dry_run: bool = False) -> Tuple[int, int]:
        """Async cleanup of directories.
        
        Args:
            dry_run: If True, simulate operations without actual deletion
            
        Returns:
            Tuple[int, int]: (number of removed directories, number of removed files)
        """
        try:
            if dry_run:
                self.logger.info("🔍 DRY-RUN MODE: Simulating cleanup operations without actual deletion")
            
            removed_files = 0
            
            removed_dirs, latest_directory = await self._cleanup_orders_async(dry_run)

            if latest_directory:
                # Clean up old numeric files in the latest directory
                files_removed = await self._cleanup_numeric_files_async(latest_directory, dry_run)
                removed_files += files_removed

            removed_dirs += await self._cleanup_replica_cmds_async(dry_run)
            removed_dirs += await self._cleanup_periodic_abci_async(dry_run)
            removed_dirs += await self._cleanup_evm_block_receipts_async(dry_run)
            removed_dirs += await self._cleanup_validator_connections_async(dry_run)
            removed_dirs += await self._cleanup_node_fast_block_times_async(dry_run)
            removed_dirs += await self._cleanup_checkpoints_async(dry_run)
            
            # New cleanup methods from spec
            removed_dirs += await self._cleanup_temp_dirs_async(dry_run)
            removed_dirs += await self._cleanup_crit_msg_stats_async(dry_run)
            removed_dirs += await self._cleanup_dhs_data_async(dry_run)
            removed_dirs += await self._cleanup_latency_buckets_async(dry_run)
            removed_dirs += await self._cleanup_node_logs_async(dry_run)
            removed_dirs += await self._cleanup_periodic_data_async(dry_run)

            self.logger.info(f"✅ Cleanup completed: removed {removed_dirs} directories, {removed_files} files")
            return removed_dirs, removed_files
            
        except Exception as e:
            self.logger.error(f"❌ Error cleaning directories: {e}")
            raise

    async def _cleanup_orders_async(self, dry_run: bool = False) -> Tuple[int, Optional[Path]]:
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
                if dry_run:
                    self.logger.info(f"🔍 [DRY-RUN] Would delete old directory: {dir_path.name}")
                else:
                    self.logger.info(f"🗑️ Deleting old directory: {dir_path.name}")
                    await self._remove_directory_async(dir_path)
                removed_dirs += 1

            return removed_dirs, latest_directory

        except Exception as e:
            self.logger.error(f"❌ Error cleaning directories: {e}")
            raise

    async def _cleanup_replica_cmds_async(self, dry_run: bool = False) -> int:
        """Async cleanup of the replica_cmds directory.
        Removes directories with ISO datetime format (2025-10-10T23:11:09Z).
    
        Returns:
            int: Number of removed directories
        """
        try:
            self.logger.info(f"🧹 Starting cleanup in: {self.replica_path}")
            if not self.replica_path.exists():
                self.logger.warning(f"Target cleanup path does not exist: {self.replica_path}")
                return 0
            
            # Find all directories with ISO datetime format in replica_path
            directories = []
            for item in self.replica_path.iterdir():
                if item.is_dir() and self.iso_datetime_pattern.match(item.name):
                    directories.append(item)
            
            if not directories:
                self.logger.info("No ISO datetime directories found in replica_cmds")
                return 0
            
            # Sort by name (ISO format sorts correctly alphabetically)
            directories.sort(key=lambda p: p.name, reverse=True)
            
            self.logger.info(f"Found {len(directories)} directories in {self.replica_path}")
            
            # Keep last max_replica_dirs directories
            directories_to_remove = directories[self.max_replica_dirs:]
            removed_dirs = 0
            
            # Delete old directories
            for dir_path in directories_to_remove:
                self._log_dry_run_operation("delete old directory", dir_path.name, dry_run)
                if not dry_run:
                    await self._remove_directory_async(dir_path)
                removed_dirs += 1

            return removed_dirs
        except Exception as e:
            self.logger.error(f"❌ Error cleaning replica_cmds directories: {e}")
            raise
    
    async def _cleanup_periodic_abci_async(self, dry_run: bool = False) -> int:
        """Async cleanup of the periodic_abci_states directory.
        Keeps only the latest directory (in yyyyMMdd format).
    
        Returns:
            int: Number of removed directories
        """
        try:
            self.logger.info(f"🧹 Starting cleanup in: {self.periodic_abci_path}")
            if not self.periodic_abci_path.exists():
                self.logger.warning(f"Target cleanup path does not exist: {self.periodic_abci_path}")
                return 0
            
            # Find all directories with date format in periodic_abci_path
            directories = []
            for item in self.periodic_abci_path.iterdir():
                if item.is_dir() and self.date_pattern.match(item.name):
                    directories.append(item)
            
            if not directories:
                self.logger.info("No date directories found in periodic_abci_states")
                return 0
            
            # Sort by name (yyyyMMdd format)
            directories.sort(key=lambda p: p.name, reverse=True)
            
            self.logger.info(f"Found {len(directories)} directories in {self.periodic_abci_path}")
            
            # Keep only the latest directory, delete all others
            directories_to_remove = directories[1:]
            removed_dirs = 0
            
            # Delete old directories
            for dir_path in directories_to_remove:
                self.logger.info(f"🗑️ Deleting old directory: {dir_path.name}")
                await self._remove_directory_async(dir_path)
                removed_dirs += 1

            return removed_dirs
        except Exception as e:
            self.logger.error(f"❌ Error cleaning periodic_abci_states directories: {e}")
            raise
    
    async def _cleanup_evm_block_receipts_async(self, dry_run: bool = False) -> int:
        """Async cleanup of the evm_block_and_receipts/hourly directory.
        Keeps only the latest directory (in yyyyMMdd format).
    
        Returns:
            int: Number of removed directories
        """
        try:
            self.logger.info(f"🧹 Starting cleanup in: {self.evm_block_receipts_path}")
            if not self.evm_block_receipts_path.exists():
                self.logger.warning(f"Target cleanup path does not exist: {self.evm_block_receipts_path}")
                return 0
            
            # Find all directories with date format in evm_block_receipts_path
            directories = []
            for item in self.evm_block_receipts_path.iterdir():
                if item.is_dir() and self.date_pattern.match(item.name):
                    directories.append(item)
            
            if not directories:
                self.logger.info("No date directories found in evm_block_and_receipts/hourly")
                return 0
            
            # Sort by name (yyyyMMdd format)
            directories.sort(key=lambda p: p.name, reverse=True)
            
            self.logger.info(f"Found {len(directories)} directories in {self.evm_block_receipts_path}")
            
            # Keep only the latest directory, delete all others
            directories_to_remove = directories[1:]
            removed_dirs = 0
            
            # Delete old directories
            for dir_path in directories_to_remove:
                self.logger.info(f"🗑️ Deleting old directory: {dir_path.name}")
                await self._remove_directory_async(dir_path)
                removed_dirs += 1

            return removed_dirs
        except Exception as e:
            self.logger.error(f"❌ Error cleaning evm_block_and_receipts directories: {e}")
            raise
    
    async def _cleanup_validator_connections_async(self, dry_run: bool = False) -> int:
        """Async cleanup of the validator_connections directory.
        Keeps only the latest directory (in yyyyMMdd format).
    
        Returns:
            int: Number of removed directories
        """
        try:
            self.logger.info(f"🧹 Starting cleanup in: {self.validator_connections_path}")
            if not self.validator_connections_path.exists():
                self.logger.warning(f"Target cleanup path does not exist: {self.validator_connections_path}")
                return 0
            
            # Find all directories with date format in validator_connections_path
            directories = []
            for item in self.validator_connections_path.iterdir():
                if item.is_dir() and self.date_pattern.match(item.name):
                    directories.append(item)
            
            if not directories:
                self.logger.info("No date directories found in validator_connections")
                return 0
            
            # Sort by name (yyyyMMdd format)
            directories.sort(key=lambda p: p.name, reverse=True)

            self.logger.info(f"Found {len(directories)} directories in {self.validator_connections_path}")
            
            # Keep only the latest directory, delete all others
            directories_to_remove = directories[1:]
            removed_dirs = 0
            
            # Delete old directories
            for dir_path in directories_to_remove:
                self.logger.info(f"🗑️ Deleting old directory: {dir_path.name}")
                await self._remove_directory_async(dir_path)
                removed_dirs += 1

            return removed_dirs
        except Exception as e:
            self.logger.error(f"❌ Error cleaning validator_connections directories: {e}")
            raise

    async def _cleanup_node_fast_block_times_async(self, dry_run: bool = False) -> int:
        """Async cleanup of the node_fast_block_times directory.
        Keeps only the latest directory (in yyyyMMdd format).
    
        Returns:
            int: Number of removed directories
        """
        try:
            self.logger.info(f"🧹 Starting cleanup in: {self.node_fast_block_times_path}")
            if not self.node_fast_block_times_path.exists():
                self.logger.warning(f"Target cleanup path does not exist: {self.node_fast_block_times_path}")
                return 0
            
            # Find all directories with date format in node_fast_block_times_path
            directories = []
            for item in self.node_fast_block_times_path.iterdir():
                if item.is_dir() and self.date_pattern.match(item.name):
                    directories.append(item)
            
            if not directories:
                self.logger.info("No date directories found in node_fast_block_times")
                return 0
            
            # Sort by name (yyyyMMdd format)
            directories.sort(key=lambda p: p.name, reverse=True)
            
            self.logger.info(f"Found {len(directories)} directories in {self.node_fast_block_times_path}")
            
            # Keep only the latest directory, delete all others
            directories_to_remove = directories[1:]
            removed_dirs = 0
            
            # Delete old directories
            for dir_path in directories_to_remove:
                self.logger.info(f"🗑️ Deleting old directory: {dir_path.name}")
                await self._remove_directory_async(dir_path)
                removed_dirs += 1

            return removed_dirs
        except Exception as e:
            self.logger.error(f"❌ Error cleaning node_fast_block_times directories: {e}")
            raise
    
    async def _cleanup_checkpoints_async(self, dry_run: bool = False) -> int:
        """Async cleanup of the checkpoints directory.
        Keeps last N checkpoint directories (numeric IDs like 768860000).
    
        Returns:
            int: Number of removed directories
        """
        try:
            self.logger.info(f"🧹 Starting cleanup in: {self.checkpoints_path}")
            if not self.checkpoints_path.exists():
                self.logger.warning(f"Target cleanup path does not exist: {self.checkpoints_path}")
                return 0
            
            # Find all directories with numeric names in checkpoints_path
            directories = []
            for item in self.checkpoints_path.iterdir():
                if item.is_dir() and self.numeric_pattern.match(item.name):
                    directories.append(item)
            
            if not directories:
                self.logger.info("No numeric checkpoint directories found")
                return 0
            
            # Sort by numeric value (not string) - newest checkpoints have higher numbers
            directories.sort(key=lambda p: int(p.name), reverse=True)
            
            self.logger.info(f"Found {len(directories)} directories in {self.checkpoints_path}")
            
            # Keep last max_checkpoints_dirs directories
            directories_to_remove = directories[self.max_checkpoints_dirs:]
            removed_dirs = 0
            
            # Delete old directories
            for dir_path in directories_to_remove:
                self.logger.info(f"🗑️ Deleting old directory: {dir_path.name}")
                await self._remove_directory_async(dir_path)
                removed_dirs += 1

            return removed_dirs
        except Exception as e:
            self.logger.error(f"❌ Error cleaning checkpoints directories: {e}")
            raise
    
    async def _remove_directory_async(self, dir_path: Path) -> None:
        """Async remove directory."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, shutil.rmtree, str(dir_path))
        except OSError as e:
            self.logger.error(f"Error removing directory {dir_path}: {e}")
    
    async def _cleanup_numeric_files_async(self, dir_path: Path, dry_run: bool = False) -> int:
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
                    if dry_run:
                        self.logger.info(f"🔍 [DRY-RUN] Would delete old file: {file_path.name}")
                    else:
                        self.logger.info(f"🗑️ Deleting old file: {file_path.name}")
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, file_path.unlink)
                    removed_files += 1
                except OSError as e:
                    self.logger.warning(f"Failed to delete file {file_path}: {e}")
            
            if removed_files > 0:
                if dry_run:
                    self.logger.info(f"🔍 [DRY-RUN] Would delete {removed_files} old files from {dir_path.name}")
                else:
                    self.logger.info(f"✅ Deleted {removed_files} old files from {dir_path.name}")
            
        except Exception as e:
            self.logger.error(f"Error cleaning up numeric files in {dir_path}: {e}")
        
        return removed_files
    
    def _log_dry_run_operation(self, operation: str, target: str, dry_run: bool = False) -> None:
        """Log operation with dry-run prefix if in dry-run mode.
        
        Args:
            operation: Type of operation (delete, remove, etc.)
            target: Target file/directory name
            dry_run: Whether in dry-run mode
        """
        if dry_run:
            self.logger.info(f"🔍 [DRY-RUN] Would {operation}: {target}")
        else:
            self.logger.info(f"🗑️ {operation.capitalize()}: {target}")
    
    def get_cleanup_report(self, dry_run: bool = True) -> Dict[str, Any]:
        """Generate a detailed report of what would be cleaned up.
        
        Args:
            dry_run: If True, generate report without actual cleanup
            
        Returns:
            Dictionary with cleanup report
        """
        report = {
            "timestamp": asyncio.get_event_loop().time(),
            "dry_run": dry_run,
            "summary": {
                "total_directories_to_remove": 0,
                "total_files_to_remove": 0,
                "estimated_space_to_free_mb": 0.0
            },
            "categories": {}
        }
        
        try:
            # This would be implemented to scan directories and generate report
            # For now, return basic structure
            self.logger.info("📊 Generating cleanup report...")
            
            if dry_run:
                self.logger.info("🔍 Report mode: No actual cleanup will be performed")
            else:
                self.logger.info("⚠️ Report mode: Actual cleanup will be performed")
            
            report["summary"]["status"] = "report_generated"
            report["summary"]["message"] = "Cleanup report generated successfully"
            
        except Exception as e:
            self.logger.error(f"❌ Error generating cleanup report: {e}")
            report["summary"]["status"] = "error"
            report["summary"]["message"] = str(e)
        
        return report
    
    def estimate_space_to_free(self, path: Path) -> float:
        """Estimate space that would be freed by cleaning a path.
        
        Args:
            path: Path to analyze
            
        Returns:
            float: Estimated space in MB
        """
        try:
            if not path.exists():
                return 0.0
            
            total_size = 0
            if path.is_file():
                total_size = path.stat().st_size
            else:
                for item in path.rglob('*'):
                    if item.is_file():
                        try:
                            total_size += item.stat().st_size
                        except OSError:
                            # Skip files we can't access
                            continue
            
            return total_size / (1024 * 1024)  # Convert to MB
            
        except Exception as e:
            self.logger.warning(f"Could not estimate size for {path}: {e}")
            return 0.0
    
    async def _cleanup_temp_dirs_async(self, dry_run: bool = False) -> int:
        """Async cleanup of temporary directories.
        Removes files older than 2 days based on date in filename.
        
        Returns:
            int: Number of removed files
        """
        removed_files = 0
        
        try:
            # Temporary directories to clean
            temp_paths = [
                "/home/hl/hl/tmp/fu_write_string_to_file_tmp/",
                "/home/hl/hl/tmp/shell_rs_out/"
            ]
            
            for temp_path in temp_paths:
                self.logger.info(f"🧹 Starting cleanup in: {temp_path}")
                
                temp_dir = Path(temp_path)
                if not temp_dir.exists():
                    self.logger.warning(f"Temporary directory does not exist: {temp_path}")
                    continue
                
                # Find all files with date pattern in filename
                temp_files = []
                for file_path in temp_dir.iterdir():
                    if file_path.is_file() and self.temp_file_pattern.match(file_path.name):
                        temp_files.append(file_path)
                
                if not temp_files:
                    self.logger.info(f"No temporary files found in {temp_path}")
                    continue
                
                # Parse dates from filenames and filter by retention
                current_time = asyncio.get_event_loop().time()
                retention_seconds = 2 * 24 * 3600  # 2 days in seconds
                
                files_to_remove = []
                for file_path in temp_files:
                    try:
                        # Extract date from filename (YYYY-MM-DD_HH:MM:SS)
                        filename = file_path.name
                        date_part = filename.split('_')[0] + '_' + filename.split('_')[1].split('.')[0]
                        
                        # Parse date string
                        from datetime import datetime
                        file_date = datetime.strptime(date_part, "%Y-%m-%d_%H:%M:%S")
                        file_timestamp = file_date.timestamp()
                        
                        # Check if file is older than retention period
                        if current_time - file_timestamp > retention_seconds:
                            files_to_remove.append(file_path)
                            
                    except (ValueError, IndexError) as e:
                        self.logger.warning(f"Could not parse date from filename {file_path.name}: {e}")
                        continue
                
                # Remove old files
                for file_path in files_to_remove:
                    try:
                        self._log_dry_run_operation("delete old temporary file", file_path.name, dry_run)
                        if not dry_run:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(None, file_path.unlink)
                        removed_files += 1
                    except OSError as e:
                        self.logger.warning(f"Failed to delete file {file_path}: {e}")
                
                if files_to_remove:
                    self.logger.info(f"✅ Cleaned {len(files_to_remove)} old files from {temp_path}")
            
            return removed_files
            
        except Exception as e:
            self.logger.error(f"❌ Error cleaning temporary directories: {e}")
            raise
    
    async def _cleanup_crit_msg_stats_async(self, dry_run: bool = False) -> int:
        """Async cleanup of critical message statistics.
        Keeps last 30 files in each directory.
        
        Returns:
            int: Number of removed files
        """
        removed_files = 0
        
        try:
            # Critical message statistics directories
            crit_msg_paths = [
                "/home/hl/hl/data/crit_msg_stats/hl-node/",
                "/home/hl/hl/data/crit_msg_stats/hl-visor/"
            ]
            
            for crit_msg_path in crit_msg_paths:
                self.logger.info(f"🧹 Starting cleanup in: {crit_msg_path}")
                
                crit_dir = Path(crit_msg_path)
                if not crit_dir.exists():
                    self.logger.warning(f"Critical message stats directory does not exist: {crit_msg_path}")
                    continue
                
                # Find all files with date pattern (yyyyMMdd)
                date_files = []
                for file_path in crit_dir.iterdir():
                    if file_path.is_file() and self.date_pattern.match(file_path.name):
                        date_files.append(file_path)
                
                if not date_files:
                    self.logger.info(f"No date files found in {crit_msg_path}")
                    continue
                
                # Sort by filename (date format sorts correctly)
                date_files.sort(key=lambda p: p.name, reverse=True)
                
                self.logger.info(f"Found {len(date_files)} files in {crit_msg_path}, keeping last 30")
                
                # Keep last 30 files, remove the rest
                files_to_remove = date_files[30:]
                
                for file_path in files_to_remove:
                    try:
                        self._log_dry_run_operation("delete old stats file", file_path.name, dry_run)
                        if not dry_run:
                            loop = asyncio.get_event_loop()
                            await loop.run_in_executor(None, file_path.unlink)
                        removed_files += 1
                    except OSError as e:
                        self.logger.warning(f"Failed to delete file {file_path}: {e}")
                
                if files_to_remove:
                    self.logger.info(f"✅ Cleaned {len(files_to_remove)} old files from {crit_msg_path}")
            
            return removed_files
            
        except Exception as e:
            self.logger.error(f"❌ Error cleaning critical message statistics: {e}")
            raise
    
    async def _cleanup_dhs_data_async(self, dry_run: bool = False) -> int:
        """Async cleanup of DHS data directories.
        Keeps last 10 files by creation time in each directory.
        
        Returns:
            int: Number of removed files
        """
        removed_files = 0
        
        try:
            # DHS data directories
            dhs_paths = [
                "/home/hl/hl/data/dhs/EvmBlockNumbers/hourly/",
                "/home/hl/hl/data/dhs/EvmBlocks/hourly/",
                "/home/hl/hl/data/dhs/EvmTxs/hourly/",
                "/home/hl/hl/data/evm_block_and_receipts/hourly/"
            ]
            
            for dhs_path in dhs_paths:
                self.logger.info(f"🧹 Starting cleanup in: {dhs_path}")
                
                dhs_dir = Path(dhs_path)
                if not dhs_dir.exists():
                    self.logger.warning(f"DHS data directory does not exist: {dhs_path}")
                    continue
                
                # Find all files in directory
                all_files = []
                for file_path in dhs_dir.iterdir():
                    if file_path.is_file():
                        all_files.append(file_path)
                
                if not all_files:
                    self.logger.info(f"No files found in {dhs_path}")
                    continue
                
                # Sort by creation time (newest first)
                all_files.sort(key=lambda p: p.stat().st_ctime, reverse=True)
                
                self.logger.info(f"Found {len(all_files)} files in {dhs_path}, keeping last 10")
                
                # Keep last 10 files, remove the rest
                files_to_remove = all_files[10:]
                
                for file_path in files_to_remove:
                    try:
                        self.logger.info(f"🗑️ Deleting old DHS file: {file_path.name}")
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, file_path.unlink)
                        removed_files += 1
                    except OSError as e:
                        self.logger.warning(f"Failed to delete file {file_path}: {e}")
                
                if files_to_remove:
                    self.logger.info(f"✅ Cleaned {len(files_to_remove)} old files from {dhs_path}")
            
            return removed_files
            
        except Exception as e:
            self.logger.error(f"❌ Error cleaning DHS data: {e}")
            raise
    
    async def _cleanup_latency_buckets_async(self, dry_run: bool = False) -> int:
        """Async cleanup of latency buckets directories.
        Keeps latest directory in each hourly subdirectory.
        
        Returns:
            int: Number of removed directories
        """
        removed_dirs = 0
        
        try:
            # Latency buckets base paths
            latency_base_paths = [
                "/home/hl/hl/data/latency_buckets/bucket_guard/",
                "/home/hl/hl/data/latency_buckets/"
            ]
            
            for base_path in latency_base_paths:
                self.logger.info(f"🧹 Starting cleanup in: {base_path}")
                
                base_dir = Path(base_path)
                if not base_dir.exists():
                    self.logger.warning(f"Latency buckets base directory does not exist: {base_path}")
                    continue
                
                # Find all subdirectories
                subdirs = []
                for item in base_dir.iterdir():
                    if item.is_dir():
                        subdirs.append(item)
                
                if not subdirs:
                    self.logger.info(f"No subdirectories found in {base_path}")
                    continue
                
                # Process each subdirectory
                for subdir in subdirs:
                    hourly_path = subdir / "hourly"
                    if not hourly_path.exists():
                        self.logger.debug(f"No hourly directory in {subdir.name}")
                        continue
                    
                    # Find all date directories in hourly subdirectory
                    date_dirs = []
                    for item in hourly_path.iterdir():
                        if item.is_dir() and self.date_pattern.match(item.name):
                            date_dirs.append(item)
                    
                    if not date_dirs:
                        self.logger.debug(f"No date directories in {hourly_path}")
                        continue
                    
                    # Sort by name (date format sorts correctly)
                    date_dirs.sort(key=lambda p: p.name, reverse=True)
                    
                    self.logger.info(f"Found {len(date_dirs)} date directories in {hourly_path}, keeping latest")
                    
                    # Keep latest directory, remove the rest
                    dirs_to_remove = date_dirs[1:]
                    
                    for dir_path in dirs_to_remove:
                        try:
                            self.logger.info(f"🗑️ Deleting old latency bucket directory: {dir_path.name}")
                            await self._remove_directory_async(dir_path)
                            removed_dirs += 1
                        except OSError as e:
                            self.logger.warning(f"Failed to delete directory {dir_path}: {e}")
                    
                    if dirs_to_remove:
                        self.logger.info(f"✅ Cleaned {len(dirs_to_remove)} old directories from {hourly_path}")
            
            return removed_dirs
            
        except Exception as e:
            self.logger.error(f"❌ Error cleaning latency buckets: {e}")
            raise
    
    async def _cleanup_node_logs_async(self, dry_run: bool = False) -> int:
        """Async cleanup of node logs directories.
        Handles different types of node log cleanup rules.
        
        Returns:
            int: Number of removed files/directories
        """
        removed_items = 0
        
        try:
            # Node logs cleanup rules
            node_log_rules = [
                {
                    "path": "/home/hl/hl/data/log/*/*/",
                    "type": "keep_last_files",
                    "count": 3,
                    "pattern": "yyyyMMdd"
                },
                {
                    "path": "/home/hl/hl/data/node_fast_block_times/",
                    "type": "keep_last_files", 
                    "count": 3,
                    "pattern": "yyyyMMdd"
                },
                {
                    "path": "/home/hl/hl/data/node_logs/*/hourly",
                    "type": "keep_last_by_creation_time",
                    "count": 10
                },
                {
                    "path": "/home/hl/hl/data/node_slow_block_times/",
                    "type": "keep_last_by_creation_time",
                    "count": 3
                }
            ]
            
            for rule in node_log_rules:
                self.logger.info(f"🧹 Starting cleanup for rule: {rule['path']}")
                
                # Handle wildcard paths
                if "*" in rule["path"]:
                    # For wildcard paths, we need to find matching directories
                    base_path = rule["path"].split("*")[0]
                    base_dir = Path(base_path)
                    
                    if not base_dir.exists():
                        self.logger.warning(f"Base directory does not exist: {base_path}")
                        continue
                    
                    # Find matching subdirectories
                    subdirs = []
                    for item in base_dir.iterdir():
                        if item.is_dir():
                            subdirs.append(item)
                    
                    # Process each subdirectory
                    for subdir in subdirs:
                        if rule["type"] == "keep_last_files":
                            removed_items += await self._cleanup_node_log_files_async(
                                subdir, rule["count"], rule["pattern"]
                            )
                        elif rule["type"] == "keep_last_by_creation_time":
                            removed_items += await self._cleanup_node_log_by_time_async(
                                subdir, rule["count"]
                            )
                else:
                    # Direct path
                    target_dir = Path(rule["path"])
                    if not target_dir.exists():
                        self.logger.warning(f"Target directory does not exist: {rule['path']}")
                        continue
                    
                    if rule["type"] == "keep_last_files":
                        removed_items += await self._cleanup_node_log_files_async(
                            target_dir, rule["count"], rule["pattern"]
                        )
                    elif rule["type"] == "keep_last_by_creation_time":
                        removed_items += await self._cleanup_node_log_by_time_async(
                            target_dir, rule["count"]
                        )
            
            return removed_items
            
        except Exception as e:
            self.logger.error(f"❌ Error cleaning node logs: {e}")
            raise
    
    async def _cleanup_node_log_files_async(self, target_dir: Path, keep_count: int, pattern: str) -> int:
        """Cleanup node log files by pattern.
        
        Args:
            target_dir: Target directory to clean
            keep_count: Number of files to keep
            pattern: File pattern to match
            
        Returns:
            int: Number of removed files
        """
        removed_files = 0
        
        try:
            # Find files matching pattern
            pattern_files = []
            for file_path in target_dir.iterdir():
                if file_path.is_file() and self.date_pattern.match(file_path.name):
                    pattern_files.append(file_path)
            
            if not pattern_files:
                return 0
            
            # Sort by filename (date format sorts correctly)
            pattern_files.sort(key=lambda p: p.name, reverse=True)
            
            self.logger.info(f"Found {len(pattern_files)} files in {target_dir}, keeping last {keep_count}")
            
            # Keep last N files, remove the rest
            files_to_remove = pattern_files[keep_count:]
            
            for file_path in files_to_remove:
                try:
                    self.logger.info(f"🗑️ Deleting old node log file: {file_path.name}")
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, file_path.unlink)
                    removed_files += 1
                except OSError as e:
                    self.logger.warning(f"Failed to delete file {file_path}: {e}")
            
            return removed_files
            
        except Exception as e:
            self.logger.error(f"❌ Error cleaning node log files in {target_dir}: {e}")
            return 0
    
    async def _cleanup_node_log_by_time_async(self, target_dir: Path, keep_count: int) -> int:
        """Cleanup node log files by creation time.
        
        Args:
            target_dir: Target directory to clean
            keep_count: Number of files to keep
            
        Returns:
            int: Number of removed files
        """
        removed_files = 0
        
        try:
            # Find all files
            all_files = []
            for file_path in target_dir.iterdir():
                if file_path.is_file():
                    all_files.append(file_path)
            
            if not all_files:
                return 0
            
            # Sort by creation time (newest first)
            all_files.sort(key=lambda p: p.stat().st_ctime, reverse=True)
            
            self.logger.info(f"Found {len(all_files)} files in {target_dir}, keeping last {keep_count}")
            
            # Keep last N files, remove the rest
            files_to_remove = all_files[keep_count:]
            
            for file_path in files_to_remove:
                try:
                    self.logger.info(f"🗑️ Deleting old node log file: {file_path.name}")
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, file_path.unlink)
                    removed_files += 1
                except OSError as e:
                    self.logger.warning(f"Failed to delete file {file_path}: {e}")
            
            return removed_files
            
        except Exception as e:
            self.logger.error(f"❌ Error cleaning node log files by time in {target_dir}: {e}")
            return 0
    
    async def _cleanup_periodic_data_async(self, dry_run: bool = False) -> int:
        """Async cleanup of periodic data directories.
        Handles various periodic data cleanup rules.
        
        Returns:
            int: Number of removed files/directories
        """
        removed_items = 0
        
        try:
            # Periodic data cleanup rules
            periodic_rules = [
                {
                    "path": "/home/hl/hl/data/periodic_abci_state_statuses/20251014",
                    "type": "keep_last_directories",
                    "count": 3
                },
                {
                    "path": "/home/hl/hl/data/rate_limited_ips/*/hourly",
                    "type": "keep_last_by_creation_time",
                    "count": 10
                },
                {
                    "path": "/home/hl/hl/data/tcp_lz4_stats/20250914",
                    "type": "keep_last_by_creation_time",
                    "count": 3
                },
                {
                    "path": "/home/hl/hl/data/tcp_traffic/hourly",
                    "type": "keep_last_by_creation_time",
                    "count": 10
                },
                {
                    "path": "/home/hl/hl/data/tokio_spawn_forever_metrics/hourly",
                    "type": "keep_last_by_creation_time",
                    "count": 10
                },
                {
                    "path": "/home/hl/hl/data/visor_abci_states/hourly",
                    "type": "keep_last_by_creation_time",
                    "count": 10
                },
                {
                    "path": "/home/hl/hl/data/visor_child_stderr/",
                    "type": "keep_last_directories",
                    "count": 3,
                    "pattern": "yyyyMMdd"
                }
            ]
            
            for rule in periodic_rules:
                self.logger.info(f"🧹 Starting cleanup for rule: {rule['path']}")
                
                # Handle wildcard paths
                if "*" in rule["path"]:
                    # For wildcard paths, we need to find matching directories
                    base_path = rule["path"].split("*")[0]
                    base_dir = Path(base_path)
                    
                    if not base_dir.exists():
                        self.logger.warning(f"Base directory does not exist: {base_path}")
                        continue
                    
                    # Find matching subdirectories
                    subdirs = []
                    for item in base_dir.iterdir():
                        if item.is_dir():
                            subdirs.append(item)
                    
                    # Process each subdirectory
                    for subdir in subdirs:
                        if rule["type"] == "keep_last_by_creation_time":
                            removed_items += await self._cleanup_periodic_by_time_async(
                                subdir, rule["count"]
                            )
                else:
                    # Direct path
                    target_dir = Path(rule["path"])
                    if not target_dir.exists():
                        self.logger.warning(f"Target directory does not exist: {rule['path']}")
                        continue
                    
                    if rule["type"] == "keep_last_directories":
                        removed_items += await self._cleanup_periodic_directories_async(
                            target_dir, rule["count"], rule.get("pattern")
                        )
                    elif rule["type"] == "keep_last_by_creation_time":
                        removed_items += await self._cleanup_periodic_by_time_async(
                            target_dir, rule["count"]
                        )
            
            return removed_items
            
        except Exception as e:
            self.logger.error(f"❌ Error cleaning periodic data: {e}")
            raise
    
    async def _cleanup_periodic_directories_async(self, target_dir: Path, keep_count: int, pattern: str = None) -> int:
        """Cleanup periodic data directories.
        
        Args:
            target_dir: Target directory to clean
            keep_count: Number of directories to keep
            pattern: Directory pattern to match (optional)
            
        Returns:
            int: Number of removed directories
        """
        removed_dirs = 0
        
        try:
            # Find directories
            dirs = []
            for item in target_dir.iterdir():
                if item.is_dir():
                    if pattern == "yyyyMMdd":
                        # Match date pattern
                        if self.date_pattern.match(item.name):
                            dirs.append(item)
                    else:
                        # No pattern, include all directories
                        dirs.append(item)
            
            if not dirs:
                return 0
            
            # Sort by name (for date pattern) or creation time
            if pattern == "yyyyMMdd":
                dirs.sort(key=lambda p: p.name, reverse=True)
            else:
                dirs.sort(key=lambda p: p.stat().st_ctime, reverse=True)
            
            self.logger.info(f"Found {len(dirs)} directories in {target_dir}, keeping last {keep_count}")
            
            # Keep last N directories, remove the rest
            dirs_to_remove = dirs[keep_count:]
            
            for dir_path in dirs_to_remove:
                try:
                    self.logger.info(f"🗑️ Deleting old periodic directory: {dir_path.name}")
                    await self._remove_directory_async(dir_path)
                    removed_dirs += 1
                except OSError as e:
                    self.logger.warning(f"Failed to delete directory {dir_path}: {e}")
            
            return removed_dirs
            
        except Exception as e:
            self.logger.error(f"❌ Error cleaning periodic directories in {target_dir}: {e}")
            return 0
    
    async def _cleanup_periodic_by_time_async(self, target_dir: Path, keep_count: int) -> int:
        """Cleanup periodic data files by creation time.
        
        Args:
            target_dir: Target directory to clean
            keep_count: Number of files to keep
            
        Returns:
            int: Number of removed files
        """
        removed_files = 0
        
        try:
            # Find all files
            all_files = []
            for file_path in target_dir.iterdir():
                if file_path.is_file():
                    all_files.append(file_path)
            
            if not all_files:
                return 0
            
            # Sort by creation time (newest first)
            all_files.sort(key=lambda p: p.stat().st_ctime, reverse=True)
            
            self.logger.info(f"Found {len(all_files)} files in {target_dir}, keeping last {keep_count}")
            
            # Keep last N files, remove the rest
            files_to_remove = all_files[keep_count:]
            
            for file_path in files_to_remove:
                try:
                    self.logger.info(f"🗑️ Deleting old periodic file: {file_path.name}")
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, file_path.unlink)
                    removed_files += 1
                except OSError as e:
                    self.logger.warning(f"Failed to delete file {file_path}: {e}")
            
            return removed_files
            
        except Exception as e:
            self.logger.error(f"❌ Error cleaning periodic files by time in {target_dir}: {e}")
            return 0
    
    async def start_periodic_cleanup_async(self) -> None:
        """Start periodic cleanup every N hours."""
        self.logger.info(f"🔄 Starting periodic cleanup every {self.cleanup_interval_hours} hours")
        
        # Run cleanup immediately on startup
        try:
            self.logger.info("🧹 Running initial cleanup on startup")
            await self.cleanup_async()
        except Exception as e:
            self.logger.error(f"❌ Error in initial cleanup: {e}")
        
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
    
    def load_config(self, config_path: str) -> None:
        """Load cleanup configuration from JSON file.
        
        Args:
            config_path: Path to configuration file
        """
        try:
            self.config_path = Path(config_path).resolve()
            
            if not self.config_path.exists():
                self.logger.warning(f"Configuration file not found: {self.config_path}")
                return
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            self.logger.info(f"✅ Configuration loaded from: {self.config_path}")
            self._validate_config()
            
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ Invalid JSON in configuration file: {e}")
            raise
        except Exception as e:
            self.logger.error(f"❌ Error loading configuration: {e}")
            raise
    
    def _validate_config(self) -> None:
        """Validate configuration structure and rules."""
        if not self.config:
            self.logger.warning("No configuration loaded")
            return
        
        required_keys = ["version", "rules", "rule_types", "settings"]
        for key in required_keys:
            if key not in self.config:
                self.logger.warning(f"Missing required configuration key: {key}")
        
        # Validate rule types
        if "rule_types" in self.config:
            for rule_type, definition in self.config["rule_types"].items():
                if "description" not in definition:
                    self.logger.warning(f"Rule type {rule_type} missing description")
                if "parameters" not in definition:
                    self.logger.warning(f"Rule type {rule_type} missing parameters")
        
        # Validate rules
        if "rules" in self.config:
            for category, rules in self.config["rules"].items():
                if "paths" not in rules:
                    self.logger.warning(f"Category {category} missing paths")
                    continue
                
                for rule in rules["paths"]:
                    self._validate_rule(rule)
        
        self.logger.info("✅ Configuration validation completed")
    
    def _validate_rule(self, rule: Dict[str, Any]) -> None:
        """Validate individual rule.
        
        Args:
            rule: Rule dictionary to validate
        """
        required_fields = ["path", "rule_type"]
        for field in required_fields:
            if field not in rule:
                self.logger.warning(f"Rule missing required field: {field}")
                return
        
        rule_type = rule["rule_type"]
        if rule_type not in self.config.get("rule_types", {}):
            self.logger.warning(f"Unknown rule type: {rule_type}")
            return
        
        # Validate rule-specific parameters
        rule_definition = self.config["rule_types"][rule_type]
        required_params = rule_definition.get("parameters", [])
        
        for param in required_params:
            if param not in rule:
                self.logger.warning(f"Rule {rule['path']} missing parameter: {param}")
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get configuration summary.
        
        Returns:
            Dictionary with configuration summary
        """
        if not self.config:
            return {"status": "no_config_loaded"}
        
        summary = {
            "status": "loaded",
            "version": self.config.get("version", "unknown"),
            "config_path": str(self.config_path) if self.config_path else None,
            "categories": list(self.config.get("rules", {}).keys()),
            "rule_types": list(self.config.get("rule_types", {}).keys()),
            "settings": self.config.get("settings", {})
        }
        
        # Count total rules
        total_rules = 0
        for category, rules in self.config.get("rules", {}).items():
            if "paths" in rules:
                total_rules += len(rules["paths"])
        
        summary["total_rules"] = total_rules
        return summary
    
    async def apply_config_rules_async(self, dry_run: bool = False) -> Tuple[int, int]:
        """Apply cleanup rules from configuration.
        
        Args:
            dry_run: If True, simulate operations without actual deletion
            
        Returns:
            Tuple[int, int]: (number of removed directories, number of removed files)
        """
        if not self.config:
            self.logger.warning("No configuration loaded")
            return 0, 0
        
        total_removed_dirs = 0
        total_removed_files = 0
        
        try:
            for category, rules in self.config.get("rules", {}).items():
                self.logger.info(f"🧹 Processing category: {category}")
                
                for rule in rules.get("paths", []):
                    removed_dirs, removed_files = await self._apply_rule_async(rule, dry_run)
                    total_removed_dirs += removed_dirs
                    total_removed_files += removed_files
            
            self.logger.info(f"✅ Configuration rules applied: {total_removed_dirs} dirs, {total_removed_files} files removed")
            return total_removed_dirs, total_removed_files
            
        except Exception as e:
            self.logger.error(f"❌ Error applying configuration rules: {e}")
            raise
    
    async def _apply_rule_async(self, rule: Dict[str, Any], dry_run: bool = False) -> Tuple[int, int]:
        """Apply individual rule.
        
        Args:
            rule: Rule dictionary
            dry_run: If True, simulate operations without actual deletion
            
        Returns:
            Tuple[int, int]: (number of removed directories, number of removed files)
        """
        rule_type = rule.get("rule_type")
        path = rule.get("path")
        
        if not rule_type or not path:
            self.logger.warning(f"Invalid rule: {rule}")
            return 0, 0
        
        self.logger.debug(f"Applying rule: {rule_type} for {path}")
        
        try:
            if rule_type == "date_in_filename":
                return await self._apply_date_in_filename_rule(rule, dry_run)
            elif rule_type == "keep_last_files":
                return await self._apply_keep_last_files_rule(rule, dry_run)
            elif rule_type == "keep_last_by_creation_time":
                return await self._apply_keep_last_by_creation_time_rule(rule, dry_run)
            elif rule_type == "keep_latest_directory":
                return await self._apply_keep_latest_directory_rule(rule, dry_run)
            elif rule_type == "keep_last_directories":
                return await self._apply_keep_last_directories_rule(rule, dry_run)
            else:
                self.logger.warning(f"Unknown rule type: {rule_type}")
                return 0, 0
                
        except Exception as e:
            self.logger.error(f"❌ Error applying rule {rule_type} for {path}: {e}")
            return 0, 0
    
    async def _apply_date_in_filename_rule(self, rule: Dict[str, Any], dry_run: bool = False) -> Tuple[int, int]:
        """Apply date in filename rule."""
        # TODO: Implement date in filename cleanup
        self.logger.debug(f"Date in filename rule not implemented yet: {rule}")
        return 0, 0
    
    async def _apply_keep_last_files_rule(self, rule: Dict[str, Any], dry_run: bool = False) -> Tuple[int, int]:
        """Apply keep last files rule."""
        # TODO: Implement keep last files cleanup
        self.logger.debug(f"Keep last files rule not implemented yet: {rule}")
        return 0, 0
    
    async def _apply_keep_last_by_creation_time_rule(self, rule: Dict[str, Any], dry_run: bool = False) -> Tuple[int, int]:
        """Apply keep last by creation time rule."""
        # TODO: Implement keep last by creation time cleanup
        self.logger.debug(f"Keep last by creation time rule not implemented yet: {rule}")
        return 0, 0
    
    async def _apply_keep_latest_directory_rule(self, rule: Dict[str, Any], dry_run: bool = False) -> Tuple[int, int]:
        """Apply keep latest directory rule."""
        # TODO: Implement keep latest directory cleanup
        self.logger.debug(f"Keep latest directory rule not implemented yet: {rule}")
        return 0, 0
    
    async def _apply_keep_last_directories_rule(self, rule: Dict[str, Any], dry_run: bool = False) -> Tuple[int, int]:
        """Apply keep last directories rule."""
        # TODO: Implement keep last directories cleanup
        self.logger.debug(f"Keep last directories rule not implemented yet: {rule}")
        return 0, 0
