"""Тесты для мониторинга NATS клиента."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

from src.nats.nats_client import NATSClient
from src.nats.monitoring import NATSMonitoring


class TestNATSMonitoring:
    """Тесты для NATSMonitoring."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.monitoring = NATSMonitoring()
    
    def test_initial_state(self):
        """Тест начального состояния мониторинга."""
        health = self.monitoring.get_health_status()
        metrics = self.monitoring.get_metrics()
        
        assert health["status"] == "unhealthy"
        assert health["is_connected"] is False
        assert health["is_active"] is False
        
        assert metrics["connection"]["uptime_seconds"] == 0
        assert metrics["messages"]["total_sent"] == 0
        assert metrics["messages"]["total_received"] == 0
        assert metrics["errors"]["total_errors"] == 0
        assert metrics["reconnections"]["total_reconnects"] == 0
    
    def test_connection_established(self):
        """Тест установки соединения."""
        self.monitoring.on_connection_established()
        
        health = self.monitoring.get_health_status()
        metrics = self.monitoring.get_metrics()
        
        assert health["status"] == "healthy"
        assert health["is_connected"] is True
        assert health["is_active"] is True
        assert health["uptime_seconds"] >= 0
        
        assert metrics["connection"]["is_connected"] is True
        assert metrics["connection"]["uptime_seconds"] >= 0
    
    def test_connection_lost(self):
        """Тест потери соединения."""
        self.monitoring.on_connection_established()
        self.monitoring.on_connection_lost()
        
        health = self.monitoring.get_health_status()
        
        assert health["status"] == "unhealthy"
        assert health["is_connected"] is False
        assert health["uptime_seconds"] == 0
    
    def test_message_sent(self):
        """Тест отправки сообщения."""
        self.monitoring.on_connection_established()
        self.monitoring.on_message_sent()
        
        metrics = self.monitoring.get_metrics()
        
        assert metrics["messages"]["total_sent"] == 1
        assert metrics["messages"]["total_processed"] == 1
        assert metrics["performance"]["messages_per_second"] >= 0
    
    def test_message_received(self):
        """Тест получения сообщения."""
        self.monitoring.on_connection_established()
        self.monitoring.on_message_received()
        
        metrics = self.monitoring.get_metrics()
        
        assert metrics["messages"]["total_received"] == 1
        assert metrics["messages"]["total_processed"] == 1
        assert metrics["performance"]["messages_per_second"] >= 0
    
    def test_error_handling(self):
        """Тест обработки ошибки."""
        self.monitoring.on_connection_established()
        self.monitoring.on_error("Test error")
        
        health = self.monitoring.get_health_status()
        metrics = self.monitoring.get_metrics()
        
        assert health["last_error"] == "Test error"
        assert health["last_error_time"] is not None
        
        assert metrics["errors"]["total_errors"] == 1
        assert metrics["errors"]["last_error"] == "Test error"
        assert metrics["errors"]["last_error_time"] is not None
    
    def test_reconnect(self):
        """Тест переподключения."""
        self.monitoring.on_connection_established()
        self.monitoring.on_reconnect()
        
        metrics = self.monitoring.get_metrics()
        
        assert metrics["reconnections"]["total_reconnects"] == 1
        assert metrics["connection"]["uptime_seconds"] >= 0
    
    def test_health_status_degraded(self):
        """Тест статуса degraded при неактивности."""
        self.monitoring.on_connection_established()
        
        # Симулируем неактивность (более 5 минут назад)
        old_time = datetime.now() - timedelta(minutes=10)
        self.monitoring._last_activity_time = old_time
        
        health = self.monitoring.get_health_status()
        
        assert health["status"] == "degraded"
        assert health["is_connected"] is True
        assert health["is_active"] is False
    
    def test_messages_per_second_calculation(self):
        """Тест расчета сообщений в секунду."""
        self.monitoring.on_connection_established()
        
        # Отправляем несколько сообщений
        for _ in range(5):
            self.monitoring.on_message_sent()
        
        # Ждем немного времени
        import time
        time.sleep(0.1)
        
        metrics = self.monitoring.get_metrics()
        
        assert metrics["performance"]["messages_per_second"] > 0
        assert metrics["messages"]["total_sent"] == 5
    
    def test_error_rate_calculation(self):
        """Тест расчета частоты ошибок."""
        self.monitoring.on_connection_established()
        
        # Отправляем сообщения и ошибки
        for _ in range(10):
            self.monitoring.on_message_sent()
        
        for _ in range(2):
            self.monitoring.on_error("Test error")
        
        metrics = self.monitoring.get_metrics()
        
        # Частота ошибок: 2 ошибки / 12 операций = 0.167
        expected_error_rate = 2 / 12
        assert abs(metrics["performance"]["error_rate"] - expected_error_rate) < 0.01
    
    def test_reset_metrics(self):
        """Тест сброса метрик."""
        self.monitoring.on_connection_established()
        self.monitoring.on_message_sent()
        self.monitoring.on_error("Test error")
        self.monitoring.on_reconnect()
        
        self.monitoring.reset_metrics()
        
        health = self.monitoring.get_health_status()
        metrics = self.monitoring.get_metrics()
        
        assert health["status"] == "unhealthy"
        assert health["is_connected"] is False
        
        assert metrics["connection"]["uptime_seconds"] == 0
        assert metrics["messages"]["total_sent"] == 0
        assert metrics["messages"]["total_received"] == 0
        assert metrics["errors"]["total_errors"] == 0
        assert metrics["reconnections"]["total_reconnects"] == 0


