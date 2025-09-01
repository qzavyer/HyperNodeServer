"""Tests for OrderManager module."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from typing import Set

from src.storage.order_manager import OrderManager
from src.storage.file_storage import FileStorage
from src.storage.models import Order

class TestOrderManager:
    """Tests for OrderManager class."""
    
    def setup_method(self):
        """Setup before each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = FileStorage(self.temp_dir)
        self.manager = OrderManager(self.storage)
    
    def teardown_method(self):
        """Cleanup after each test."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @pytest.mark.asyncio
    async def test_initialize_loads_orders(self):
        """Test initialization loads existing orders."""
        # Create test orders
        orders = [
            Order(
                id="1",
                symbol="BTC",
                side="Bid",
                price=50000.0,
                size=1.0,
                owner="0x123",
                timestamp=datetime.now(),
                status="open"
            ),
            Order(
                id="2",
                symbol="ETH",
                side="Ask",
                price=3000.0,
                size=10.0,
                owner="0x456",
                timestamp=datetime.now(),
                status="filled"
            )
        ]
        
        # Save orders to storage
        await self.storage.save_orders_async(orders)
        
        # Initialize manager
        await self.manager.initialize()
        
        assert self.manager.get_order_count() == 2
        assert self.manager.get_order_by_id("1") is not None
        assert self.manager.get_order_by_id("2") is not None
    
    @pytest.mark.asyncio
    async def test_add_new_order(self):
        """Test adding new order."""
        order = Order(
            id="1",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        
        await self.manager.update_order(order)
        
        assert self.manager.get_order_count() == 1
        stored_order = self.manager.get_order_by_id("1")
        assert stored_order is not None
        assert stored_order.status == "open"
    
    @pytest.mark.asyncio
    async def test_update_existing_order(self):
        """Test updating existing order."""
        # Add initial order
        order = Order(
            id="1",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="open"
        )
        await self.manager.update_order(order)
        
        # Update order status
        updated_order = Order(
            id="1",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x123",
            timestamp=datetime.now(),
            status="filled"
        )
        await self.manager.update_order(updated_order)
        
        stored_order = self.manager.get_order_by_id("1")
        assert stored_order.status == "filled"
    
    def test_status_transition_open_to_filled(self):
        """Test status transition from open to filled."""
        result = self.manager._apply_status_transition("open", "filled")
        assert result == "filled"
    
    def test_status_transition_open_to_cancelled(self):
        """Test status transition from open to cancelled."""
        result = self.manager._apply_status_transition("open", "cancelled")
        assert result == "cancelled"
    
    def test_status_transition_open_to_triggered(self):
        """Test status transition from open to triggered."""
        result = self.manager._apply_status_transition("open", "triggered")
        assert result == "triggered"
    
    def test_status_transition_triggered_to_filled(self):
        """Test status transition from triggered to filled."""
        result = self.manager._apply_status_transition("triggered", "filled")
        assert result == "filled"
    
    def test_status_transition_triggered_to_cancelled(self):
        """Test status transition from triggered to cancelled."""
        result = self.manager._apply_status_transition("triggered", "cancelled")
        assert result == "cancelled"
    
    def test_status_transition_filled_ignores_new_status(self):
        """Test that filled orders ignore new status updates."""
        result = self.manager._apply_status_transition("filled", "cancelled")
        assert result == "filled"  # Should remain filled
    
    def test_status_transition_cancelled_ignores_new_status(self):
        """Test that cancelled orders ignore new status updates."""
        result = self.manager._apply_status_transition("cancelled", "filled")
        assert result == "cancelled"  # Should remain cancelled
    
    def test_status_transition_unknown_current_status(self):
        """Test handling of unknown current status."""
        result = self.manager._apply_status_transition("unknown", "filled")
        assert result == "cancelled"  # Should default to cancelled
    
    def test_status_transition_unknown_new_status(self):
        """Test handling of unknown new status."""
        result = self.manager._apply_status_transition("open", "unknown")
        assert result == "cancelled"  # Should default to cancelled
    
    def test_get_orders_filter_by_symbol(self):
        """Test filtering orders by symbol."""
        # Add test orders
        orders = [
            Order(id="1", symbol="BTC", side="Bid", price=50000.0, size=1.0, 
                  owner="0x123", timestamp=datetime.now(), status="open"),
            Order(id="2", symbol="ETH", side="Ask", price=3000.0, size=10.0,
                  owner="0x456", timestamp=datetime.now(), status="open"),
            Order(id="3", symbol="BTC", side="Ask", price=49000.0, size=0.5,
                  owner="0x789", timestamp=datetime.now(), status="open")
        ]
        
        for order in orders:
            self.manager.orders[order.id] = order
        
        btc_orders = self.manager.get_orders(symbol="BTC")
        assert len(btc_orders) == 2
        assert all(o.symbol == "BTC" for o in btc_orders)
    
    def test_get_orders_filter_by_side(self):
        """Test filtering orders by side."""
        # Add test orders
        orders = [
            Order(id="1", symbol="BTC", side="Bid", price=50000.0, size=1.0,
                  owner="0x123", timestamp=datetime.now(), status="open"),
            Order(id="2", symbol="ETH", side="Ask", price=3000.0, size=10.0,
                  owner="0x456", timestamp=datetime.now(), status="open"),
            Order(id="3", symbol="BTC", side="Bid", price=49000.0, size=0.5,
                  owner="0x789", timestamp=datetime.now(), status="open")
        ]
        
        for order in orders:
            self.manager.orders[order.id] = order
        
        bid_orders = self.manager.get_orders(side="Bid")
        assert len(bid_orders) == 2
        assert all(o.side == "Bid" for o in bid_orders)
    
    def test_get_orders_filter_by_min_liquidity(self):
        """Test filtering orders by minimum liquidity."""
        # Add test orders
        orders = [
            Order(id="1", symbol="BTC", side="Bid", price=50000.0, size=1.0,  # 50000
                  owner="0x123", timestamp=datetime.now(), status="open"),
            Order(id="2", symbol="ETH", side="Ask", price=3000.0, size=10.0,  # 30000
                  owner="0x456", timestamp=datetime.now(), status="open"),
            Order(id="3", symbol="BTC", side="Ask", price=49000.0, size=0.5,  # 24500
                  owner="0x789", timestamp=datetime.now(), status="open")
        ]
        
        for order in orders:
            self.manager.orders[order.id] = order
        
        high_liquidity_orders = self.manager.get_orders(min_liquidity=30000.0)
        assert len(high_liquidity_orders) == 2
        assert all(o.price * o.size >= 30000.0 for o in high_liquidity_orders)
    
    def test_get_orders_filter_by_status(self):
        """Test filtering orders by status."""
        # Add test orders
        orders = [
            Order(id="1", symbol="BTC", side="Bid", price=50000.0, size=1.0,
                  owner="0x123", timestamp=datetime.now(), status="open"),
            Order(id="2", symbol="ETH", side="Ask", price=3000.0, size=10.0,
                  owner="0x456", timestamp=datetime.now(), status="filled"),
            Order(id="3", symbol="BTC", side="Ask", price=49000.0, size=0.5,
                  owner="0x789", timestamp=datetime.now(), status="open")
        ]
        
        for order in orders:
            self.manager.orders[order.id] = order
        
        open_orders = self.manager.get_orders(status="open")
        assert len(open_orders) == 2
        assert all(o.status == "open" for o in open_orders)
    
    def test_get_orders_multiple_filters(self):
        """Test filtering orders with multiple criteria."""
        # Add test orders
        orders = [
            Order(id="1", symbol="BTC", side="Bid", price=50000.0, size=1.0,
                  owner="0x123", timestamp=datetime.now(), status="open"),
            Order(id="2", symbol="BTC", side="Ask", price=49000.0, size=0.5,
                  owner="0x456", timestamp=datetime.now(), status="open"),
            Order(id="3", symbol="ETH", side="Bid", price=3000.0, size=10.0,
                  owner="0x789", timestamp=datetime.now(), status="open")
        ]
        
        for order in orders:
            self.manager.orders[order.id] = order
        
        filtered_orders = self.manager.get_orders(
            symbol="BTC", 
            side="Bid", 
            status="open",
            min_liquidity=40000.0
        )
        assert len(filtered_orders) == 1
        assert filtered_orders[0].id == "1"
    
    def test_get_orders_by_owner(self):
        """Test getting orders by owner."""
        # Add test orders
        orders = [
            Order(id="1", symbol="BTC", side="Bid", price=50000.0, size=1.0,
                  owner="0x123", timestamp=datetime.now(), status="open"),
            Order(id="2", symbol="ETH", side="Ask", price=3000.0, size=10.0,
                  owner="0x123", timestamp=datetime.now(), status="open"),
            Order(id="3", symbol="BTC", side="Ask", price=49000.0, size=0.5,
                  owner="0x456", timestamp=datetime.now(), status="open")
        ]
        
        for order in orders:
            self.manager.orders[order.id] = order
        
        owner_orders = self.manager.get_orders_by_owner("0x123")
        assert len(owner_orders) == 2
        assert all(o.owner == "0x123" for o in owner_orders)
    
    def test_get_order_count_by_status(self):
        """Test getting order count by status."""
        # Add test orders
        orders = [
            Order(id="1", symbol="BTC", side="Bid", price=50000.0, size=1.0,
                  owner="0x123", timestamp=datetime.now(), status="open"),
            Order(id="2", symbol="ETH", side="Ask", price=3000.0, size=10.0,
                  owner="0x456", timestamp=datetime.now(), status="open"),
            Order(id="3", symbol="BTC", side="Ask", price=49000.0, size=0.5,
                  owner="0x789", timestamp=datetime.now(), status="filled")
        ]
        
        for order in orders:
            self.manager.orders[order.id] = order
        
        counts = self.manager.get_order_count_by_status()
        assert counts["open"] == 2
        assert counts["filled"] == 1
    
    @pytest.mark.asyncio
    async def test_cleanup_old_orders(self):
        """Test cleanup of old orders."""
        # Add test orders with different timestamps
        now = datetime.now()
        orders = [
            Order(id="1", symbol="BTC", side="Bid", price=50000.0, size=1.0,
                  owner="0x123", timestamp=now, status="open"),
            Order(id="2", symbol="ETH", side="Ask", price=3000.0, size=10.0,
                  owner="0x456", timestamp=now - timedelta(hours=25), status="open"),
            Order(id="3", symbol="BTC", side="Ask", price=49000.0, size=0.5,
                  owner="0x789", timestamp=now - timedelta(hours=12), status="open")
        ]
        
        for order in orders:
            self.manager.orders[order.id] = order
        
        # Cleanup orders older than 24 hours
        removed_count = await self.manager.cleanup_old_orders(max_age_hours=24)
        
        assert removed_count == 1
        assert self.manager.get_order_count() == 2
        assert "2" not in self.manager.orders  # Old order should be removed

    @pytest.mark.asyncio
    async def test_batch_update_conflict_filled_cancelled(self):
        """If filled and cancelled arrive together, choose cancelled and log warning."""
        await self.manager.initialize()

        open_order = Order(
            id="1", symbol="BTC", side="Bid", price=50000.0, size=1.0,
            owner="0x123", timestamp=datetime.now(), status="open"
        )
        await self.manager.update_order(open_order)

        filled_update = Order(
            id="1", symbol="BTC", side="Bid", price=50000.0, size=0.0,
            owner="0x123", timestamp=datetime.now(), status="filled"
        )
        cancelled_update = Order(
            id="1", symbol="BTC", side="Bid", price=50000.0, size=0.0,
            owner="0x123", timestamp=datetime.now(), status="cancelled"
        )

        await self.manager.update_orders_batch_async([filled_update, cancelled_update])

        final = self.manager.get_order_by_id("1")
        assert final.status == "cancelled"

    @pytest.mark.asyncio
    async def test_batch_update_priority(self):
        """Batch update resolves by priority: cancelled > filled > triggered > open."""
        await self.manager.initialize()

        open_order = Order(
            id="2", symbol="ETH", side="Ask", price=3000.0, size=2.0,
            owner="0x456", timestamp=datetime.now(), status="open"
        )
        await self.manager.update_order(open_order)

        triggered_update = Order(
            id="2", symbol="ETH", side="Ask", price=3000.0, size=1.5,
            owner="0x456", timestamp=datetime.now(), status="triggered"
        )
        open_update = Order(
            id="2", symbol="ETH", side="Ask", price=3000.0, size=1.5,
            owner="0x456", timestamp=datetime.now(), status="open"
        )

        await self.manager.update_orders_batch_async([triggered_update, open_update])
        final = self.manager.get_order_by_id("2")
        assert final.status == "triggered"
