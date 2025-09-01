"""Tests for parser module."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from src.parser.log_parser import LogParser
from src.parser.order_extractor import OrderExtractor
from src.storage.models import Order

class TestLogParser:
    """Tests for LogParser class."""
    
    def setup_method(self):
        """Setup before each test."""
        self.parser = LogParser()
    
    def test_parse_file_not_found(self):
        """Test parsing non-existent file."""
        with pytest.raises(FileNotFoundError):
            self.parser.parse_file("non_existent_file.json")
    
    def test_parse_line_invalid_json(self):
        """Test parsing invalid JSON line."""
        result = self.parser._parse_line("invalid json")
        assert result is None
    
    def test_parse_new_order(self):
        """Test parsing new order."""
        json_line = '{"user":"0x123","oid":123,"coin":"BTC","side":"Bid","px":"50000","raw_book_diff":{"new":{"sz":"1.5"}}}'
        result = self.parser._parse_line(json_line)
        
        assert result is not None
        assert result.symbol == "BTC"
        assert result.side == "Bid"
        assert result.price == 50000.0
        assert result.size == 1.5
        assert result.status == "open"
        assert result.owner == "0x123"
    
    def test_parse_update_order(self):
        """Test parsing updated order."""
        json_line = '{"user":"0x456","oid":456,"coin":"ETH","side":"Ask","px":"3000","raw_book_diff":{"update":{"origSz":"2.0","newSz":"1.8"}}}'
        result = self.parser._parse_line(json_line)
        
        assert result is not None
        assert result.symbol == "ETH"
        assert result.side == "Ask"
        assert result.price == 3000.0
        assert result.size == 1.8
        assert result.status == "open"
    
    def test_parse_remove_order(self):
        """Test parsing removed order."""
        json_line = '{"user":"0x789","oid":789,"coin":"BTC","side":"Bid","px":"49000","raw_book_diff":"remove"}'
        result = self.parser._parse_line(json_line)
        
        assert result is not None
        assert result.symbol == "BTC"
        assert result.side == "Bid"
        assert result.price == 49000.0
        assert result.size == 0.0
        assert result.status == "cancelled"
    
    def test_parse_file_with_orders(self):
        """Test parsing file with multiple orders."""
        # Create temporary file with test data
        test_data = [
            '{"user":"0x123","oid":123,"coin":"BTC","side":"Bid","px":"50000","raw_book_diff":{"new":{"sz":"1.5"}}}',
            '{"user":"0x456","oid":456,"coin":"ETH","side":"Ask","px":"3000","raw_book_diff":{"new":{"sz":"2.0"}}}',
            '{"user":"0x789","oid":789,"coin":"BTC","side":"Bid","px":"49000","raw_book_diff":"remove"}'
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            for line in test_data:
                f.write(line + '\n')
            temp_file = f.name
        
        try:
            orders = self.parser.parse_file(temp_file)
            assert len(orders) == 3
            
            # Check first order (new)
            assert orders[0].symbol == "BTC"
            assert orders[0].side == "Bid"
            assert orders[0].status == "open"
            
            # Check second order (new)
            assert orders[1].symbol == "ETH"
            assert orders[1].side == "Ask"
            assert orders[1].status == "open"
            
            # Check third order (removed)
            assert orders[2].symbol == "BTC"
            assert orders[2].status == "cancelled"
            assert orders[2].size == 0.0
            
        finally:
            import os
            os.unlink(temp_file)

class TestOrderExtractor:
    """Tests for OrderExtractor class."""
    
    def setup_method(self):
        """Setup before each test."""
        self.extractor = OrderExtractor()
    
    def test_validate_order_data_valid(self):
        """Test validation of valid order data."""
        data = {
            "user": "0x123",
            "oid": 123,
            "coin": "BTC",
            "side": "Bid",
            "px": "50000"
        }
        assert self.extractor._validate_order_data(data) is True
    
    def test_validate_order_data_invalid(self):
        """Test validation of invalid order data."""
        data = {
            "user": "0x123",
            "oid": 123,
            # Missing required fields
        }
        assert self.extractor._validate_order_data(data) is False
    
    def test_get_operation_type_new(self):
        """Test operation type detection for new order."""
        data = {"raw_book_diff": {"new": {"sz": "1.5"}}}
        assert self.extractor._get_operation_type(data) == "new"
    
    def test_get_operation_type_update(self):
        """Test operation type detection for update."""
        data = {"raw_book_diff": {"update": {"origSz": "2.0", "newSz": "1.8"}}}
        assert self.extractor._get_operation_type(data) == "update"
    
    def test_get_operation_type_remove(self):
        """Test operation type detection for remove."""
        data = {"raw_book_diff": "remove"}
        assert self.extractor._get_operation_type(data) == "remove"
    
    def test_get_operation_type_unknown(self):
        """Test operation type detection for unknown type."""
        data = {"raw_book_diff": {"unknown": "data"}}
        assert self.extractor._get_operation_type(data) == "unknown"
    

