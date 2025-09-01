"""API routes for HyperLiquid Node Parser."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional

from src.storage.models import Order
from src.storage.order_manager import OrderManager

router = APIRouter()

# Global order manager instance (will be initialized in main.py)
order_manager: Optional[OrderManager] = None

def get_order_manager() -> OrderManager:
    """Get order manager instance."""
    if order_manager is None:
        raise HTTPException(status_code=500, detail="Order manager not initialized")
    return order_manager

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
        orders = manager.get_orders(
            symbol=symbol,
            side=side,
            min_liquidity=min_liquidity,
            status=status
        )
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

@router.get("/config")
async def get_config_async():
    """Get current configuration.

    Returns:
        Current configuration
    """
    # TODO: Implement config retrieval
    return {"status": "not implemented"}

@router.put("/config")
async def update_config_async(config: dict):
    """Update configuration.

    Args:
        config: New configuration

    Returns:
        Updated configuration
    """
    # TODO: Implement config update
    return {"status": "not implemented"}
