# Resilient Logging System

## Problem

When the disk fills up, the logging system crashes with:

```
OSError: [Errno 28] No space left on device
```

After this error:
- Application stops logging
- Application may become unresponsive
- Even after freeing disk space, logging doesn't recover
- Manual restart is required

## Solution

We've implemented a **ResilientRotatingFileHandler** that:
1. Handles disk full errors gracefully
2. Automatically recovers when disk space is freed
3. Falls back to stdout when disk is full
4. Performs emergency cleanup automatically
5. Continues application operation without crashes

## Architecture

### ResilientRotatingFileHandler

```
┌─────────────────────────────────────────┐
│  Normal Operation                        │
│  - Write logs to file                    │
│  - Rotate when size limit reached        │
└──────────────┬──────────────────────────┘
               │
               ▼ (Disk Full!)
┌─────────────────────────────────────────┐
│  Degraded Mode                           │
│  - Switch to stdout fallback             │
│  - Perform emergency cleanup             │
│  - Start recovery thread                 │
└──────────────┬──────────────────────────┘
               │
               ▼ (Every 60s)
┌─────────────────────────────────────────┐
│  Recovery Checks                         │
│  - Check available disk space            │
│  - Try to reopen file                    │
│  - Test write to file                    │
└──────────────┬──────────────────────────┘
               │
               ▼ (Space Available!)
┌─────────────────────────────────────────┐
│  Recovery Successful                     │
│  - Resume file logging                   │
│  - Stop fallback to stdout               │
│  - Stop recovery thread                  │
└─────────────────────────────────────────┘
```

## Features

### 1. Graceful Degradation

When disk is full:
- Immediately switches to stdout logging
- No logs are lost (sent to stdout)
- Application continues running
- Clear error messages in stderr

### 2. Emergency Cleanup

Automatically:
- Finds old log backup files
- Removes them oldest-first
- Frees specified amount of space (default: 50 MB)
- Truncates current log file if too large

### 3. Automatic Recovery

Background thread:
- Checks disk space every 60 seconds (configurable)
- Attempts to reopen log file
- Tests write capability
- Resumes normal operation when possible

### 4. State Tracking

Monitors:
- Degraded mode status
- Error count
- Last error timestamp
- Recovery attempts

### 5. Thread-Safe

All operations are:
- Protected with locks
- Thread-safe
- Safe for concurrent logging

## Configuration

### In settings.py

```python
LOG_LEVEL: str = "DEBUG"
LOG_FILE_PATH: str = "logs/app.log"
LOG_MAX_SIZE_MB: int = 100
LOG_RETENTION_DAYS: int = 30
```

### Custom Configuration

```python
from src.utils.resilient_file_handler import ResilientRotatingFileHandler

handler = ResilientRotatingFileHandler(
    filename="logs/app.log",
    maxBytes=100 * 1024 * 1024,  # 100 MB
    backupCount=5,
    encoding='utf-8',
    emergency_cleanup_threshold_mb=50,  # Free 50 MB when disk is full
    recovery_check_interval_sec=60  # Check every 60 seconds
)
```

## Usage

### Automatic (Recommended)

The resilient handler is automatically used when you call `get_logger()`:

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)
logger.info("This log is resilient!")
```

### Manual Setup

```python
import logging
from src.utils.resilient_file_handler import ResilientRotatingFileHandler

# Create handler
handler = ResilientRotatingFileHandler(
    "logs/app.log",
    maxBytes=100 * 1024 * 1024,
    backupCount=5
)

# Create logger
logger = logging.getLogger("my_app")
logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# Use logger
logger.info("Logging with automatic recovery!")
```

## Behavior

### When Disk Fills Up

```
================================================================================
⚠️  CRITICAL: Disk full! No space left on device
================================================================================
Log file: /app/logs/app.log
Time: 2025-10-07T12:34:56
Error count: 1

Switching to stdout logging...
Attempting emergency cleanup...
================================================================================

🗑️  Removed: app.log.5 (25.34 MB)
🗑️  Removed: app.log.4 (18.12 MB)
🗑️  Removed: app.log.3 (12.45 MB)

✅ Emergency cleanup complete:
   - Removed 3 files
   - Freed 55.91 MB

✂️  Truncated current log file: 105.23 MB → 10.52 MB

📝 Fallback handler configured (stdout)

🔄 Recovery thread started (checking every 60s)
```

### When Space is Freed

```
================================================================================
✅ RECOVERY SUCCESSFUL!
================================================================================
Log file: /app/logs/app.log
Free space: 156.78 MB
Time: 2025-10-07T12:36:42
Downtime: 106 seconds

