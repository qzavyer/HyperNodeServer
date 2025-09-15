"""Application settings and configuration."""

import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings."""
    
    # Node logs path
    NODE_LOGS_PATH: str = "/app/node_logs"
    
    # Cleanup settings
    CLEANUP_INTERVAL_HOURS: int = 2
    
    # Directory cleanup settings
    DIRECTORY_CLEANUP_INTERVAL_HOURS: int = 1  # Очистка директорий каждый час
    FILE_RETENTION_HOURS: int = 1  # Файлы старше 1 часа удаляются
    
    # File monitoring and retry settings
    FILE_READ_RETRY_ATTEMPTS: int = 3
    FILE_READ_RETRY_DELAY: float = 1.0
    
    # Performance optimization settings
    MAX_FILE_SIZE_GB: float = 50.0  # Maximum file size to process (GB)
    MAX_ORDERS_PER_FILE: Optional[int] = 1000000  # Maximum orders per file (None = unlimited)
    CHUNK_SIZE_BYTES: int = 16384  # Increased chunk size for faster reading (16KB)
    BATCH_SIZE: int = 2000  # Increased batch size for faster processing
    PROCESSING_TIMEOUT_PER_GB: int = 5  # Seconds per GB for file processing
    BATCH_PROCESSING_DELAY_MS: float = 0.001  # Minimal delay between batches (1ms)
    PERIODIC_SCAN_INTERVAL_SEC: int = 1  # Scan interval for real-time data (1 second)
    
    # Single file tail watcher settings
    SINGLE_FILE_TAIL_ENABLED: bool = True  # Enable single file tail approach
    FALLBACK_SCAN_INTERVAL_SEC: int = 600  # Fallback scan interval (10 minutes)
    TAIL_READLINE_INTERVAL_MS: float = 10.0  # Balanced polling (10ms)
    TAIL_BATCH_SIZE: int = 20  # Process fewer lines at once
    TAIL_BUFFER_SIZE: int = 16384  # Larger buffer for faster reading (16KB)
    TAIL_AGGRESSIVE_POLLING: bool = True  # Enable aggressive polling for maximum speed
    
    # Parallel processing settings
    TAIL_PARALLEL_WORKERS: int = 2  # Number of parallel workers for parsing
    TAIL_PARALLEL_BATCH_SIZE: int = 200  # Batch size for parallel processing
    TAIL_JSON_OPTIMIZATION: bool = True  # Enable JSON parsing optimization
    TAIL_PRE_FILTER: bool = True  # Enable pre-filtering of lines before parsing
    
    # Revolutionary memory-mapped processing
    TAIL_MEMORY_MAPPED: bool = True  # Enable memory-mapped file processing
    TAIL_MMAP_CHUNK_SIZE: int = 2 * 1024 * 1024  # 2MB chunks for memory mapping
    TAIL_ZERO_COPY: bool = True  # Enable zero-copy string processing
    TAIL_LOCK_FREE: bool = True  # Enable lock-free concurrent processing
    
    # Streaming processing for maximum speed
    TAIL_STREAMING: bool = True  # Enable streaming processing
    TAIL_STREAM_BUFFER_SIZE: int = 128 * 1024  # 128KB stream buffer
    TAIL_STREAM_CHUNK_SIZE: int = 32 * 1024  # 32KB chunks
    TAIL_STREAM_PROCESSING_DELAY_MS: float = 1.0  # 1ms delay between chunks
    
    # Ultra-aggressive processing settings
    TAIL_ULTRA_FAST_MODE: bool = False  # Enable ultra-fast mode
    TAIL_NO_SLEEP_MODE: bool = False  # Disable all sleep delays
    TAIL_CONTINUOUS_POLLING: bool = False  # Continuous polling without breaks
    TAIL_MAX_BATCH_SIZE: int = 500  # Maximum batch size for processing
    TAIL_EMERGENCY_MODE: bool = False  # Emergency mode for maximum speed
    
    # Python optimization settings
    PYTHON_OPTIMIZATION: bool = True  # Enable Python-specific optimizations
    USE_LRU_CACHE: bool = True  # Enable LRU caching for frequently used functions
    CACHE_SIZE: int = 1000  # Size of LRU cache
    ENABLE_CONCURRENT_FUTURES: bool = True  # Use concurrent.futures for CPU tasks
    MAX_WORKERS_AUTO: bool = True  # Automatically set max workers based on CPU count
    
    # WebSocket settings
    WEBSOCKET_PING_INTERVAL: int = 20  # Ping interval in seconds
    WEBSOCKET_PING_TIMEOUT: int = 20   # Ping timeout in seconds
    WEBSOCKET_CLOSE_TIMEOUT: int = 10  # Close timeout in seconds
    WEBSOCKET_BATCH_SIZE: int = 100  # Batch size for WebSocket messages
    WEBSOCKET_BATCH_DELAY_MS: float = 0.001  # Delay between WebSocket batches
    
    # API settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Logging settings
    LOG_LEVEL: str = "DEBUG"
    LOG_FILE_PATH: str = "logs/app.log"
    LOG_MAX_SIZE_MB: int = 100
    LOG_RETENTION_DAYS: int = 30
    
    # Data settings
    DATA_DIR: str = "data"
    CONFIG_FILE_PATH: str = "config/coins.json"
    
    # API limits
    MAX_ORDERS_PER_REQUEST: int = 1000
    
    # Development settings (for compatibility)
    DEBUG: bool = False
    RELOAD: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()
