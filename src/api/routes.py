"""API routes for HyperLiquid Node Parser."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any

from src.storage.models import Order, Config, SymbolConfig
from src.storage.order_manager import OrderManager
from src.storage.config_manager import ConfigManager
from src.models.reactive_api import OrderSearchRequest, OrderTrackRequest, ReactiveWatcherStatus

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

@router.get("/debug/single-file-tail")
async def debug_single_file_tail() -> Dict[str, Any]:
    """Debug endpoint for SingleFileTailWatcher status and diagnostics."""
    try:
        # Import here to avoid circular imports
        import src.main
        
        single_file_tail_watcher = src.main.single_file_tail_watcher
        if single_file_tail_watcher is None:
            raise HTTPException(status_code=500, detail="SingleFileTailWatcher not initialized")
        
        # Get basic status
        status = single_file_tail_watcher.get_status()
        
        # Get detailed diagnostics
        logs_path = single_file_tail_watcher.logs_path
        hourly_path = logs_path / "node_order_statuses" / "hourly"
        
        # Count log files (numeric names)
        log_files = []
        total_size = 0
        if hourly_path.exists():
            all_files = list(hourly_path.rglob("*"))
            log_files = [f for f in all_files if f.is_file() and (f.name.isdigit() or f.name.endswith('.json'))]
            total_size = sum(f.stat().st_size for f in log_files)
        
        diagnostics = {
            "logs_path": str(logs_path),
            "logs_path_exists": logs_path.exists(),
            "hourly_path": str(hourly_path),
            "hourly_path_exists": hourly_path.exists(),
            "log_files_count": len(log_files),
            "total_size_mb": round(total_size / (1024*1024), 2),
            "latest_files": [str(f) for f in log_files[-5:]] if log_files else [],
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

@router.post("/config/node-health")
async def update_node_health_config(
    config_data: Dict[str, Any],
    manager: ConfigManager = Depends(get_config_manager)
) -> Dict[str, Any]:
    """Update node health monitoring configuration.
    
    Args:
        config_data: Configuration data to update
        manager: Config manager instance
        
    Returns:
        Updated configuration
    """
    try:
        # Validate required fields
        required_fields = ["threshold_minutes", "check_interval_seconds"]
        for field in required_fields:
            if field not in config_data:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Missing required field: {field}"
                )
        
        # Validate field types and ranges
        threshold_minutes = config_data.get("threshold_minutes")
        if not isinstance(threshold_minutes, int) or threshold_minutes < 1 or threshold_minutes > 60:
            raise HTTPException(
                status_code=400, 
                detail="threshold_minutes must be an integer between 1 and 60"
            )
        
        check_interval_seconds = config_data.get("check_interval_seconds")
        if not isinstance(check_interval_seconds, int) or check_interval_seconds < 10 or check_interval_seconds > 300:
            raise HTTPException(
                status_code=400, 
                detail="check_interval_seconds must be an integer between 10 and 300"
            )
        
        # Get current config and update
        config = manager.get_config()
        config.node_health.threshold_minutes = threshold_minutes
        config.node_health.check_interval_seconds = check_interval_seconds
        
        # Save updated config
        await manager.save_config_async(config)
        
        return {
            "success": True,
            "message": "Node health configuration updated successfully",
            "config": {
                "threshold_minutes": config.node_health.threshold_minutes,
                "check_interval_seconds": config.node_health.check_interval_seconds
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to update node health configuration: {str(e)}"
        )

@router.get("/config/node-health")
async def get_node_health_config(
    manager: ConfigManager = Depends(get_config_manager)
) -> Dict[str, Any]:
    """Get current node health monitoring configuration.
    
    Args:
        manager: Config manager instance
        
    Returns:
        Current configuration
    """
    try:
        config = manager.get_config()
        return {
            "threshold_minutes": config.node_health.threshold_minutes,
            "check_interval_seconds": config.node_health.check_interval_seconds
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get node health configuration: {str(e)}"
        )

# ReactiveOrderWatcher endpoints
@router.post("/reactive-orders/search")
async def search_orders_reactive(request: OrderSearchRequest) -> Dict[str, Any]:
    """Поиск ордеров через ReactiveOrderWatcher.
    
    Args:
        request: Параметры поиска ордеров
        
    Returns:
        Статус поиска (ордера отправляются через WebSocket)
    """
    try:
        # Import here to avoid circular imports
        import src.main
        
        reactive_watcher = src.main.reactive_order_watcher
        if reactive_watcher is None:
            raise HTTPException(status_code=500, detail="ReactiveOrderWatcher not initialized")
        
        # Получаем конфигурацию для проверки минимальной ликвидности
        config_manager = src.main.config_manager
        if config_manager is None:
            raise HTTPException(status_code=500, detail="ConfigManager not initialized")
        
        config = config_manager.get_config()
        
        # Находим конфигурацию символа
        symbol_config = None
        for symbol in config.symbols_config:
            if symbol.symbol == request.ticker:
                symbol_config = symbol
                break
        
        if symbol_config is None:
            raise HTTPException(
                status_code=400, 
                detail=f"Symbol {request.ticker} not found in configuration"
            )
        
        # Проверяем минимальную ликвидность
        min_liquidity = symbol_config.min_liquidity
        if min_liquidity <= 0:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid min_liquidity for symbol {request.ticker}: {min_liquidity}"
            )
        
        # Добавляем запрос на поиск (ордера автоматически отправятся в WebSocket)
        await reactive_watcher.add_search_request(
            ticker=request.ticker,
            side=request.side,
            price=request.price,
            timestamp=request.timestamp,
            tolerance=request.tolerance
        )
        
        return {
            "success": True,
            "message": f"Search initiated for {request.ticker} {request.side} @ {request.price}",
            "min_liquidity": min_liquidity,
            "tolerance": request.tolerance,
            "timestamp": request.timestamp,
            "note": "Search is being processed. Found orders will be sent via WebSocket orderUpdate channel"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@router.post("/reactive-orders/track")
async def track_order_reactive(request: OrderTrackRequest) -> Dict[str, Any]:
    """Начать отслеживание ордера по ID.
    
    Args:
        request: Параметры отслеживания ордера
        
    Returns:
        Статус отслеживания
    """
    try:
        # Import here to avoid circular imports
        import src.main
        
        reactive_watcher = src.main.reactive_order_watcher
        if reactive_watcher is None:
            raise HTTPException(status_code=500, detail="ReactiveOrderWatcher not initialized")
        
        await reactive_watcher.start_tracking_order(request.order_id)
        
        return {
            "success": True,
            "message": f"Started tracking order {request.order_id}",
            "order_id": request.order_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start tracking: {str(e)}")

@router.delete("/reactive-orders/untrack")
async def untrack_order_reactive(request: OrderTrackRequest) -> Dict[str, Any]:
    """Остановить отслеживание ордера по ID.
    
    Args:
        request: Параметры остановки отслеживания ордера
        
    Returns:
        Статус остановки отслеживания
    """
    try:
        # Import here to avoid circular imports
        import src.main
        
        reactive_watcher = src.main.reactive_order_watcher
        if reactive_watcher is None:
            raise HTTPException(status_code=500, detail="ReactiveOrderWatcher not initialized")
        
        await reactive_watcher.stop_tracking_order(request.order_id)
        
        return {
            "success": True,
            "message": f"Stopped tracking order {request.order_id}",
            "order_id": request.order_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop tracking: {str(e)}")

@router.get("/reactive-orders/status", response_model=ReactiveWatcherStatus)
async def get_reactive_watcher_status() -> ReactiveWatcherStatus:
    """Получить статус ReactiveOrderWatcher.
    
    Returns:
        Статус ReactiveOrderWatcher
    """
    try:
        # Import here to avoid circular imports
        import src.main
        
        reactive_watcher = src.main.reactive_order_watcher
        if reactive_watcher is None:
            raise HTTPException(status_code=500, detail="ReactiveOrderWatcher not initialized")
        
        return ReactiveWatcherStatus(
            is_initialized=reactive_watcher.current_file_path is not None,
            current_file=str(reactive_watcher.current_file_path) if reactive_watcher.current_file_path else None,
            tracked_orders_count=len(reactive_watcher.tracked_orders),
            cached_orders_count=sum(len(orders) for orders in reactive_watcher.cached_orders.values()),
            monitoring_active=reactive_watcher.monitoring_task is not None and not reactive_watcher.monitoring_task.done(),
            cache_duration_seconds=reactive_watcher.cache_duration_seconds,
            monitoring_interval_ms=reactive_watcher.monitoring_interval_ms
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")