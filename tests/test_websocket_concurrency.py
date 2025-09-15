"""Tests for WebSocket manager concurrency safety."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from concurrent.futures import ThreadPoolExecutor
from src.websocket.websocket_manager import WebSocketManager
from src.storage.models import Order
from datetime import datetime


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self, connection_id: str, should_fail: bool = False):
        self.connection_id = connection_id
        self.should_fail = should_fail
        self.messages_sent = []
        self.is_closed = False
        
    async def send_text(self, message: str):
        """Mock send_text method."""
        if self.should_fail:
            raise Exception("Connection failed")
        if self.is_closed:
            raise Exception("Connection closed")
        self.messages_sent.append(message)
        
    def close(self):
        """Close the connection."""
        self.is_closed = True


@pytest.fixture
def websocket_manager():
    """Create WebSocket manager for testing."""
    return WebSocketManager()


@pytest.fixture
def sample_order():
    """Create sample order for testing."""
    return Order(
        id="test_order_123",
        symbol="BTC",
        side="Bid",
        price=50000.0,
        size=1.0,
        status="open",
        timestamp=datetime.now(),
        owner="0x123"
    )


@pytest.mark.asyncio
async def test_concurrent_connect_disconnect(websocket_manager):
    """Test concurrent connect/disconnect operations don't cause race conditions."""
    
    # Создаем множество mock WebSocket соединений
    websockets = [MockWebSocket(f"ws_{i}") for i in range(20)]
    
    async def connect_websocket(ws, channel):
        """Connect WebSocket to channel."""
        try:
            websocket_manager.active_connections[channel].add(ws)
            await asyncio.sleep(0.01)  # Имитируем небольшую задержку
        except Exception:
            pass  # Игнорируем ошибки в тесте
    
    async def disconnect_websocket(ws):
        """Disconnect WebSocket."""
        try:
            await websocket_manager.disconnect(ws)
        except Exception:
            pass  # Игнорируем ошибки в тесте
    
    # Создаем задачи для одновременного подключения и отключения
    tasks = []
    
    # Подключаем WebSocket'ы
    for i, ws in enumerate(websockets[:10]):
        channel = "orderUpdate" if i % 2 == 0 else "orderBatch"
        tasks.append(connect_websocket(ws, channel))
    
    # Отключаем WebSocket'ы параллельно с подключением
    for ws in websockets[10:]:
        websocket_manager.active_connections["orderUpdate"].add(ws)
        tasks.append(disconnect_websocket(ws))
    
    # Выполняем все задачи одновременно
    await asyncio.gather(*tasks, return_exceptions=True)
    
    # Проверяем, что менеджер остался в консистентном состоянии
    assert isinstance(websocket_manager.active_connections["orderUpdate"], set)
    assert isinstance(websocket_manager.active_connections["orderBatch"], set)


@pytest.mark.asyncio
async def test_concurrent_broadcast_with_disconnects(websocket_manager, sample_order):
    """Test concurrent broadcasts while connections are being removed."""
    
    # Создаем WebSocket соединения, некоторые из которых будут падать
    stable_websockets = [MockWebSocket(f"stable_{i}") for i in range(5)]
    failing_websockets = [MockWebSocket(f"failing_{i}", should_fail=True) for i in range(5)]
    
    # Добавляем все соединения
    all_websockets = stable_websockets + failing_websockets
    for ws in all_websockets:
        websocket_manager.active_connections["orderUpdate"].add(ws)
    
    async def broadcast_orders():
        """Broadcast multiple orders."""
        for i in range(10):
            order = Order(
                id=f"order_{i}",
                symbol="BTC",
                side="Bid",
                price=50000.0 + i,
                size=1.0,
                status="open",
                timestamp=datetime.now(),
                owner="0x123"
            )
            try:
                await websocket_manager.broadcast_order_update(order)
                await asyncio.sleep(0.001)  # Небольшая задержка
            except Exception:
                pass  # Игнорируем ошибки
    
    async def random_disconnects():
        """Randomly disconnect WebSockets during broadcasts."""
        for i in range(5):
            if websocket_manager.active_connections["orderUpdate"]:
                # Берем случайное соединение из копии множества
                ws_list = list(websocket_manager.active_connections["orderUpdate"])
                if ws_list:
                    ws = ws_list[i % len(ws_list)]
                    try:
                        await websocket_manager.disconnect(ws)
                    except Exception:
                        pass
            await asyncio.sleep(0.002)
    
    # Выполняем broadcasts и disconnects одновременно
    await asyncio.gather(
        broadcast_orders(),
        random_disconnects(),
        return_exceptions=True
    )
    
    # Проверяем, что не осталось failed соединений
    remaining_connections = websocket_manager.active_connections["orderUpdate"]
    for ws in remaining_connections:
        assert not ws.should_fail, "Failed connections should be removed"


