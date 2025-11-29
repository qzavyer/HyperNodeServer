"""Тесты для подписки на конфигурационные сообщения в NATS."""

import pytest
import json
from unittest.mock import AsyncMock, Mock, patch

from src.nats.nats_client import NATSClient


class TestNATSSubscribe:
    """Тесты для подписки на конфигурационные сообщения."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.client = NATSClient()
        self.client._nc = AsyncMock()
        self.client._is_connected = True
    
    def test_validate_config_data_success(self):
        """Тест успешной валидации конфигурационных данных."""
        valid_config = {
            "symbols": ["BTC", "ETH"],
            "min_liquidity": 1000.0,
            "price_deviation": 0.05
        }
        
        # Не должно вызывать исключение
        self.client._validate_config_data(valid_config)
    
    def test_validate_config_data_not_dict(self):
        """Тест валидации с неверным типом данных."""
        with pytest.raises(ValueError, match="Конфигурация должна быть объектом"):
            self.client._validate_config_data("invalid config")
    
    def test_validate_config_data_empty(self):
        """Тест валидации с пустой конфигурацией."""
        with pytest.raises(ValueError, match="Конфигурация не может быть пустой"):
            self.client._validate_config_data({})
    
    def test_is_subscribed_to_config_initial_state(self):
        """Тест начального состояния подписки."""
        assert not self.client.is_subscribed_to_config()
    
    def test_is_subscribed_to_config_after_subscription(self):
        """Тест состояния подписки после подписки."""
        self.client._config_subscription = Mock()
        assert self.client.is_subscribed_to_config()
    
    @pytest.mark.asyncio
    async def test_subscribe_to_config_success(self):
        """Тест успешной подписки на конфигурации."""
        mock_subscription = AsyncMock()
        self.client._nc.subscribe.return_value = mock_subscription
        
        callback_called = False
        received_config = None
        
        def test_callback(config):
            nonlocal callback_called, received_config
            callback_called = True
            received_config = config
        
        await self.client.subscribe_to_config(test_callback, "parser_config.test")
        
        # Проверяем, что подписка создана
        self.client._nc.subscribe.assert_called_once_with(
            "parser_config.test",
            cb=self.client._handle_config_message
        )
        
        # Проверяем состояние
        assert self.client.is_subscribed_to_config()
        assert self.client._config_callback == test_callback
        assert self.client._config_subscription == mock_subscription
    
    @pytest.mark.asyncio
    async def test_subscribe_to_config_not_connected(self):
        """Тест подписки без подключения."""
        self.client._is_connected = False
        
        def test_callback(config):
            pass
        
        with pytest.raises(ConnectionError, match="Не подключен к NATS серверу"):
            await self.client.subscribe_to_config(test_callback)
    
    @pytest.mark.asyncio
    async def test_subscribe_to_config_no_callback(self):
        """Тест подписки без callback."""
        with pytest.raises(ValueError, match="Callback функция обязательна"):
            await self.client.subscribe_to_config(None)
    
    @pytest.mark.asyncio
    async def test_subscribe_to_config_default_topic(self):
        """Тест подписки с топиком по умолчанию."""
        mock_subscription = AsyncMock()
        self.client._nc.subscribe.return_value = mock_subscription
        
        def test_callback(config):
            pass
        
        await self.client.subscribe_to_config(test_callback)
        
        # Проверяем, что использован топик по умолчанию
        self.client._nc.subscribe.assert_called_once_with(
            "parser_config.>",
            cb=self.client._handle_config_message
        )
    
    @pytest.mark.asyncio
    async def test_handle_config_message_success(self):
        """Тест успешной обработки конфигурационного сообщения."""
        callback_called = False
        received_config = None
        
        def test_callback(config):
            nonlocal callback_called, received_config
            callback_called = True
            received_config = config
        
        self.client._config_callback = test_callback
        
        # Создаем mock сообщение
        mock_msg = Mock()
        mock_msg.subject = "parser_config.test"
        mock_msg.data = json.dumps({
            "symbols": ["BTC", "ETH"],
            "min_liquidity": 1000.0
        }).encode('utf-8')
        
        await self.client._handle_config_message(mock_msg)
        
        # Проверяем, что callback был вызван
        assert callback_called
        assert received_config == {
            "symbols": ["BTC", "ETH"],
            "min_liquidity": 1000.0
        }
    
    @pytest.mark.asyncio
    async def test_handle_config_message_invalid_json(self):
        """Тест обработки сообщения с неверным JSON."""
        callback_called = False
        
        def test_callback(config):
            nonlocal callback_called
            callback_called = True
        
        self.client._config_callback = test_callback
        
        # Создаем mock сообщение с неверным JSON
        mock_msg = Mock()
        mock_msg.subject = "parser_config.test"
        mock_msg.data = b"invalid json"
        
        # Не должно вызывать исключение, но callback не должен быть вызван
        await self.client._handle_config_message(mock_msg)
        
        assert not callback_called
    
    @pytest.mark.asyncio
    async def test_handle_config_message_invalid_config(self):
        """Тест обработки сообщения с невалидной конфигурацией."""
        callback_called = False
        
        def test_callback(config):
            nonlocal callback_called
            callback_called = True
        
        self.client._config_callback = test_callback
        
        # Создаем mock сообщение с пустой конфигурацией
        mock_msg = Mock()
        mock_msg.subject = "parser_config.test"
        mock_msg.data = json.dumps({}).encode('utf-8')
        
        # Не должно вызывать исключение, но callback не должен быть вызван
        await self.client._handle_config_message(mock_msg)
        
        assert not callback_called
    
    @pytest.mark.asyncio
    async def test_handle_config_message_no_callback(self):
        """Тест обработки сообщения без callback."""
        # Создаем mock сообщение
        mock_msg = Mock()
        mock_msg.subject = "parser_config.test"
        mock_msg.data = json.dumps({
            "symbols": ["BTC", "ETH"]
        }).encode('utf-8')
        
        # Не должно вызывать исключение
        await self.client._handle_config_message(mock_msg)
    
    @pytest.mark.asyncio
    async def test_disconnect_with_subscription(self):
        """Тест отключения с активной подпиской."""
        mock_subscription = AsyncMock()
        self.client._config_subscription = mock_subscription
        
        await self.client.disconnect()
        
        # Проверяем, что подписка была отменена
        mock_subscription.unsubscribe.assert_called_once()
        assert self.client._config_subscription is None
        assert not self.client.is_subscribed_to_config()
    
    @pytest.mark.asyncio
    async def test_disconnect_without_subscription(self):
        """Тест отключения без подписки."""
        # Не должно вызывать исключение
        await self.client.disconnect()
        assert not self.client.is_subscribed_to_config()
