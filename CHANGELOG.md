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

### Changed
- Updated `logger.py` to use `ResilientRotatingFileHandler` instead of standard `RotatingFileHandler`
- Improved error handling in logging system

### Fixed
- **Critical**: Application no longer crashes when disk is full
- **Critical**: Logging automatically recovers after disk space is freed
- No more manual restart required after disk full errors

## [1.0.0] - Previous Release

### Features
- Single file tail watcher for real-time log monitoring
- WebSocket support for live order updates
- Resource monitoring for HyperLiquid node coexistence
- Automatic directory cleanup
- Reactive order processing


