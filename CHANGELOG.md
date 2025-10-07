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
- **Critical**: Executor overflow - chunks limited to available workers preventing task queue buildup
- Buffer clearing happens immediately after snapshot, not at end of processing
- Parallel processing completes successfully without hanging on task completion
- WebSocket broadcasting now works correctly when orders are parsed

## [1.0.0] - Previous Release

### Features
- Single file tail watcher for real-time log monitoring
- WebSocket support for live order updates
- Resource monitoring for HyperLiquid node coexistence
- Automatic directory cleanup
- Reactive order processing


