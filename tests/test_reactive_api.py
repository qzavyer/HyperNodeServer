"""Тесты для ReactiveOrderWatcher API endpoints."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.api.routes import router
from src.models.reactive_api import OrderSearchRequest, OrderTrackRequest, ReactiveWatcherStatus


class TestReactiveAPI:
    """Тесты для ReactiveOrderWatcher API endpoints."""
    
    def setup_method(self):
        """Настройка перед каждым тестом."""
        self.app = FastAPI()
        self.app.include_router(router, prefix="/api/v1")
        self.client = TestClient(self.app)
    
    def test_search_orders_reactive_success(self):
        """Тест успешного поиска ордеров через API."""
        # Настраиваем моки
        mock_config = Mock()
        mock_symbol_config = Mock()
        mock_symbol_config.symbol = "BTC"
        mock_symbol_config.min_liquidity = 1000.0
        mock_config.symbols_config = [mock_symbol_config]
        
        mock_config_manager = Mock()
        mock_config_manager.get_config.return_value = mock_config
        
        mock_watcher_instance = Mock()
        mock_watcher_instance.add_search_request = AsyncMock()
        
        # Устанавливаем моки как глобальные переменные
        import src.main
        src.main.config_manager = mock_config_manager
        src.main.reactive_order_watcher = mock_watcher_instance
        
        # Выполняем запрос
        response = self.client.post(
            "/api/v1/reactive-orders/search",
            json={
                "ticker": "BTC",
                "side": "Bid",
                "price": 50000.0,
                "tolerance": 0.000001,
                "timestamp": "2024-01-01T12:00:00Z"
            }
        )
        
        # Проверяем результат
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Search initiated for BTC Bid @ 50000.0"
        assert data["min_liquidity"] == 1000.0
        assert data["tolerance"] == 0.000001
        assert data["timestamp"] == "2024-01-01T12:00:00Z"
        assert "Search is being processed" in data["note"]
        
        # Проверяем, что add_search_request был вызван с правильными параметрами
        mock_watcher_instance.add_search_request.assert_called_once_with(
            ticker="BTC",
            side="Bid",
            price=50000.0,
            timestamp="2024-01-01T12:00:00Z",
            tolerance=0.000001
        )
    
    def test_search_orders_reactive_symbol_not_found(self):
        """Тест поиска ордеров для несуществующего символа."""
        # Настраиваем моки
        mock_config = Mock()
        mock_config.symbols_config = []  # Пустой список символов
        
        mock_config_manager = Mock()
        mock_config_manager.get_config.return_value = mock_config
        
        mock_watcher_instance = Mock()
        mock_watcher_instance.add_search_request = AsyncMock()
        
        # Устанавливаем моки как глобальные переменные
        import src.main
        src.main.config_manager = mock_config_manager
        src.main.reactive_order_watcher = mock_watcher_instance
        
        # Выполняем запрос
        response = self.client.post(
            "/api/v1/reactive-orders/search",
            json={
                "ticker": "UNKNOWN",
                "side": "Bid",
                "price": 50000.0,
                "timestamp": "2024-01-01T12:00:00Z"
            }
        )
        
        # Проверяем результат
        assert response.status_code == 400
        data = response.json()
        assert "Symbol UNKNOWN not found in configuration" in data["detail"]
    
    def test_search_orders_reactive_watcher_not_initialized(self):
        """Тест поиска ордеров когда ReactiveOrderWatcher не инициализирован."""
        # Устанавливаем None как глобальную переменную
        import src.main
        src.main.reactive_order_watcher = None
        
        # Выполняем запрос
        response = self.client.post(
            "/api/v1/reactive-orders/search",
            json={
                "ticker": "BTC",
                "side": "Bid",
                "price": 50000.0,
                "timestamp": "2024-01-01T12:00:00Z"
            }
        )
        
        # Проверяем результат
        assert response.status_code == 500
        data = response.json()
        assert "ReactiveOrderWatcher not initialized" in data["detail"]
    
    def test_track_order_reactive_success(self):
        """Тест успешного начала отслеживания ордера."""
        # Настраиваем моки
        mock_watcher_instance = Mock()
        mock_watcher_instance.start_tracking_order = AsyncMock()
        
        # Устанавливаем мок как глобальную переменную
        import src.main
        src.main.reactive_order_watcher = mock_watcher_instance
        
        # Выполняем запрос
        response = self.client.post(
            "/api/v1/reactive-orders/track",
            json={
                "order_id": "test_order_123"
            }
        )
        
        # Проверяем результат
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Started tracking order test_order_123"
        assert data["order_id"] == "test_order_123"
        
        # Проверяем, что start_tracking_order был вызван
        mock_watcher_instance.start_tracking_order.assert_called_once_with("test_order_123")
    
    def test_untrack_order_reactive_success(self):
        """Тест успешной остановки отслеживания ордера."""
        # Настраиваем моки
        mock_watcher_instance = Mock()
        mock_watcher_instance.stop_tracking_order = AsyncMock()
        
        # Устанавливаем мок как глобальную переменную
        import src.main
        src.main.reactive_order_watcher = mock_watcher_instance
        
        # Выполняем запрос
        response = self.client.request(
            "DELETE",
            "/api/v1/reactive-orders/untrack",
            json={
                "order_id": "test_order_123"
            }
        )
        
        # Проверяем результат
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message"] == "Stopped tracking order test_order_123"
        assert data["order_id"] == "test_order_123"
        
        # Проверяем, что stop_tracking_order был вызван
        mock_watcher_instance.stop_tracking_order.assert_called_once_with("test_order_123")
    
    def test_get_reactive_watcher_status_success(self):
        """Тест успешного получения статуса ReactiveOrderWatcher."""
        # Настраиваем моки
        mock_watcher_instance = Mock()
        mock_watcher_instance.current_file_path = Mock()
        mock_watcher_instance.current_file_path.__str__ = Mock(return_value="/test/file")
        mock_watcher_instance.tracked_orders = {"order1": Mock(), "order2": Mock()}
        mock_watcher_instance.cached_orders = {
            "timestamp1": [Mock(), Mock()],
            "timestamp2": [Mock()]
        }
        mock_task = Mock()
        mock_task.done.return_value = False
        mock_watcher_instance.monitoring_task = mock_task
        mock_watcher_instance.cache_duration_seconds = 10
        
        # Устанавливаем мок как глобальную переменную
        import src.main
        src.main.reactive_order_watcher = mock_watcher_instance
        mock_watcher_instance.monitoring_interval_ms = 10.0
        
        # Выполняем запрос
        response = self.client.get("/api/v1/reactive-orders/status")
        
        # Проверяем результат
        assert response.status_code == 200
        data = response.json()
        assert data["is_initialized"] is True
        assert data["current_file"] == "/test/file"
        assert data["tracked_orders_count"] == 2
        assert data["cached_orders_count"] == 3
        assert data["monitoring_active"] is True
        assert data["cache_duration_seconds"] == 10
        assert data["monitoring_interval_ms"] == 10.0
    
    def test_get_reactive_watcher_status_not_initialized(self):
        """Тест получения статуса когда ReactiveOrderWatcher не инициализирован."""
        # Устанавливаем None как глобальную переменную
        import src.main
        src.main.reactive_order_watcher = None
        
        # Выполняем запрос
        response = self.client.get("/api/v1/reactive-orders/status")
        
        # Проверяем результат
        assert response.status_code == 500
        data = response.json()
        assert "Failed to get status:" in data["detail"]
    
    def test_order_search_request_validation(self):
        """Тест валидации OrderSearchRequest."""
        # Валидный запрос
        valid_request = OrderSearchRequest(
            ticker="BTC",
            side="Bid",
            price=50000.0,
            tolerance=0.000001,
            timestamp="2024-01-01T12:00:00Z"
        )
        assert valid_request.ticker == "BTC"
        assert valid_request.side == "Bid"
        assert valid_request.price == 50000.0
        assert valid_request.tolerance == 0.000001
        
        # Невалидный side
        with pytest.raises(ValueError):
            OrderSearchRequest(
                ticker="BTC",
                side="Invalid",
                price=50000.0,
                timestamp="2024-01-01T12:00:00Z"
            )
        
        # Невалидная цена
        with pytest.raises(ValueError):
            OrderSearchRequest(
                ticker="BTC",
                side="Bid",
                price=-100.0,
                timestamp="2024-01-01T12:00:00Z"
            )
    
    def test_order_track_request_validation(self):
        """Тест валидации OrderTrackRequest."""
        # Валидный запрос
        valid_request = OrderTrackRequest(order_id="test_order_123")
        assert valid_request.order_id == "test_order_123"
