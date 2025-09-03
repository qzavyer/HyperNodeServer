"""WebSocket routes for real-time order updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.websocket.websocket_manager import WebSocketManager
from src.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# WebSocket manager instance (будет инициализирован в main.py)
websocket_manager: WebSocketManager = None

def set_websocket_manager(manager: WebSocketManager):
    """Set WebSocket manager instance."""
    global websocket_manager
    websocket_manager = manager

@router.websocket("/ws/orderUpdate")
async def websocket_order_update(websocket: WebSocket):
    """WebSocket endpoint for real-time order updates."""
    if not websocket_manager:
        await websocket.close(code=1000, reason="WebSocket manager not initialized")
        return
    
    try:
        await websocket_manager.connect(websocket, "orderUpdate")
        
        # Держим соединение открытым
        while True:
            # Ждем сообщения от клиента (можно использовать для ping/pong)
            data = await websocket.receive_text()
            logger.debug(f"Received message from orderUpdate client: {data}")
            
    except WebSocketDisconnect:
        logger.info("WebSocket orderUpdate client disconnected")
    except Exception as e:
        logger.error(f"Error in orderUpdate WebSocket: {e}")
    finally:
        await websocket_manager.disconnect(websocket)

@router.websocket("/ws/orderBatch")
async def websocket_order_batch(websocket: WebSocket):
    """WebSocket endpoint for batched order updates."""
    if not websocket_manager:
        await websocket.close(code=1000, reason="WebSocket manager not initialized")
        return
    
    try:
        await websocket_manager.connect(websocket, "orderBatch")
        
        # Держим соединение открытым
        while True:
            # Ждем сообщения от клиента (можно использовать для ping/pong)
            data = await websocket.receive_text()
            logger.debug(f"Received message from orderBatch client: {data}")
            
    except WebSocketDisconnect:
        logger.info("WebSocket orderBatch client disconnected")
    except Exception as e:
        logger.error(f"Error in orderBatch WebSocket: {e}")
    finally:
        await websocket_manager.disconnect(websocket)

@router.get("/ws/status")
async def websocket_status():
    """Get WebSocket connection status."""
    if not websocket_manager:
        return {"error": "WebSocket manager not initialized"}
    
    return websocket_manager.get_connection_stats()
