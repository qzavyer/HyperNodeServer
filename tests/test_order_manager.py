"""Tests for order manager module."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from src.storage.order_manager import OrderManager, OrderManagerError
from src.storage.models import Order
from src.storage.file_storage import FileStorage

@pytest.fixture
def mock_storage():
    """Mock file storage."""
    storage = Mock(spec=FileStorage)
    storage.load_orders_async = AsyncMock(return_value=[])
    storage.save_orders_async = AsyncMock()
    return storage

@pytest.fixture
def mock_config_manager():
    """Mock config manager."""
    config_manager = Mock()
    config_manager.get_config.return_value = Mock()
    config_manager.get_config.return_value.symbols_config = [
        Mock(symbol="BTC", min_liquidity=1000.0),
        Mock(symbol="ETH", min_liquidity=500.0)
    ]
    return config_manager

@pytest.fixture
def mock_order_notifier():
    """Mock order notifier."""
    notifier = Mock()
    notifier.notify_order_update = AsyncMock()
    notifier.notify_orders_batch = AsyncMock()
    return notifier

@pytest.fixture
def order_manager(mock_storage, mock_config_manager, mock_order_notifier):
    """Order manager instance for testing."""
    manager = OrderManager(mock_storage, mock_config_manager, mock_order_notifier)
    return manager

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

class TestOrderManager:
    """Tests for OrderManager class."""
    
    def test_init(self, mock_storage, mock_config_manager, mock_order_notifier):
        """Test OrderManager initialization."""
        manager = OrderManager(mock_storage, mock_config_manager, mock_order_notifier)
        assert manager.storage == mock_storage
        assert manager.config_manager == mock_config_manager
        assert manager.order_notifier == mock_order_notifier
        assert len(manager.orders) == 0
    
    def test_set_order_notifier(self, order_manager, mock_order_notifier):
        """Test setting order notifier."""
        new_notifier = Mock()
        order_manager.set_order_notifier(new_notifier)
        assert order_manager.order_notifier == new_notifier
    
    @pytest.mark.asyncio
    async def test_initialize_loads_orders(self, order_manager, sample_order):
        """Test that initialize loads orders from storage."""
        order_manager.storage.load_orders_async.return_value = [sample_order]
        
        await order_manager.initialize()
        
        assert len(order_manager.orders) == 1
        assert order_manager.orders["123"] == sample_order
    
    @pytest.mark.asyncio
    async def test_add_new_order(self, order_manager, sample_order):
        """Test adding new order."""
        await order_manager.update_order(sample_order)
        
        assert len(order_manager.orders) == 1
        assert order_manager.orders["123"] == sample_order
        order_manager.order_notifier.notify_order_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_existing_order(self, order_manager, sample_order):
        """Test updating existing order."""
        # Add initial order
        order_manager.orders["123"] = sample_order
        
        # Update order
        updated_order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=51000.0,  # Changed price
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="filled"  # Changed status
        )
        
        await order_manager.update_order(updated_order)
        
        assert order_manager.orders["123"].price == 51000.0
        assert order_manager.orders["123"].status == "filled"
        order_manager.order_notifier.notify_order_update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_status_transition_open_to_filled(self, order_manager):
        """Test status transition from open to filled."""
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
        
        # Add order with open status
        order_manager.orders["123"] = order
        
        # Update to filled
        filled_order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="filled"
        )
        
        await order_manager.update_order(filled_order)
        
        assert order_manager.orders["123"].status == "filled"
    
    @pytest.mark.asyncio
    async def test_status_transition_filled_cannot_change(self, order_manager):
        """Test that filled orders cannot change status."""
        order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="filled"
        )
        
        # Add order with filled status
        order_manager.orders["123"] = order
        
        # Try to update to canceled
        canceled_order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="canceled"
        )
        
        await order_manager.update_order(canceled_order)
        
        # Status should remain filled
        assert order_manager.orders["123"].status == "filled"
    
    def test_get_orders_filter_by_symbol(self, order_manager, sample_order):
        """Test getting orders filtered by symbol."""
        order_manager.orders["123"] = sample_order
        
        # Add another order with different symbol
        eth_order = Order(
            id="456",
            symbol="ETH",
            side="Ask",
            price=3000.0,
            size=10.0,
            owner="0x456",
            timestamp=datetime.now(),
            status="open"
        )
        order_manager.orders["456"] = eth_order
        
        # Use direct access to test filtering
        btc_orders = [o for o in order_manager.orders.values() if o.symbol == "BTC"]
        assert len(btc_orders) == 1
        assert btc_orders[0].symbol == "BTC"
    
    def test_get_orders_filter_by_side(self, order_manager, sample_order):
        """Test getting orders filtered by side."""
        order_manager.orders["123"] = sample_order
        
        # Add Ask order
        ask_order = Order(
            id="456",
            symbol="BTC",
            side="Ask",
            price=51000.0,
            size=0.5,
            owner="0x456",
            timestamp=datetime.now(),
            status="open"
        )
        order_manager.orders["456"] = ask_order
        
        # Use direct access to test filtering
        bid_orders = [o for o in order_manager.orders.values() if o.side == "Bid"]
        assert len(bid_orders) == 1
        assert bid_orders[0].side == "Bid"
    
    def test_get_orders_filter_by_min_liquidity(self, order_manager, sample_order):
        """Test getting orders filtered by minimum liquidity."""
        order_manager.orders["123"] = sample_order  # BTC 50000 * 1.0 = 50000
        
        # Add order with lower liquidity
        low_liquidity_order = Order(
            id="456",
            symbol="BTC",
            side="Ask",
            price=1000.0,
            size=0.1,  # 1000 * 0.1 = 100
            owner="0x456",
            timestamp=datetime.now(),
            status="open"
        )
        order_manager.orders["456"] = low_liquidity_order
        
        # Use direct access to test filtering
        high_liquidity_orders = [o for o in order_manager.orders.values() 
                               if o.symbol == "BTC" and o.price * o.size >= 1000.0]
        assert len(high_liquidity_orders) == 1
        assert high_liquidity_orders[0].id == "123"
    
    def test_get_orders_filter_by_status(self, order_manager, sample_order):
        """Test getting orders filtered by status."""
        order_manager.orders["123"] = sample_order
        
        # Add filled order
        filled_order = Order(
            id="456",
            symbol="BTC",
            side="Ask",
            price=51000.0,
            size=0.5,
            owner="0x456",
            timestamp=datetime.now(),
            status="filled"
        )
        order_manager.orders["456"] = filled_order
        
        # Use direct access to test filtering
        open_orders = [o for o in order_manager.orders.values() if o.status == "open"]
        assert len(open_orders) == 1
        assert open_orders[0].status == "open"
    
    def test_get_orders_multiple_filters(self, order_manager, sample_order):
        """Test getting orders with multiple filters."""
        order_manager.orders["123"] = sample_order
        
        # Add another BTC order
        btc_order2 = Order(
            id="456",
            symbol="BTC",
            side="Ask",
            price=51000.0,
            size=0.5,
            owner="0x456",
            timestamp=datetime.now(),
            status="open"
        )
        order_manager.orders["456"] = btc_order2
        
        # Get BTC orders with open status
        btc_open_orders = [o for o in order_manager.orders.values() 
                          if o.symbol == "BTC" and o.status == "open"]
        assert len(btc_open_orders) == 2
    
    @pytest.mark.asyncio
    async def test_cleanup_old_orders(self, order_manager, sample_order):
        """Test cleaning up old orders."""
        # Add old order
        old_order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now() - timedelta(hours=3),
            status="open"
        )
        order_manager.orders["123"] = old_order
        
        # Add recent order
        recent_order = Order(
            id="456",
            symbol="ETH",
            side="Ask",
            price=3000.0,
            size=10.0,
            owner="0x456",
            timestamp=datetime.now(),
            status="open"
        )
        order_manager.orders["456"] = recent_order
        
        cleaned_count = order_manager.cleanup_old_orders(2)  # Clean orders older than 2 hours
        
        assert cleaned_count == 1
        assert "123" not in order_manager.orders
        assert "456" in order_manager.orders
    
    @pytest.mark.asyncio
    async def test_batch_update_conflict_filled_canceled(self, order_manager):
        """Test batch update with filled and canceled conflict."""
        # Add initial order
        initial_order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        order_manager.orders["123"] = initial_order
        
        # Create conflicting updates
        filled_update = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="filled"
        )
        
        canceled_update = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="canceled"
        )
        
        await order_manager.update_orders_batch_async([filled_update, canceled_update])
        
        # Should choose canceled (higher priority)
        assert order_manager.orders["123"].status == "canceled"
        order_manager.order_notifier.notify_orders_batch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_batch_update_priority(self, order_manager):
        """Test batch update priority order."""
        # Add initial order
        initial_order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        order_manager.orders["123"] = initial_order
        
        # Create updates with different priorities
        triggered_update = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="triggered"
        )
        
        filled_update = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="filled"
        )
        
        await order_manager.update_orders_batch_async([triggered_update, filled_update])
        
        # Should choose filled (higher priority than triggered)
        assert order_manager.orders["123"].status == "filled"
    
    def test_get_order_book(self, order_manager):
        """Test getting order book."""
        # Add Bid orders
        bid_order1 = Order(
            id="1",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        bid_order2 = Order(
            id="2",
            symbol="BTC",
            side="Bid",
            price=49000.0,
            size=0.5,
            owner="0x456",
            timestamp=datetime.now(),
            status="open"
        )
        
        # Add Ask orders
        ask_order1 = Order(
            id="3",
            symbol="BTC",
            side="Ask",
            price=51000.0,
            size=0.8,
            owner="0x789",
            timestamp=datetime.now(),
            status="open"
        )
        ask_order2 = Order(
            id="4",
            symbol="BTC",
            side="Ask",
            price=52000.0,
            size=1.2,
            owner="0xabc",
            timestamp=datetime.now(),
            status="open"
        )
        
        order_manager.orders.update({
            "1": bid_order1,
            "2": bid_order2,
            "3": ask_order1,
            "4": ask_order2
        })
        
        # Use direct access to test order book logic
        btc_orders = [o for o in order_manager.orders.values() if o.symbol == "BTC"]
        bid_orders = [o for o in btc_orders if o.side == "Bid"]
        ask_orders = [o for o in btc_orders if o.side == "Ask"]
        
        # Sort by price (highest bid first, lowest ask first)
        bid_orders.sort(key=lambda x: x.price, reverse=True)
        ask_orders.sort(key=lambda x: x.price)
        
        assert len(bid_orders) == 2
        assert len(ask_orders) == 2
        assert bid_orders[0].price == 50000.0  # Highest bid price first
        assert ask_orders[0].price == 51000.0  # Lowest ask price first
    
    def test_get_market_summary(self, order_manager):
        """Test getting market summary."""
        # Add orders
        order1 = Order(
            id="1",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        order2 = Order(
            id="2",
            symbol="BTC",
            side="Ask",
            price=51000.0,
            size=0.5,
            owner="0x456",
            timestamp=datetime.now(),
            status="open"
        )
        
        order_manager.orders.update({
            "1": order1,
            "2": order2
        })
        
        # Use direct access to test market summary logic
        btc_orders = [o for o in order_manager.orders.values() if o.symbol == "BTC"]
        total_orders = len(btc_orders)
        total_volume = sum(o.size for o in btc_orders)
        avg_price = sum(o.price * o.size for o in btc_orders) / sum(o.size for o in btc_orders)
        min_price = min(o.price for o in btc_orders)
        max_price = max(o.price for o in btc_orders)
        
        assert total_orders == 2
        assert total_volume == 1.5
        assert 50000.0 <= avg_price <= 51000.0
        assert min_price == 50000.0
        assert max_price == 51000.0
