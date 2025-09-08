"""API routes for HyperLiquid Node Parser."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any

from src.storage.models import Order, Config, SymbolConfig
from src.storage.order_manager import OrderManager
from src.storage.config_manager import ConfigManager

router = APIRouter()

# Global instances (will be initialized in main.py)
order_manager: Optional[OrderManager] = None
config_manager: Optional[ConfigManager] = None

# Import from main to access global instances
import src.main

def get_order_manager() -> OrderManager:
    """Get order manager instance."""
    if src.main.order_manager is None:
        raise HTTPException(status_code=500, detail="Order manager not initialized")
    return src.main.order_manager

def get_config_manager() -> ConfigManager:
    """Get config manager instance."""
    if src.main.config_manager is None:
        raise HTTPException(status_code=500, detail="Config manager not initialized")
    return src.main.config_manager

@router.get("/orders", response_model=List[Order])
async def get_orders_async(
    symbol: Optional[str] = None,
    side: Optional[str] = None,
    min_liquidity: Optional[float] = None,
    status: Optional[str] = None,
    manager: OrderManager = Depends(get_order_manager)
) -> List[Order]:
    """Get filtered list of orders.

    Args:
        symbol: Filter by symbol/coin
        side: Filter by side (Bid/Ask)
        min_liquidity: Minimum liquidity filter
        status: Filter by status
        manager: Order manager instance

    Returns:
        List of filtered orders
    """
    try:
        # Start with all orders
        orders = list(manager.orders.values())
        
        # Apply filters
        if symbol:
            orders = [order for order in orders if order.symbol == symbol]
        
        if side:
            orders = [order for order in orders if order.side == side]
        
        if status:
            orders = [order for order in orders if order.status == status]
        
        if min_liquidity:
            orders = [order for order in orders if (order.price * order.size) >= min_liquidity]
        
        return orders
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get orders: {str(e)}")

@router.get("/orders/{order_id}", response_model=Order)
async def get_order_by_id_async(
    order_id: str,
    manager: OrderManager = Depends(get_order_manager)
) -> Order:
    """Get order by ID.

    Args:
        order_id: Order ID
        manager: Order manager instance

    Returns:
        Order details
    """
    order = manager.get_order_by_id(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.get("/orders/stats/summary")
async def get_orders_summary_async(
    manager: OrderManager = Depends(get_order_manager)
) -> dict:
    """Get orders summary statistics.

    Args:
        manager: Order manager instance

    Returns:
        Summary statistics
    """
    try:
        total_count = manager.get_order_count()
        status_counts = manager.get_order_count_by_status()
        open_orders = manager.get_open_orders()
        
        return {
            "total_orders": total_count,
            "status_counts": status_counts,
            "open_orders_count": len(open_orders)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {str(e)}")

@router.get("/config", response_model=Config)
async def get_config_async(
    manager: ConfigManager = Depends(get_config_manager)
) -> Config:
    """Get current configuration.

    Args:
        manager: Config manager instance

    Returns:
        Current configuration
    """
    try:
        return manager.get_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")

@router.put("/config", response_model=Config)
async def update_config_async(
    updates: Dict[str, Any],
    manager: ConfigManager = Depends(get_config_manager)
) -> Config:
    """Update configuration.

    Args:
        updates: Configuration updates
        manager: Config manager instance

    Returns:
        Updated configuration
    """
    try:
        return await manager.update_config_async(updates)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update config: {str(e)}")

@router.put("/config/symbols", response_model=Config)
async def update_symbols_async(
    symbols: List[SymbolConfig],
    manager: ConfigManager = Depends(get_config_manager)
) -> Config:
    """Update symbols configuration only.

    Args:
        symbols: List of symbol configurations
        manager: Config manager instance

    Returns:
        Updated configuration
    """
    try:
        return await manager.update_symbols_async(symbols)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update symbols: {str(e)}")

@router.get("/debug/filewatcher")
async def debug_filewatcher() -> Dict[str, Any]:
    """Debug endpoint for FileWatcher status and diagnostics."""
    try:
        # Import here to avoid circular imports
        import src.main
        
        file_watcher = src.main.file_watcher
        if file_watcher is None:
            raise HTTPException(status_code=500, detail="FileWatcher not initialized")
        
        # Get basic status
        status = file_watcher.get_processing_status()
        
        # Get detailed diagnostics
        logs_path = file_watcher.logs_path
        hourly_path = logs_path / "node_order_statuses" / "hourly"
        
        # Count files
        json_files = []
        total_size = 0
        if hourly_path.exists():
            json_files = list(hourly_path.rglob("*.json"))
            total_size = sum(f.stat().st_size for f in json_files)
        
        diagnostics = {
            "logs_path": str(logs_path),
            "logs_path_exists": logs_path.exists(),
            "hourly_path": str(hourly_path),
            "hourly_path_exists": hourly_path.exists(),
            "json_files_count": len(json_files),
            "total_size_mb": round(total_size / (1024*1024), 2),
            "latest_files": [str(f) for f in json_files[-5:]] if json_files else [],
            "directory_contents": [],
        }
        
        # Add directory listing if exists
        if logs_path.exists():
            try:
                diagnostics["directory_contents"] = [str(p) for p in logs_path.iterdir()][:10]
            except Exception as e:
                diagnostics["directory_error"] = str(e)
        
        return {
            "status": status,
            "diagnostics": diagnostics,
            "settings": {
                "max_file_size_gb": src.main.settings.MAX_FILE_SIZE_GB,
                "batch_size": src.main.settings.BATCH_SIZE,
                "chunk_size": src.main.settings.CHUNK_SIZE_BYTES,
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Debug error: {str(e)}")