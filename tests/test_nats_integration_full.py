"""Комплексные интеграционные тесты для полного цикла работы NATS."""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from src.nats.nats_client import NATSClient
from src.nats.auth import JWTAuth
from src.storage.models import Order


class TestNATSFullIntegration:
    """Комплексные тесты полного цикла работы NATS."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.client = NATSClient(max_retry_attempts=3, retry_delay=0.1)
        self.client._nc = AsyncMock()
        self.client._is_connected = True
    
    @pytest.mark.asyncio
    async def test_full_workflow_with_orders(self):
        """Тест полного цикла: подключение -> публикация -> мониторинг."""
        # 1. Подключение
        await self.client.connect("nats://localhost:4222")
        
        # 2. Проверяем статус подключения
        assert self.client.is_connected()
        assert self.client.is_authenticated() is False  # Без JWT
        
        # 3. Создаем тестовые ордера
        orders = [
            Order(
                id="order_1",
                symbol="BTC",
                side="Bid",
                price=50000.0,
                size=1.5,
                owner="0x1234567890abcdef",
                timestamp=datetime.now(),
                status="open"
            ),
            Order(
                id="order_2", 
                symbol="ETH",
                side="Ask",
                price=3000.0,
                size=10.0,
                owner="0xabcdef1234567890",
                timestamp=datetime.now(),
                status="open"
            )
        ]
        
        # 4. Публикуем ордера
        for order in orders:
            order_data = {
                "id": order.id,
                "symbol": order.symbol,
                "side": order.side,
                "price": order.price,
                "size": order.size,
                "owner": order.owner,
                "timestamp": order.timestamp,
                "status": order.status
            }
            await self.client.publish_order_data(order_data)
        
        # 5. Проверяем метрики
        metrics = self.client.get_metrics()
        assert metrics["messages"]["total_sent"] == 2
        assert metrics["connection"]["is_connected"] is True
        assert metrics["performance"]["messages_per_second"] >= 0
        
        # 6. Проверяем health status
        health = self.client.get_health_status()
        assert health["status"] == "healthy"
        assert health["is_connected"] is True
        assert health["is_active"] is True
        
        # 7. Отключаемся
        await self.client.disconnect()
        assert not self.client.is_connected()
    
    @pytest.mark.asyncio
    async def test_config_subscription_workflow(self):
        """Тест полного цикла подписки на конфигурации."""
        # 1. Подключаемся
        await self.client.connect("nats://localhost:4222")
        
        # 2. Настраиваем callback для конфигураций
        config_received = []
        
        def config_callback(config_data):
            config_received.append(config_data)
        
        # 3. Подписываемся на конфигурации
        await self.client.subscribe_to_config(config_callback)
        assert self.client.is_subscribed_to_config()
        
        # 4. Симулируем получение конфигурации
        test_config = {
            "parser": {
                "enabled": True,
                "batch_size": 100
            },
            "nats": {
                "enabled": True,
                "url": "nats://localhost:4222"
            }
        }
        
        # Симулируем обработку сообщения
        await self.client._handle_config_message(Mock(data=json.dumps(test_config).encode()))
        
        # 5. Проверяем, что конфигурация была получена
        assert len(config_received) == 1
        assert config_received[0] == test_config
        
        # 6. Проверяем метрики
        metrics = self.client.get_metrics()
        assert metrics["messages"]["total_received"] == 1
        
        # 7. Отключаемся
        await self.client.disconnect()
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Тест обработки ошибок и восстановления."""
        # 1. Подключаемся
        await self.client.connect("nats://localhost:4222")
        
        # 2. Симулируем ошибку публикации
        self.client._nc.publish = AsyncMock(side_effect=Exception("Network error"))
        
        order_data = {
            "id": "error_test",
            "symbol": "BTC",
            "side": "Bid",
            "price": 50000.0,
            "size": 1.0,
            "owner": "0x123",
            "timestamp": datetime.now(),
            "status": "open"
        }
        
        # 3. Пытаемся опубликовать (должна быть ошибка)
        with pytest.raises(ConnectionError):
            await self.client.publish_order_data(order_data)
        
        # 4. Проверяем метрики ошибок
        metrics = self.client.get_metrics()
        assert metrics["errors"]["total_errors"] > 0
        assert metrics["errors"]["last_error"] is not None
        
        # 5. Восстанавливаем соединение
        self.client._nc.publish = AsyncMock()
        await self.client._reconnect_with_retry()
        
        # 6. Проверяем, что переподключение зафиксировано
        metrics = self.client.get_metrics()
        assert metrics["reconnections"]["total_reconnects"] > 0
        
        # 7. Пробуем опубликовать снова
        await self.client.publish_order_data(order_data)
        
        # 8. Проверяем успешную публикацию
        metrics = self.client.get_metrics()
        assert metrics["messages"]["total_sent"] > 0
    
    @pytest.mark.asyncio
    async def test_jwt_authentication_workflow(self):
        """Тест полного цикла с JWT аутентификацией."""
        # 1. Создаем тестовый JWT файл
        test_jwt = {
            "user": "test_user",
            "jwt": "test_jwt_token",
            "seed": "test_seed"
        }
        
        with patch("builtins.open", Mock()) as mock_open:
            with patch("json.load", return_value=test_jwt):
                # 2. Загружаем JWT
                self.client.load_credentials("test_creds.json")
                assert self.client.is_authenticated()
                
                # 3. Подключаемся с JWT
                await self.client.connect("nats://localhost:4222", "test_creds.json")
                
                # 4. Проверяем подключение
                assert self.client.is_connected()
                assert self.client.is_authenticated()
                
                # 5. Публикуем данные
                order_data = {
                    "id": "jwt_test",
                    "symbol": "BTC",
                    "side": "Bid",
                    "price": 50000.0,
                    "size": 1.0,
                    "owner": "0x123",
                    "timestamp": datetime.now(),
                    "status": "open"
                }
                
                await self.client.publish_order_data(order_data)
                
                # 6. Проверяем метрики
                metrics = self.client.get_metrics()
                assert metrics["messages"]["total_sent"] == 1
                
                # 7. Отключаемся
                await self.client.disconnect()
    
    @pytest.mark.asyncio
    async def test_performance_metrics(self):
        """Тест производительности и метрик."""
        # 1. Подключаемся
        await self.client.connect("nats://localhost:4222")
        
        # 2. Публикуем много сообщений
        num_messages = 100
        for i in range(num_messages):
            order_data = {
                "id": f"perf_test_{i}",
                "symbol": "BTC",
                "side": "Bid",
                "price": 50000.0 + i,
                "size": 1.0,
                "owner": f"0x{i:040x}",
                "timestamp": datetime.now(),
                "status": "open"
            }
            await self.client.publish_order_data(order_data)
        
        # 3. Проверяем метрики производительности
        metrics = self.client.get_metrics()
        
        assert metrics["messages"]["total_sent"] == num_messages
        assert metrics["performance"]["messages_per_second"] > 0
        assert metrics["connection"]["uptime_seconds"] > 0
        
        # 4. Проверяем health status
        health = self.client.get_health_status()
        assert health["status"] == "healthy"
        assert health["is_active"] is True
        
        # 5. Отключаемся
        await self.client.disconnect()
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Тест использования как контекстного менеджера."""
        # 1. Используем как контекстный менеджер
        async with NATSClient() as client:
            # 2. Подключаемся
            await client.connect("nats://localhost:4222")
            
            # 3. Проверяем подключение
            assert client.is_connected()
            
            # 4. Публикуем данные
            order_data = {
                "id": "context_test",
                "symbol": "BTC",
                "side": "Bid",
                "price": 50000.0,
                "size": 1.0,
                "owner": "0x123",
                "timestamp": datetime.now(),
                "status": "open"
            }
            
            await client.publish_order_data(order_data)
            
            # 5. Проверяем метрики
            metrics = client.get_metrics()
            assert metrics["messages"]["total_sent"] == 1
        
        # 6. После выхода из контекста соединение должно быть закрыто
        # (в реальном коде это произойдет автоматически)
    
    def test_retry_statistics(self):
        """Тест статистики retry операций."""
        # 1. Создаем клиент с настройками retry
        client = NATSClient(max_retry_attempts=5, retry_delay=0.1)
        
        # 2. Проверяем начальные настройки
        stats = client.get_retry_stats()
        assert stats["max_retry_attempts"] == 5
        assert stats["retry_delay"] == 0.1
        assert stats["retry_count"] == 0
        assert stats["is_connected"] is False
        assert stats["is_authenticated"] is False
        
        # 3. Подключаемся
        client._is_connected = True
        client._auth._is_loaded = True
        
        # 4. Проверяем обновленную статистику
        stats = client.get_retry_stats()
        assert stats["is_connected"] is True
        assert stats["is_authenticated"] is True
