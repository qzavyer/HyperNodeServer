"""Tests for order notifier module."""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime
from src.notifications.order_notifier import OrderNotifier
from src.storage.models import Order, Config, SymbolConfig

@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return Config(
        node_logs_path="/test/path",
        cleanup_interval_hours=2,
        api_host="0.0.0.0",
        api_port=8000,
        log_level="DEBUG",
        log_file_path="logs/app.log",
        log_max_size_mb=100,
        log_retention_days=30,
        data_dir="data",
        config_file_path="config/config.json",
        max_orders_per_request=1000,
        file_read_retry_attempts=3,
        file_read_retry_delay=1.0,
        symbols_config=[
            SymbolConfig(symbol="BTC", min_liquidity=1000.0, price_deviation=0.01),
            SymbolConfig(symbol="ETH", min_liquidity=500.0, price_deviation=0.01)
        ]
    )

@pytest.fixture
def mock_config_manager(sample_config):
    """Mock config manager."""
    config_manager = Mock()
    config_manager.get_config.return_value = sample_config
    return config_manager

@pytest.fixture
def mock_websocket_manager():
    """Mock WebSocket manager."""
    websocket_manager = Mock()
    websocket_manager.broadcast_order_update = AsyncMock()
    websocket_manager.queue_order_for_batch = AsyncMock()
    websocket_manager.is_running = True
    websocket_manager.get_connection_stats.return_value = {
        "channels": {"orderUpdate": 1, "orderBatch": 1},
        "pending_orders": 5,
        "is_running": True
    }
    return websocket_manager

@pytest.fixture
def order_notifier(mock_websocket_manager, mock_config_manager):
    """Order notifier instance for testing."""
    return OrderNotifier(mock_websocket_manager, mock_config_manager)

@pytest.fixture
def sample_order():
    """Sample order for testing."""
    return Order(
        id="123",
        symbol="BTC",
        side="Bid",
        price=50000.0,
        size=1.0,
        owner="0x123",
        timestamp=datetime.now(),
        status="open"
    )

