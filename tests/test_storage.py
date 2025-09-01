"""Tests for file storage module."""

import pytest
import tempfile
import os
from pathlib import Path
from src.storage.file_storage import FileStorage, StorageError
from src.storage.models import Order
from datetime import datetime

class TestFileStorage:
    """Tests for FileStorage class."""
    
    def setup_method(self):
        """Setup before each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.storage = FileStorage(self.temp_dir)
    
    def teardown_method(self):
        """Cleanup after each test."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_save_and_load_orders(self):
        """Test saving and loading orders."""
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
            )
        ]
        
        self.storage.save_orders(orders)
        loaded_orders = self.storage.load_orders()
        
        assert len(loaded_orders) == 1
        assert loaded_orders[0].id == "1"
        assert loaded_orders[0].symbol == "BTC"
        assert loaded_orders[0].side == "Bid"
    
    def test_load_orders_empty_file(self):
        """Test loading orders from empty file."""
        orders = self.storage.load_orders()
        assert orders == []
