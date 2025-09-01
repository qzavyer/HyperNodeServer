"""Log parser for HyperLiquid node logs."""

import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from src.storage.models import LogEntry, ParsedData, Order
from src.parser.order_extractor import OrderExtractor
from src.utils.logger import get_logger

logger = get_logger(__name__)

class ParserError(Exception):
    """Base exception for parser errors."""
    pass

class LogParser:
    """Parser for HyperLiquid Node log files."""
    
    def __init__(self):
        """Initialize log parser."""
        self.logger = get_logger(__name__)
    
    def parse_file(self, file_path: str) -> List['Order']:
        """Parse log file and extract orders.
        
        Args:
            file_path: Path to log file
            
        Returns:
            List of extracted orders
            
        Raises:
            FileNotFoundError: If file not found
            ParserError: If parsing fails
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {file_path}")
        
        orders = []
        try:
            with open(path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        order = self._parse_line(line)
                        if order:
                            orders.append(order)
                    except Exception as e:
                        self.logger.warning(f"Failed to parse line {line_num}: {e}")
                        continue
            
            self.logger.info(f"Parsed {len(orders)} orders from {file_path}")
            return orders
            
        except Exception as e:
            raise ParserError(f"Failed to parse file {file_path}: {e}")
    
    def _parse_line(self, line: str) -> Optional['Order']:
        """Parse single log line.
        
        Args:
            line: Raw log line
            
        Returns:
            Order object if valid, None otherwise
        """
        try:
            data = json.loads(line)
            return self._extract_order(data)
        except json.JSONDecodeError as e:
            self.logger.debug(f"Invalid JSON in line: {line[:100]}...")
            return None
    
    def _extract_order(self, data: Dict[str, Any]) -> Optional['Order']:
        """Extract order from parsed JSON data.
        
        Args:
            data: Parsed JSON data
            
        Returns:
            Order object if valid data, None otherwise
        """
        extractor = OrderExtractor()
        return extractor.extract_order(data)
