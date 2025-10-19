"""Integration tests for HyperLiquid Node Parser."""

import pytest
import tempfile
import shutil
import json
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, Mock
from datetime import datetime, timedelta

from src.storage.order_manager import OrderManager
from src.storage.config_manager import ConfigManager
from src.parser.log_parser import LogParser
from src.parser.order_extractor import OrderExtractor
from src.watcher.single_file_tail_watcher import SingleFileTailWatcher
from src.storage.models import Order, Config, SymbolConfig

@pytest.fixture
def temp_dir():
    """Create temporary directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def sample_config(temp_dir):
    """Create sample configuration."""
    config = Config(
        node_logs_path=str(temp_dir / "logs"),
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
    return config

@pytest.fixture
def mock_order_notifier():
    """Mock order notifier."""
    notifier = Mock()
    notifier.notify_order_update = AsyncMock()
    notifier.notify_orders_batch = AsyncMock()
    return notifier

class TestIntegration:
    """Integration tests for complete workflow."""
    
    def setup_method(self):
        """Setup before each test."""
        # Always create a fresh temporary directory
        self.temp_dir = Path(tempfile.mkdtemp())
        self.data_dir = self.temp_dir / "data"
        self.logs_dir = self.temp_dir / "logs"
        
        # Create fresh directories
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create test log file
        self.test_log_file = self.logs_dir / "test.log"
        self.create_test_log_file()
    
    def teardown_method(self):
        """Cleanup after each test."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_log_file(self):
        """Create test log file with sample data."""
        test_data = [
            '{"time":"2025-09-02T08:26:36.877863946","user":"0x1234567890abcdef","status":"open","order":{"coin":"BTC","side":"B","limitPx":"50000","origSz":"1.0","oid":123}}',
            '{"time":"2025-09-02T08:26:36.877863946","user":"0xfedcba0987654321","status":"open","order":{"coin":"ETH","side":"A","limitPx":"3000","origSz":"10.0","oid":456}}',
            '{"time":"2025-09-02T08:26:36.877863946","user":"0xabcdef1234567890","status":"open","order":{"coin":"BTC","side":"B","limitPx":"49000","origSz":"0.5","oid":789}}',
            'invalid json line',
            '{"time":"2025-09-02T08:26:36.877863946","user":"0x1111111111111111","status":"open","order":{"coin":"SOL","side":"A","limitPx":"100","origSz":"100.0","oid":999}}'
        ]
        
        with open(self.test_log_file, 'w') as f:
            for line in test_data:
                f.write(line + '\n')
    
    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """Test complete workflow from log parsing to API response."""
        # 1. Initialize components
        config_manager = ConfigManager(str(self.data_dir / "config.json"))
        
        # Create order notifier
        from src.notifications.order_notifier import OrderNotifier
        from src.websocket.websocket_manager import WebSocketManager
        websocket_manager = WebSocketManager()
        order_notifier = OrderNotifier(websocket_manager, config_manager)
        
        order_manager = OrderManager(config_manager, order_notifier)
        
        # 2. Load configuration with symbols
        with patch('src.storage.config_manager.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = str(self.logs_dir)
            mock_settings.DATA_PATH = str(self.data_dir)
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
            
            # Add symbols configuration to allow orders
            await config_manager.update_config_async({
                "symbols_config": [
                    {"symbol": "BTC", "min_liquidity": 100.0, "price_deviation": 0.01},
                    {"symbol": "ETH", "min_liquidity": 50.0, "price_deviation": 0.02},
                    {"symbol": "SOL", "min_liquidity": 10.0, "price_deviation": 0.03}
                ]
            })
        
        # 3. Clear any existing state before initialization
        order_manager.clear()
        
        # Clear any existing data files before initialization
        if self.data_dir.exists():
            for file in self.data_dir.glob('*'):
                if file.is_file():
                    file.unlink()
        
        # Initialize order manager (after clearing files)
        await order_manager.initialize()
        
        # 4. Parse log file
        log_parser = LogParser()
        orders = log_parser.parse_file(str(self.test_log_file))
        
        # 5. Add orders to manager
        for order in orders:
            await order_manager.update_order(order)
        
        # 6. Orders are processed in real-time (no storage needed)
        
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
        filtered_orders = order_manager.get_orders_by_symbol("BTC")
        assert len(filtered_orders) == 2
        
        # 9. Test order retrieval by ID
        order_id = "123"
        retrieved_order = order_manager.orders.get(order_id)
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
        config_manager = ConfigManager(str(self.data_dir / "config.json"))
        # Create order notifier
        from src.notifications.order_notifier import OrderNotifier
        from src.websocket.websocket_manager import WebSocketManager
        websocket_manager = WebSocketManager()
        order_notifier = OrderNotifier(websocket_manager, config_manager)
        
        order_manager = OrderManager(config_manager, order_notifier)
        
        # Load configuration with symbols
        with patch('src.storage.config_manager.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = str(self.data_dir)
            mock_settings.DATA_PATH = str(self.data_dir)
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
            
            # Add symbols configuration to allow orders
            await config_manager.update_config_async({
                "symbols_config": [
                    {"symbol": "BTC", "min_liquidity": 100.0, "price_deviation": 0.01},
                    {"symbol": "ETH", "min_liquidity": 50.0, "price_deviation": 0.02}
                ]
            })
        
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
        
        await order_manager.update_order(order)
        
        # Test status transitions
        assert order.status == "open"
        
        # Verify order was added
        retrieved_order = order_manager.orders.get("test_order_1")
        assert retrieved_order is not None
        assert retrieved_order.status == "open"
        
        # Fill order
        filled_order = Order(
            id="test_order_1",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,  # Keep size > 0 to pass liquidity filter
            owner="0x1234567890abcdef",
            timestamp=datetime.now(),
            status="filled"
        )
        await order_manager.update_order(filled_order)
        
        # Verify status was updated
        updated_order = order_manager.orders.get("test_order_1")
        assert updated_order is not None
        print(f"DEBUG: Order status after update: {updated_order.status}")
        print(f"DEBUG: Order manager orders: {list(order_manager.orders.keys())}")
        print(f"DEBUG: Order manager order statuses: {[(k, v.status) for k, v in order_manager.orders.items()]}")
        assert updated_order.status == "filled"
        
        # Try to cancel filled order (should not work)
        cancelled_order = Order(
            id="test_order_1",
            symbol="BTC",
            side="Bid",
            price=50000.0,
            size=1.0,  # Keep size > 0 to pass liquidity filter
            owner="0x1234567890abcdef",
            timestamp=datetime.now(),
            status="canceled"
        )
        await order_manager.update_order(cancelled_order)
        assert order_manager.orders.get("test_order_1").status == "filled"  # Should remain filled
        
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
        
        await order_manager.update_order(order2)
        cancelled_order2 = Order(
            id="test_order_2",
            symbol="ETH",
            side="Ask",
            price=3000.0,
            size=10.0,  # Keep size > 0 to pass liquidity filter
            owner="0xfedcba0987654321",
            timestamp=datetime.now(),
            status="canceled"
        )
        await order_manager.update_order(cancelled_order2)
        assert order_manager.orders.get("test_order_2").status == "canceled"
    
    @pytest.mark.asyncio
    async def test_configuration_persistence(self):
        """Test configuration persistence across restarts."""
        # Setup
        config_manager = ConfigManager(str(self.data_dir / "config.json"))
        
        # Load initial config
        with patch('src.storage.config_manager.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = "/initial/path"
            mock_settings.DATA_PATH = "/initial/path"
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
            "symbols_config": [
                {"symbol": "BTC", "min_liquidity": 1000.0, "price_deviation": 0.01}
            ]
        }
        
        updated_config = await config_manager.update_config_async(updates)
        
        # Verify updates
        assert updated_config.api_port == 9000
        assert updated_config.log_level == "INFO"
        assert len(updated_config.symbols_config) == 1
        assert updated_config.symbols_config[0].symbol == "BTC"
        assert updated_config.symbols_config[0].min_liquidity == 1000.0
        
        # Create new config manager (simulate restart)
        new_config_manager = ConfigManager(str(self.data_dir / "config.json"))
        
        # Load config again
        reloaded_config = await new_config_manager.load_config_async()
        
        # Verify persistence
        assert reloaded_config.api_port == 9000
        assert reloaded_config.log_level == "INFO"
        assert len(reloaded_config.symbols_config) == 1
        assert reloaded_config.symbols_config[0].symbol == "BTC"
        assert reloaded_config.symbols_config[0].min_liquidity == 1000.0
    
    @pytest.mark.asyncio
    async def test_error_handling_and_recovery(self):
        """Test error handling and recovery scenarios."""
        # Setup
        config_manager = ConfigManager(str(self.data_dir / "config.json"))
        # Create order notifier
        from src.notifications.order_notifier import OrderNotifier
        from src.websocket.websocket_manager import WebSocketManager
        websocket_manager = WebSocketManager()
        order_notifier = OrderNotifier(websocket_manager, config_manager)
        
        order_manager = OrderManager(config_manager, order_notifier)
        
        # Load configuration with symbols
        with patch('src.storage.config_manager.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = str(self.data_dir)
            mock_settings.DATA_PATH = str(self.data_dir)
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
            
            # Add symbols configuration to allow orders
            await config_manager.update_config_async({
                "symbols_config": [
                    {"symbol": "BTC", "min_liquidity": 100.0, "price_deviation": 0.01},
                    {"symbol": "ETH", "min_liquidity": 50.0, "price_deviation": 0.02}
                ]
            })
        
        await order_manager.initialize()
        
        # Test invalid order data
        invalid_order_data = {
            "user": "0x123",
            "oid": 123,
            "coin": "BTC",
            "side": "InvalidSide",  # Invalid side
            "px": "-50000",  # Negative price
            "origSz": "0",  # Zero size
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
        await order_manager.update_order(order1)
        assert order_manager.orders.get("duplicate_order") is not None
        
        # Add duplicate order (should update existing)
        await order_manager.update_order(order2)
        updated_order = order_manager.orders.get("duplicate_order")
        assert updated_order.price == 51000.0  # Should be updated
        assert updated_order.size == 2.0  # Should be updated
    
    @pytest.mark.asyncio
    async def test_performance_with_large_dataset(self):
        """Test performance with large dataset."""
        # Setup
        config_manager = ConfigManager(str(self.data_dir / "config.json"))
        # Create order notifier
        from src.notifications.order_notifier import OrderNotifier
        from src.websocket.websocket_manager import WebSocketManager
        websocket_manager = WebSocketManager()
        order_notifier = OrderNotifier(websocket_manager, config_manager)
        
        order_manager = OrderManager(config_manager, order_notifier)
        
        # Load configuration with symbols
        with patch('src.storage.config_manager.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = str(self.data_dir)
            mock_settings.DATA_PATH = str(self.data_dir)
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
            
            # Add symbols configuration to allow orders
            await config_manager.update_config_async({
                "symbols_config": [
                    {"symbol": "BTC", "min_liquidity": 100.0, "price_deviation": 0.01},
                    {"symbol": "ETH", "min_liquidity": 50.0, "price_deviation": 0.02}
                ]
            })
        
        # Clear any existing state before initialization
        order_manager.clear()
        
        # Clear any existing data files before initialization
        if self.data_dir.exists():
            for file in self.data_dir.glob('*'):
                if file.is_file():
                    file.unlink()
        
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
                await order_manager.update_order(order)
        
        # Test filtering performance
        btc_orders = order_manager.get_orders_by_symbol("BTC")
        assert len(btc_orders) == 500
        
        bid_orders = [o for o in order_manager.orders.values() if o.side == "Bid"]
        assert len(bid_orders) == 334  # Every 3rd order
        
        # Test statistics performance
        total_count = order_manager.get_order_count()
        assert total_count == 1000
        
        status_counts = order_manager.get_order_count_by_status()
        assert status_counts["open"] == 1000
        
        # Test order retrieval performance
        test_order_id = "order_500"
        retrieved_order = order_manager.orders.get(test_order_id)
        assert retrieved_order is not None
        assert retrieved_order.symbol == "BTC"  # 500 is even, so BTC
        assert retrieved_order.side == "Ask"  # 500 % 3 = 2, so Ask
