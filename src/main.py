"""Main FastAPI application for HyperLiquid Node Parser."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.storage.file_storage import FileStorage
from src.storage.order_manager import OrderManager
from src.watcher.file_watcher import FileWatcher
from src.utils.logger import setup_logger
from config.settings import settings

# Setup logging
logger = setup_logger(__name__, log_level=settings.LOG_LEVEL)

# Create FastAPI app
app = FastAPI(
    title="HyperLiquid Node Parser",
    description="API for parsing HyperLiquid node logs and providing order book data",
    version="1.0.0"
)

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

# Global instances
file_storage = FileStorage()
order_manager = OrderManager(file_storage)
file_watcher = FileWatcher(order_manager)

@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    try:
        # Initialize order manager
        await order_manager.initialize()
        logger.info("✅ Application started successfully")
        logger.info(f"📊 Loaded {order_manager.get_order_count()} orders")
        
        # Start file watcher
        await file_watcher.start_async()
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    try:
        # Stop file watcher
        await file_watcher.stop_async()
        
        # Cleanup old orders
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
            "cancelled": status_counts.get("cancelled", 0),
            "triggered": status_counts.get("triggered", 0)
        }
    }
