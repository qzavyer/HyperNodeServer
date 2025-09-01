"""Integration tests for HyperLiquid Node Parser."""

import pytest
import tempfile
import shutil
import json
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock
from datetime import datetime, timedelta

from src.storage.file_storage import FileStorage
from src.storage.order_manager import OrderManager
from src.storage.config_manager import ConfigManager
from src.parser.log_parser import LogParser
from src.parser.order_extractor import OrderExtractor
from src.storage.models import Order, Config

class TestIntegration:
    """Integration tests for complete workflow."""
    
    def setup_method(self):
        """Setup before each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "data"
        self.logs_dir = Path(self.temp_dir) / "logs"
        self.data_dir.mkdir()
        self.logs_dir.mkdir()
        
        # Create test log file
        self.test_log_file = self.logs_dir / "test.log"
        self.create_test_log_file()
    
    def teardown_method(self):
        """Cleanup after each test."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_log_file(self):
        """Create test log file with sample data."""
        test_data = [
            '{"user":"0x1234567890abcdef","oid":123,"coin":"BTC","side":"Bid","px":"50000","sz":"1.0","time":1640995200000}',
            '{"user":"0xfedcba0987654321","oid":456,"coin":"ETH","side":"Ask","px":"3000","sz":"10.0","time":1640995201000}',
            '{"user":"0xabcdef1234567890","oid":789,"coin":"BTC","side":"Bid","px":"49000","sz":"0.5","time":1640995202000}',
            'invalid json line',
            '{"user":"0x1111111111111111","oid":999,"coin":"SOL","side":"Ask","px":"100","sz":"100.0","time":1640995203000}'
        ]
        
        with open(self.test_log_file, 'w') as f:
            for line in test_data:
                f.write(line + '\n')
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """Test complete workflow from log parsing to API response."""
        # 1. Initialize components
        file_storage = FileStorage()
        file_storage.data_dir = self.data_dir
        
        order_manager = OrderManager(file_storage)
        config_manager = ConfigManager(str(self.data_dir / "config.json"))
        
        # 2. Load configuration
        with patch('src.storage.config_manager.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = str(self.logs_dir)
            mock_settings.CLEANUP_INTERVAL_HOURS = 2
            mock_settings.API_HOST = "0.0.0.0"
            mock_settings.API_PORT = 8000
            mock_settings.LOG_LEVEL = "DEBUG"
            mock_settings.LOG_FILE_PATH = "logs/app.log"
            mock_settings.LOG_MAX_SIZE_MB = 100
            mock_settings.LOG_RETENTION_DAYS = 30
            mock_settings.DATA_DIR = "data"
            mock_settings.CONFIG_FILE_PATH = "config/config.json"
            mock_settings.MAX_ORDERS_PER_REQUEST = 1000
            mock_settings.FILE_READ_RETRY_ATTEMPTS = 3
            mock_settings.FILE_READ_RETRY_DELAY = 1.0
            
            config = await config_manager.load_config_async()
        
        # 3. Initialize order manager
        await order_manager.initialize()
        
        # 4. Parse log file
        log_parser = LogParser()
        orders = log_parser.parse_file(str(self.test_log_file))
        
        # 5. Add orders to manager
        for order in orders:
            order_manager.add_order(order)
        
        # 6. Save orders to storage
        await file_storage.save_orders_async(orders)
        
        # 7. Verify results
        assert len(orders) == 4  # 4 valid orders, 1 invalid line
        
        # Check order details
        btc_orders = [o for o in orders if o.symbol == "BTC"]
        eth_orders = [o for o in orders if o.symbol == "ETH"]
        sol_orders = [o for o in orders if o.symbol == "SOL"]
        
        assert len(btc_orders) == 2
        assert len(eth_orders) == 1
        assert len(sol_orders) == 1
        
        # Check specific order
        btc_bid_order = next(o for o in btc_orders if o.side == "Bid" and o.price == 50000.0)
        assert btc_bid_order.size == 1.0
        assert btc_bid_order.owner == "0x1234567890abcdef"
        assert btc_bid_order.status == "open"
        
        # 8. Test filtering
        filtered_orders = order_manager.get_orders(symbol="BTC", side="Bid")
        assert len(filtered_orders) == 2
        
        # 9. Test order retrieval by ID
        order_id = f"0x1234567890abcdef_123"
        retrieved_order = order_manager.get_order_by_id(order_id)
        assert retrieved_order is not None
        assert retrieved_order.symbol == "BTC"
        assert retrieved_order.price == 50000.0
        
        # 10. Test statistics
        total_count = order_manager.get_order_count()
        assert total_count == 4
        
        status_counts = order_manager.get_order_count_by_status()
        assert status_counts["open"] == 4
        
        open_orders = order_manager.get_open_orders()
        assert len(open_orders) == 4
    
    @pytest.mark.asyncio
    async def test_order_status_transitions(self):
        """Test order status transitions."""
        # Setup
        file_storage = FileStorage()
        file_storage.data_dir = self.data_dir
        order_manager = OrderManager(file_storage)
        await order_manager.initialize()
        
        # Create test order
        order = Order(
            id="test_order_1",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x1234567890abcdef",
            timestamp=datetime.now(),
            status="open"
        )
        
        order_manager.add_order(order)
        
        # Test status transitions
        assert order.status == "open"
        
        # Fill order
        order_manager.update_order_status("test_order_1", "filled")
        assert order.status == "filled"
        
        # Try to cancel filled order (should not work)
        order_manager.update_order_status("test_order_1", "cancelled")
        assert order.status == "filled"  # Should remain filled
        
        # Create new order and cancel it
        order2 = Order(
            id="test_order_2",
            symbol="ETH",
            side="Ask",
            price=3000.0,
            size=10.0,
            owner="0xfedcba0987654321",
            timestamp=datetime.now(),
            status="open"
        )
        
        order_manager.add_order(order2)
        order_manager.update_order_status("test_order_2", "cancelled")
        assert order2.status == "cancelled"
    
    @pytest.mark.asyncio
    async def test_configuration_persistence(self):
        """Test configuration persistence across restarts."""
        # Setup
        config_manager = ConfigManager(str(self.data_dir / "config.json"))
        
        # Load initial config
        with patch('src.storage.config_manager.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = "/initial/path"
            mock_settings.CLEANUP_INTERVAL_HOURS = 2
            mock_settings.API_HOST = "0.0.0.0"
            mock_settings.API_PORT = 8000
            mock_settings.LOG_LEVEL = "DEBUG"
            mock_settings.LOG_FILE_PATH = "logs/app.log"
            mock_settings.LOG_MAX_SIZE_MB = 100
            mock_settings.LOG_RETENTION_DAYS = 30
            mock_settings.DATA_DIR = "data"
            mock_settings.CONFIG_FILE_PATH = "config/config.json"
            mock_settings.MAX_ORDERS_PER_REQUEST = 1000
            mock_settings.FILE_READ_RETRY_ATTEMPTS = 3
            mock_settings.FILE_READ_RETRY_DELAY = 1.0
            
            initial_config = await config_manager.load_config_async()
        
        # Update configuration
        updates = {
            "api_port": 9000,
            "log_level": "INFO",
            "min_liquidity_by_symbol": {"BTC": 1000.0},
            "supported_symbols": ["BTC", "ETH"]
        }
        
        updated_config = await config_manager.update_config_async(updates)
        
        # Verify updates
        assert updated_config.api_port == 9000
        assert updated_config.log_level == "INFO"
        assert updated_config.min_liquidity_by_symbol == {"BTC": 1000.0}
        assert updated_config.supported_symbols == ["BTC", "ETH"]
        
        # Create new config manager (simulate restart)
        new_config_manager = ConfigManager(str(self.data_dir / "config.json"))
        
        # Load config again
        reloaded_config = await new_config_manager.load_config_async()
        
        # Verify persistence
        assert reloaded_config.api_port == 9000
        assert reloaded_config.log_level == "INFO"
        assert reloaded_config.min_liquidity_by_symbol == {"BTC": 1000.0}
        assert reloaded_config.supported_symbols == ["BTC", "ETH"]
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Test error handling and recovery scenarios."""
        # Setup
        file_storage = FileStorage()
        file_storage.data_dir = self.data_dir
        order_manager = OrderManager(file_storage)
        await order_manager.initialize()
        
        # Test invalid order data
        invalid_order_data = {
            "user": "0x123",
            "oid": 123,
            "coin": "BTC",
            "side": "InvalidSide",  # Invalid side
            "px": "-50000",  # Negative price
            "sz": "0",  # Zero size
            "time": 1640995200000
        }
        
        # Test parsing invalid data
        order_extractor = OrderExtractor()
        result = order_extractor.extract_order(invalid_order_data)
        assert result is None  # Should return None for invalid data
        
        # Test duplicate order handling
        order1 = Order(
            id="duplicate_order",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,
            owner="0x1234567890abcdef",
            timestamp=datetime.now(),
            status="open"
        )
        
        order2 = Order(
            id="duplicate_order",  # Same ID
            symbol="BTC",
            side="Bid",
            price=51000.0,  # Different price
            size=2.0,  # Different size
            owner="0x1234567890abcdef",
            timestamp=datetime.now(),
            status="open"
        )
        
        # Add first order
        order_manager.add_order(order1)
        assert order_manager.get_order_by_id("duplicate_order") is not None
        
        # Add duplicate order (should update existing)
        order_manager.add_order(order2)
        updated_order = order_manager.get_order_by_id("duplicate_order")
        assert updated_order.price == 51000.0  # Should be updated
        assert updated_order.size == 2.0  # Should be updated
    
    @pytest.mark.asyncio
    async def test_performance_with_large_dataset(self):
        """Test performance with large dataset."""
        # Setup
        file_storage = FileStorage()
        file_storage.data_dir = self.data_dir
        order_manager = OrderManager(file_storage)
        await order_manager.initialize()
        
        # Create large dataset
        orders = []
        for i in range(1000):
            order = Order(
                id=f"order_{i}",
                symbol="BTC" if i % 2 == 0 else "ETH",
                side="Bid" if i % 3 == 0 else "Ask",
                price=50000.0 + (i % 1000),
                size=1.0 + (i % 10) * 0.1,
                owner=f"0x{i:040x}",
                timestamp=datetime.now() + timedelta(seconds=i),
                status="open"
            )
            orders.append(order)
        
        # Add orders in batches
        batch_size = 100
        for i in range(0, len(orders), batch_size):
            batch = orders[i:i + batch_size]
            for order in batch:
                order_manager.add_order(order)
        
        # Test filtering performance
        btc_orders = order_manager.get_orders(symbol="BTC")
        assert len(btc_orders) == 500
        
        bid_orders = order_manager.get_orders(side="Bid")
        assert len(bid_orders) == 334  # Every 3rd order
        
        # Test statistics performance
        total_count = order_manager.get_order_count()
        assert total_count == 1000
        
        status_counts = order_manager.get_order_count_by_status()
        assert status_counts["open"] == 1000
        
        # Test order retrieval performance
        test_order_id = "order_500"
        retrieved_order = order_manager.get_order_by_id(test_order_id)
        assert retrieved_order is not None
        assert retrieved_order.symbol == "ETH"  # 500 is even, so ETH
        assert retrieved_order.side == "Ask"  # 500 % 3 = 2, so Ask