class TestOrderNotifier:
    """Tests for OrderNotifier class."""
    
    def test_init(self, mock_websocket_manager, mock_config_manager):
        """Test OrderNotifier initialization."""
        notifier = OrderNotifier(mock_websocket_manager, mock_config_manager)
        
        assert notifier.websocket_manager == mock_websocket_manager
        assert notifier.config_manager == mock_config_manager
    
    def test_should_notify_order_supported_symbol_sufficient_liquidity(self, order_notifier, sample_order):
        """Test notification criteria for supported symbol with sufficient liquidity."""
        # BTC order with 50000 * 1.0 = 50000 liquidity >= 1000 min_liquidity
        result = order_notifier._should_notify_order(sample_order)
        assert result is True
    
    def test_should_notify_order_supported_symbol_insufficient_liquidity(self, order_notifier):
        """Test notification criteria for supported symbol with insufficient liquidity."""
        # BTC order with 500 * 0.1 = 50 liquidity < 1000 min_liquidity
        order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=500.0,
            size=0.1,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        result = order_notifier._should_notify_order(order)
        assert result is False
    
    def test_should_notify_order_unsupported_symbol(self, order_notifier):
        """Test notification criteria for unsupported symbol."""
        # SOL order (not in config)
        order = Order(
            id="123",
            symbol="SOL",
            side="Bid",
            price=100.0,
            size=10.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        result = order_notifier._should_notify_order(order)
        assert result is False
    
    def test_should_notify_order_eth_sufficient_liquidity(self, order_notifier):
        """Test notification criteria for ETH with sufficient liquidity."""
        # ETH order with 3000 * 1.0 = 3000 liquidity >= 500 min_liquidity
        order = Order(
            id="123",
            symbol="ETH",
            side="Ask",
            price=3000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        result = order_notifier._should_notify_order(order)
        assert result is True
    
    def test_should_notify_order_eth_insufficient_liquidity(self, order_notifier):
        """Test notification criteria for ETH with insufficient liquidity."""
        # ETH order with 100 * 2.0 = 200 liquidity < 500 min_liquidity
        order = Order(
            id="123",
            symbol="ETH",
            side="Ask",
            price=100.0,
            size=2.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        result = order_notifier._should_notify_order(order)
        assert result is False
    
    def test_should_notify_order_config_error(self, mock_websocket_manager):
        """Test notification criteria when config manager fails."""
        # Mock config manager that raises error
        error_config_manager = Mock()
        error_config_manager.get_config.side_effect = Exception("Config error")
        
        notifier = OrderNotifier(mock_websocket_manager, error_config_manager)
        
        # Create sample order for this test
        order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        # Should return False on config error
        result = notifier._should_notify_order(order)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_notify_order_update_should_notify(self, order_notifier, sample_order):
        """Test order update notification when criteria are met."""
        await order_notifier.notify_order_update(sample_order, notification_type="both")
        
        # Verify WebSocket manager was called
        order_notifier.websocket_manager.broadcast_order_update.assert_called_once_with(sample_order)
        order_notifier.websocket_manager.queue_order_for_batch.assert_called_once_with(sample_order)
    
    @pytest.mark.asyncio
    async def test_notify_order_update_should_not_notify(self, order_notifier):
        """Test order update notification when criteria are not met."""
        # Order with unsupported symbol
        order = Order(
            id="123",
            symbol="SOL",
            side="Bid",
            price=100.0,
            size=10.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        await order_notifier.notify_order_update(order, notification_type="both")
        
        # Verify WebSocket manager was not called
        order_notifier.websocket_manager.broadcast_order_update.assert_not_called()
        order_notifier.websocket_manager.queue_order_for_batch.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_notify_order_update_instant_only(self, order_notifier, sample_order):
        """Test order update notification with instant type only."""
        await order_notifier.notify_order_update(sample_order, notification_type="instant")
        
        # Verify only instant notification was sent
        order_notifier.websocket_manager.broadcast_order_update.assert_called_once_with(sample_order)
        order_notifier.websocket_manager.queue_order_for_batch.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_notify_order_update_batch_only(self, order_notifier, sample_order):
        """Test order update notification with batch type only."""
        await order_notifier.notify_order_update(sample_order, notification_type="batch")
        
        # Verify only batch notification was sent
        order_notifier.websocket_manager.broadcast_order_update.assert_not_called()
        order_notifier.websocket_manager.queue_order_for_batch.assert_called_once_with(sample_order)
    
    @pytest.mark.asyncio
    async def test_notify_orders_batch_mixed_criteria(self, order_notifier):
        """Test batch notification with mixed criteria."""
        # Create orders with different criteria
        btc_order = Order(
            id="1",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,  # 50000 * 1.0 = 50000 >= 1000
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        sol_order = Order(
            id="2",
            symbol="SOL",  # Not supported
            side="Ask",
            price=100.0,
            size=10.0,
            owner="0x456",
            timestamp=datetime.now(),
            status="open"
        )
        
        small_btc_order = Order(
            id="3",
            symbol="BTC",
            side="Bid",
            price=100.0,
            size=0.1,  # 100 * 0.1 = 10 < 1000
            owner="0x789",
            timestamp=datetime.now(),
            status="open"
        )
        
        orders_batch = [btc_order, sol_order, small_btc_order]
        
        await order_notifier.notify_orders_batch(orders_batch, notification_type="both")
        
        # Verify only BTC order with sufficient liquidity was notified
        assert order_notifier.websocket_manager.broadcast_order_update.call_count == 1
        assert order_notifier.websocket_manager.queue_order_for_batch.call_count == 1
        
        # Verify the correct order was notified
        order_notifier.websocket_manager.broadcast_order_update.assert_called_once_with(btc_order)
        order_notifier.websocket_manager.queue_order_for_batch.assert_called_once_with(btc_order)
    
    @pytest.mark.asyncio
    async def test_notify_orders_batch_no_relevant_orders(self, order_notifier):
        """Test batch notification with no relevant orders."""
        # Create orders that don't meet criteria
        sol_order = Order(
            id="1",
            symbol="SOL",  # Not supported
            side="Ask",
            price=100.0,
            size=10.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        small_btc_order = Order(
            id="2",
            symbol="BTC",
            side="Bid",
            price=100.0,
            size=0.1,  # 100 * 0.1 = 10 < 1000
            owner="0x456",
            timestamp=datetime.now(),
            status="open"
        )
        
        orders_batch = [sol_order, small_btc_order]
        
        await order_notifier.notify_orders_batch(orders_batch, notification_type="both")
        
        # Verify no notifications were sent
        order_notifier.websocket_manager.broadcast_order_update.assert_not_called()
        order_notifier.websocket_manager.queue_order_for_batch.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_notify_orders_batch_websocket_error(self, mock_websocket_manager, mock_config_manager):
        """Test batch notification when WebSocket manager fails."""
        # Mock WebSocket manager that raises error
        error_websocket_manager = Mock()
        error_websocket_manager.broadcast_order_update = AsyncMock(side_effect=Exception("WebSocket error"))
        error_websocket_manager.queue_order_for_batch = AsyncMock(side_effect=Exception("WebSocket error"))
        error_websocket_manager.is_running = True
        error_websocket_manager.get_connection_stats.return_value = {}
        
        notifier = OrderNotifier(error_websocket_manager, mock_config_manager)
        
        # Create valid order
        order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        # Should handle error gracefully
        await notifier.notify_orders_batch([order], notification_type="both")
        # Should complete without raising exception
    
    def test_get_notification_stats(self, order_notifier):
        """Test getting notification statistics."""
        stats = order_notifier.get_notification_stats()
        
        assert "websocket_manager_running" in stats
        assert "websocket_connections" in stats
        assert "config_manager_available" in stats
        
        assert stats["websocket_manager_running"] is True
        assert stats["config_manager_available"] is True
        assert "channels" in stats["websocket_connections"]
        assert "pending_orders" in stats["websocket_connections"]
        assert "is_running" in stats["websocket_connections"]
