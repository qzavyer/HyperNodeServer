# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Resilient Logging System** - Automatic recovery from disk full errors
  - `ResilientRotatingFileHandler` - Custom logging handler
  - Automatic fallback to stdout when disk is full
  - Emergency cleanup of old log files
  - Background recovery thread
  - Thread-safe operations
  - Comprehensive documentation in `docs/resilient-logging.md`
- **Comprehensive Diagnostic Logging** - INFO-level logging for batch processing pipeline
  - Full visibility into buffer snapshot, parallel/sequential processing paths
  - Worker-level logging in thread pool execution
  - Task creation and completion tracking with emoji markers
  - Detailed error reporting with tracebacks

### Changed
- Updated `logger.py` to use `ResilientRotatingFileHandler` instead of standard `RotatingFileHandler`
- Improved error handling in logging system
- Refactored `_process_batch()` with immediate buffer clearing to prevent race conditions
- Replaced individual `asyncio.wait_for()` with `asyncio.gather()` for proper ThreadPoolExecutor future handling
- Limited parallel chunks to `parallel_workers` count to prevent executor overflow

### Fixed
- **Critical**: Application no longer crashes when disk is full
- **Critical**: Logging automatically recovers after disk space is freed
- **Critical**: Memory leak from buffer race condition - buffer no longer grows from 41M to 44M+ lines
- **Critical**: Deadlock in parallel processing - asyncio.gather() properly waits for ThreadPoolExecutor tasks
- **Critical**: Executor overflow - exact chunk count matching worker count preventing task queue buildup
- **Critical**: Task cancellation - increased _tail_loop timeout from 2s to 60s allowing gather() to complete
- **Critical**: Stuck threads - executor recreated after timeout to clear zombie threads
- **Critical**: Infinite lag - aggressive buffer limit drops old data when buffer exceeds 500K lines
- **Critical**: Low throughput - increased workers from 4 to 8-16 based on CPU cores
- **Critical**: Per-line timeout removed - was causing thread hangs and 2x slowdown
- Buffer clearing happens immediately after snapshot, not at end of processing
- Batch size increased from 100K to 200K lines for higher throughput
- Parallel processing completes successfully without hanging on task completion
- WebSocket broadcasting now works correctly when orders are parsed
- Chunks created using explicit loop with remainder distribution (not list comprehension)
- ThreadPoolExecutor futures properly handled with asyncio.gather() instead of wait_for()
- Log spam reduced (removed "Added X lines", reduced frequency of global stats)

## [1.0.0] - Previous Release

### Features
- Single file tail watcher for real-time log monitoring
- WebSocket support for live order updates
- Resource monitoring for HyperLiquid node coexistence
- Automatic directory cleanup
- Reactive order processing


