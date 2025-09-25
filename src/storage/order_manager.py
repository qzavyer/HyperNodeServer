"""Order manager for handling order state and persistence."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from src.storage.models import Order
from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.storage.config_manager import ConfigManager
    from src.notifications.order_notifier import OrderNotifier

logger = get_logger(__name__)

class OrderManagerError(Exception):
    """Base exception for order manager errors."""
    pass

class OrderManager:
    """Manage order state and status transitions."""
    
    def __init__(self, config_manager: Optional['ConfigManager'] = None, order_notifier: Optional['OrderNotifier'] = None):
        """Initialize order manager.
        
        Args:
            config_manager: Configuration manager for filtering rules
            order_notifier: Order notifier for WebSocket updates
        """
        self.config_manager = config_manager
        self.order_notifier = order_notifier
        self.orders: Dict[str, Order] = {}
        self.logger = get_logger(__name__)
        
        # Log order notifier initialization
        if self.order_notifier:
            self.logger.info("Order notifier set for WebSocket updates")
        else:
            self.logger.warning("Order notifier not provided - WebSocket notifications disabled")
    
    def set_order_notifier(self, order_notifier: 'OrderNotifier'):
        """Set order notifier for WebSocket updates."""
        self.order_notifier = order_notifier
        self.logger.info("Order notifier set for WebSocket updates")
    
    async def initialize(self) -> None:
        """Initialize order manager (no persistent storage needed)."""
        self.logger.info("Order manager initialized - running in real-time mode without persistent storage")
    
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
            
            # Find symbol configuration
            symbol_config = next((sc for sc in config.symbols_config if sc.symbol == order.symbol), None)
            if symbol_config is None:
                # self.logger.debug(f"Order {order.id} skipped: symbol {order.symbol} not in supported symbols")
                return False
            
            # Check minimum liquidity requirement
            order_liquidity = order.price * order.size
            if order_liquidity < symbol_config.min_liquidity:
                # self.logger.debug(f"Order {order.id} skipped: liquidity {order_liquidity} < min_liquidity {symbol_config.min_liquidity} for {order.symbol}")
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
            
            # Log orders that passed filtering and are sent to WebSocket
            liquidity = order.price * order.size
            self.logger.info(f"WS Order: {order.symbol} {order.side} @ {order.price} size={order.size} liquidity=${liquidity:,.2f} time={order.timestamp}")
            
            order_id = order.id
            order_updated = False
            
            if order_id in self.orders:
                existing = self.orders[order_id]
                # Apply status transition logic
                new_status = self._apply_status_transition(existing.status, order.status)
                order.status = new_status
                
                # Check if order actually changed
                if (existing.status != order.status or 
                    existing.price != order.price or 
                    existing.size != order.size):
                    order_updated = True
                
                self.logger.debug(f"Updated order {order_id}: {existing.status} -> {order.status}")
            else:
                order_updated = True
                self.logger.debug(f"Added new order {order_id} with status {order.status}")
            
            self.orders[order_id] = order
            
            # Send WebSocket notification if order was updated and notifier is available
            if order_updated and self.order_notifier:
                await self.order_notifier.notify_order_update(order, notification_type="both")
            
            # Schedule async save instead of immediate save
            
        except Exception as e:
            self.logger.error(f"Failed to update order {order.id}: {e}")
            raise OrderManagerError(f"Update failed: {e}")

    async def update_orders_batch_async(self, orders: List[Order]) -> None:
        """Batch update orders with conflict resolution and optimized saving.

        - Groups updates by order id
        - If both filled and canceled are present simultaneously, chooses canceled and logs warning
        - Otherwise applies status priority: canceled > filled > triggered > open
        - Applies transition rules from current status to resolved status
        - Filters orders based on configuration rules
        - Uses batched saving for better performance
        - Sends WebSocket notifications for relevant orders

        Args:
            orders: Orders to apply in one batch
        """
        try:
            self.logger.info(f"OrderManager.update_orders_batch_async called with {len(orders)} orders")
            print(f"OrderManager.update_orders_batch_async called with {len(orders)} orders")
            
            # Filter orders based on configuration
            filtered_orders = [order for order in orders if self._should_process_order(order)]
            self.logger.info(f"After filtering: {len(filtered_orders)} orders (filtered out: {len(orders) - len(filtered_orders)})")
            print(f"After filtering: {len(filtered_orders)} orders (filtered out: {len(orders) - len(filtered_orders)})")
            
            # Log all orders that passed filtering and are sent to WebSocket
            for order in filtered_orders:
                liquidity = order.price * order.size
                self.logger.info(f"WS Order: {order.symbol} {order.side} @ {order.price} size={order.size} liquidity=${liquidity:,.2f} time={order.timestamp}")
            
            # Group by order id
            grouped: Dict[str, List[Order]] = {}
            for order in filtered_orders:
                grouped.setdefault(order.id, []).append(order)

            updated_orders = []
            for order_id, updates in grouped.items():
                statuses: Set[str] = {o.status for o in updates}

                # Determine resolved status per batch
                resolved_status = self._resolve_batch_status(statuses)

                # Take the last update data for non-status fields
                latest = updates[-1]

                if order_id in self.orders:
                    current = self.orders[order_id]
                    final_status = self._apply_status_transition(current.status, resolved_status)
                    
                    # Check if order actually changed
                    if (current.status != final_status or 
                        current.price != latest.price or 
                        current.size != latest.size):
                        updated_orders.append(order_id)
                else:
                    final_status = resolved_status
                    updated_orders.append(order_id)

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

            # Send WebSocket notifications for updated orders if notifier is available
            if updated_orders and self.order_notifier:
                relevant_orders = [self.orders[order_id] for order_id in updated_orders]
                await self.order_notifier.notify_orders_batch(relevant_orders, notification_type="both")

            # Schedule async save for the entire batch

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
            new_status: New status to apply
            
        Returns:
            Final status after applying transition rules
        """
        # Status transition rules
        if current_status == "open":
            if new_status in ["filled", "canceled", "triggered"]:
                return new_status
            return current_status
        
        elif current_status == "triggered":
            if new_status in ["filled", "canceled"]:
                return new_status
            return current_status
        
        elif current_status == "filled":
            # Filled orders cannot change status
            return current_status
        
        elif current_status == "canceled":
            # Canceled orders cannot change status
            return current_status
        
        # Unknown current status, allow change
        return new_status
    
    def get_order_count(self) -> int:
        """Get total number of orders."""
        return len(self.orders)
    
    def get_order_count_by_status(self) -> Dict[str, int]:
        """Get count of orders by status."""
        counts = {}
        for order in self.orders.values():
            status = order.status
            counts[status] = counts.get(status, 0) + 1
        return counts
    
    def get_open_orders(self) -> List[Order]:
        """Get all open orders."""
        return [order for order in self.orders.values() if order.status == "open"]
    
    def get_orders(self, limit: Optional[int] = None) -> List[Order]:
        """Get list of orders with optional limit."""
        orders = list(self.orders.values())
        if limit:
            orders = orders[:limit]
        return orders
    
    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self.orders.get(order_id)
    
    def get_orders_by_symbol(self, symbol: str, limit: Optional[int] = None) -> List[Order]:
        """Get orders by symbol."""
        orders = [order for order in self.orders.values() if order.symbol == symbol]
        if limit:
            orders = orders[:limit]
        return orders
    
    def get_orders_by_status(self, status: str, limit: Optional[int] = None) -> List[Order]:
        """Get orders by status."""
        orders = [order for order in self.orders.values() if order.status == status]
        if limit:
            orders = orders[:limit]
        return orders
    
    def get_orders_by_owner(self, owner: str, limit: Optional[int] = None) -> List[Order]:
        """Get orders by owner address."""
        orders = [order for order in self.orders.values() if order.owner == owner]
        if limit:
            orders = orders[:limit]
        return orders
    
    def get_orders_by_price_range(self, symbol: str, min_price: float, max_price: float, limit: Optional[int] = None) -> List[Order]:
        """Get orders by price range for a symbol."""
        orders = [
            order for order in self.orders.values() 
            if order.symbol == symbol and min_price <= order.price <= max_price
        ]
        if limit:
            orders = orders[:limit]
        return orders
    
    def get_orders_by_liquidity_range(self, symbol: str, min_liquidity: float, max_liquidity: float, limit: Optional[int] = None) -> List[Order]:
        """Get orders by liquidity range for a symbol."""
        orders = [
            order for order in self.orders.values() 
            if order.symbol == symbol and min_liquidity <= (order.price * order.size) <= max_liquidity
        ]
        if limit:
            orders = orders[:limit]
        return orders
    
    def get_orders_by_time_range(self, start_time: datetime, end_time: datetime, limit: Optional[int] = None) -> List[Order]:
        """Get orders by time range."""
        orders = [
            order for order in self.orders.values() 
            if start_time <= order.timestamp <= end_time
        ]
        if limit:
            orders = orders[:limit]
        return orders
    
    def get_order_book(self, symbol: str, depth: int = 10) -> Dict[str, List[Order]]:
        """Get order book for a symbol with specified depth."""
        symbol_orders = [order for order in self.orders.values() if order.symbol == symbol and order.status == "open"]
        
        # Separate bid and ask orders
        bid_orders = [order for order in symbol_orders if order.side == "Bid"]
        ask_orders = [order for order in symbol_orders if order.side == "Ask"]
        
        # Sort by price (bid: descending, ask: ascending)
        bid_orders.sort(key=lambda x: x.price, reverse=True)
        ask_orders.sort(key=lambda x: x.price)
        
        # Limit depth
        bid_orders = bid_orders[:depth]
        ask_orders = ask_orders[:depth]
        
        return {
            "bid": bid_orders,
            "ask": ask_orders
        }
    
    def get_market_summary(self, symbol: str) -> Dict[str, any]:
        """Get market summary for a symbol."""
        symbol_orders = [order for order in self.orders.values() if order.symbol == symbol and order.status == "open"]
        
        if not symbol_orders:
            return {
                "symbol": symbol,
                "total_orders": 0,
                "total_volume": 0.0,
                "avg_price": 0.0,
                "price_range": {"min": 0.0, "max": 0.0}
            }
        
        total_volume = sum(order.size for order in symbol_orders)
        avg_price = sum(order.price * order.size for order in symbol_orders) / total_volume
        prices = [order.price for order in symbol_orders]
        
        return {
            "symbol": symbol,
            "total_orders": len(symbol_orders),
            "total_volume": total_volume,
            "avg_price": avg_price,
            "price_range": {"min": min(prices), "max": max(prices)}
        }
    
    def cleanup_old_orders(self, hours: int) -> int:
        """Remove orders older than specified hours."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        old_orders = [
            order_id for order_id, order in self.orders.items() 
            if order.timestamp < cutoff_time
        ]
        
        for order_id in old_orders:
            del self.orders[order_id]
        
        if old_orders:
            self.logger.info(f"Cleaned up {len(old_orders)} orders older than {hours} hours")
            # Schedule save after cleanup
        
        return len(old_orders)
