"""Node health monitoring for HyperLiquid Node Parser."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)

class NodeHealthStatus:
    """Status of HyperLiquid node health."""
    
    def __init__(
        self,
        status: str,
        last_log_update: Optional[datetime],
        log_directory_accessible: bool,
        threshold_minutes: int,
        check_timestamp: datetime
    ):
        self.status = status  # 'healthy' | 'unhealthy' | 'server_unavailable'
        self.last_log_update = last_log_update
        self.log_directory_accessible = log_directory_accessible
        self.threshold_minutes = threshold_minutes
        self.check_timestamp = check_timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "status": self.status,
            "last_log_update": self.last_log_update.isoformat() if self.last_log_update else None,
            "log_directory_accessible": self.log_directory_accessible,
            "threshold_minutes": self.threshold_minutes,
            "check_timestamp": self.check_timestamp.isoformat()
        }

class NodeHealthMonitor:
    """Monitors the health of HyperLiquid node by checking log file updates."""
    
    def __init__(self, node_logs_path: str, threshold_minutes: int = 5):
        """Initialize node health monitor.
        
        Args:
            node_logs_path: Path to node logs directory
            threshold_minutes: Threshold in minutes for determining unhealthy state
        """
        self.node_logs_path = Path(node_logs_path)
        self.threshold_minutes = threshold_minutes
        logger.debug(f"NodeHealthMonitor initialized: path={node_logs_path}, threshold={threshold_minutes}min")
    
    def get_last_log_update_time(self) -> Optional[datetime]:
        """Get the timestamp of the most recently updated log file.
        
        Returns:
            Datetime of last log update or None if no logs found
        """
        try:
            if not self.node_logs_path.exists():
                logger.warning(f"Log directory does not exist: {self.node_logs_path}")
                return None
            
            latest_time = None
            log_files_count = 0
            
            # Check all files in the directory and subdirectories
            for file_path in self.node_logs_path.rglob("*"):
                try:
                    if file_path.is_file():
                        log_files_count += 1
                        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
                        
                        if latest_time is None or file_mtime > latest_time:
                            latest_time = file_mtime
                except (PermissionError, FileNotFoundError, OSError) as e:
                    # Skip inaccessible files (broken symlinks, permission denied, etc.)
                    logger.debug(f"Skipping inaccessible file {file_path}: {e}")
                    continue
            
            logger.debug(f"Found {log_files_count} log files, latest update: {latest_time}")
            return latest_time
            
        except Exception as e:
            logger.error(f"Error getting last log update time: {e}")
            return None
    
    def check_log_directory_access(self) -> bool:
        """Check if the log directory is accessible.
        
        Returns:
            True if directory is accessible, False otherwise
        """
        try:
            # Check if directory exists
            if not self.node_logs_path.exists():
                logger.warning(f"Log directory does not exist: {self.node_logs_path}")
                return False
            
            # Check if it's actually a directory
            if not self.node_logs_path.is_dir():
                logger.warning(f"Path is not a directory: {self.node_logs_path}")
                return False
            
            # Try to list contents to check read permissions
            try:
                list(self.node_logs_path.iterdir())
                logger.debug(f"Log directory is accessible: {self.node_logs_path}")
                return True
            except PermissionError:
                logger.warning(f"Permission denied accessing log directory: {self.node_logs_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking log directory access: {e}")
            return False
    
    def get_health_status(self) -> NodeHealthStatus:
        """Get the current health status of the node.
        
        Returns:
            NodeHealthStatus object with current health information
        """
        check_timestamp = datetime.now(timezone.utc)
        
        # Check if directory is accessible
        directory_accessible = self.check_log_directory_access()
        
        if not directory_accessible:
            logger.warning("Log directory is not accessible, marking as server_unavailable")
            return NodeHealthStatus(
                status="server_unavailable",
                last_log_update=None,
                log_directory_accessible=False,
                threshold_minutes=self.threshold_minutes,
                check_timestamp=check_timestamp
            )
        
        # Get last log update time
        last_update = self.get_last_log_update_time()
        
        if last_update is None:
            logger.warning("No log files found, marking as unhealthy")
            return NodeHealthStatus(
                status="unhealthy",
                last_log_update=None,
                log_directory_accessible=True,
                threshold_minutes=self.threshold_minutes,
                check_timestamp=check_timestamp
            )
        
        # Check if logs are recent enough
        time_diff = check_timestamp - last_update
        time_diff_minutes = time_diff.total_seconds() / 60
        
        if time_diff_minutes <= self.threshold_minutes:
            status = "healthy"
            logger.debug(f"Node is healthy: last update {time_diff_minutes:.1f} minutes ago")
        else:
            status = "unhealthy"
            logger.warning(f"Node is unhealthy: last update {time_diff_minutes:.1f} minutes ago (threshold: {self.threshold_minutes}min)")
        
        return NodeHealthStatus(
            status=status,
            last_log_update=last_update,
            log_directory_accessible=True,
            threshold_minutes=self.threshold_minutes,
            check_timestamp=check_timestamp
        )
