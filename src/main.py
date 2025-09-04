"""Main FastAPI application for HyperLiquid Node Parser."""

import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import time

from src.api.routes import router
from src.api.websocket_routes import router as websocket_router, set_websocket_manager
from src.storage.file_storage import FileStorage
from src.storage.order_manager import OrderManager
from src.storage.config_manager import ConfigManager
from src.watcher.file_watcher import FileWatcher
from src.websocket.websocket_manager import WebSocketManager
from src.notifications.order_notifier import OrderNotifier
from src.cleanup.directory_cleaner import DirectoryCleaner
from src.utils.logger import setup_logger
from config.settings import settings

# Setup logging
logger = setup_logger(__name__, log_level=settings.LOG_LEVEL)

class TimeoutMiddleware(BaseHTTPMiddleware):
    """Middleware for request timeout handling."""
    
    def __init__(self, app, timeout_seconds: int = 30):
        super().__init__(app)
        self.timeout_seconds = timeout_seconds
    
    async def dispatch(self, request: Request, call_next):
        try:
            # Set timeout for the request
            async with asyncio.timeout(self.timeout_seconds):
                start_time = time.time()
                response = await call_next(request)
                process_time = time.time() - start_time
                
                # Add processing time header
                response.headers["X-Process-Time"] = str(process_time)
                return response
                
        except asyncio.TimeoutError:
            logger.warning(f"Request timeout after {self.timeout_seconds}s: {request.url}")
            raise HTTPException(status_code=408, detail="Request timeout")
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

class PerformanceMiddleware(BaseHTTPMiddleware):
    """Middleware for performance monitoring and optimization."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Add request start time to state
        request.state.start_time = start_time
        
        try:
            response = await call_next(request)
            
            # Calculate processing time
            process_time = time.time() - start_time
            
            # Log slow requests
            if process_time > 1.0:  # Log requests taking more than 1 second
                logger.warning(f"Slow request: {request.method} {request.url} took {process_time:.2f}s")
            
            # Add performance headers
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            response.headers["X-Request-ID"] = str(id(request))
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(f"Request failed after {process_time:.3f}s: {request.method} {request.url} - {e}")
            raise

# Create FastAPI app
app = FastAPI(
    title="HyperLiquid Node Parser",
    description="API for parsing HyperLiquid node logs and providing order book data",
    version="1.0.0"
)

# Add middleware for performance and security
app.add_middleware(TimeoutMiddleware, timeout_seconds=60)  # 60 second timeout
app.add_middleware(PerformanceMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/ws")

# Global instances
file_storage = FileStorage()
config_manager = ConfigManager()
websocket_manager = WebSocketManager()
order_notifier = OrderNotifier(websocket_manager, config_manager)
order_manager = OrderManager(file_storage, config_manager, order_notifier)
file_watcher = FileWatcher(order_manager)
directory_cleaner = DirectoryCleaner(settings.NODE_LOGS_PATH)

# Set WebSocket manager in routes
set_websocket_manager(websocket_manager)

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    try:
        # Initialize config manager
        await config_manager.load_config_async()
        logger.info("✅ Configuration loaded successfully")
        
        # Start WebSocket manager
        await websocket_manager.start()
        logger.info("✅ WebSocket manager started successfully")
        
        # Initialize order manager
        await order_manager.initialize()
        logger.info("✅ Application started successfully")
        logger.info(f"📊 Loaded {order_manager.get_order_count()} orders")
        
        # Start file watcher
        await file_watcher.start_async()
        
        # Start directory cleaner
        asyncio.create_task(directory_cleaner.start_periodic_cleanup_async())
        logger.info("✅ Directory cleaner started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    try:
        # Stop file watcher
        await file_watcher.stop_async()
        
        # Stop WebSocket manager
        await websocket_manager.stop()
        
        # Cleanup old orders (synchronous method)
        cleaned_count = order_manager.cleanup_old_orders(settings.CLEANUP_INTERVAL_HOURS)
        logger.info(f"🧹 Cleaned up {cleaned_count} old orders")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "HyperLiquid Node Parser API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    status_counts = order_manager.get_order_count_by_status()
    return {
        "status": "healthy",
        "order_count": order_manager.get_order_count(),
        "order_manager_stats": {
            "open": status_counts.get("open", 0),
            "filled": status_counts.get("filled", 0),
            "canceled": status_counts.get("canceled", 0),
            "triggered": status_counts.get("triggered", 0)
        }
    }

@app.get("/performance")
async def performance_info():
    """Performance information endpoint."""
    return {
        "file_watcher_running": file_watcher.is_running,
        "background_processing": file_watcher.get_processing_status(),
        "websocket_status": websocket_manager.get_connection_stats(),
        "notifications": order_notifier.get_notification_stats(),
        "memory_usage": {
            "orders_in_memory": order_manager.get_order_count(),
            "estimated_memory_mb": order_manager.get_order_count() * 0.001  # Rough estimate
        },
        "settings": {
            "max_file_size_gb": settings.MAX_FILE_SIZE_GB,
            "max_orders_per_file": settings.MAX_ORDERS_PER_FILE,
            "chunk_size_bytes": settings.CHUNK_SIZE_BYTES,
            "batch_size": settings.BATCH_SIZE
        },
        "directory_cleanup": directory_cleaner.get_cleanup_stats()
    }
