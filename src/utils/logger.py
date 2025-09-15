"""Centralized logging configuration for HyperLiquid Node Parser."""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Global logger cache
_loggers = {}


def setup_logger(
    name: str,
    max_size_mb: int = 100,
    retention_days: int = 30,
    log_level: str = "DEBUG"
) -> logging.Logger:
    """Setup logger with file rotation and fallback to stdout.
    
    Args:
        name: Logger name (usually __name__)
        max_size_mb: Maximum log file size in MB
        retention_days: Number of days to keep log files
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        
    Returns:
        Configured logger instance
    """
    # Return cached logger if already exists and has handlers
    if name in _loggers and _loggers[name].handlers:
        return _loggers[name]
    
    # Create logs directory (use absolute path for Docker consistency)
    logs_dir = Path("/app/logs") if os.path.exists("/app") else Path("logs")
    logs_dir.mkdir(exist_ok=True, parents=True)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )
    
    # Create rotating file handler
    log_filename = "app.log"
    log_filepath = logs_dir / log_filename
    
    try:
        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_filepath,
            maxBytes=max_size_mb * 1024 * 1024,  # Convert MB to bytes
            backupCount=5,  # Keep 5 backup files
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(formatter)
        
        # Add file handler to logger
        logger.addHandler(file_handler)
        
        # Log successful file handler setup
        print(f"✅ Logging to file: {log_filepath}")
        
        # Also add console handler for Docker logs visibility
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)  # Less verbose for console
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
    except Exception as e:
        # Fallback to stdout if file logging fails
        print(f"⚠️ Failed to setup file logging: {e}")
        print("📝 Falling back to stdout logging")
        
        # Clear any handlers that might have been added before the exception
        logger.handlers.clear()
        
        # Create stdout handler
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setLevel(getattr(logging, log_level.upper()))
        stdout_handler.setFormatter(formatter)
        logger.addHandler(stdout_handler)
    
    # Cleanup old log files
    cleanup_old_logs(logs_dir, retention_days)
    
    # Cache logger
    _loggers[name] = logger
    
    return logger


def cleanup_old_logs(logs_dir: Path, retention_days: int) -> None:
    """Remove log files older than specified days.
    
    Args:
        logs_dir: Directory containing log files
        retention_days: Number of days to keep logs
    """
    try:
        cutoff_time = datetime.now().timestamp() - (retention_days * 24 * 3600)
        
        for log_file in logs_dir.glob("app.log*"):
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()
                print(f"🗑️ Removed old log file: {log_file}")
                
    except Exception as e:
        print(f"⚠️ Failed to cleanup old logs: {e}")


def get_logger(name: str) -> logging.Logger:
    """Get existing logger or create new one with default settings.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    if name in _loggers:
        return _loggers[name]
    else:
        return setup_logger(name)
