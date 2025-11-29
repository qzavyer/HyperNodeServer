"""Тесты для публикации данных в NATS."""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

from src.nats.nats_client import NATSClient


class TestNATSPublish:
    """Тесты для публикации данных в NATS."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.client = NATSClient()
        self.client._nc = AsyncMock()
        self.client._is_connected = True
    
    def test_validate_order_data_success(self):
        """Тест успешной валидации данных ордера."""
        valid_order = {
            "id": "12345",
            "symbol": "BTC",
            "side": "Bid",
            "price": 50000.0,
            "size": 1.5,
            "owner": "0x1234567890abcdef",
            "timestamp": datetime.now(),
            "status": "open"
        }
        
        # Не должно вызывать исключение
        self.client._validate_order_data(valid_order)
    
    def test_validate_order_data_missing_field(self):
        """Тест валидации с отсутствующим полем."""
        invalid_order = {
            "id": "12345",
            "symbol": "BTC",
            "side": "Bid",
            "price": 50000.0,
            "size": 1.5,
            "owner": "0x1234567890abcdef",
            "timestamp": datetime.now()
            # Отсутствует status
        }
        
        with pytest.raises(ValueError, match="Отсутствует обязательное поле: status"):
            self.client._validate_order_data(invalid_order)
    
    def test_validate_order_data_invalid_side(self):
        """Тест валидации с неверным side."""
        invalid_order = {
            "id": "12345",
            "symbol": "BTC",
            "side": "invalid",
            "price": 50000.0,
            "size": 1.5,
            "owner": "0x1234567890abcdef",
            "timestamp": datetime.now(),
            "status": "open"
        }
        
        with pytest.raises(ValueError, match="Поле 'side' должно быть 'Bid' или 'Ask'"):
            self.client._validate_order_data(invalid_order)
    
    def test_validate_order_data_invalid_price(self):
        """Тест валидации с неверной ценой."""
        invalid_order = {
            "id": "12345",
            "symbol": "BTC",
            "side": "Bid",
            "price": -100.0,  # Отрицательная цена
            "size": 1.5,
            "owner": "0x1234567890abcdef",
            "timestamp": datetime.now(),
            "status": "open"
        }
        
        with pytest.raises(ValueError, match="Поле 'price' должно быть положительным числом"):
            self.client._validate_order_data(invalid_order)
    
    def test_validate_order_data_invalid_size(self):
        """Тест валидации с неверным размером."""
        invalid_order = {
            "id": "12345",
            "symbol": "BTC",
            "side": "Bid",
            "price": 50000.0,
            "size": -1.0,  # Отрицательный размер
            "owner": "0x1234567890abcdef",
            "timestamp": datetime.now(),
            "status": "open"
        }
        
        with pytest.raises(ValueError, match="Поле 'size' должно быть неотрицательным числом"):
            self.client._validate_order_data(invalid_order)
    
    def test_validate_order_data_invalid_status(self):
        """Тест валидации с неверным статусом."""
        invalid_order = {
            "id": "12345",
            "symbol": "BTC",
            "side": "Bid",
            "price": 50000.0,
            "size": 1.5,
            "owner": "0x1234567890abcdef",
            "timestamp": datetime.now(),
            "status": "invalid"
        }
        
        with pytest.raises(ValueError, match="Поле 'status' должно быть одним из: open, filled, canceled, triggered"):
            self.client._validate_order_data(invalid_order)
    
    def test_format_order_data_with_datetime(self):
        """Тест форматирования данных с datetime."""
        test_time = datetime(2024, 1, 1, 12, 0, 0)
        order_data = {
            "id": "12345",
            "symbol": "BTC",
            "side": "Bid",
            "price": 50000.0,
            "size": 1.5,
            "owner": "0x1234567890abcdef",
            "timestamp": test_time,
            "status": "open"
        }
        
        result = self.client._format_order_data(order_data)
        
        expected = {
            "id": "12345",
            "symbol": "BTC",
            "side": "bid",
            "price": 50000.0,
            "size": 1.5,
            "owner": "0x1234567890abcdef",
            "timestamp": "2024-01-01T12:00:00Z",
            "status": "open",
            "source": "parser"
        }
        
        assert result == expected
    
    def test_format_order_data_with_string_timestamp(self):
        """Тест форматирования данных со строковым timestamp."""
        order_data = {
            "id": "12345",
            "symbol": "BTC",
            "side": "Ask",
            "price": 50000.0,
            "size": 1.5,
            "owner": "0x1234567890abcdef",
            "timestamp": "2024-01-01T12:00:00Z",
            "status": "filled"
        }
        
        result = self.client._format_order_data(order_data)
        
        expected = {
            "id": "12345",
            "symbol": "BTC",
            "side": "ask",
            "price": 50000.0,
            "size": 1.5,
            "owner": "0x1234567890abcdef",
            "timestamp": "2024-01-01T12:00:00Z",
            "status": "filled",
            "source": "parser"
        }
        
        assert result == expected
    
    def test_format_order_data_side_normalization(self):
        """Тест нормализации side."""
        test_cases = [
            ("Bid", "bid"),
            ("Ask", "ask"),
            ("bid", "bid"),
            ("ask", "ask")
        ]
        
        for input_side, expected_side in test_cases:
            order_data = {
                "id": "12345",
                "symbol": "BTC",
                "side": input_side,
                "price": 50000.0,
                "size": 1.5,
                "owner": "0x1234567890abcdef",
                "timestamp": datetime.now(),
                "status": "open"
            }
            
            result = self.client._format_order_data(order_data)
            assert result["side"] == expected_side
    
    @pytest.mark.asyncio
    async def test_publish_order_data_success(self):
        """Тест успешной публикации данных ордера."""
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
        
        await self.client.publish_order_data(order_data, "parser_data.orders")
        
        # Проверяем, что publish был вызван
        self.client._nc.publish.assert_called_once()
        call_args = self.client._nc.publish.call_args
        
        # Проверяем топик
        assert call_args[0][0] == "parser_data.orders"
        
        # Проверяем сообщение
        message = call_args[0][1]
        parsed_message = json.loads(message.decode('utf-8'))
        
        assert parsed_message["id"] == "12345"
        assert parsed_message["symbol"] == "BTC"
        assert parsed_message["side"] == "bid"
        assert parsed_message["price"] == 50000.0
        assert parsed_message["size"] == 1.5
        assert parsed_message["owner"] == "0x1234567890abcdef"
        assert parsed_message["status"] == "open"
        assert parsed_message["source"] == "parser"
    
    @pytest.mark.asyncio
    async def test_publish_order_data_not_connected(self):
        """Тест публикации без подключения."""
        self.client._is_connected = False
        
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
        
        with pytest.raises(ConnectionError, match="Не подключен к NATS серверу"):
            await self.client.publish_order_data(order_data)
    
    @pytest.mark.asyncio
    async def test_publish_order_data_invalid_data(self):
        """Тест публикации с невалидными данными."""
        invalid_order = {
            "id": "12345",
            "symbol": "BTC",
            "side": "Bid",
            "price": 50000.0,
            "size": 1.5,
            "owner": "0x1234567890abcdef",
            "timestamp": datetime.now()
            # Отсутствует status
        }
        
        with pytest.raises(ValueError, match="Отсутствует обязательное поле: status"):
            await self.client.publish_order_data(invalid_order)
    
    @pytest.mark.asyncio
    async def test_publish_order_data_default_topic(self):
        """Тест публикации с топиком по умолчанию."""
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
        
        await self.client.publish_order_data(order_data)
        
        # Проверяем, что использован топик по умолчанию
        call_args = self.client._nc.publish.call_args
        assert call_args[0][0] == "parser_data.orders"
