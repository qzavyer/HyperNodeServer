"""Application settings and configuration."""

import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings."""
    
    # Node logs path
    NODE_LOGS_PATH: str = "/app/node_logs"
    NODE_LOGS_PATH_HYPERLIQUID: str = "/app/node_logs_hyperliquid"
    HYPERLIQUID_DATA_PATH: str = "/app/hyperliquid_data"
    DATA_PATH: str = "/app/data"

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
    
    # Single file tail watcher settings - optimized for HyperLiquid node coexistence
    SINGLE_FILE_TAIL_ENABLED: bool = True  # Enable single file tail approach
    FALLBACK_SCAN_INTERVAL_SEC: int = 300  # Fallback scan interval (5 minutes) - reduced
    TAIL_READLINE_INTERVAL_MS: float = 1000.0  # Conservative polling (1 second) - increased to reduce CPU
    TAIL_BATCH_SIZE: int = 50  # Larger batches to reduce processing frequency
    TAIL_BUFFER_SIZE: int = 8192  # Smaller buffer (8KB) to reduce memory usage
    TAIL_AGGRESSIVE_POLLING: bool = False  # Disable aggressive polling for stability
    
    # Parallel processing settings - conservative for HyperLiquid node coexistence
    TAIL_PARALLEL_WORKERS: int = 4  # Single worker to reduce CPU contention
    TAIL_PARALLEL_BATCH_SIZE: int = 50  # Smaller batches to reduce memory spikes
    TAIL_JSON_OPTIMIZATION: bool = True  # Enable JSON parsing optimization
    TAIL_PRE_FILTER: bool = True  # Enable pre-filtering of lines before parsing
    
    # Revolutionary memory-mapped processing - conservative settings
    TAIL_MEMORY_MAPPED: bool = False  # Disable memory mapping to reduce memory usage
    TAIL_MMAP_CHUNK_SIZE: int = 512 * 1024  # 512KB chunks if enabled
    TAIL_ZERO_COPY: bool = False  # Disable zero-copy to reduce complexity
    TAIL_LOCK_FREE: bool = False  # Disable lock-free processing for stability
    
    # Streaming processing - conservative settings
    TAIL_STREAMING: bool = False
    TAIL_STREAM_BUFFER_SIZE: int = 32 * 1024  # 32KB stream buffer if enabled
    TAIL_STREAM_CHUNK_SIZE: int = 8 * 1024  # 8KB chunks if enabled
    TAIL_STREAM_PROCESSING_DELAY_MS: float = 10.0  # 10ms delay between chunks
    
    # Ultra-aggressive processing settings
    TAIL_ULTRA_FAST_MODE: bool = False  # Enable ultra-fast mode
    TAIL_NO_SLEEP_MODE: bool = False  # Disable all sleep delays
    TAIL_CONTINUOUS_POLLING: bool = False  # Continuous polling without breaks
    TAIL_MAX_BATCH_SIZE: int = 500  # Maximum batch size for processing
    TAIL_EMERGENCY_MODE: bool = False  # Emergency mode for maximum speed
    
    # Python optimization settings - conservative for HyperLiquid node coexistence
    PYTHON_OPTIMIZATION: bool = True  # Enable Python-specific optimizations
    USE_LRU_CACHE: bool = True  # Enable LRU caching for frequently used functions
    CACHE_SIZE: int = 100  # Smaller cache size to reduce memory usage
    ENABLE_CONCURRENT_FUTURES: bool = False  # Disable concurrent.futures to reduce CPU contention
    MAX_WORKERS_AUTO: bool = False  # Use fixed number of workers
    
    # WebSocket settings - conservative for stability
    WEBSOCKET_PING_INTERVAL: int = 30  # Increased ping interval (30 seconds)
    WEBSOCKET_PING_TIMEOUT: int = 30   # Increased ping timeout (30 seconds)
    WEBSOCKET_CLOSE_TIMEOUT: int = 15  # Increased close timeout (15 seconds)
    WEBSOCKET_BATCH_SIZE: int = 10  # Smaller batch size to reduce memory spikes
    WEBSOCKET_BATCH_DELAY_MS: float = 10.0  # Increased delay between WebSocket batches
    
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
    
    # Resource monitoring settings for HyperLiquid node coexistence
    ENABLE_RESOURCE_MONITORING: bool = True  # Enable resource monitoring
    MAX_CPU_USAGE_PERCENT: float = 30.0  # Maximum CPU usage (30% to leave 70% for HyperLiquid)
    MAX_MEMORY_USAGE_MB: int = 2048  # Maximum memory usage (2GB)
    RESOURCE_CHECK_INTERVAL_SEC: int = 60  # Check resources every 60 seconds
    THROTTLE_ON_HIGH_USAGE: bool = True  # Throttle processing when resources are high
    THROTTLE_FACTOR: float = 0.5  # Reduce processing by 50% when throttling
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