Resuming normal file logging...
================================================================================
```

## Emergency Cleanup Logic

1. **Find backup files**: Searches for `app.log.*`, `*.log.*` patterns
2. **Sort by age**: Oldest files first
3. **Remove files**: Until threshold is met (default: 50 MB)
4. **Truncate current file**: If too large, keep only last 10%

## Recovery Logic

1. **Check disk space**: Needs at least 100 MB free
2. **Close old handle**: Release file resources
3. **Reopen file**: Try to open log file
4. **Test write**: Write test record
5. **Resume**: If successful, resume normal logging

## Thread Safety

All critical operations use `threading.RLock()`:
- `emit()` - Log writing
- `_handle_disk_full()` - Error handling
- `_attempt_recovery()` - Recovery attempts
- `_perform_emergency_cleanup()` - Cleanup operations

## Monitoring

### Check Handler Status

```python
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Get the resilient handler
for handler in logger.handlers:
    if hasattr(handler, 'is_degraded'):
        print(f"Degraded: {handler.is_degraded}")
        print(f"Error count: {handler.error_count}")
        if handler.last_error_time:
            print(f"Last error: {handler.last_error_time}")
```

### Logs to Monitor

Watch stderr for:
- `⚠️  CRITICAL: Disk full!` - Disk full detected
- `✅ Emergency cleanup complete` - Cleanup successful
- `🔄 Recovery thread started` - Recovery initiated
- `✅ RECOVERY SUCCESSFUL!` - Recovery complete
- `⚠️  Recovery attempt failed` - Recovery failed

## Testing

Run tests:

```bash
cd /app
pytest tests/test_resilient_logging.py -v
```

Tests cover:
- Normal logging operation
- Emergency cleanup
- Fallback to stdout
- State tracking
- Recovery thread
- Log rotation

## Performance Impact

- **Normal operation**: Minimal overhead (lock acquisition)
- **Degraded mode**: Slightly slower due to stdout
- **Recovery checks**: Every 60 seconds (configurable)
- **Emergency cleanup**: One-time cost when triggered

## Best Practices

1. **Monitor disk space**: Set up alerts for low disk space
2. **Regular cleanup**: Use `DirectoryCleaner` for proactive cleanup
3. **Appropriate log levels**: Use INFO/WARNING in production
4. **Reasonable file sizes**: Don't make log files too large
5. **Sufficient retention**: Balance between history and disk space

## Troubleshooting

### Recovery Not Working

Check:
1. Is there actually free space? (Need 100+ MB)
2. Are file permissions correct?
3. Is the recovery thread running?
4. Check stderr for recovery attempt logs

### Emergency Cleanup Not Freeing Space

Check:
1. Are there old backup files to remove?
2. Is cleanup threshold set too low?
3. Is current log file being truncated?

### Still Seeing Errors

1. Check if other processes are filling disk
2. Verify log rotation is working
3. Consider reducing `LOG_MAX_SIZE_MB`
4. Enable more aggressive cleanup

## Migration from Old Logger

No changes needed! The resilient handler is a drop-in replacement:

```python
# Old code (still works!)
from src.utils.logger import get_logger
logger = get_logger(__name__)

# New code (same!)
from src.utils.logger import get_logger
logger = get_logger(__name__)
```

## Advanced Configuration

### Aggressive Recovery

```python
handler = ResilientRotatingFileHandler(
    "logs/app.log",
    maxBytes=50 * 1024 * 1024,  # Smaller files
    backupCount=3,  # Fewer backups
    emergency_cleanup_threshold_mb=100,  # More aggressive cleanup
    recovery_check_interval_sec=30  # Check more frequently
)
```

### Conservative Approach

```python
handler = ResilientRotatingFileHandler(
    "logs/app.log",
    maxBytes=200 * 1024 * 1024,  # Larger files
    backupCount=10,  # More backups
    emergency_cleanup_threshold_mb=20,  # Less aggressive cleanup
    recovery_check_interval_sec=300  # Check less frequently (5 min)
)
```

## Related Files

- `src/utils/resilient_file_handler.py` - Main implementation
- `src/utils/logger.py` - Logger setup using resilient handler
- `tests/test_resilient_logging.py` - Tests
- `config/settings.py` - Configuration

## Future Improvements

- [ ] Add metrics for monitoring
- [ ] Add webhook notifications for disk full events
- [ ] Implement compression for old log files
- [ ] Add automatic log upload to external storage
- [ ] Implement log streaming to external service

---

**Last Updated:** 2025-10-07  
**Version:** 1.0.0

