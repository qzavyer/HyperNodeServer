"""Order manager for handling order state and persistence."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from src.storage.models import Order
from src.storage.file_storage import FileStorage
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.storage.config_manager import ConfigManager

logger = get_logger(__name__)

class OrderManagerError(Exception):
    """Base exception for order manager errors."""
    pass

class OrderManager:
    """Manage order state and status transitions."""
    
    def __init__(self, storage: FileStorage, config_manager: Optional['ConfigManager'] = None):
        """Initialize order manager.
        
        Args:
            storage: File storage instance
            config_manager: Configuration manager for filtering rules
        """
        self.storage = storage
        self.config_manager = config_manager
        self.orders: Dict[str, Order] = {}
        self.logger = get_logger(__name__)
    
    async def initialize(self) -> None:
        """Initialize order manager by loading existing orders."""
        try:
            orders = await self.storage.load_orders_async()
            for order in orders:
                self.orders[order.id] = order
            
            self.logger.info(f"Loaded {len(orders)} orders from storage")
        except Exception as e:
            self.logger.error(f"Failed to initialize order manager: {e}")
            raise OrderManagerError(f"Initialization failed: {e}")
    
    def clear(self) -> None:
        """Clear all orders from memory (for testing)."""
        self.orders.clear()
    
    def _should_process_order(self, order: Order) -> bool:
        """Check if order should be processed based on configuration.
        
        Args:
            order: Order to check
            
        Returns:
            True if order should be processed, False otherwise
        """
        if self.config_manager is None:
            # If no config manager, process all orders
            return True
            
        try:
            config = self.config_manager.get_config()
            
            # Check if symbol is supported
            if config.supported_symbols and order.symbol not in config.supported_symbols:
                self.logger.debug(f"Order {order.id} skipped: symbol {order.symbol} not in supported_symbols")
                return False
            
            # Check minimum liquidity requirement
            if config.min_liquidity_by_symbol and order.symbol in config.min_liquidity_by_symbol:
                min_liquidity = config.min_liquidity_by_symbol[order.symbol]
                if order.size < min_liquidity:
                    self.logger.debug(f"Order {order.id} skipped: size {order.size} < min_liquidity {min_liquidity} for {order.symbol}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Failed to check order filtering rules: {e}, processing order anyway")
            return True
    
    async def update_order(self, order: Order) -> None:
        """Update order status and data.
        
        Args:
            order: Order to update
        """
        try:
            # Check if order should be processed
            if not self._should_process_order(order):
                self.logger.debug(f"Order {order.id} filtered out by configuration rules")
                return
            
            order_id = order.id
            
            if order_id in self.orders:
                existing = self.orders[order_id]
                # Apply status transition logic
                new_status = self._apply_status_transition(existing.status, order.status)
                order.status = new_status
                
                self.logger.debug(f"Updated order {order_id}: {existing.status} -> {order.status}")
            else:
                self.logger.debug(f"Added new order {order_id} with status {order.status}")
            
            self.orders[order_id] = order
            await self.storage.save_orders_async(list(self.orders.values()))
            
        except Exception as e:
            self.logger.error(f"Failed to update order {order.id}: {e}")
            raise OrderManagerError(f"Update failed: {e}")

    async def update_orders_batch_async(self, orders: List[Order]) -> None:
        """Batch update orders with conflict resolution.

        - Groups updates by order id
        - If both filled and canceled are present simultaneously, chooses canceled and logs warning
        - Otherwise applies status priority: canceled > filled > triggered > open
        - Applies transition rules from current status to resolved status
        - Filters orders based on configuration rules

        Args:
            orders: Orders to apply in one batch
        """
        try:
            # Filter orders based on configuration
            filtered_orders = [order for order in orders if self._should_process_order(order)]
            
            if len(filtered_orders) != len(orders):
                self.logger.info(f"Filtered out {len(orders) - len(filtered_orders)} orders by configuration rules")
            
            # Group by order id
            grouped: Dict[str, List[Order]] = {}
            for order in filtered_orders:
                grouped.setdefault(order.id, []).append(order)

            for order_id, updates in grouped.items():
                statuses: Set[str] = {o.status for o in updates}

                # Determine resolved status per batch
                resolved_status = self._resolve_batch_status(statuses)

                # Take the last update data for non-status fields
                latest = updates[-1]

                if order_id in self.orders:
                    current = self.orders[order_id]
                    final_status = self._apply_status_transition(current.status, resolved_status)
                else:
                    final_status = resolved_status

                updated = Order(
                    id=order_id,
                    symbol=latest.symbol,
                    side=latest.side,
                    price=latest.price,
                    size=latest.size,
                    owner=latest.owner,
                    timestamp=latest.timestamp,
                    status=final_status,
                )

                self.orders[order_id] = updated

            # Persist once after batch
            await self.storage.save_orders_async(list(self.orders.values()))

        except Exception as e:
            self.logger.error(f"Failed to apply batch update: {e}")
            raise OrderManagerError(f"Batch update failed: {e}")

    def _resolve_batch_status(self, statuses: Set[str]) -> str:
        """Resolve final status for a batch of simultaneous updates.

        Rules:
        - If both filled and canceled present -> choose canceled and log warning
        - Else priority: canceled > filled > triggered > open
        """
        if "filled" in statuses and "canceled" in statuses:
            self.logger.warning("Simultaneous filled and canceled detected; choosing canceled")
            return "canceled"

        if "canceled" in statuses:
            return "canceled"
        if "filled" in statuses:
            return "filled"
        if "triggered" in statuses:
            return "triggered"
        if "open" in statuses:
            return "open"

        # Unknown -> default to canceled
        self.logger.warning(f"Unknown statuses in batch: {statuses}; defaulting to canceled")
        return "canceled"
    
    def _apply_status_transition(self, current_status: str, new_status: str) -> str:
        """Apply status transition rules from vision.md.
        
        Args:
            current_status: Current order status
            new_status: New status from log
            
        Returns:
            Final status after applying transition rules
        """
        # Valid transitions according to vision.md:
        # open -> filled
        # open -> canceled  
        # open -> triggered -> filled
        # open -> triggered -> canceled
        
        if current_status == "open":
            if new_status in ["filled", "canceled", "triggered"]:
                return new_status
            elif new_status == "open":
                return "open"  # Allow staying in open status
            else:
                self.logger.warning(f"Unknown status transition: {current_status} -> {new_status}, defaulting to canceled")
                return "canceled"
        
        elif current_status == "triggered":
            if new_status in ["filled", "canceled"]:
                return new_status
            else:
                self.logger.warning(f"Unknown status transition: {current_status} -> {new_status}, defaulting to canceled")
                return "canceled"
        
        elif current_status in ["filled", "canceled"]:
            # If order was already filled or canceled, log warning but don't change status
            self.logger.warning(f"Order already in final state {current_status}, ignoring new status {new_status}")
            return current_status
        
        else:
            # Unknown current status, default to canceled
            self.logger.warning(f"Unknown current status {current_status}, defaulting to canceled")
            return "canceled"
    
    def get_orders(self, 
                   symbol: Optional[str] = None,
                   side: Optional[str] = None,
                   min_liquidity: Optional[float] = None,
                   status: Optional[str] = None) -> List[Order]:
        """Get filtered list of orders.
        
        Args:
            symbol: Filter by symbol/coin
            side: Filter by side (Bid/Ask)
            min_liquidity: Minimum liquidity filter (price * size)
            status: Filter by status
            
        Returns:
            List of filtered orders
        """
        filtered_orders = list(self.orders.values())
        
        if symbol:
            filtered_orders = [o for o in filtered_orders if o.symbol == symbol]
        
        if side:
            filtered_orders = [o for o in filtered_orders if o.side == side]
        
        if status:
            filtered_orders = [o for o in filtered_orders if o.status == status]
        
        if min_liquidity is not None:
            filtered_orders = [o for o in filtered_orders if o.price * o.size >= min_liquidity]
        
        return filtered_orders
    
    def get_order_by_id(self, order_id: str) -> Optional[Order]:
        """Get order by ID.
        
        Args:
            order_id: Order ID to find
            
        Returns:
            Order if found, None otherwise
        """
        return self.orders.get(order_id)
    
    def get_open_orders(self) -> List[Order]:
        """Get all open orders.
        
        Returns:
            List of open orders
        """
        return self.get_orders(status="open")
    
    def get_orders_by_symbol(self, symbol: str) -> List[Order]:
        """Get all orders for specific symbol.
        
        Args:
            symbol: Symbol to filter by
            
        Returns:
            List of orders for symbol
        """
        return self.get_orders(symbol=symbol)
    
    def get_orders_by_owner(self, owner: str) -> List[Order]:
        """Get all orders for specific owner.
        
        Args:
            owner: Owner address to filter by
            
        Returns:
            List of orders for owner
        """
        return [o for o in self.orders.values() if o.owner == owner]
    
    def get_order_count(self) -> int:
        """Get total number of orders.
        
        Returns:
            Total order count
        """
        return len(self.orders)
    
    def get_order_count_by_status(self) -> Dict[str, int]:
        """Get order count by status.
        
        Returns:
            Dictionary with status as key and count as value
        """
        counts = {}
        for order in self.orders.values():
            counts[order.status] = counts.get(order.status, 0) + 1
        return counts
    
    async def cleanup_old_orders(self, max_age_hours: int = 24) -> int:
        """Remove orders older than specified age.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of removed orders
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        old_orders = []
        
        for order_id, order in list(self.orders.items()):
            if order.timestamp < cutoff_time:
                old_orders.append(order_id)
                del self.orders[order_id]
        
        if old_orders:
            await self.storage.save_orders_async(list(self.orders.values()))
            self.logger.info(f"Removed {len(old_orders)} old orders")
        
        return len(old_orders)
    
    def set_config_manager(self, config_manager: 'ConfigManager') -> None:
        """Set configuration manager for filtering rules.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager
        self.logger.info("Configuration manager set for order filtering")
