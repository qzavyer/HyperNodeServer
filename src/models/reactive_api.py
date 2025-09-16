"""Pydantic модели для ReactiveOrderWatcher API."""

from pydantic import BaseModel, Field
from typing import Optional


class OrderSearchRequest(BaseModel):
    """Запрос на поиск ордеров."""
    ticker: str = Field(..., description="Символ торговой пары (например, BTC)")
    side: str = Field(..., pattern="^(Bid|Ask)$", description="Сторона ордера (Bid или Ask)")
    price: float = Field(..., gt=0, description="Цена ордера")
    timestamp: str = Field(..., description="Время сигнала в UTC (ISO format)")
    tolerance: float = Field(default=0.000001, ge=0, description="Допустимое отклонение цены")


class OrderTrackRequest(BaseModel):
    """Запрос на отслеживание ордера."""
    order_id: str = Field(..., description="ID ордера для отслеживания")


class ReactiveWatcherStatus(BaseModel):
    """Статус ReactiveOrderWatcher."""
    is_initialized: bool = Field(..., description="Инициализирован ли watcher")
    current_file: Optional[str] = Field(None, description="Текущий файл")
    tracked_orders_count: int = Field(..., description="Количество отслеживаемых ордеров")
    cached_orders_count: int = Field(..., description="Количество ордеров в кэше")
    monitoring_active: bool = Field(..., description="Активен ли мониторинг")
    cache_duration_seconds: int = Field(..., description="Длительность кэша в секундах")
    monitoring_interval_ms: float = Field(..., description="Интервал мониторинга в миллисекундах")
