"""Тесты для новой логики поиска ордеров в ReactiveOrderWatcher."""

import pytest
import asyncio
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone

from src.watcher.reactive_order_watcher import ReactiveOrderWatcher
from src.storage.models import Order, Config, SymbolConfig
from src.models.tracked_order import OrderSearchCriteria


class TestNewSearchLogic:
    """Тесты для новой логики поиска ордеров."""

    @pytest.fixture
    def temp_dir(self):
        """Создает временную директорию для тестов."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def mock_order_manager(self):
        """Создает мок OrderManager."""
        manager = Mock()
        manager.update_orders_batch_async = AsyncMock()
        return manager

    @pytest.fixture
    def mock_websocket_manager(self):
        """Создает мок WebSocketManager."""
        manager = Mock()
        manager.broadcast_order_update = AsyncMock()
        return manager

    @pytest.fixture
    def mock_config_manager(self):
        """Создает мок ConfigManager."""
        manager = Mock()
        config = Config(
            node_logs_path="/tmp/logs",
            cleanup_interval_hours=2,
            api_host="0.0.0.0",
            api_port=8000,
            log_level="DEBUG",
            log_file_path="/tmp/app.log",
            log_max_size_mb=100,
            log_retention_days=7,
            data_dir="/tmp/data",
            config_file_path="/tmp/config.json",
            max_orders_per_request=1000,
            file_read_retry_attempts=3,
            file_read_retry_delay=1.0,
            symbols_config=[
                SymbolConfig(symbol="PAMP", min_liquidity=100.0, price_deviation=0.01),
                SymbolConfig(symbol="SOL", min_liquidity=1000.0, price_deviation=0.01),
                SymbolConfig(symbol="BTC", min_liquidity=50000.0, price_deviation=0.01)
            ]
        )
        manager.get_config.return_value = config
        return manager

    @pytest.fixture
    def reactive_watcher(self, temp_dir, mock_order_manager, mock_websocket_manager, mock_config_manager):
        """Создает экземпляр ReactiveOrderWatcher для тестов."""
        watcher = ReactiveOrderWatcher(
            logs_path=temp_dir,
            order_manager=mock_order_manager,
            websocket_manager=mock_websocket_manager,
            config_manager=mock_config_manager
        )
        return watcher

    @pytest.mark.asyncio
    async def test_add_search_request(self, reactive_watcher):
        """Тест добавления запроса на поиск."""
        # Добавляем запрос
        await reactive_watcher.add_search_request(
            ticker="PAMP",
            side="Bid",
            price=0.081,
            timestamp="2025-01-15T20:10:12Z"
        )
        
        # Проверяем, что запрос добавлен
        assert len(reactive_watcher.active_requests) == 1
        request = reactive_watcher.active_requests[0]
        assert request['ticker'] == "PAMP"
        assert request['side'] == "Bid"
        assert request['price'] == 0.081
        assert request['tolerance'] == 0.000001

    @pytest.mark.asyncio
    async def test_check_order_configuration(self, reactive_watcher):
        """Тест проверки конфигурации ордера."""
        # Ордер с достаточной ликвидностью
        order1 = Order(
            id="order_1",
            symbol="PAMP",
            side="Bid",
            price=0.081,
            size=1500.0,  # 0.081 * 1500 = 121.5 > 100
            owner="0x123",
            timestamp=datetime.now(timezone.utc),
            status="open"
        )
        
        # Ордер с недостаточной ликвидностью
        order2 = Order(
            id="order_2",
            symbol="PAMP",
            side="Bid",
            price=0.081,
            size=100.0,  # 0.081 * 100 = 8.1 < 100
            owner="0x123",
            timestamp=datetime.now(timezone.utc),
            status="open"
        )
        
        # Ордер для неизвестного символа
        order3 = Order(
            id="order_3",
            symbol="UNKNOWN",
            side="Bid",
            price=1.0,
            size=1000.0,
            owner="0x123",
            timestamp=datetime.now(timezone.utc),
            status="open"
        )
        
        # Проверяем конфигурацию
        assert await reactive_watcher._check_order_configuration(order1) == True
        assert await reactive_watcher._check_order_configuration(order2) == False
        assert await reactive_watcher._check_order_configuration(order3) == False

    @pytest.mark.asyncio
    async def test_find_matching_requests(self, reactive_watcher):
        """Тест поиска соответствующих запросов."""
        # Добавляем запросы
        await reactive_watcher.add_search_request(
            ticker="PAMP",
            side="Bid",
            price=0.081,
            timestamp="2025-01-15T20:10:12Z"
        )
        
        await reactive_watcher.add_search_request(
            ticker="SOL",
            side="Ask",
            price=125.2,
            timestamp="2025-01-15T20:10:13Z"
        )
        
        # Создаем ордер, который соответствует первому запросу
        order = Order(
            id="order_1",
            symbol="PAMP",
            side="Bid",
            price=0.081,
            size=1500.0,
            owner="0x123",
            timestamp=datetime(2025, 1, 15, 20, 10, 11, tzinfo=timezone.utc),  # За 1 секунду до запроса
            status="open"
        )
        
        # Ищем соответствующие запросы
        matching_requests = await reactive_watcher._find_matching_requests(order)
        
        # Должен найти только один запрос (PAMP)
        assert len(matching_requests) == 1
        assert matching_requests[0]['ticker'] == "PAMP"

    @pytest.mark.asyncio
    async def test_find_matching_requests_time_filter(self, reactive_watcher):
        """Тест фильтрации по времени."""
        # Добавляем запрос
        await reactive_watcher.add_search_request(
            ticker="PAMP",
            side="Bid",
            price=0.081,
            timestamp="2025-01-15T20:10:12Z"
        )
        
        # Ордер слишком старый (за 3 секунды до запроса)
        old_order = Order(
            id="old_order",
            symbol="PAMP",
            side="Bid",
            price=0.081,
            size=1500.0,
            owner="0x123",
            timestamp=datetime(2025, 1, 15, 20, 10, 9, tzinfo=timezone.utc),  # За 3 секунды
            status="open"
        )
        
        # Ордер подходящий по времени (за 1 секунду до запроса)
        good_order = Order(
            id="good_order",
            symbol="PAMP",
            side="Bid",
            price=0.081,
            size=1500.0,
            owner="0x123",
            timestamp=datetime(2025, 1, 15, 20, 10, 11, tzinfo=timezone.utc),  # За 1 секунду
            status="open"
        )
        
        # Проверяем фильтрацию
        old_matching = await reactive_watcher._find_matching_requests(old_order)
        good_matching = await reactive_watcher._find_matching_requests(good_order)
        
        assert len(old_matching) == 0  # Слишком старый
        assert len(good_matching) == 1  # Подходящий

    @pytest.mark.asyncio
    async def test_select_best_order(self, reactive_watcher):
        """Тест выбора лучшего ордера."""
        # Создаем запрос
        request = {
            'ticker': 'PAMP',
            'side': 'Bid',
            'price': 0.081,
            'tolerance': 0.000001
        }
        
        # Создаем ордера с разной ликвидностью
        order1 = Order(
            id="order_1",
            symbol="PAMP",
            side="Bid",
            price=0.081,
            size=1000.0,  # Ликвидность: 81
            owner="0x123",
            timestamp=datetime.now(timezone.utc),
            status="open"
        )
        
        order2 = Order(
            id="order_2",
            symbol="PAMP",
            side="Bid",
            price=0.081,
            size=2000.0,  # Ликвидность: 162 (максимальная)
            owner="0x456",
            timestamp=datetime.now(timezone.utc),
            status="open"
        )
        
        order3 = Order(
            id="order_3",
            symbol="PAMP",
            side="Bid",
            price=0.081,
            size=1500.0,  # Ликвидность: 121.5
            owner="0x789",
            timestamp=datetime.now(timezone.utc),
            status="open"
        )
        
        orders = [order1, order2, order3]
        
        # Выбираем лучший ордер
        best_order = await reactive_watcher._select_best_order(orders, request)
        
        # Должен выбрать order2 с максимальной ликвидностью
        assert best_order.id == "order_2"
        assert best_order.size == 2000.0

    @pytest.mark.asyncio
    async def test_select_best_order_closed_orders(self, reactive_watcher):
        """Тест выбора лучшего ордера среди закрытых."""
        # Создаем запрос
        request = {
            'ticker': 'PAMP',
            'side': 'Bid',
            'price': 0.081,
            'tolerance': 0.000001
        }
        
        # Создаем закрытые ордера
        closed_order1 = Order(
            id="closed_1",
            symbol="PAMP",
            side="Bid",
            price=0.081,
            size=1000.0,
            owner="0x123",
            timestamp=datetime.now(timezone.utc),
            status="filled"
        )
        
        closed_order2 = Order(
            id="closed_2",
            symbol="PAMP",
            side="Bid",
            price=0.081,
            size=2000.0,
            owner="0x456",
            timestamp=datetime.now(timezone.utc),
            status="canceled"
        )
        
        # Добавляем open ордер
        open_order = Order(
            id="open_1",
            symbol="PAMP",
            side="Bid",
            price=0.081,
            size=1500.0,
            owner="0x789",
            timestamp=datetime.now(timezone.utc),
            status="open"
        )
        
        orders = [closed_order1, closed_order2, open_order]
        
        # Выбираем лучший ордер
        best_order = await reactive_watcher._select_best_order(orders, request)
        
        # Должен выбрать open ордер
        assert best_order.id == "open_1"
        assert best_order.status == "open"

    @pytest.mark.asyncio
    async def test_add_order_to_cache(self, reactive_watcher):
        """Тест добавления ордера в кэш."""
        order = Order(
            id="order_1",
            symbol="PAMP",
            side="Bid",
            price=0.081,
            size=1500.0,
            owner="0x123",
            timestamp=datetime.now(timezone.utc),
            status="open"
        )
        
        # Добавляем в кэш
        await reactive_watcher._add_order_to_cache(order)
        
        # Проверяем, что ордер добавлен
        assert "PAMP" in reactive_watcher.orders_cache
        assert len(reactive_watcher.orders_cache["PAMP"]) == 1
        assert reactive_watcher.orders_cache["PAMP"][0].id == "order_1"

    @pytest.mark.asyncio
    async def test_invalid_timestamp_format(self, reactive_watcher):
        """Тест обработки неверного формата времени."""
        # Добавляем запрос с неверным форматом времени
        await reactive_watcher.add_search_request(
            ticker="PAMP",
            side="Bid",
            price=0.081,
            timestamp="invalid_timestamp"
        )
        
        # Запрос не должен быть добавлен
        assert len(reactive_watcher.active_requests) == 0
