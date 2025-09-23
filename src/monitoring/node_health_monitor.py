"""Node health monitoring for HyperLiquid Node Parser."""

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from src.utils.logger import get_logger

logger = get_logger(__name__)

class Alert:
    """Alert model for health monitoring."""
    
    def __init__(self, alert_id: str, alert_type: str, message: str, timestamp: datetime, resolved: bool = False):
        self.id = alert_id
        self.type = alert_type  # 'critical' | 'warning'
        self.message = message
        self.timestamp = timestamp
        self.resolved = resolved
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": self.id,
            "type": self.type,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved
        }

class NodeHealthStatus:
    """Status of HyperLiquid node health."""
    
    def __init__(
        self,
        status: str,
        last_log_update: Optional[datetime],
        log_directory_accessible: bool,
        threshold_minutes: int,
        check_timestamp: datetime,
        error_count: int = 0,
        response_time: float = 0.0,
        uptime: float = 0.0,
        critical_alerts: Optional[List[Alert]] = None
    ):
        self.status = status  # 'online' | 'offline' | 'degraded'
        self.last_log_update = last_log_update
        self.log_directory_accessible = log_directory_accessible
        self.threshold_minutes = threshold_minutes
        self.check_timestamp = check_timestamp
        self.error_count = error_count
        self.response_time = response_time  # milliseconds
        self.uptime = uptime  # seconds
        self.critical_alerts = critical_alerts or []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "nodeStatus": self.status,
            "lastUpdate": self.last_log_update.isoformat() if self.last_log_update else None,
            "errorCount": self.error_count,
            "responseTime": self.response_time,
            "uptime": self.uptime,
            "criticalAlerts": [alert.to_dict() for alert in self.critical_alerts],
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
        self.start_time = time.time()
        self.error_count = 0
        self.response_times = []
        self.alerts = []
        logger.debug(f"NodeHealthMonitor initialized: path={node_logs_path}, threshold={threshold_minutes}min")
    
    def record_response_time(self, response_time_ms: float):
        """Record response time for health checks.
        
        Args:
            response_time_ms: Response time in milliseconds
        """
        self.response_times.append(response_time_ms)
        # Keep only last 100 response times for average calculation
        if len(self.response_times) > 100:
            self.response_times = self.response_times[-100:]
    
    def record_error(self, error_message: str = "Unknown error"):
        """Record an error occurrence.
        
        Args:
            error_message: Description of the error
        """
        self.error_count += 1
        logger.warning(f"Health monitoring error #{self.error_count}: {error_message}")
    
    def get_average_response_time(self) -> float:
        """Get average response time in milliseconds.
        
        Returns:
            Average response time in milliseconds
        """
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def get_uptime(self) -> float:
        """Get uptime in seconds.
        
        Returns:
            Uptime in seconds
        """
        return time.time() - self.start_time
    
    def create_alert(self, alert_type: str, message: str) -> Alert:
        """Create a new alert.
        
        Args:
            alert_type: Type of alert ('critical' | 'warning')
            message: Alert message
            
        Returns:
            Created Alert object
        """
        alert_id = f"alert_{int(time.time())}_{len(self.alerts)}"
        alert = Alert(alert_id, alert_type, message, datetime.now(timezone.utc))
        self.alerts.append(alert)
        logger.warning(f"Created {alert_type} alert: {message}")
        return alert
    
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
        start_time = time.time()
        
        # Check if directory is accessible
        directory_accessible = self.check_log_directory_access()
        
        if not directory_accessible:
            logger.warning("Log directory is not accessible, marking as offline")
            self.record_error("Log directory not accessible")
            return NodeHealthStatus(
                status="offline",
                last_log_update=None,
                log_directory_accessible=False,
                threshold_minutes=self.threshold_minutes,
                check_timestamp=check_timestamp,
                error_count=self.error_count,
                response_time=0.0,
                uptime=self.get_uptime(),
                critical_alerts=self.alerts
            )
        
        # Get last log update time
        last_update = self.get_last_log_update_time()
        
        if last_update is None:
            logger.warning("No log files found, marking as degraded")
            self.record_error("No log files found")
            return NodeHealthStatus(
                status="degraded",
                last_log_update=None,
                log_directory_accessible=True,
                threshold_minutes=self.threshold_minutes,
                check_timestamp=check_timestamp,
                error_count=self.error_count,
                response_time=0.0,
                uptime=self.get_uptime(),
                critical_alerts=self.alerts
            )
        
        # Check if logs are recent enough
        time_diff = check_timestamp - last_update
        time_diff_minutes = time_diff.total_seconds() / 60
        
        # Determine status based on log freshness and error count
        if time_diff_minutes <= self.threshold_minutes and self.error_count < 10:
            status = "online"
            logger.debug(f"Node is online: last update {time_diff_minutes:.1f} minutes ago, errors: {self.error_count}")
        elif time_diff_minutes > self.threshold_minutes:
            status = "degraded"
            logger.warning(f"Node is degraded: last update {time_diff_minutes:.1f} minutes ago (threshold: {self.threshold_minutes}min)")
            self.create_alert("critical", f"Node hanging: last update {time_diff_minutes:.1f} minutes ago")
        else:
            status = "degraded"
            logger.warning(f"Node is degraded: high error count ({self.error_count})")
            self.create_alert("critical", f"High error rate: {self.error_count} errors")
        
        # Record response time
        response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        self.record_response_time(response_time)
        
        return NodeHealthStatus(
            status=status,
            last_log_update=last_update,
            log_directory_accessible=True,
            threshold_minutes=self.threshold_minutes,
            check_timestamp=check_timestamp,
            error_count=self.error_count,
            response_time=self.get_average_response_time(),
            uptime=self.get_uptime(),
            critical_alerts=self.alerts
        )
