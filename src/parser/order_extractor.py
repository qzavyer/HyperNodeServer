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
            order = data["order"]
            
            order_id = str(order["oid"])
            symbol = order["coin"]
            side = convert_side(order["side"])
            price = float(order["limitPx"])
            size = float(order["sz"])
            owner = data["user"]
            timestamp = datetime.now()  # TODO: Extract from log timestamp
            status = data["status"]
            
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
    

def convert_side(side: str) -> str:
    """Convert side to Bid or Ask."""
    return "Bid" if side.upper() == "B" else "Ask"