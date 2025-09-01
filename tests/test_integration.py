"""Integration tests for HyperLiquid Node Parser."""

import pytest
import tempfile
import json
from datetime import datetime
from unittest.mock import patch

from src.parser.log_parser import LogParser
from src.storage.file_storage import FileStorage
from src.storage.order_manager import OrderManager
from src.storage.models import Order

class TestIntegration:
    """Integration tests for complete workflow."""
    
    def setup_method(self):
        """Setup before each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = FileStorage(self.temp_dir)
        self.manager = OrderManager(self.storage)
        self.parser = LogParser()
    
    def teardown_method(self):
        """Cleanup after each test."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """Test complete workflow: parse -> store -> manage -> query."""
        # Create test log file
        test_log_data = [
            '{"user":"0x123","oid":123,"coin":"BTC","side":"Bid","px":"50000","raw_book_diff":{"new":{"sz":"1.5"}}}',
            '{"user":"0x456","oid":456,"coin":"ETH","side":"Ask","px":"3000","raw_book_diff":{"new":{"sz":"2.0"}}}',
            '{"user":"0x789","oid":789,"coin":"BTC","side":"Bid","px":"49000","raw_book_diff":"remove"}',
            '{"user":"0x123","oid":123,"coin":"BTC","side":"Bid","px":"50000","raw_book_diff":{"update":{"origSz":"1.5","newSz":"1.0"}}}'
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            for line in test_log_data:
                f.write(line + '\n')
            temp_file = f.name
        
        try:
            # Step 1: Parse log file
            orders = self.parser.parse_file(temp_file)
            assert len(orders) == 4
            
            # Step 2: Initialize order manager
            await self.manager.initialize()
            
            # Step 3: Add orders to manager (simulating real-time updates)
            for order in orders:
                await self.manager.update_order(order)
            
            # Step 4: Verify orders are stored and managed correctly
            assert self.manager.get_order_count() == 3  # 3 unique orders (123, 456, 789)
            
            # Check order 123 (new -> update)
            order_123 = self.manager.get_order_by_id("123")
            assert order_123 is not None
            assert order_123.status == "open"
            assert order_123.size == 1.0  # Updated size
            
            # Check order 456 (new)
            order_456 = self.manager.get_order_by_id("456")
            assert order_456 is not None
            assert order_456.status == "open"
            assert order_456.symbol == "ETH"
            
            # Check order 789 (remove)
            order_789 = self.manager.get_order_by_id("789")
            assert order_789 is not None
            assert order_789.status == "cancelled"
            assert order_789.size == 0.0
            
            # Step 5: Test filtering
            btc_orders = self.manager.get_orders(symbol="BTC")
            assert len(btc_orders) == 2
            
            open_orders = self.manager.get_orders(status="open")
            assert len(open_orders) == 2
            
            bid_orders = self.manager.get_orders(side="Bid")
            assert len(bid_orders) == 2
            
            # Step 6: Test statistics
            stats = self.manager.get_order_count_by_status()
            assert stats["open"] == 2
            assert stats["cancelled"] == 1
            
        finally:
            import os
            os.unlink(temp_file)
    
    @pytest.mark.asyncio
    async def test_status_transition_workflow(self):
        """Test status transition workflow."""
        await self.manager.initialize()
        
        # Create order with open status
        order = self.parser._parse_line(
            '{"user":"0x123","oid":123,"coin":"BTC","side":"Bid","px":"50000","raw_book_diff":{"new":{"sz":"1.5"}}}'
        )
        await self.manager.update_order(order)
        
        # Update to triggered (create order manually since parser doesn't handle triggered)
        triggered_order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.5,
            owner="0x123",
            timestamp=datetime.now(),
            status="triggered"
        )
        await self.manager.update_order(triggered_order)
        
        # Update to filled
        filled_order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.5,
            owner="0x123",
            timestamp=datetime.now(),
            status="filled"
        )
        await self.manager.update_order(filled_order)
        
        # Verify final status
        final_order = self.manager.get_order_by_id("123")
        assert final_order.status == "filled"
        
        # Try to update filled order (should be ignored)
        cancelled_order = Order(
            id="123",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.5,
            owner="0x123",
            timestamp=datetime.now(),
            status="cancelled"
        )
        await self.manager.update_order(cancelled_order)
        
        # Status should remain filled
        final_order = self.manager.get_order_by_id("123")
        assert final_order.status == "filled"
    
    @pytest.mark.asyncio
    async def test_persistence_workflow(self):
        """Test persistence workflow."""
        # Add orders to manager
        await self.manager.initialize()
        
        order1 = self.parser._parse_line(
            '{"user":"0x123","oid":123,"coin":"BTC","side":"Bid","px":"50000","raw_book_diff":{"new":{"sz":"1.5"}}}'
        )
        order2 = self.parser._parse_line(
            '{"user":"0x456","oid":456,"coin":"ETH","side":"Ask","px":"3000","raw_book_diff":{"new":{"sz":"2.0"}}}'
        )
        
        await self.manager.update_order(order1)
        await self.manager.update_order(order2)
        
        # Verify orders are in memory
        assert self.manager.get_order_count() == 2
        
        # Create new manager instance (simulating restart)
        new_storage = FileStorage(self.temp_dir)
        new_manager = OrderManager(new_storage)
        await new_manager.initialize()
        
        # Verify orders are loaded from storage
        assert new_manager.get_order_count() == 2
        assert new_manager.get_order_by_id("123") is not None
        assert new_manager.get_order_by_id("456") is not None
