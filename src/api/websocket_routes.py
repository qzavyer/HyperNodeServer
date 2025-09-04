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

@router.websocket("/orderUpdate")
async def websocket_order_update(websocket: WebSocket):
    """WebSocket endpoint for real-time order updates."""
    
    logger.info("=== WebSocket Connection Attempt ===")
    logger.info(f"Client IP: {websocket.client.host}")
    logger.info(f"User-Agent: {websocket.headers.get('user-agent')}")
    logger.info(f"Authorization: {websocket.headers.get('authorization')}")
    logger.info(f"Protocol: {websocket.headers.get('sec-websocket-protocol')}")
    logger.info(f"All Headers: {dict(websocket.headers)}")
    
    if not websocket_manager:
        logger.error("WebSocket manager not initialized")
        await websocket.close(code=1000, reason="WebSocket manager not initialized")
        return
    
    try:
        await websocket.accept()
        logger.info("✅ WebSocket connection accepted")
        
        await websocket_manager.connect(websocket, "orderUpdate")
        logger.info("✅ WebSocket connected to manager")
        
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received message from orderUpdate client: {data}")
                
                if data == "ping":
                    await websocket.send_text("pong")
                    logger.debug("Sent pong response")
                
            except WebSocketDisconnect:
                logger.info("WebSocket orderUpdate client disconnected")
                break
                
    except WebSocketDisconnect:
        logger.info("WebSocket orderUpdate client disconnected during handshake")
    except Exception as e:
        logger.error(f"Error in orderUpdate WebSocket: {e}")
        try:
            await websocket.close(code=1011, reason=f"Internal error: {str(e)}")
        except:
            pass
    finally:
        try:
            await websocket_manager.disconnect(websocket)
            logger.info("✅ WebSocket disconnected from manager")
        except Exception as e:
            logger.error(f"Error disconnecting from manager: {e}")


@router.websocket("/orderBatch")
async def websocket_order_batch(websocket: WebSocket):
    """WebSocket endpoint for batched order updates."""
    logger.info("=== WebSocket Batch Connection Attempt ===")
    logger.info(f"Client IP: {websocket.client.host}")
    
    if not websocket_manager:
        logger.error("WebSocket manager not initialized")
        await websocket.close(code=1000, reason="WebSocket manager not initialized")
        return
    
    try:
        await websocket.accept()
        logger.info("✅ WebSocket batch connection accepted")
        
        await websocket_manager.connect(websocket, "orderBatch")
        logger.info("✅ WebSocket batch connected to manager")
        
        # Держим соединение открытым
        while True:
            try:
                # Ждем сообщения от клиента (можно использовать для ping/pong)
                data = await websocket.receive_text()
                logger.debug(f"Received message from orderBatch client: {data}")
                
                if data == "ping":
                    await websocket.send_text("pong")
                    logger.debug("Sent pong response to batch client")
                    
            except WebSocketDisconnect:
                logger.info("WebSocket orderBatch client disconnected")
                break
                
    except WebSocketDisconnect:
        logger.info("WebSocket orderBatch client disconnected during handshake")
    except Exception as e:
        logger.error(f"Error in orderBatch WebSocket: {e}")
        try:
            await websocket.close(code=1011, reason=f"Internal error: {str(e)}")
        except:
            pass
    finally:
        try:
            await websocket_manager.disconnect(websocket)
            logger.info("✅ WebSocket batch disconnected from manager")
        except Exception as e:
            logger.error(f"Error disconnecting batch from manager: {e}")

@router.get("/status")
async def websocket_status():
    """Get WebSocket connection status."""
    if not websocket_manager:
        return {"error": "WebSocket manager not initialized"}
    
    return websocket_manager.get_connection_stats()
