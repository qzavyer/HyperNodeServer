"""Модуль для мониторинга и метрик NATS клиента."""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class NATSMonitoring:
    """Класс для мониторинга состояния NATS клиента."""
    
    def __init__(self):
        """Инициализация мониторинга."""
        self._connection_start_time: Optional[datetime] = None
        self._last_activity_time: Optional[datetime] = None
        self._total_messages_sent = 0
        self._total_messages_received = 0
        self._total_errors = 0
        self._total_reconnects = 0
        self._last_error: Optional[str] = None
        self._last_error_time: Optional[datetime] = None
    
    def on_connection_established(self) -> None:
        """Вызывается при установке соединения."""
        self._connection_start_time = datetime.now()
        self._last_activity_time = datetime.now()
        logger.info("NATS соединение установлено")
    
    def on_connection_lost(self) -> None:
        """Вызывается при потере соединения."""
        self._connection_start_time = None
        logger.warning("NATS соединение потеряно")
    
    def on_message_sent(self) -> None:
        """Вызывается при отправке сообщения."""
        self._total_messages_sent += 1
        self._last_activity_time = datetime.now()
        logger.debug(f"Сообщение отправлено (всего: {self._total_messages_sent})")
    
    def on_message_received(self) -> None:
        """Вызывается при получении сообщения."""
        self._total_messages_received += 1
        self._last_activity_time = datetime.now()
        logger.debug(f"Сообщение получено (всего: {self._total_messages_received})")
    
    def on_error(self, error: str) -> None:
        """Вызывается при ошибке."""
        self._total_errors += 1
        self._last_error = error
        self._last_error_time = datetime.now()
        logger.error(f"NATS ошибка: {error}")
    
    def on_reconnect(self) -> None:
        """Вызывается при переподключении."""
        self._total_reconnects += 1
        self._connection_start_time = datetime.now()
        self._last_activity_time = datetime.now()
        logger.info(f"NATS переподключение (всего: {self._total_reconnects})")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Получает статус здоровья NATS соединения.
        
        Returns:
            Словарь со статусом здоровья
        """
        now = datetime.now()
        
        # Проверяем, есть ли соединение
        is_connected = self._connection_start_time is not None
        
        # Проверяем активность (последняя активность не более 5 минут назад)
        is_active = False
        if self._last_activity_time:
            time_since_activity = now - self._last_activity_time
            is_active = time_since_activity < timedelta(minutes=5)
        
        # Определяем общий статус
        if is_connected and is_active:
            status = "healthy"
        elif is_connected and not is_active:
            status = "degraded"
        else:
            status = "unhealthy"
        
        # Время работы соединения
        uptime_seconds = 0
        if self._connection_start_time:
            uptime_seconds = (now - self._connection_start_time).total_seconds()
        
        return {
            "status": status,
            "is_connected": is_connected,
            "is_active": is_active,
            "uptime_seconds": uptime_seconds,
            "last_activity": self._last_activity_time.isoformat() if self._last_activity_time else None,
            "last_error": self._last_error,
            "last_error_time": self._last_error_time.isoformat() if self._last_error_time else None
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Получает метрики NATS клиента.
        
        Returns:
            Словарь с метриками
        """
        now = datetime.now()
        
        # Время работы соединения
        uptime_seconds = 0
        if self._connection_start_time:
            uptime_seconds = (now - self._connection_start_time).total_seconds()
        
        # Время с последней активности
        seconds_since_activity = None
        if self._last_activity_time:
            seconds_since_activity = (now - self._last_activity_time).total_seconds()
        
        # Время с последней ошибки
        seconds_since_error = None
        if self._last_error_time:
            seconds_since_error = (now - self._last_error_time).total_seconds()
        
        return {
            "connection": {
                "uptime_seconds": uptime_seconds,
                "is_connected": self._connection_start_time is not None,
                "connection_start": self._connection_start_time.isoformat() if self._connection_start_time else None,
                "last_activity": self._last_activity_time.isoformat() if self._last_activity_time else None,
                "seconds_since_activity": seconds_since_activity
            },
            "messages": {
                "total_sent": self._total_messages_sent,
                "total_received": self._total_messages_received,
                "total_processed": self._total_messages_sent + self._total_messages_received
            },
            "errors": {
                "total_errors": self._total_errors,
                "last_error": self._last_error,
                "last_error_time": self._last_error_time.isoformat() if self._last_error_time else None,
                "seconds_since_error": seconds_since_error
            },
            "reconnections": {
                "total_reconnects": self._total_reconnects
            },
            "performance": {
                "messages_per_second": self._calculate_messages_per_second(),
                "error_rate": self._calculate_error_rate()
            }
        }
    
    def _calculate_messages_per_second(self) -> float:
        """Вычисляет количество сообщений в секунду."""
        if not self._connection_start_time:
            return 0.0
        
        uptime_seconds = (datetime.now() - self._connection_start_time).total_seconds()
        if uptime_seconds <= 0:
            return 0.0
        
        total_messages = self._total_messages_sent + self._total_messages_received
        return total_messages / uptime_seconds
    
    def _calculate_error_rate(self) -> float:
        """Вычисляет частоту ошибок."""
        total_operations = self._total_messages_sent + self._total_messages_received + self._total_errors
        if total_operations <= 0:
            return 0.0
        
        return self._total_errors / total_operations
    
    def reset_metrics(self) -> None:
        """Сбрасывает все метрики."""
        self._connection_start_time = None
        self._last_activity_time = None
        self._total_messages_sent = 0
        self._total_messages_received = 0
        self._total_errors = 0
        self._total_reconnects = 0
        self._last_error = None
        self._last_error_time = None
        logger.info("Метрики NATS сброшены")
