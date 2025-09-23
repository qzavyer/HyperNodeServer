"""Health API routes for HyperLiquid Node Parser."""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from datetime import datetime, timezone

from src.monitoring.node_health_monitor import NodeHealthMonitor, NodeHealthStatus

router = APIRouter()

# Global instance (will be initialized in main.py)
node_health_monitor: NodeHealthMonitor = None

# Import from main to access global instance
import src.main

def get_node_health_monitor() -> NodeHealthMonitor:
    """Get node health monitor instance.
    
    Returns:
        NodeHealthMonitor instance
        
    Raises:
        HTTPException: If monitor not initialized
    """
    if src.main.node_health_monitor is None:
        raise HTTPException(
            status_code=500, 
            detail="Node health monitor not initialized"
        )
    return src.main.node_health_monitor

@router.get("/node-health", response_model=Dict[str, Any])
async def get_node_health_status(
    monitor: NodeHealthMonitor = Depends(get_node_health_monitor)
) -> Dict[str, Any]:
    """Get current node health status.
    
    Returns:
        Node health status information
        
    Raises:
        HTTPException: If unable to get health status
    """
    try:
        status = monitor.get_health_status()
        return status.to_dict()
        
    except Exception as e:
        # Log the error but don't expose internal details
        from src.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"Failed to get node health status: {e}")
        
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve node health status"
        )

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Enhanced health check endpoint with metrics.
    
    Returns:
        Health status with metrics
    """
    try:
        monitor = get_node_health_monitor()
        status = monitor.get_health_status()
        return {
            "status": "success",
            "data": status.to_dict(),
            "timestamp": status.check_timestamp.isoformat()
        }
    except Exception as e:
        from src.utils.logger import get_logger
        logger = get_logger(__name__)
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "data": {
                "nodeStatus": "offline",
                "lastUpdate": None,
                "errorCount": 0,
                "responseTime": 0.0,
                "uptime": 0.0,
                "criticalAlerts": []
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
