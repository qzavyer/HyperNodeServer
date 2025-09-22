"""Log parser for HyperLiquid node logs."""

import json
import asyncio
import aiofiles
from pathlib import Path
from typing import List, Optional, Dict, Any, AsyncGenerator
from src.storage.models import LogEntry, ParsedData, Order
from src.parser.order_extractor import OrderExtractor
from src.utils.logger import get_logger

logger = get_logger(__name__)

class ParserError(Exception):
    """Base exception for parser errors."""
    pass

class LogParser:
    """Parser for HyperLiquid Node log files."""
    
    def __init__(self, chunk_size: int = 8192, batch_size: int = 1000):
        """Initialize log parser.
        
        Args:
            chunk_size: Size of file chunks to read (bytes)
            batch_size: Number of orders to process in one batch
        """
        self.logger = get_logger(__name__)
        self.chunk_size = chunk_size
        self.batch_size = batch_size
        self.order_extractor = OrderExtractor()
    
    def parse_file(self, file_path: str) -> List['Order']:
        """Parse log file and extract orders (synchronous, for backward compatibility).
        
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
    
    async def parse_file_async(self, file_path: str, max_orders: Optional[int] = None) -> AsyncGenerator[List[Order], None]:
        """Asynchronously parse large log file in chunks to prevent blocking.
        
        Args:
            file_path: Path to log file
            max_orders: Maximum number of orders to process (None = all)
            
        Yields:
            Batches of orders for processing
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {file_path}")
        
        file_size = path.stat().st_size
        self.logger.info(f"Starting async parse of {file_path} ({file_size / (1024**3):.2f} GB)")
        
        try:
            async with aiofiles.open(path, 'r') as f:
                buffer = ""
                orders_batch = []
                total_orders = 0
                
                while True:
                    # Read chunk of data
                    chunk = await f.read(self.chunk_size)
                    if not chunk:
                        break
                    
                    # Add to buffer and process complete lines
                    buffer += chunk
                    lines = buffer.split('\n')
                    
                    # Keep incomplete line in buffer
                    buffer = lines[-1]
                    lines = lines[:-1]
                    
                    # Process complete lines
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            order = self._parse_line(line)
                            if order:
                                orders_batch.append(order)
                                total_orders += 1
                                
                                # Yield batch when it reaches batch size
                                if len(orders_batch) >= self.batch_size:
                                    yield orders_batch
                                    orders_batch = []
                                    
                                    # Check if we've reached max orders limit
                                    if max_orders and total_orders >= max_orders:
                                        self.logger.info(f"Reached max orders limit: {max_orders}")
                                        return
                                    
                                    # Small delay to prevent blocking
                                    await asyncio.sleep(0.001)
                                    
                        except Exception as e:
                            self.logger.warning(f"Failed to parse line: {e}")
                            continue
                
                # Yield remaining orders
                if orders_batch:
                    yield orders_batch
                
                self.logger.info(f"Completed async parse: {total_orders} orders from {file_path}")
                
        except Exception as e:
            raise ParserError(f"Failed to parse file {file_path} asynchronously: {e}")
    
    async def parse_file_with_timeout_async(self, file_path: str, timeout_seconds: int = 30, max_orders: Optional[int] = None) -> List[Order]:
        """Parse file with timeout to prevent hanging.
        
        Args:
            file_path: Path to log file
            timeout_seconds: Maximum time to spend parsing
            max_orders: Maximum number of orders to process
            
        Returns:
            List of parsed orders
        """
        try:
            orders = []
            async with asyncio.timeout(timeout_seconds):
                async for batch in self.parse_file_async(file_path, max_orders):
                    orders.extend(batch)
                    
                    # Check timeout periodically
                    if len(orders) % (self.batch_size * 10) == 0:
                        await asyncio.sleep(0.001)
            
            return orders
            
        except asyncio.TimeoutError:
            self.logger.warning(f"Parsing timeout after {timeout_seconds}s, returning {len(orders)} orders")
            return orders
        except Exception as e:
            self.logger.error(f"Error in timeout parsing: {e}")
            raise
    
    def parse_line(self, line: str) -> Optional['Order']:
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
    
    def _parse_line(self, line: str) -> Optional['Order']:
        """Parse single log line (private method for internal use).
        
        Args:
            line: Raw log line
            
        Returns:
            Order object if valid, None otherwise
        """
        return self.parse_line(line)
    
    def _extract_order(self, data: Dict[str, Any]) -> Optional['Order']:
        """Extract order from parsed JSON data.
        
        Args:
            data: Parsed JSON data
            
        Returns:
            Order object if valid data, None otherwise
        """
        return self.order_extractor.extract_order(data)
    
    def _create_order_from_data(self, data: Dict[str, Any]) -> Optional['Order']:
        """Create order from cached JSON data (optimized version).
        
        Args:
            data: Cached JSON data
            
        Returns:
            Order object if valid data, None otherwise
        """
        return self._extract_order(data)
