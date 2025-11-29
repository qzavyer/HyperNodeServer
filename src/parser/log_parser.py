"""Log parser for HyperLiquid node logs."""

import json
import asyncio
import aiofiles
from pathlib import Path
from typing import List, Optional, Dict, Any, AsyncGenerator
from src.storage.models import LogEntry, ParsedData, Order
from src.parser.order_extractor import OrderExtractor
from src.utils.logger import get_logger

# Импорт NATS клиента (опциональный)
try:
    from src.nats.nats_client import NATSClient
    NATS_AVAILABLE = False
except ImportError:
    NATS_AVAILABLE = False
    NATSClient = None

logger = get_logger(__name__)

class ParserError(Exception):
    """Base exception for parser errors."""
    pass

class LogParser:
    """Parser for HyperLiquid Node log files."""
    
    def __init__(self, chunk_size: int = 8192, batch_size: int = 1000, nats_client: Optional['NATSClient'] = None):
        """Initialize log parser.
        
        Args:
            chunk_size: Size of file chunks to read (bytes)
            batch_size: Number of orders to process in one batch
            nats_client: Optional NATS client for publishing data
        """
        self.logger = get_logger(__name__)
        self.chunk_size = chunk_size
        self.batch_size = batch_size
        self.order_extractor = OrderExtractor()
        self.nats_client = nats_client
        self._nats_enabled = nats_client is not None and NATS_AVAILABLE
    
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
                        order = self.parse_line(line)
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
                            order = self.parse_line(line)
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
                    # Отправляем в NATS если включено
                    if self._nats_enabled:
                        await self._send_orders_batch_to_nats(orders_batch)
                    
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
    
    async def _send_order_to_nats(self, order: Order) -> None:
        """Send order data to NATS if enabled.
        
        Args:
            order: Order to send
        """
        if not self._nats_enabled or not self.nats_client:
            return
        
        try:
            # Преобразуем Order в словарь для отправки
            order_data = {
                "id": order.id,
                "symbol": order.symbol,
                "side": order.side,
                "price": order.price,
                "size": order.size,
                "owner": order.owner,
                "timestamp": order.timestamp,
                "status": order.status
            }
            
            # Отправляем в NATS
            await self.nats_client.publish_order_data(order_data, "parser_data.orders")
            self.logger.debug(f"Order {order.id} sent to NATS")
            
        except Exception as e:
            self.logger.error(f"Failed to send order {order.id} to NATS: {e}")
    
    async def _send_orders_batch_to_nats(self, orders: List[Order]) -> None:
        """Send batch of orders to NATS if enabled.
        
        Args:
            orders: List of orders to send
        """
        if not self._nats_enabled or not self.nats_client or not orders:
            return
        
        try:
            # Отправляем каждый ордер отдельно
            for order in orders:
                await self._send_order_to_nats(order)
            
            self.logger.debug(f"Sent {len(orders)} orders to NATS")
            
        except Exception as e:
            self.logger.error(f"Failed to send orders batch to NATS: {e}")
    
    def is_nats_enabled(self) -> bool:
        """Check if NATS integration is enabled.
        
        Returns:
            True if NATS is enabled and available
        """
        return self._nats_enabled
