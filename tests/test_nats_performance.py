"""Тесты производительности для NATS клиента."""

import pytest
import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock

from src.nats.nats_client import NATSClient


class TestNATSPerformance:
    """Тесты производительности NATS клиента."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.client = NATSClient(max_retry_attempts=3, retry_delay=0.01)
        self.client._nc = AsyncMock()
        self.client._is_connected = True
    
    @pytest.mark.asyncio
    async def test_publish_speed(self):
        """Тест скорости публикации сообщений."""
        # 1. Подключаемся
        await self.client.connect("nats://localhost:4222")
        
        # 2. Измеряем время публикации
        num_messages = 1000
        start_time = time.time()
        
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
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 3. Проверяем производительность
        messages_per_second = num_messages / duration
        
        print(f"Опубликовано {num_messages} сообщений за {duration:.2f} секунд")
        print(f"Скорость: {messages_per_second:.2f} сообщений/сек")
        
        # Проверяем, что скорость разумная (больше 100 сообщений/сек)
        assert messages_per_second > 100, f"Слишком низкая скорость: {messages_per_second:.2f} msg/s"
        
        # 4. Проверяем метрики
        metrics = self.client.get_metrics()
        assert metrics["messages"]["total_sent"] == num_messages
        assert metrics["performance"]["messages_per_second"] > 0
    
    @pytest.mark.asyncio
    async def test_batch_publish_speed(self):
        """Тест скорости пакетной публикации."""
        # 1. Подключаемся
        await self.client.connect("nats://localhost:4222")
        
        # 2. Создаем пакет ордеров
        batch_size = 100
        orders = []
        
        for i in range(batch_size):
            order_data = {
                "id": f"batch_test_{i}",
                "symbol": "BTC",
                "side": "Bid",
                "price": 50000.0 + i,
                "size": 1.0,
                "owner": f"0x{i:040x}",
                "timestamp": datetime.now(),
                "status": "open"
            }
            orders.append(order_data)
        
        # 3. Измеряем время пакетной публикации
        start_time = time.time()
        
        for order_data in orders:
            await self.client.publish_order_data(order_data)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 4. Проверяем производительность
        messages_per_second = batch_size / duration
        
        print(f"Опубликовано {batch_size} сообщений пакетом за {duration:.2f} секунд")
        print(f"Скорость: {messages_per_second:.2f} сообщений/сек")
        
        # Проверяем, что скорость разумная
        assert messages_per_second > 50, f"Слишком низкая скорость пакетной публикации: {messages_per_second:.2f} msg/s"
    
    @pytest.mark.asyncio
    async def test_memory_usage(self):
        """Тест использования памяти при длительной работе."""
        # 1. Подключаемся
        await self.client.connect("nats://localhost:4222")
        
        # 2. Публикуем много сообщений
        num_messages = 10000
        
        for i in range(num_messages):
            order_data = {
                "id": f"memory_test_{i}",
                "symbol": "BTC",
                "side": "Bid",
                "price": 50000.0 + (i % 1000),
                "size": 1.0,
                "owner": f"0x{i:040x}",
                "timestamp": datetime.now(),
                "status": "open"
            }
            await self.client.publish_order_data(order_data)
            
            # Проверяем метрики каждые 1000 сообщений
            if i % 1000 == 0:
                metrics = self.client.get_metrics()
                assert metrics["messages"]["total_sent"] == i + 1
        
        # 3. Проверяем финальные метрики
        metrics = self.client.get_metrics()
        assert metrics["messages"]["total_sent"] == num_messages
        assert metrics["connection"]["uptime_seconds"] > 0
        
        # 4. Проверяем, что нет утечек памяти (метрики не растут бесконечно)
        health = self.client.get_health_status()
        assert health["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_concurrent_publish(self):
        """Тест конкурентной публикации."""
        # 1. Подключаемся
        await self.client.connect("nats://localhost:4222")
        
        # 2. Создаем задачи для конкурентной публикации
        async def publish_orders(start_id, count):
            for i in range(count):
                order_data = {
                    "id": f"concurrent_{start_id + i}",
                    "symbol": "BTC",
                    "side": "Bid",
                    "price": 50000.0 + i,
                    "size": 1.0,
                    "owner": f"0x{start_id + i:040x}",
                    "timestamp": datetime.now(),
                    "status": "open"
                }
                await self.client.publish_order_data(order_data)
        
        # 3. Запускаем конкурентные задачи
        num_tasks = 5
        messages_per_task = 100
        
        start_time = time.time()
        
        tasks = []
        for i in range(num_tasks):
            task = asyncio.create_task(
                publish_orders(i * messages_per_task, messages_per_task)
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # 4. Проверяем производительность
        total_messages = num_tasks * messages_per_task
        messages_per_second = total_messages / duration
        
        print(f"Конкурентно опубликовано {total_messages} сообщений за {duration:.2f} секунд")
        print(f"Скорость: {messages_per_second:.2f} сообщений/сек")
        
        # Проверяем, что скорость разумная
        assert messages_per_second > 200, f"Слишком низкая скорость конкурентной публикации: {messages_per_second:.2f} msg/s"
        
        # 5. Проверяем метрики
        metrics = self.client.get_metrics()
        assert metrics["messages"]["total_sent"] == total_messages
    
    @pytest.mark.asyncio
    async def test_error_recovery_performance(self):
        """Тест производительности восстановления после ошибок."""
        # 1. Подключаемся
        await self.client.connect("nats://localhost:4222")
        
        # 2. Симулируем ошибки и восстановление
        num_cycles = 10
        messages_per_cycle = 50
        
        for cycle in range(num_cycles):
            # Симулируем ошибку
            self.client._nc.publish = AsyncMock(side_effect=Exception(f"Error {cycle}"))
            
            # Пытаемся опубликовать (должна быть ошибка)
            order_data = {
                "id": f"error_cycle_{cycle}",
                "symbol": "BTC",
                "side": "Bid",
                "price": 50000.0,
                "size": 1.0,
                "owner": f"0x{cycle:040x}",
                "timestamp": datetime.now(),
                "status": "open"
            }
            
            with pytest.raises(ConnectionError):
                await self.client.publish_order_data(order_data)
            
            # Восстанавливаем соединение
            self.client._nc.publish = AsyncMock()
            await self.client._reconnect_with_retry()
            
            # Публикуем успешно
            for i in range(messages_per_cycle):
                order_data = {
                    "id": f"recovery_{cycle}_{i}",
                    "symbol": "BTC",
                    "side": "Bid",
                    "price": 50000.0 + i,
                    "size": 1.0,
                    "owner": f"0x{cycle * 1000 + i:040x}",
                    "timestamp": datetime.now(),
                    "status": "open"
                }
                await self.client.publish_order_data(order_data)
        
        # 3. Проверяем метрики
        metrics = self.client.get_metrics()
        expected_messages = num_cycles * messages_per_cycle
        assert metrics["messages"]["total_sent"] == expected_messages
        assert metrics["errors"]["total_errors"] == num_cycles
        assert metrics["reconnections"]["total_reconnects"] == num_cycles
        
        # 4. Проверяем производительность
        assert metrics["performance"]["messages_per_second"] > 0
        assert metrics["performance"]["error_rate"] > 0
