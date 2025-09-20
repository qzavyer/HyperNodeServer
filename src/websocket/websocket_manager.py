"""WebSocket manager for real-time order updates."""

import asyncio
import json
from typing import Dict, List, Set, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosedError
from src.storage.models import Order
from src.utils.logger import get_logger

logger = get_logger(__name__)

class WebSocketManager:
    """Manages WebSocket connections and broadcasts order updates."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "orderUpdate": set(),
            "orderBatch": set()
        }
        self.pending_orders: List[Order] = []
        self.batch_timer: Optional[asyncio.Task] = None
        self.is_running = False

    async def start(self):
        """Start the WebSocket manager."""
        self.is_running = True
        # Запускаем таймер для батчевых уведомлений
        self.batch_timer = asyncio.create_task(self._batch_timer_loop())
        logger.info("WebSocket manager started")

    async def stop(self):
        """Stop the WebSocket manager."""
        self.is_running = False
        if self.batch_timer:
            self.batch_timer.cancel()
            try:
                await self.batch_timer
            except asyncio.CancelledError:
                pass
            finally:
                self.batch_timer = None

        # Закрываем все соединения
        for channel in self.active_connections.values():
            # Создаем копию для безопасной итерации
            connections_copy = list(channel)
            for connection in connections_copy:
                await self.disconnect(connection)

        logger.info("WebSocket manager stopped")

    async def connect(self, websocket: WebSocket, channel: str):
        """Connect a WebSocket to a specific channel.
        
        Note: websocket.accept() should be called before this method.
        """
        if channel not in self.active_connections:
            raise ValueError(f"Unknown channel: {channel}")

        # WebSocket уже должен быть принят в роуте
        self.active_connections[channel].add(websocket)
        logger.info(f"WebSocket connected to channel: {channel}")

        # Отправляем приветственное сообщение
        await websocket.send_text(json.dumps({
            "type": "connected",
            "channel": channel,
            "timestamp": datetime.now().isoformat()
        }))

    async def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket from all channels."""
        for channel_name, channel in self.active_connections.items():
            if websocket in channel:
                channel.remove(websocket)
                logger.info(f"WebSocket disconnected from channel: {channel_name}")
                # Пытаемся корректно закрыть соединение
                try:
                    if websocket.client_state.name == "CONNECTED":
                        await websocket.close(code=1000, reason="Normal closure")
                except Exception as e:
                    logger.debug(f"Could not close websocket during disconnect: {e}")
                break

    async def broadcast_order_update(self, order: Order):
        """Broadcast single order update to all subscribers."""
        if not self.active_connections["orderUpdate"]:
            return

        message = {
            "type": "orderUpdate",
            "channel": "orderUpdate",
            "timestamp": datetime.now().isoformat(),
            "data": json.loads(order.model_dump_json())
        }

        message_text = json.dumps(message)
        disconnected = set()

        # Создаем копию множества для безопасной итерации
        connections_copy = self.active_connections["orderUpdate"].copy()
        for connection in connections_copy:
            try:
                await connection.send_text(message_text)
            except WebSocketDisconnect:
                logger.debug(f"WebSocket connection disconnected during order update")
                disconnected.add(connection)
            except ConnectionClosedError:
                logger.debug(f"WebSocket connection closed during order update")
                disconnected.add(connection)
            except asyncio.TimeoutError:
                logger.warning(f"WebSocket send timeout during order update")
                disconnected.add(connection)
            except Exception as e:
                # Специальная обработка для различных типов ошибок
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ["keepalive ping timeout", "1011", "no close frame", "connection closed"]):
                    logger.warning(f"WebSocket connection issue, removing connection: {e}")
                else:
                    logger.error(f"Error sending order update: {e}")
                disconnected.add(connection)

        # Удаляем отключенные соединения
        for connection in disconnected:
            await self.disconnect(connection)

        logger.debug(f"Broadcasted order update for {order.symbol} to {len(self.active_connections['orderUpdate'])} subscribers")

    async def queue_order_for_batch(self, order: Order):
        """Add order to batch queue for periodic updates."""
        self.pending_orders.append(order)

        # Если это первый ордер в очереди, запускаем таймер
        if len(self.pending_orders) == 1 and not self.batch_timer:
            self.batch_timer = asyncio.create_task(self._batch_timer_loop())

    async def _batch_timer_loop(self):
        """Timer loop for batch updates (every 500ms)."""
        while self.is_running:
            try:
                await asyncio.sleep(0.5)  # 500ms

                if self.pending_orders and self.active_connections["orderBatch"]:
                    await self._send_batch_update()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch timer loop: {e}")

    async def _send_batch_update(self):
        """Send batch update to all subscribers."""
        if not self.pending_orders:
            return

        # Берем все накопленные ордера
        orders_batch = self.pending_orders.copy()
        self.pending_orders.clear()

        message = {
            "type": "orderBatch",
            "channel": "orderBatch",
            "timestamp": datetime.now().isoformat(),
            "data": {
                "orders": [json.loads(order.model_dump_json()) for order in orders_batch],
                "count": len(orders_batch)
            }
        }

        message_text = json.dumps(message)
        disconnected = set()

        # Создаем копию множества для безопасной итерации
        connections_copy = self.active_connections["orderBatch"].copy()
        for connection in connections_copy:
            try:
                await connection.send_text(message_text)
            except WebSocketDisconnect:
                logger.debug(f"WebSocket connection disconnected during batch update")
                disconnected.add(connection)
            except ConnectionClosedError:
                logger.debug(f"WebSocket connection closed during batch update")
                disconnected.add(connection)
            except asyncio.TimeoutError:
                logger.warning(f"WebSocket send timeout during batch update")
                disconnected.add(connection)
            except Exception as e:
                # Специальная обработка для различных типов ошибок
                error_str = str(e).lower()
                if any(keyword in error_str for keyword in ["keepalive ping timeout", "1011", "no close frame", "connection closed"]):
                    logger.warning(f"WebSocket connection issue, removing connection: {e}")
                else:
                    logger.error(f"Error sending batch update: {e}")
                disconnected.add(connection)

        # Удаляем отключенные соединения
        for connection in disconnected:
            await self.disconnect(connection)

        logger.debug(f"Sent batch update with {len(orders_batch)} orders to {len(self.active_connections['orderBatch'])} subscribers")

    def get_connection_stats(self) -> Dict:
        """Get current connection statistics."""
        return {
            "channels": {
                channel: len(connections)
                for channel, connections in self.active_connections.items()
            },
            "pending_orders": len(self.pending_orders),
            "is_running": self.is_running
        }
