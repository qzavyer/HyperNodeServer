"""Order extractor for parsing order data from log entries."""

from datetime import datetime
from typing import Optional, Dict, Any
from src.storage.models import Order
from src.utils.logger import get_logger

logger = get_logger(__name__)

class OrderExtractor:
    """Extract order data from parsed log entries."""
    
    def __init__(self):
        """Initialize order extractor."""
        self.logger = get_logger(__name__)
    
    def extract_order(self, data: Dict[str, Any]) -> Optional[Order]:
        """Extract order from log data.
        
        Args:
            data: Parsed log data
            
        Returns:
            Order object if valid, None otherwise
        """
        try:
            if not self._validate_order_data(data):
                return None
            
            # Determine operation type
            operation_type = self._get_operation_type(data)
            
            if operation_type == "new":
                return self._extract_new_order(data)
            elif operation_type == "update":
                return self._extract_updated_order(data)
            elif operation_type == "remove":
                return self._extract_removed_order(data)
            else:
                self.logger.warning(f"Unknown operation type: {operation_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to extract order from data: {e}")
            return None
    
    def _validate_order_data(self, data: Dict[str, Any]) -> bool:
        """Validate order data structure.
        
        Args:
            data: Order data to validate
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['user', 'oid', 'coin', 'side', 'px']
        return all(field in data for field in required_fields)
    
    def _get_operation_type(self, data: Dict[str, Any]) -> str:
        """Determine operation type from raw_book_diff.
        
        Args:
            data: Order data
            
        Returns:
            Operation type: "new", "update", "remove", or "unknown"
        """
        raw_book_diff = data.get("raw_book_diff")
        
        if isinstance(raw_book_diff, dict):
            if "new" in raw_book_diff:
                return "new"
            elif "update" in raw_book_diff:
                return "update"
        elif raw_book_diff == "remove":
            return "remove"
        
        return "unknown"
    
    def _extract_new_order(self, data: Dict[str, Any]) -> Optional[Order]:
        """Extract new order data.
        
        Args:
            data: Order data with "new" operation
            
        Returns:
            Order object
        """
        try:
            raw_book_diff = data["raw_book_diff"]
            new_data = raw_book_diff["new"]
            
            order_id = str(data["oid"])
            symbol = data["coin"]
            side = data["side"]
            price = float(data["px"])
            size = float(new_data["sz"])
            owner = data["user"]
            timestamp = datetime.now()  # TODO: Extract from log timestamp
            status = "open"
            
            return Order(
                id=order_id,
                symbol=symbol,
                side=side,
                price=price,
                size=size,
                owner=owner,
                timestamp=timestamp,
                status=status
            )
        except Exception as e:
            self.logger.error(f"Failed to extract new order: {e}")
            return None
    
    def _extract_updated_order(self, data: Dict[str, Any]) -> Optional[Order]:
        """Extract updated order data.
        
        Args:
            data: Order data with "update" operation
            
        Returns:
            Order object with updated size
        """
        try:
            raw_book_diff = data["raw_book_diff"]
            update_data = raw_book_diff["update"]
            
            order_id = str(data["oid"])
            symbol = data["coin"]
            side = data["side"]
            price = float(data["px"])
            size = float(update_data["newSz"])
            owner = data["user"]
            timestamp = datetime.now()  # TODO: Extract from log timestamp
            status = "open"
            
            return Order(
                id=order_id,
                symbol=symbol,
                side=side,
                price=price,
                size=size,
                owner=owner,
                timestamp=timestamp,
                status=status
            )
        except Exception as e:
            self.logger.error(f"Failed to extract updated order: {e}")
            return None
    
    def _extract_removed_order(self, data: Dict[str, Any]) -> Optional[Order]:
        """Extract removed order data.
        
        Args:
            data: Order data with "remove" operation
            
        Returns:
            Order object with cancelled status
        """
        try:
            order_id = str(data["oid"])
            symbol = data["coin"]
            side = data["side"]
            price = float(data["px"])
            size = 0.0  # Removed order has zero size
            owner = data["user"]
            timestamp = datetime.now()  # TODO: Extract from log timestamp
            status = "cancelled"
            
            return Order(
                id=order_id,
                symbol=symbol,
                side=side,
                price=price,
                size=size,
                owner=owner,
                timestamp=timestamp,
                status=status
            )
        except Exception as e:
            self.logger.error(f"Failed to extract removed order: {e}")
            return None
    

