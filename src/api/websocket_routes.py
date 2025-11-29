"""WebSocket routes for real-time order updates."""

import asyncio
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

@router.websocket("/")
async def websocket_root(websocket: WebSocket):
    """Root WebSocket endpoint - redirects to orderUpdate."""
    logger.info("=== WebSocket Root Connection (redirecting to orderUpdate) ===")
    logger.info(f"Client IP: {websocket.client.host}")
    
    # Перенаправляем на orderUpdate обработчик
    await websocket_order_update(websocket)

@router.websocket("/orderUpdate")
async def websocket_order_update(websocket: WebSocket):
    """WebSocket endpoint for real-time order updates."""
    
    logger.info("=== WebSocket orderUpdate Connection Attempt ===")
    logger.info(f"Client IP: {websocket.client.host if websocket.client else 'unknown'}")
    logger.info(f"WebSocket URL: {websocket.url}")
    logger.info(f"WebSocket headers: {dict(websocket.headers)}")
    
    # Проверяем менеджер до accept()
    if not websocket_manager:
        logger.error("WebSocket manager not initialized")
        # Отклоняем соединение без accept()
        return
    
    try:
        # Принимаем соединение с таймаутом
        await asyncio.wait_for(websocket.accept(), timeout=30.0)
        logger.info("✅ WebSocket orderUpdate connection accepted")
        
        # Подключаем к менеджеру
        await websocket_manager.connect(websocket, "orderUpdate")
        logger.info("✅ WebSocket orderUpdate connected to manager")
        
        # Основной цикл обработки сообщений
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received from orderUpdate client: {data}")
                
                if data == "ping":
                    await websocket.send_text("pong")
                    logger.debug("Sent pong to orderUpdate client")
                elif data == "close":
                    logger.info("Client requested close")
                    await websocket.close(code=1000, reason="Client requested close")
                    break
                
            except WebSocketDisconnect:
                logger.info("WebSocket orderUpdate client disconnected in loop")
                break
            except Exception as e:
                logger.error(f"Error in orderUpdate message loop: {e}")
                break
                
    except WebSocketDisconnect:
        logger.info("WebSocket orderUpdate client disconnected during handshake")
    except Exception as e:
        logger.error(f"Error in orderUpdate WebSocket: {e}")
        # Пытаемся корректно закрыть соединение
        try:
            if websocket.client_state.name == "CONNECTED":
                await websocket.close(code=1000, reason="Server error")
        except Exception as close_error:
            logger.debug(f"Could not close orderUpdate websocket: {close_error}")
    finally:
        # Всегда пытаемся отключить от менеджера
        try:
            if websocket_manager:
                await websocket_manager.disconnect(websocket)
                logger.info("✅ WebSocket orderUpdate disconnected from manager")
        except Exception as e:
            logger.error(f"Error disconnecting orderUpdate from manager: {e}")


@router.websocket("/orderBatch")
async def websocket_order_batch(websocket: WebSocket):
    """WebSocket endpoint for batched order updates."""
    logger.info("=== WebSocket orderBatch Connection Attempt ===")
    logger.info(f"Client IP: {websocket.client.host if websocket.client else 'unknown'}")
    logger.info(f"WebSocket URL: {websocket.url}")
    logger.info(f"WebSocket headers: {dict(websocket.headers)}")
    
    # Проверяем менеджер до accept()
    if not websocket_manager:
        logger.error("WebSocket manager not initialized")
        # Отклоняем соединение без accept()
        return
    
    try:
        # Принимаем соединение с таймаутом
        await asyncio.wait_for(websocket.accept(), timeout=30.0)
        logger.info("✅ WebSocket orderBatch connection accepted")
        
        # Подключаем к менеджеру
        await websocket_manager.connect(websocket, "orderBatch")
        logger.info("✅ WebSocket orderBatch connected to manager")
        
        # Основной цикл обработки сообщений
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received from orderBatch client: {data}")
                
                if data == "ping":
                    await websocket.send_text("pong")
                    logger.debug("Sent pong to orderBatch client")
                elif data == "close":
                    logger.info("Client requested close")
                    await websocket.close(code=1000, reason="Client requested close")
                    break
                    
            except WebSocketDisconnect:
                logger.info("WebSocket orderBatch client disconnected in loop")
                break
            except Exception as e:
                logger.error(f"Error in orderBatch message loop: {e}")
                break
                
    except WebSocketDisconnect:
        logger.info("WebSocket orderBatch client disconnected during handshake")
    except Exception as e:
        logger.error(f"Error in orderBatch WebSocket: {e}")
        # Пытаемся корректно закрыть соединение
        try:
            if websocket.client_state.name == "CONNECTED":
                await websocket.close(code=1000, reason="Server error")
        except Exception as close_error:
            logger.debug(f"Could not close orderBatch websocket: {close_error}")
    finally:
        # Всегда пытаемся отключить от менеджера
        try:
            if websocket_manager:
                await websocket_manager.disconnect(websocket)
                logger.info("✅ WebSocket orderBatch disconnected from manager")
        except Exception as e:
            logger.error(f"Error disconnecting orderBatch from manager: {e}")

@router.get("/status")
async def websocket_status():
    """Get WebSocket connection status."""
    if not websocket_manager:
        return {"error": "WebSocket manager not initialized"}
    
    return websocket_manager.get_connection_stats()
