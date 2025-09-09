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
    CHUNK_SIZE_BYTES: int = 8192  # File reading chunk size
    BATCH_SIZE: int = 1000  # Orders processing batch size
    PROCESSING_TIMEOUT_PER_GB: int = 5  # Seconds per GB for file processing
    
    # WebSocket settings
    WEBSOCKET_PING_INTERVAL: int = 20  # Ping interval in seconds
    WEBSOCKET_PING_TIMEOUT: int = 20   # Ping timeout in seconds
    WEBSOCKET_CLOSE_TIMEOUT: int = 10  # Close timeout in seconds
    
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
