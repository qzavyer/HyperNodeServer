"""Order notifier for WebSocket updates based on configuration."""

from typing import Optional, List
from src.storage.models import Order
from src.storage.config_manager import ConfigManager
from src.websocket.websocket_manager import WebSocketManager
from src.utils.logger import get_logger

# Импорт NATS клиента (опциональный)
try:
    from src.nats.nats_client import NATSClient
    NATS_AVAILABLE = False
except ImportError:
    NATS_AVAILABLE = False
    NATSClient = None

logger = get_logger(__name__)

class OrderNotifier:
    """Notifies WebSocket subscribers about relevant order updates."""
    
    def __init__(self, websocket_manager: WebSocketManager, config_manager: ConfigManager, nats_client: Optional['NATSClient'] = None):
        self.websocket_manager = websocket_manager
        self.config_manager = config_manager
        self.nats_client = nats_client
        self.logger = get_logger(__name__)
        
        # Кэш конфигурации для быстрого доступа
        self._symbol_config_cache = {}
        self._last_config_update = None
        
        # NATS интеграция
        self._nats_enabled = nats_client is not None and NATS_AVAILABLE
        
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
            
            # Отправляем в NATS если включено
            if self._nats_enabled:
                await self._send_order_to_nats(order)
                
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
                
                # Отправляем в NATS если включено
                if self._nats_enabled:
                    await self._send_order_to_nats(order)
                    
        except Exception as e:
            self.logger.error(f"Error sending batch order notifications: {e}")
    
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
            self.logger.debug(f"Order {order.id} sent to NATS via OrderNotifier")
            
        except Exception as e:
            self.logger.error(f"Failed to send order {order.id} to NATS via OrderNotifier: {e}")
    
    def is_nats_enabled(self) -> bool:
        """Check if NATS integration is enabled.
        
        Returns:
            True if NATS is enabled and available
        """
        return self._nats_enabled
    
    def get_notification_stats(self) -> dict:
        """Get notification statistics."""
        stats = {
            "websocket_manager_running": self.websocket_manager.is_running if self.websocket_manager else False,
            "websocket_connections": self.websocket_manager.get_connection_stats() if self.websocket_manager else {},
            "config_manager_available": self.config_manager is not None,
            "nats_enabled": self._nats_enabled,
            "nats_connected": self.nats_client.is_connected() if self.nats_client else False
        }
        return stats