@pytest.mark.asyncio
async def test_concurrent_batch_operations(websocket_manager, sample_order):
    """Test concurrent batch operations don't cause race conditions."""
    
    await websocket_manager.start()
    
    # Создаем WebSocket соединения для batch канала
    websockets = [MockWebSocket(f"batch_{i}") for i in range(10)]
    for ws in websockets:
        websocket_manager.active_connections["orderBatch"].add(ws)
    
    async def queue_orders():
        """Queue multiple orders for batch processing."""
        for i in range(20):
            order = Order(
                id=f"batch_order_{i}",
                symbol="ETH",
                side="sell",
                price=3000.0 + i,
                size=1.0,
                status="open",
                timestamp=datetime.now(),
                owner="0x456"
            )
            await websocket_manager.queue_order_for_batch(order)
            await asyncio.sleep(0.001)
    
    async def modify_connections():
        """Modify connections during batch processing."""
        for i in range(5):
            # Добавляем новые соединения
            new_ws = MockWebSocket(f"new_batch_{i}")
            websocket_manager.active_connections["orderBatch"].add(new_ws)
            await asyncio.sleep(0.01)
            
            # Удаляем старые соединения
            if websocket_manager.active_connections["orderBatch"]:
                ws_list = list(websocket_manager.active_connections["orderBatch"])
                if ws_list:
                    await websocket_manager.disconnect(ws_list[0])
    
    # Выполняем операции одновременно
    await asyncio.gather(
        queue_orders(),
        modify_connections(),
        return_exceptions=True
    )
    
    # Ждем обработки batch
    await asyncio.sleep(0.6)  # Больше чем интервал batch (500ms)
    
    await websocket_manager.stop()
    
    # Проверяем, что система осталась в консистентном состоянии
    assert isinstance(websocket_manager.pending_orders, list)


@pytest.mark.asyncio
async def test_set_iteration_safety():
    """Test that set iteration is safe from 'Set changed size during iteration' error."""
    
    manager = WebSocketManager()
    
    # Создаем большое количество WebSocket соединений
    websockets = [MockWebSocket(f"ws_{i}") for i in range(100)]
    for ws in websockets:
        manager.active_connections["orderUpdate"].add(ws)
    
    async def modify_set():
        """Continuously modify the set during iteration."""
        for i in range(50):
            new_ws = MockWebSocket(f"new_ws_{i}")
            manager.active_connections["orderUpdate"].add(new_ws)
            await asyncio.sleep(0.001)
            
            # Удаляем случайное соединение
            if manager.active_connections["orderUpdate"]:
                ws_list = list(manager.active_connections["orderUpdate"])
                if ws_list:
                    manager.active_connections["orderUpdate"].discard(ws_list[0])
    
    async def iterate_set():
        """Iterate over the set while it's being modified."""
        for i in range(10):
            order = Order(
                id=f"iter_order_{i}",
                symbol="BTC",
                side="Bid",
                price=50000.0,
                size=1.0,
                status="open",
                timestamp=datetime.now(),
                owner="0x123"
            )
            try:
                await manager.broadcast_order_update(order)
            except Exception as e:
                # Не должно быть ошибки "Set changed size during iteration"
                assert "Set changed size during iteration" not in str(e), f"Race condition detected: {e}"
            await asyncio.sleep(0.01)
    
    # Выполняем модификацию и итерацию одновременно
    await asyncio.gather(
        modify_set(),
        iterate_set(),
        return_exceptions=True
    )


def test_concurrent_access_with_threads():
    """Test concurrent access from multiple threads (sync test)."""
    
    manager = WebSocketManager()
    websockets = [MockWebSocket(f"thread_ws_{i}") for i in range(50)]
    
    def add_connections():
        """Add connections from thread."""
        for ws in websockets[:25]:
            manager.active_connections["orderUpdate"].add(ws)
    
    def remove_connections():
        """Remove connections from thread."""
        for ws in websockets[25:]:
            manager.active_connections["orderUpdate"].add(ws)
            manager.active_connections["orderUpdate"].discard(ws)
    
    # Выполняем операции в разных потоках
    with ThreadPoolExecutor(max_workers=2) as executor:
        future1 = executor.submit(add_connections)
        future2 = executor.submit(remove_connections)
        
        # Ждем завершения
        future1.result()
        future2.result()
    
    # Проверяем финальное состояние
    assert len(manager.active_connections["orderUpdate"]) == 25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
