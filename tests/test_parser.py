"""Tests for parser module."""

import pytest
import tempfile
import os
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
    
    def test_parse_valid_order_new_format(self):
        """Тест парсинга валидного ордера в новом формате."""
        # Arrange
        json_line = '{"time":"2025-09-02T08:26:36.877863946","user":"0x123","status":"open","order":{"coin":"BTC","side":"B","limitPx":"50000","sz":"1.0","oid":123}}'
        
        # Act
        result = self.parser._parse_line(json_line)
        
        # Assert
        assert result is not None
        assert result.symbol == "BTC"
        assert result.price == 50000.0
        assert result.size == 1.0
        assert result.side == "Bid"
        assert result.status == "open"
        assert result.owner == "0x123"
    
    def test_parse_order_with_ask_side(self):
        """Тест парсинга ордера со стороной Ask."""
        # Arrange
        json_line = '{"time":"2025-09-02T08:26:36.877863946","user":"0x456","status":"filled","order":{"coin":"ETH","side":"A","limitPx":"3000","sz":"10.0","oid":456}}'
        
        # Act
        result = self.parser._parse_line(json_line)
        
        # Assert
        assert result is not None
        assert result.side == "Ask"
        assert result.status == "filled"
    
    def test_parse_order_with_canceled_status(self):
        """Тест парсинга отмененного ордера."""
        # Arrange
        json_line = '{"time":"2025-09-02T08:26:36.877863946","user":"0x789","status":"canceled","order":{"coin":"ETH","side":"B","limitPx":"44.663","sz":"223.03","oid":789}}'
        
        # Act
        result = self.parser._parse_line(json_line)
        
        # Assert
        assert result is not None
        assert result.status == "canceled"
        assert result.size == 223.03
    
    def test_parse_file_with_orders(self):
        """Test parsing file with multiple orders."""
        # Create temporary file with test data
        test_data = [
            '{"time":"2025-09-02T08:26:36.877863946","user":"0x123","status":"open","order":{"coin":"BTC","side":"B","limitPx":"50000","sz":"1.0","oid":123}}',
            '{"time":"2025-09-02T08:26:36.877863946","user":"0x456","status":"open","order":{"coin":"ETH","side":"A","limitPx":"3000","sz":"10.0","oid":456}}',
            '{"time":"2025-09-02T08:26:36.877863946","user":"0x789","status":"open","order":{"coin":"BTC","side":"B","limitPx":"49000","sz":"0.5","oid":789}}'
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            for line in test_data:
                f.write(line + '\n')
            temp_file = f.name
        
        try:
            orders = self.parser.parse_file(temp_file)
            assert len(orders) == 3
            
            # Check first order
            assert orders[0].symbol == "BTC"
            assert orders[0].side == "Bid"
            assert orders[0].status == "open"
            
            # Check second order
            assert orders[1].symbol == "ETH"
            assert orders[1].side == "Ask"
            assert orders[1].status == "open"
            
            # Check third order
            assert orders[2].symbol == "BTC"
            assert orders[2].side == "Bid"
            assert orders[2].status == "open"
            
        finally:
            os.remove(temp_file)

class TestOrderExtractor:
    """Tests for OrderExtractor class."""
    
    def setup_method(self):
        """Setup before each test."""
        self.extractor = OrderExtractor()
    
    def test_extract_order_new_format(self):
        """Test extracting order from new format log."""
        log_entry = {
            "time": "2025-09-02T08:26:36.877863946",
            "user": "0x123",
            "status": "open",
            "order": {
                "coin": "BTC",
                "side": "B",
                "limitPx": "50000",
                "sz": "1.0",
                "oid": 123
            }
        }
        
        result = self.extractor.extract_order(log_entry)
        assert result is not None
        assert result.symbol == "BTC"
        assert result.side == "Bid"
        assert result.price == 50000.0