class TestNATSClientMonitoring:
    """Тесты для мониторинга в NATSClient."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.client = NATSClient()
        self.client._nc = AsyncMock()
        self.client._is_connected = True
    
    def test_get_health_status(self):
        """Тест получения статуса здоровья."""
        health = self.client.get_health_status()
        
        assert "status" in health
        assert "is_connected" in health
        assert "is_active" in health
        assert "uptime_seconds" in health
    
    def test_get_metrics(self):
        """Тест получения метрик."""
        metrics = self.client.get_metrics()
        
        assert "connection" in metrics
        assert "messages" in metrics
        assert "errors" in metrics
        assert "reconnections" in metrics
        assert "performance" in metrics
    
    def test_reset_metrics(self):
        """Тест сброса метрик."""
        # Добавляем некоторые метрики
        self.client._monitoring.on_connection_established()
        self.client._monitoring.on_message_sent()
        
        # Сбрасываем метрики
        self.client.reset_metrics()
        
        metrics = self.client.get_metrics()
        
        assert metrics["connection"]["uptime_seconds"] == 0
        assert metrics["messages"]["total_sent"] == 0
    
    @pytest.mark.asyncio
    async def test_monitoring_on_publish(self):
        """Тест мониторинга при публикации."""
        order_data = {
            "id": "12345",
            "symbol": "BTC",
            "side": "Bid",
            "price": 50000.0,
            "size": 1.5,
            "owner": "0x1234567890abcdef",
            "timestamp": datetime.now(),
            "status": "open"
        }
        
        # Настраиваем mock для успешной публикации
        self.client._nc.publish = AsyncMock()
        
        await self.client.publish_order_data(order_data)
        
        # Проверяем метрики
        metrics = self.client.get_metrics()
        assert metrics["messages"]["total_sent"] == 1
    
    @pytest.mark.asyncio
    async def test_monitoring_on_error(self):
        """Тест мониторинга при ошибке."""
        order_data = {
            "id": "12345",
            "symbol": "BTC",
            "side": "Bid",
            "price": 50000.0,
            "size": 1.5,
            "owner": "0x1234567890abcdef",
            "timestamp": datetime.now(),
            "status": "open"
        }
        
        # Настраиваем mock для ошибки
        self.client._nc.publish = AsyncMock(side_effect=Exception("Network error"))
        
        with pytest.raises(ConnectionError):
            await self.client.publish_order_data(order_data)
        
        # Проверяем метрики ошибок
        metrics = self.client.get_metrics()
        assert metrics["errors"]["total_errors"] > 0
        assert metrics["errors"]["last_error"] is not None
