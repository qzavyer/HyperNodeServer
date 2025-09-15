"""File-based storage for order data."""

import json
import aiofiles
from pathlib import Path
from typing import List, Optional
from src.storage.models import Order
from src.utils.logger import get_logger

logger = get_logger(__name__)

class StorageError(Exception):
    """Base exception for storage errors."""
    pass

class FileStorage:
    """File-based storage for orders."""
    
    def __init__(self, data_dir: str = "data"):
        """Initialize file storage.
        
        Args:
            data_dir: Directory for data storage
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.orders_file = self.data_dir / "orders.json"
        self.logger = get_logger(__name__)
    
    async def save_orders_async(self, orders: List[Order]) -> None:
        """Save orders to file asynchronously.
        
        Args:
            orders: List of orders to save
        """
        try:
            orders_data = [order.model_dump() for order in orders]
            async with aiofiles.open(self.orders_file, 'w') as f:
                await f.write(json.dumps(orders_data, indent=2, default=str))
            
            self.logger.info(f"Saved {len(orders)} orders to {self.orders_file}")
        except Exception as e:
            raise StorageError(f"Failed to save orders: {e}")
    
    async def load_orders_async(self) -> List[Order]:
        """Load orders from file asynchronously.
        
        Returns:
            List of loaded orders
        """
        try:
            if not self.orders_file.exists():
                return []
            
            async with aiofiles.open(self.orders_file, 'r') as f:
                content = await f.read()
                
                # Check if file is empty or contains only whitespace
                if not content.strip():
                    self.logger.info(f"Orders file {self.orders_file} is empty, returning empty list")
                    return []
                
                orders_data = json.loads(content)
            
            orders = [Order(**order_data) for order_data in orders_data]
            self.logger.info(f"Loaded {len(orders)} orders from {self.orders_file}")
            return orders
        except json.JSONDecodeError as e:
            self.logger.warning(f"Invalid JSON in orders file {self.orders_file}: {e}")
            self.logger.info("Returning empty orders list due to invalid JSON")
            return []
        except Exception as e:
            raise StorageError(f"Failed to load orders: {e}")
    
    def save_orders(self, orders: List[Order]) -> None:
        """Save orders to file synchronously.
        
        Args:
            orders: List of orders to save
        """
        try:
            orders_data = [order.model_dump() for order in orders]
            with open(self.orders_file, 'w') as f:
                json.dump(orders_data, f, indent=2, default=str)
            
            self.logger.info(f"Saved {len(orders)} orders to {self.orders_file}")
        except Exception as e:
            raise StorageError(f"Failed to save orders: {e}")
    
    def load_orders(self) -> List[Order]:
        """Load orders from file synchronously.
        
        Returns:
            List of loaded orders
        """
        try:
            if not self.orders_file.exists():
                return []
            
            with open(self.orders_file, 'r') as f:
                content = f.read()
                
                # Check if file is empty or contains only whitespace
                if not content.strip():
                    self.logger.info(f"Orders file {self.orders_file} is empty, returning empty list")
                    return []
                
                orders_data = json.loads(content)
            
            orders = [Order(**order_data) for order_data in orders_data]
            self.logger.info(f"Loaded {len(orders)} orders from {self.orders_file}")
            return orders
        except json.JSONDecodeError as e:
            self.logger.warning(f"Invalid JSON in orders file {self.orders_file}: {e}")
            self.logger.info("Returning empty orders list due to invalid JSON")
            return []
        except Exception as e:
            raise StorageError(f"Failed to load orders: {e}")
