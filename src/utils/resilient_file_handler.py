"""Resilient file handler for logging that handles disk space errors."""

import logging
import logging.handlers
import os
import sys
import time
import threading
from pathlib import Path
from typing import Optional
from datetime import datetime


class ResilientRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler with automatic recovery from disk space errors.
    
    Features:
    - Handles OSError: No space left on device
    - Automatically recovers when disk space is freed
    - Falls back to stdout when disk is full
    - Performs emergency cleanup when needed
    - Monitors disk space and logs warnings
    """
    
    def __init__(
        self,
        filename,
        mode='a',
        maxBytes=0,
        backupCount=0,
        encoding=None,
        delay=False,
        emergency_cleanup_threshold_mb: int = 50,
        recovery_check_interval_sec: int = 60
    ):
        """Initialize resilient handler.
        
        Args:
            filename: Log file path
            mode: File open mode
            maxBytes: Maximum file size before rotation
            backupCount: Number of backup files to keep
            encoding: File encoding
            delay: Delay file opening
            emergency_cleanup_threshold_mb: Free space threshold for emergency cleanup
            recovery_check_interval_sec: How often to check for recovery
        """
        self.emergency_cleanup_threshold = emergency_cleanup_threshold_mb * 1024 * 1024
        self.recovery_check_interval = recovery_check_interval_sec
        
        # State tracking
        self.is_degraded = False
        self.last_error_time = None
        self.error_count = 0
        self.last_recovery_check = time.time()
        
        # Fallback handler for stdout
        self.fallback_handler: Optional[logging.StreamHandler] = None
        
        # Recovery thread
        self.recovery_thread: Optional[threading.Thread] = None
        self.stop_recovery = threading.Event()
        
        # Lock for thread-safe operations
        self.handler_lock = threading.RLock()
        
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
    
    def emit(self, record):
        """Emit a record with error handling and recovery.
        
        Args:
            record: LogRecord to emit
        """
        try:
            with self.handler_lock:
                # If in degraded mode, try to recover first
                if self.is_degraded:
                    self._attempt_recovery()
                
                # Try normal emit
                if not self.is_degraded:
                    super().emit(record)
                else:
                    # Use fallback handler
                    self._emit_to_fallback(record)
                    
        except OSError as e:
            if e.errno == 28:  # No space left on device
                self._handle_disk_full(record)
            else:
                self.handleError(record)
        except Exception:
            self.handleError(record)
    
    def _handle_disk_full(self, record):
        """Handle disk full error.
        
        Args:
            record: LogRecord that failed to write
        """
        with self.handler_lock:
            if not self.is_degraded:
                self.is_degraded = True
                self.last_error_time = time.time()
                self.error_count += 1
                
                # Log to stderr
                print(
                    f"\n{'='*80}\n"
                    f"⚠️  CRITICAL: Disk full! No space left on device\n"
                    f"{'='*80}\n"
                    f"Log file: {self.baseFilename}\n"
                    f"Time: {datetime.now().isoformat()}\n"
                    f"Error count: {self.error_count}\n"
                    f"\nSwitching to stdout logging...\n"
                    f"Attempting emergency cleanup...\n"
                    f"{'='*80}\n",
                    file=sys.stderr
                )
                
                # Try emergency cleanup
                self._perform_emergency_cleanup()
                
                # Setup fallback handler
                self._setup_fallback_handler()
                
                # Start recovery thread
                self._start_recovery_thread()
                
                # Close file handle to release resources
                try:
                    if self.stream:
                        self.stream.close()
                        self.stream = None
                except Exception:
                    pass
            
            # Log to fallback
            self._emit_to_fallback(record)
    
    def _perform_emergency_cleanup(self):
        """Perform emergency cleanup of old log files."""
        try:
            log_dir = Path(self.baseFilename).parent
            
            # Find all backup log files
            backup_files = []
            for pattern in ['app.log.*', '*.log.*', '*.log']:
                backup_files.extend(log_dir.glob(pattern))
            
            # Sort by modification time (oldest first)
            backup_files.sort(key=lambda f: f.stat().st_mtime)
            
            # Remove old files
            removed_count = 0
            freed_space = 0
            
            for backup_file in backup_files:
                if backup_file == Path(self.baseFilename):
                    continue  # Don't remove current log file
                
                try:
                    size = backup_file.stat().st_size
                    backup_file.unlink()
                    removed_count += 1
                    freed_space += size
                    
                    print(
                        f"🗑️  Removed: {backup_file.name} "
                        f"({size / 1024 / 1024:.2f} MB)",
                        file=sys.stderr
                    )
                    
                    # Check if we freed enough space
                    if freed_space >= self.emergency_cleanup_threshold:
                        break
                        
                except Exception as e:
                    print(
                        f"⚠️  Failed to remove {backup_file.name}: {e}",
                        file=sys.stderr
                    )
            
            print(
                f"\n✅ Emergency cleanup complete:\n"
                f"   - Removed {removed_count} files\n"
                f"   - Freed {freed_space / 1024 / 1024:.2f} MB\n",
                file=sys.stderr
            )
            
            # Also try to truncate current log file if it's too large
            try:
                current_file = Path(self.baseFilename)
                if current_file.exists():
                    current_size = current_file.stat().st_size
                    if current_size > self.maxBytes:
                        # Keep only last 10% of the file
                        keep_size = int(self.maxBytes * 0.1)
                        with open(current_file, 'rb+') as f:
                            f.seek(-keep_size, os.SEEK_END)
                            data = f.read()
                            f.seek(0)
                            f.truncate()
                            f.write(data)
                        
                        print(
                            f"✂️  Truncated current log file: "
                            f"{current_size / 1024 / 1024:.2f} MB → "
                            f"{keep_size / 1024 / 1024:.2f} MB\n",
                            file=sys.stderr
                        )
            except Exception as e:
                print(f"⚠️  Failed to truncate current log: {e}", file=sys.stderr)
                
        except Exception as e:
            print(f"❌ Emergency cleanup failed: {e}", file=sys.stderr)
    
    def _setup_fallback_handler(self):
        """Setup fallback handler for stdout logging."""
        if not self.fallback_handler:
            self.fallback_handler = logging.StreamHandler(sys.stdout)
            self.fallback_handler.setLevel(self.level)
            self.fallback_handler.setFormatter(self.formatter)
            
            print(
                "📝 Fallback handler configured (stdout)\n",
                file=sys.stderr
            )
    
    def _emit_to_fallback(self, record):
        """Emit record to fallback handler.
        
        Args:
            record: LogRecord to emit
        """
        if self.fallback_handler:
            try:
                self.fallback_handler.emit(record)
            except Exception:
                # Last resort - just print to stderr
                print(f"[FALLBACK] {self.format(record)}", file=sys.stderr)
    
    def _start_recovery_thread(self):
        """Start background thread to check for recovery."""
        if not self.recovery_thread or not self.recovery_thread.is_alive():
            self.stop_recovery.clear()
            self.recovery_thread = threading.Thread(
                target=self._recovery_loop,
                daemon=True,
                name="LogRecoveryThread"
            )
            self.recovery_thread.start()
            
            print(
                f"🔄 Recovery thread started (checking every {self.recovery_check_interval}s)\n",
                file=sys.stderr
            )
    
    def _recovery_loop(self):
        """Background loop to periodically attempt recovery."""
        while not self.stop_recovery.is_set():
            try:
                # Wait for interval
                self.stop_recovery.wait(self.recovery_check_interval)
                
                if self.is_degraded:
                    with self.handler_lock:
                        self._attempt_recovery()
                        
            except Exception as e:
                print(f"⚠️  Recovery loop error: {e}", file=sys.stderr)
    
    def _attempt_recovery(self):
        """Attempt to recover file logging."""
        try:
            # Check disk space
            stat = os.statvfs(Path(self.baseFilename).parent)
            free_space = stat.f_bavail * stat.f_frsize
            free_space_mb = free_space / 1024 / 1024
            
            # Need at least 100 MB free to recover
            if free_space_mb < 100:
                # Not enough space yet
                return
            
            # Try to reopen file
            try:
                if self.stream:
                    self.stream.close()
                    self.stream = None
                
                # Reopen file
                self.stream = self._open()
                
                # Test write
                test_record = logging.LogRecord(
                    name="recovery_test",
                    level=logging.INFO,
                    pathname="",
                    lineno=0,
                    msg="Recovery test",
                    args=(),
                    exc_info=None
                )
                super().emit(test_record)
                
                # Success!
                self.is_degraded = False
                
                print(
                    f"\n{'='*80}\n"
                    f"✅ RECOVERY SUCCESSFUL!\n"
                    f"{'='*80}\n"
                    f"Log file: {self.baseFilename}\n"
                    f"Free space: {free_space_mb:.2f} MB\n"
                    f"Time: {datetime.now().isoformat()}\n"
                    f"Downtime: {time.time() - self.last_error_time:.0f} seconds\n"
                    f"\nResuming normal file logging...\n"
                    f"{'='*80}\n",
                    file=sys.stderr
                )
                
                # Stop recovery thread
                self.stop_recovery.set()
                
            except OSError as e:
                if e.errno == 28:
                    # Still no space, perform another cleanup
                    print(
                        f"⚠️  Still no space ({free_space_mb:.2f} MB free). "
                        f"Performing cleanup...\n",
                        file=sys.stderr
                    )
                    self._perform_emergency_cleanup()
                else:
                    raise
                    
        except Exception as e:
            print(f"⚠️  Recovery attempt failed: {e}", file=sys.stderr)
    
    def close(self):
        """Close handler and stop recovery thread."""
        # Stop recovery thread
        self.stop_recovery.set()
        if self.recovery_thread:
            self.recovery_thread.join(timeout=2)
        
        # Close fallback handler
        if self.fallback_handler:
            try:
                self.fallback_handler.close()
            except Exception:
                pass
        
        # Close file handler
        super().close()

