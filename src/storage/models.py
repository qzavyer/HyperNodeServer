"""Data models for HyperLiquid Node Parser."""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class Order(BaseModel):
    """Order model."""
    id: str = Field(..., description="Unique order ID")
    symbol: str = Field(..., description="Trading pair symbol")
    side: str = Field(..., pattern="^(Bid|Ask)$", description="Order side")
    price: float = Field(..., gt=0, description="Order price")
    size: float = Field(..., ge=0, description="Order size")
    owner: str = Field(..., description="Wallet address of order owner")
    timestamp: datetime = Field(..., description="Order timestamp")
    status: str = Field(..., pattern="^(open|filled|cancelled|triggered)$", description="Order status")

class LogEntry(BaseModel):
    """Log entry model."""
    timestamp: datetime = Field(..., description="Log timestamp")
    level: str = Field(..., pattern="^(DEBUG|INFO|WARNING|ERROR)$", description="Log level")
    class_name: str = Field(..., description="Class name where log was created")
    message: str = Field(..., description="Log message")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Raw log data")

class ParsedData(BaseModel):
    """Parsed data model."""
    orders: list[Order] = Field(default_factory=list, description="List of parsed orders")
    log_entries: list[LogEntry] = Field(default_factory=list, description="List of log entries")

class Config(BaseModel):
    """Configuration model."""
    node_logs_path: str = Field(..., description="Path to node logs directory")
    cleanup_interval_hours: int = Field(..., ge=1, le=168, description="Cleanup interval in hours")
    api_host: str = Field(..., description="API host address")
    api_port: int = Field(..., ge=1, le=65535, description="API port")
    log_level: str = Field(..., pattern="^(DEBUG|INFO|WARNING|ERROR)$", description="Log level")
    log_file_path: str = Field(..., description="Log file path")
    log_max_size_mb: int = Field(..., ge=1, le=1000, description="Maximum log file size in MB")
    log_retention_days: int = Field(..., ge=1, le=365, description="Log retention days")
    data_dir: str = Field(..., description="Data directory")
    config_file_path: str = Field(..., description="Configuration file path")
    max_orders_per_request: int = Field(..., ge=1, le=10000, description="Maximum orders per request")
    file_read_retry_attempts: int = Field(..., ge=1, le=10, description="File read retry attempts")
    file_read_retry_delay: float = Field(..., ge=0.1, le=10.0, description="File read retry delay in seconds")
    min_liquidity_by_symbol: Dict[str, float] = Field(default_factory=dict, description="Minimum liquidity by symbol")
    supported_symbols: list[str] = Field(default_factory=list, description="List of supported symbols")
