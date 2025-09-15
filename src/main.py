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
from src.api.health_routes import router as health_router
from src.storage.file_storage import FileStorage
from src.storage.order_manager import OrderManager
from src.storage.config_manager import ConfigManager
from src.watcher.single_file_tail_watcher import SingleFileTailWatcher
from src.websocket.websocket_manager import WebSocketManager
from src.notifications.order_notifier import OrderNotifier
from src.cleanup.directory_cleaner import DirectoryCleaner
from src.monitoring.node_health_monitor import NodeHealthMonitor
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
app.include_router(health_router, prefix="/api/v1")

# Global instances
file_storage = FileStorage()
config_manager = ConfigManager()
websocket_manager = WebSocketManager()
order_notifier = OrderNotifier(websocket_manager, config_manager)
order_manager = OrderManager(file_storage, config_manager, order_notifier)
single_file_tail_watcher = SingleFileTailWatcher(order_manager)
directory_cleaner = DirectoryCleaner(settings.NODE_LOGS_PATH, single_file_tail_watcher)
node_health_monitor = None  # Will be initialized in startup_event

# Set WebSocket manager in routes
set_websocket_manager(websocket_manager)

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    try:
        # Initialize config manager
        await config_manager.load_config_async()
        logger.info("✅ Configuration loaded successfully")
        
        # Initialize node health monitor
        config = config_manager.get_config()
        global node_health_monitor
        node_health_monitor = NodeHealthMonitor(
            node_logs_path=config.node_logs_path,
            threshold_minutes=config.node_health.threshold_minutes
        )
        logger.info("✅ Node health monitor initialized successfully")
        
        # Start WebSocket manager
        await websocket_manager.start()
        logger.info("✅ WebSocket manager started successfully")
        
        # Initialize order manager
        await order_manager.initialize()
        logger.info("✅ Application started successfully")
        logger.info(f"📊 Loaded {order_manager.get_order_count()} orders")
        
        # Start single file tail watcher for real-time processing
        if settings.SINGLE_FILE_TAIL_ENABLED:
            await single_file_tail_watcher.start_async()
            logger.info("✅ Single file tail watcher started successfully")
        else:
            logger.info("Single file tail watcher disabled in settings")
        
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
        # Stop single file tail watcher
        if settings.SINGLE_FILE_TAIL_ENABLED:
            await single_file_tail_watcher.stop_async()
        
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
        "single_file_tail_watcher": single_file_tail_watcher.get_status() if settings.SINGLE_FILE_TAIL_ENABLED else {"enabled": False},
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
            "batch_size": settings.BATCH_SIZE,
            "single_file_tail_enabled": settings.SINGLE_FILE_TAIL_ENABLED,
            "fallback_scan_interval_sec": settings.FALLBACK_SCAN_INTERVAL_SEC
        },
        "directory_cleanup": directory_cleaner.get_cleanup_stats()
    }

@app.get("/metrics/realtime")
async def realtime_metrics():
    """Real-time processing metrics."""
    return {
        "iteration": "1 - Single File Tail Reader",
        "single_file_tail_watcher": single_file_tail_watcher.get_status() if settings.SINGLE_FILE_TAIL_ENABLED else {"enabled": False},
        "processing": {
            "enabled": settings.SINGLE_FILE_TAIL_ENABLED,
            "current_file": single_file_tail_watcher.get_status().get("current_file") if settings.SINGLE_FILE_TAIL_ENABLED else None,
            "is_running": single_file_tail_watcher.get_status().get("is_running", False) if settings.SINGLE_FILE_TAIL_ENABLED else False
        },
        "settings": {
            "single_file_tail_enabled": settings.SINGLE_FILE_TAIL_ENABLED,
            "fallback_scan_interval_sec": settings.FALLBACK_SCAN_INTERVAL_SEC,
            "tail_readline_interval_ms": settings.TAIL_READLINE_INTERVAL_MS
        }
    }

@app.get("/metrics/single-file-tail")
async def single_file_tail_metrics():
    """Single file tail watcher metrics."""
    if not settings.SINGLE_FILE_TAIL_ENABLED:
        return {"enabled": False, "message": "Single file tail watcher is disabled"}
    
    status = single_file_tail_watcher.get_status()
    return {
        "enabled": True,
        "status": status,
        "current_file_info": {
            "path": status.get("current_file"),
            "position": status.get("current_position"),
            "is_active": status.get("is_running", False)
        },
        "performance": {
            "tail_interval_ms": status.get("tail_interval_ms"),
            "fallback_interval_sec": status.get("fallback_interval_sec"),
            "watchdog_active": status.get("watchdog_active", False)
        },
        "settings": {
            "single_file_tail_enabled": settings.SINGLE_FILE_TAIL_ENABLED,
            "fallback_scan_interval_sec": settings.FALLBACK_SCAN_INTERVAL_SEC,
            "tail_readline_interval_ms": settings.TAIL_READLINE_INTERVAL_MS
        }
    }
