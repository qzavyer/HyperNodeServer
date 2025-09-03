"""Order notifier for WebSocket updates based on configuration."""

from typing import Optional, List
from src.storage.models import Order
from src.storage.config_manager import ConfigManager
from src.websocket.websocket_manager import WebSocketManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

class OrderNotifier:
    """Notifies WebSocket subscribers about relevant order updates."""
    
    def __init__(self, websocket_manager: WebSocketManager, config_manager: ConfigManager):
        self.websocket_manager = websocket_manager
        self.config_manager = config_manager
        self.logger = get_logger(__name__)
        
        # Кэш конфигурации для быстрого доступа
        self._symbol_config_cache = {}
        self._last_config_update = None
        
    def _should_notify_order(self, order: Order) -> bool:
        """Check if order should trigger notification based on configuration.
        
        Args:
            order: Order to check
            
        Returns:
            True if order should trigger notification
        """
        try:
            # Получаем актуальную конфигурацию
            config = self.config_manager.get_config()
            
            # Находим конфигурацию для символа
            symbol_config = next(
                (sc for sc in config.symbols_config if sc.symbol == order.symbol), 
                None
            )
            
            if symbol_config is None:
                # Символ не отслеживается
                return False
            
            # Проверяем минимальный объем ликвидности
            order_liquidity = order.price * order.size
            if order_liquidity < symbol_config.min_liquidity:
                # Объем ликвидности слишком мал
                return False
            
            # Ордер соответствует критериям для уведомления
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking order notification criteria: {e}")
            return False
    
    async def notify_order_update(self, order: Order, notification_type: str = "both"):
        """Send order update notification if it meets criteria.
        
        Args:
            order: Order to notify about
            notification_type: Type of notification ("instant", "batch", or "both")
        """
        try:
            # Проверяем, нужно ли отправлять уведомление
            if not self._should_notify_order(order):
                return
            
            self.logger.debug(f"Notifying about order {order.id} for {order.symbol} (liquidity: {order.price * order.size})")
            
            # Отправляем уведомления в зависимости от типа
            if notification_type in ["instant", "both"]:
                await self.websocket_manager.broadcast_order_update(order)
            
            if notification_type in ["batch", "both"]:
                await self.websocket_manager.queue_order_for_batch(order)
                
        except Exception as e:
            self.logger.error(f"Error sending order notification: {e}")
    
    async def notify_orders_batch(self, orders: List[Order], notification_type: str = "both"):
        """Send notifications for a batch of orders.
        
        Args:
            orders: List of orders to notify about
            notification_type: Type of notification ("instant", "batch", or "both")
        """
        try:
            relevant_orders = []
            
            for order in orders:
                if self._should_notify_order(order):
                    relevant_orders.append(order)
            
            if not relevant_orders:
                return
            
            self.logger.debug(f"Notifying about {len(relevant_orders)} relevant orders out of {len(orders)} total")
            
            # Отправляем уведомления для каждого релевантного ордера
            for order in relevant_orders:
                if notification_type in ["instant", "both"]:
                    await self.websocket_manager.broadcast_order_update(order)
                
                if notification_type in ["batch", "both"]:
                    await self.websocket_manager.queue_order_for_batch(order)
                    
        except Exception as e:
            self.logger.error(f"Error sending batch order notifications: {e}")
    
    def get_notification_stats(self) -> dict:
        """Get notification statistics."""
        return {
            "websocket_manager_running": self.websocket_manager.is_running if self.websocket_manager else False,
            "websocket_connections": self.websocket_manager.get_connection_stats() if self.websocket_manager else {},
            "config_manager_available": self.config_manager is not None
        }
