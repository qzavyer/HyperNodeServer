"""Data models for HyperLiquid Node Parser."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class Order(BaseModel):
    """Order data model."""
    id: str = Field(..., description="Unique order ID")
    symbol: str = Field(..., description="Trading pair symbol")
    side: str = Field(..., pattern="^(Bid|Ask)$", description="Order side")
    price: float = Field(..., gt=0, description="Order price")
    size: float = Field(..., ge=0, description="Order size")
    owner: str = Field(..., description="Wallet address of order owner")
    timestamp: datetime = Field(..., description="Order timestamp")
    status: str = Field(..., pattern="^(open|filled|cancelled|triggered)$", description="Order status")

class LogEntry(BaseModel):
    """Log entry data model."""
    timestamp: datetime = Field(..., description="Log entry timestamp")
    level: str = Field(..., pattern="^(INFO|ERROR|DEBUG)$", description="Log level")
    class_name: str = Field(..., description="Class where log was created")
    message: str = Field(..., description="Log message")
    raw_data: str = Field(..., description="Original log line")

class ParsedData(BaseModel):
    """Parsed data result model."""
    orders: List[Order] = Field(..., description="List of parsed orders")
    metadata: dict = Field(..., description="Parsing metadata")
