"""Тесты для интеграции Parser с NATS."""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from src.parser.log_parser import LogParser
from src.notifications.order_notifier import OrderNotifier
from src.storage.models import Order
from src.nats.nats_client import NATSClient


class TestParserNATSIntegration:
    """Тесты для интеграции Parser с NATS."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.mock_nats_client = Mock(spec=NATSClient)
        self.mock_nats_client.publish_order_data = AsyncMock()
        self.mock_nats_client.is_connected.return_value = True
        
        self.parser = LogParser(nats_client=self.mock_nats_client)
        
        # Mock для OrderNotifier
        self.mock_websocket_manager = Mock()
        self.mock_config_manager = Mock()
        self.notifier = OrderNotifier(
            websocket_manager=self.mock_websocket_manager,
            config_manager=self.mock_config_manager,
            nats_client=self.mock_nats_client
        )
    
    def test_parser_nats_enabled(self):
        """Тест проверки включения NATS в Parser."""
        assert self.parser.is_nats_enabled()
        assert self.parser.nats_client == self.mock_nats_client
    
    def test_parser_nats_disabled(self):
        """Тест проверки отключения NATS в Parser."""
        parser_no_nats = LogParser()
        assert not parser_no_nats.is_nats_enabled()
        assert parser_no_nats.nats_client is None
    
    @pytest.mark.asyncio
    async def test_send_order_to_nats_success(self):
        """Тест успешной отправки ордера в NATS."""
        order = Order(
            id="12345",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.5,
            owner="0x1234567890abcdef",
            timestamp=datetime.now(),
            status="open"
        )
        
        await self.parser._send_order_to_nats(order)
        
        # Проверяем, что publish_order_data был вызван
        self.mock_nats_client.publish_order_data.assert_called_once()
        call_args = self.mock_nats_client.publish_order_data.call_args
        
        # Проверяем данные ордера
        order_data = call_args[0][0]
        assert order_data["id"] == "12345"
        assert order_data["symbol"] == "BTC"
        assert order_data["side"] == "Bid"
        assert order_data["price"] == 50000.0
        assert order_data["size"] == 1.5
        assert order_data["owner"] == "0x1234567890abcdef"
        assert order_data["status"] == "open"
        
        # Проверяем топик
        assert call_args[0][1] == "parser_data.orders"
    
    @pytest.mark.asyncio
    async def test_send_order_to_nats_disabled(self):
        """Тест отправки ордера при отключенном NATS."""
        parser_no_nats = LogParser()
        
        order = Order(
            id="12345",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.5,
            owner="0x1234567890abcdef",
            timestamp=datetime.now(),
            status="open"
        )
        
        # Не должно вызывать исключение
        await parser_no_nats._send_order_to_nats(order)
    
    @pytest.mark.asyncio
    async def test_send_orders_batch_to_nats_success(self):
        """Тест успешной отправки батча ордеров в NATS."""
        orders = [
            Order(
                id="1",
                symbol="BTC",
                side="Bid",
                price=50000.0,
                size=1.0,
                owner="0x111",
                timestamp=datetime.now(),
                status="open"
            ),
            Order(
                id="2",
                symbol="ETH",
                side="Ask",
                price=3000.0,
                size=2.0,
                owner="0x222",
                timestamp=datetime.now(),
                status="open"
            )
        ]
        
        await self.parser._send_orders_batch_to_nats(orders)
        
        # Проверяем, что publish_order_data был вызван для каждого ордера
        assert self.mock_nats_client.publish_order_data.call_count == 2
    
    @pytest.mark.asyncio
    async def test_send_orders_batch_to_nats_empty(self):
        """Тест отправки пустого батча ордеров."""
        await self.parser._send_orders_batch_to_nats([])
        
        # publish_order_data не должен быть вызван
        self.mock_nats_client.publish_order_data.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_send_order_to_nats_error_handling(self):
        """Тест обработки ошибок при отправке в NATS."""
        # Настраиваем mock для вызова исключения
        self.mock_nats_client.publish_order_data.side_effect = Exception("NATS error")
        
        order = Order(
            id="12345",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.5,
            owner="0x1234567890abcdef",
            timestamp=datetime.now(),
            status="open"
        )
        
        # Не должно вызывать исключение, только логировать ошибку
        await self.parser._send_order_to_nats(order)
    
    def test_notifier_nats_enabled(self):
        """Тест проверки включения NATS в OrderNotifier."""
        assert self.notifier.is_nats_enabled()
        assert self.notifier.nats_client == self.mock_nats_client
    
    def test_notifier_nats_disabled(self):
        """Тест проверки отключения NATS в OrderNotifier."""
        notifier_no_nats = OrderNotifier(
            websocket_manager=self.mock_websocket_manager,
            config_manager=self.mock_config_manager
        )
        assert not notifier_no_nats.is_nats_enabled()
        assert notifier_no_nats.nats_client is None
    
    @pytest.mark.asyncio
    async def test_notifier_send_order_to_nats_success(self):
        """Тест успешной отправки ордера в NATS через OrderNotifier."""
        order = Order(
            id="12345",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.5,
            owner="0x1234567890abcdef",
            timestamp=datetime.now(),
            status="open"
        )
        
        await self.notifier._send_order_to_nats(order)
        
        # Проверяем, что publish_order_data был вызван
        self.mock_nats_client.publish_order_data.assert_called_once()
        call_args = self.mock_nats_client.publish_order_data.call_args
        
        # Проверяем данные ордера
        order_data = call_args[0][0]
        assert order_data["id"] == "12345"
        assert order_data["symbol"] == "BTC"
        assert call_args[0][1] == "parser_data.orders"
    
    @pytest.mark.asyncio
    async def test_notifier_send_order_to_nats_disabled(self):
        """Тест отправки ордера при отключенном NATS в OrderNotifier."""
        notifier_no_nats = OrderNotifier(
            websocket_manager=self.mock_websocket_manager,
            config_manager=self.mock_config_manager
        )
        
        order = Order(
            id="12345",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.5,
            owner="0x1234567890abcdef",
            timestamp=datetime.now(),
            status="open"
        )
        
        # Не должно вызывать исключение
        await notifier_no_nats._send_order_to_nats(order)
    
    def test_notifier_get_notification_stats_with_nats(self):
        """Тест получения статистики уведомлений с NATS."""
        stats = self.notifier.get_notification_stats()
        
        assert "nats_enabled" in stats
        assert "nats_connected" in stats
        assert stats["nats_enabled"] is True
        assert stats["nats_connected"] is True
    
    def test_notifier_get_notification_stats_without_nats(self):
        """Тест получения статистики уведомлений без NATS."""
        notifier_no_nats = OrderNotifier(
            websocket_manager=self.mock_websocket_manager,
            config_manager=self.mock_config_manager
        )
        
        stats = notifier_no_nats.get_notification_stats()
        
        assert "nats_enabled" in stats
        assert "nats_connected" in stats
        assert stats["nats_enabled"] is False
        assert stats["nats_connected"] is False
    
    @pytest.mark.asyncio
    async def test_notifier_send_order_to_nats_error_handling(self):
        """Тест обработки ошибок при отправке в NATS через OrderNotifier."""
        # Настраиваем mock для вызова исключения
        self.mock_nats_client.publish_order_data.side_effect = Exception("NATS error")
        
        order = Order(
            id="12345",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.5,
            owner="0x1234567890abcdef",
            timestamp=datetime.now(),
            status="open"
        )
        
        # Не должно вызывать исключение, только логировать ошибку
        await self.notifier._send_order_to_nats(order)
