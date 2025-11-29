"""Тесты для обработки ошибок в NATS клиенте."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from src.nats.nats_client import NATSClient


class TestNATSErrorHandling:
    """Тесты для обработки ошибок в NATS."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.client = NATSClient(max_retry_attempts=3, retry_delay=0.1)
        self.client._nc = AsyncMock()
        self.client._is_connected = True
    
    def test_retry_stats_initial(self):
        """Тест начальной статистики retry."""
        stats = self.client.get_retry_stats()
        
        assert stats["retry_count"] == 0
        assert stats["max_retry_attempts"] == 3
        assert stats["retry_delay"] == 0.1
        assert stats["is_connected"] is True
        assert stats["is_authenticated"] is False
    
    @pytest.mark.asyncio
    async def test_publish_with_retry_success_first_attempt(self):
        """Тест успешной публикации с первой попытки."""
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
        
        await self.client._publish_with_retry(order_data, "parser_data.orders")
        
        # Проверяем, что publish был вызван
        self.client._nc.publish.assert_called_once()
        assert self.client._retry_count == 0
    
    @pytest.mark.asyncio
    async def test_publish_with_retry_success_after_failures(self):
        """Тест успешной публикации после нескольких неудачных попыток."""
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
        
        # Настраиваем mock для неудачных попыток, затем успеха
        call_count = 0
        async def mock_publish(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Network error")
            return None
        
        self.client._nc.publish = mock_publish
        
        await self.client._publish_with_retry(order_data, "parser_data.orders")
        
        # Проверяем, что publish был вызван 3 раза
        assert call_count == 3
        assert self.client._retry_count == 0
    
    @pytest.mark.asyncio
    async def test_publish_with_retry_all_attempts_failed(self):
        """Тест неудачной публикации после всех попыток."""
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
        
        # Настраиваем mock для постоянных ошибок
        self.client._nc.publish = AsyncMock(side_effect=Exception("Persistent error"))
        
        with pytest.raises(ConnectionError, match="Не удалось опубликовать данные после 3 попыток"):
            await self.client._publish_with_retry(order_data, "parser_data.orders")
    
    @pytest.mark.asyncio
    async def test_publish_with_retry_reconnection_on_disconnect(self):
        """Тест переподключения при отключении."""
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
        
        # Настраиваем mock для отключения, затем успеха
        call_count = 0
        async def mock_publish(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                self.client._is_connected = False  # Симулируем отключение
                raise Exception("Connection lost")
            return None
        
        self.client._nc.publish = mock_publish
        
        # Mock для переподключения
        with patch.object(self.client, '_reconnect_with_retry', new_callable=AsyncMock) as mock_reconnect:
            mock_reconnect.return_value = None
            
            await self.client._publish_with_retry(order_data, "parser_data.orders")
            
            # Проверяем, что переподключение было вызвано
            mock_reconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reconnect_with_retry_success(self):
        """Тест успешного переподключения."""
        # Mock для connect
        with patch.object(self.client, 'connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = None
            
            await self.client._reconnect_with_retry()
            
            # Проверяем, что connect был вызван
            mock_connect.assert_called_once()
            assert self.client._retry_count == 0
    
    @pytest.mark.asyncio
    async def test_reconnect_with_retry_all_attempts_failed(self):
        """Тест неудачного переподключения после всех попыток."""
        # Mock для connect с постоянными ошибками
        with patch.object(self.client, 'connect', new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = Exception("Connection failed")
            
            with pytest.raises(ConnectionError, match="Не удалось переподключиться после 3 попыток"):
                await self.client._reconnect_with_retry()
    
    @pytest.mark.asyncio
    async def test_reconnect_with_retry_restores_config_subscription(self):
        """Тест восстановления подписки на конфигурации при переподключении."""
        # Настраиваем callback
        callback_called = False
        def test_callback(config):
            nonlocal callback_called
            callback_called = True
        
        self.client._config_callback = test_callback
        
        # Mock для connect и subscribe_to_config
        with patch.object(self.client, 'connect', new_callable=AsyncMock) as mock_connect, \
             patch.object(self.client, 'subscribe_to_config', new_callable=AsyncMock) as mock_subscribe:
            
            mock_connect.return_value = None
            mock_subscribe.return_value = None
            
            await self.client._reconnect_with_retry()
            
            # Проверяем, что подписка была восстановлена
            mock_subscribe.assert_called_once_with(test_callback)
    
    @pytest.mark.asyncio
    async def test_publish_order_data_with_retry(self):
        """Тест публикации ордера с retry механизмом."""
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
        
        # Mock для _publish_with_retry
        with patch.object(self.client, '_publish_with_retry', new_callable=AsyncMock) as mock_publish:
            mock_publish.return_value = None
            
            await self.client.publish_order_data(order_data, "parser_data.orders")
            
            # Проверяем, что _publish_with_retry был вызван
            mock_publish.assert_called_once_with(order_data, "parser_data.orders")
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self):
        """Тест экспоненциальной задержки между попытками."""
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
        
        # Настраиваем mock для постоянных ошибок
        self.client._nc.publish = AsyncMock(side_effect=Exception("Network error"))
        
        # Засекаем время выполнения
        start_time = asyncio.get_event_loop().time()
        
        with pytest.raises(ConnectionError):
            await self.client._publish_with_retry(order_data, "parser_data.orders")
        
        end_time = asyncio.get_event_loop().time()
        execution_time = end_time - start_time
        
        # Проверяем, что время выполнения соответствует экспоненциальной задержке
        # 0.1 + 0.2 = 0.3 секунд (задержки между попытками, не после последней)
        expected_min_time = 0.1 + 0.2  # 0.3 секунд
        assert execution_time >= expected_min_time
    
    @pytest.mark.asyncio
    async def test_retry_count_reset_on_success(self):
        """Тест сброса счетчика retry при успехе."""
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
        
        # Устанавливаем начальный счетчик
        self.client._retry_count = 5
        
        # Настраиваем mock для успешной публикации
        self.client._nc.publish = AsyncMock()
        
        await self.client._publish_with_retry(order_data, "parser_data.orders")
        
        # Проверяем, что счетчик сброшен
        assert self.client._retry_count == 0
