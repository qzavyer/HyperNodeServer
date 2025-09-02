"""Tests for OrderManager module."""

import pytest
import asyncio
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from pathlib import Path
from typing import Set

from src.storage.order_manager import OrderManager
from src.storage.file_storage import FileStorage
from src.storage.config_manager import ConfigManager
from src.storage.models import Order, Config, SymbolConfig

class TestOrderManager:
    """Tests for OrderManager class."""
    
    def setup_method(self):
        """Setup before each test."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.storage = FileStorage(str(self.temp_dir))
        self.config_manager = ConfigManager(str(self.temp_dir / "config.json"))
        self.manager = OrderManager(self.storage, self.config_manager)
    
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
    
    def test_status_transition_open_to_canceled(self):
        """Test status transition from open to canceled."""
        result = self.manager._apply_status_transition("open", "canceled")
        assert result == "canceled"
    
    def test_status_transition_open_to_triggered(self):
        """Test status transition from open to triggered."""
        result = self.manager._apply_status_transition("open", "triggered")
        assert result == "triggered"
    
    def test_status_transition_triggered_to_filled(self):
        """Test status transition from triggered to filled."""
        result = self.manager._apply_status_transition("triggered", "filled")
        assert result == "filled"
    
    def test_status_transition_triggered_to_canceled(self):
        """Test status transition from triggered to canceled."""
        result = self.manager._apply_status_transition("triggered", "canceled")
        assert result == "canceled"
    
    def test_status_transition_filled_ignores_new_status(self):
        """Test that filled orders ignore new status updates."""
        result = self.manager._apply_status_transition("filled", "canceled")
        assert result == "filled"  # Should remain filled
    
    def test_status_transition_canceled_ignores_new_status(self):
        """Test that canceled orders ignore new status updates."""
        result = self.manager._apply_status_transition("canceled", "filled")
        assert result == "canceled"  # Should remain canceled
    
    def test_status_transition_unknown_current_status(self):
        """Test handling of unknown current status."""
        result = self.manager._apply_status_transition("unknown", "filled")
        assert result == "canceled"  # Should default to canceled
    
    def test_status_transition_unknown_new_status(self):
        """Test handling of unknown new status."""
        result = self.manager._apply_status_transition("open", "unknown")
        assert result == "canceled"  # Should default to canceled
    
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
    async def test_batch_update_conflict_filled_canceled(self):
        """If filled and canceled arrive together, choose canceled and log warning."""
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
        canceled_update = Order(
            id="1", symbol="BTC", side="Bid", price=50000.0, size=0.0,
            owner="0x123", timestamp=datetime.now(), status="canceled"
        )

        await self.manager.update_orders_batch_async([filled_update, canceled_update])

        final = self.manager.get_order_by_id("1")
        assert final.status == "canceled"

    @pytest.mark.asyncio
    async def test_batch_update_priority(self):
        """Batch update resolves by priority: canceled > filled > triggered > open."""
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
    
    @pytest.mark.asyncio
    async def test_order_filtering_by_symbol(self):
        """Test order filtering by supported symbols."""
        # Create config with limited symbols
        config = Config(
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
                SymbolConfig(symbol="BTC", min_liquidity=0.0, price_deviation=0.01),
                SymbolConfig(symbol="ETH", min_liquidity=0.0, price_deviation=0.01)
            ]
        )
        
        # Mock config manager
        with patch.object(self.config_manager, 'get_config', return_value=config):
            # Try to add BTC order (should work)
            btc_order = Order(
                id="btc_order",
                symbol="BTC",
                side="Bid",
                price=50000.0,
                size=1.0,
                owner="0x123",
                timestamp=datetime.now(),
                status="open"
            )
            await self.manager.update_order(btc_order)
            assert self.manager.get_order_count() == 1
            
            # Try to add SOL order (should be filtered out)
            sol_order = Order(
                id="sol_order",
                symbol="SOL",
                side="Ask",
                price=100.0,
                size=10.0,
                owner="0x456",
                timestamp=datetime.now(),
                status="open"
            )
            await self.manager.update_order(sol_order)
            assert self.manager.get_order_count() == 1  # Still only 1 order
            
            # Try to add ETH order (should work)
            eth_order = Order(
                id="eth_order",
                symbol="ETH",
                side="Ask",
                price=3000.0,
                size=5.0,
                owner="0x789",
                timestamp=datetime.now(),
                status="open"
            )
            await self.manager.update_order(eth_order)
            assert self.manager.get_order_count() == 2  # Now 2 orders
    
    @pytest.mark.asyncio
    async def test_order_filtering_by_liquidity(self):
        """Test order filtering by minimum liquidity requirements."""
        # Create config with liquidity requirements
        config = Config(
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
                SymbolConfig(symbol="BTC", min_liquidity=100000.0, price_deviation=0.01),  # BTC min 100k liquidity
                SymbolConfig(symbol="ETH", min_liquidity=15000.0, price_deviation=0.01)   # ETH min 15k liquidity
            ]
        )
        
        # Mock config manager
        with patch.object(self.config_manager, 'get_config', return_value=config):
            # Try to add BTC order with insufficient liquidity (should be filtered out)
            small_btc_order = Order(
                id="small_btc",
                symbol="BTC",
                side="Bid",
                price=50000.0,
                size=1.0,  # Liquidity = 50000 * 1.0 = 50000 < 100000
                owner="0x123",
                timestamp=datetime.now(),
                status="open"
            )
            await self.manager.update_order(small_btc_order)
            assert self.manager.get_order_count() == 0
            
            # Try to add BTC order with sufficient liquidity (should work)
            large_btc_order = Order(
                id="large_btc",
                symbol="BTC",
                side="Bid",
                price=50000.0,
                size=3.0,  # Liquidity = 50000 * 3.0 = 150000 > 100000
                owner="0x123",
                timestamp=datetime.now(),
                status="open"
            )
            await self.manager.update_order(large_btc_order)
            assert self.manager.get_order_count() == 1
            
            # Try to add ETH order with insufficient liquidity (should be filtered out)
            small_eth_order = Order(
                id="small_eth",
                symbol="ETH",
                side="Ask",
                price=3000.0,
                size=2.0,  # Liquidity = 3000 * 2.0 = 6000 < 15000
                owner="0x456",
                timestamp=datetime.now(),
                status="open"
            )
            await self.manager.update_order(small_eth_order)
            assert self.manager.get_order_count() == 1  # Still only 1 order
            
            # Try to add ETH order with sufficient liquidity (should work)
            large_eth_order = Order(
                id="large_eth",
                symbol="ETH",
                side="Ask",
                price=3000.0,
                size=10.0,  # Liquidity = 3000 * 10.0 = 30000 > 15000
                owner="0x456",
                timestamp=datetime.now(),
                status="open"
            )
            await self.manager.update_order(large_eth_order)
            assert self.manager.get_order_count() == 2  # Now 2 orders
