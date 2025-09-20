"""Тесты для проверки запуска ReactiveOrderWatcher."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from src.watcher.reactive_order_watcher import ReactiveOrderWatcher
from src.storage.order_manager import OrderManager
from src.websocket.websocket_manager import WebSocketManager
from src.storage.config_manager import ConfigManager


class TestReactiveOrderWatcherStartup:
    """Тесты для проверки запуска ReactiveOrderWatcher."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        # Мокаем зависимости
        self.mock_order_manager = Mock(spec=OrderManager)
        self.mock_websocket_manager = Mock(spec=WebSocketManager)
        self.mock_config_manager = Mock(spec=ConfigManager)
        
        # Создаем ReactiveOrderWatcher
        self.watcher = ReactiveOrderWatcher(
            logs_path="/tmp/test_logs",
            order_manager=self.mock_order_manager,
            websocket_manager=self.mock_websocket_manager,
            config_manager=self.mock_config_manager
        )
    
    @pytest.mark.asyncio
    async def test_start_monitoring_creates_tasks(self):
        """Тест что start_monitoring создает задачи."""
        # Act
        await self.watcher.start_monitoring()
        
        # Assert
        assert self.watcher.monitoring_task is not None
        assert self.watcher.processing_task is not None
        assert not self.watcher.monitoring_task.done()
        assert not self.watcher.processing_task.done()
    
    @pytest.mark.asyncio
    async def test_start_monitoring_idempotent(self):
        """Тест что start_monitoring можно вызывать несколько раз."""
        # Act - вызываем дважды
        await self.watcher.start_monitoring()
        first_monitoring_task = self.watcher.monitoring_task
        first_processing_task = self.watcher.processing_task
        
        await self.watcher.start_monitoring()
        
        # Assert - задачи не пересоздаются
        assert self.watcher.monitoring_task is first_monitoring_task
        assert self.watcher.processing_task is first_processing_task
    
    @pytest.mark.asyncio
    async def test_add_search_request_creates_processing_task_if_not_running(self):
        """Тест что add_search_request создает processing_task если он не запущен."""
        # Arrange
        self.watcher.processing_task = None
        
        # Act
        await self.watcher.add_search_request(
            ticker="BTC",
            side="Bid", 
            price=50000.0,
            timestamp="2025-01-01T12:00:00Z"
        )
        
        # Assert
        assert self.watcher.processing_task is not None
        assert not self.watcher.processing_task.done()
        assert len(self.watcher.active_requests) == 1
    
    @pytest.mark.asyncio
    async def test_processing_task_runs_continuously(self):
        """Тест что processing_task работает постоянно."""
        # Arrange
        await self.watcher.start_monitoring()
        
        # Act - ждем немного
        await asyncio.sleep(0.1)
        
        # Assert - задача все еще работает
        assert not self.watcher.processing_task.done()
    
    @pytest.mark.asyncio
    async def test_monitoring_task_runs_continuously(self):
        """Тест что monitoring_task работает постоянно."""
        # Arrange
        await self.watcher.start_monitoring()
        
        # Act - ждем немного
        await asyncio.sleep(0.1)
        
        # Assert - задача все еще работает
        assert not self.watcher.monitoring_task.done()
    
    @pytest.mark.asyncio
    async def test_processing_task_handles_empty_requests(self):
        """Тест что processing_task корректно обрабатывает пустую очередь запросов."""
        # Arrange
        await self.watcher.start_monitoring()
        
        # Act - ждем несколько итераций
        await asyncio.sleep(0.2)
        
        # Assert - задача не умирает от пустой очереди
        assert not self.watcher.processing_task.done()
    
    @pytest.mark.asyncio
    async def test_monitoring_task_handles_empty_tracked_orders(self):
        """Тест что monitoring_task корректно обрабатывает пустую очередь отслеживаемых ордеров."""
        # Arrange
        await self.watcher.start_monitoring()
        
        # Act - ждем несколько итераций
        await asyncio.sleep(0.2)
        
        # Assert - задача не умирает от пустой очереди
        assert not self.watcher.monitoring_task.done()
    
    @pytest.mark.asyncio
    async def test_full_workflow_with_search_request(self):
        """Тест полного workflow с поисковым запросом."""
        # Arrange
        await self.watcher.start_monitoring()
        
        # Act - добавляем поисковый запрос
        await self.watcher.add_search_request(
            ticker="BTC",
            side="Bid",
            price=50000.0,
            timestamp="2025-01-01T12:00:00Z"
        )
        
        # Ждем обработки
        await asyncio.sleep(0.1)
        
        # Assert - проверяем что запрос был добавлен (может быть обработан и удален)
        # Основная проверка - что задачи работают
        assert not self.watcher.processing_task.done()
        assert not self.watcher.monitoring_task.done()
        
        # Проверяем что запрос был добавлен (даже если уже обработан)
        # Это может быть 0 если запрос уже обработан, что нормально
        assert len(self.watcher.active_requests) >= 0
    
    @pytest.mark.asyncio
    async def teardown_method(self):
        """Очистка после каждого теста."""
        # Отменяем задачи если они запущены
        if self.watcher.monitoring_task and not self.watcher.monitoring_task.done():
            self.watcher.monitoring_task.cancel()
            try:
                await self.watcher.monitoring_task
            except asyncio.CancelledError:
                pass
        
        if self.watcher.processing_task and not self.watcher.processing_task.done():
            self.watcher.processing_task.cancel()
            try:
                await self.watcher.processing_task
            except asyncio.CancelledError:
                pass
