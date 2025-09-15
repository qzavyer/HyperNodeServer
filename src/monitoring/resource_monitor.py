"""Resource monitoring for HyperLiquid node coexistence."""

import time
import psutil
from typing import Dict, Any
from src.utils.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

class ResourceMonitor:
    """Monitor system resources to ensure HyperLiquid node coexistence."""
    
    def __init__(self):
        """Initialize resource monitor."""
        self.enabled = settings.ENABLE_RESOURCE_MONITORING
        self.max_cpu_usage = settings.MAX_CPU_USAGE_PERCENT
        self.max_memory_usage_mb = settings.MAX_MEMORY_USAGE_MB
        self.check_interval = settings.RESOURCE_CHECK_INTERVAL_SEC
        self.throttle_on_high_usage = settings.THROTTLE_ON_HIGH_USAGE
        self.throttle_factor = settings.THROTTLE_FACTOR
        
        self.last_check = 0
        self.is_throttled = False
        self.process = psutil.Process()
        
        logger.info(f"Resource monitor initialized - CPU limit: {self.max_cpu_usage}%, Memory limit: {self.max_memory_usage_mb}MB")
    
    def check_resources(self) -> Dict[str, Any]:
        """Check current resource usage.
        
        Returns:
            Dictionary with resource usage information
        """
        if not self.enabled:
            return {"enabled": False, "throttled": False}
        
        current_time = time.time()
        
        try:
            # Get system-wide CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Get process memory usage
            memory_info = self.process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # Get system memory usage
            system_memory = psutil.virtual_memory()
            system_memory_percent = system_memory.percent
            
            # Check if we need to throttle
            should_throttle = (
                cpu_percent > self.max_cpu_usage or 
                memory_mb > self.max_memory_usage_mb or
                system_memory_percent > 80  # System memory usage too high
            )
            
            # Update throttling status
            if should_throttle and not self.is_throttled:
                logger.warning(
                    f"Resource usage high - CPU: {cpu_percent:.1f}%, "
                    f"Process Memory: {memory_mb:.1f}MB, "
                    f"System Memory: {system_memory_percent:.1f}%. "
                    f"Throttling processing."
                )
                self.is_throttled = True
            elif not should_throttle and self.is_throttled:
                logger.info(
                    f"Resource usage normal - CPU: {cpu_percent:.1f}%, "
                    f"Process Memory: {memory_mb:.1f}MB, "
                    f"System Memory: {system_memory_percent:.1f}%. "
                    f"Resuming normal processing."
                )
                self.is_throttled = False
            
            self.last_check = current_time
            
            return {
                "enabled": True,
                "throttled": self.is_throttled,
                "cpu_percent": cpu_percent,
                "memory_mb": memory_mb,
                "system_memory_percent": system_memory_percent,
                "should_throttle": should_throttle,
                "last_check": current_time
            }
            
        except Exception as e:
            logger.error(f"Error checking resource usage: {e}")
            return {
                "enabled": True,
                "throttled": False,
                "error": str(e)
            }
    
    def should_throttle(self) -> bool:
        """Check if processing should be throttled.
        
        Returns:
            True if processing should be throttled
        """
        if not self.enabled:
            return False
        
        current_time = time.time()
        if current_time - self.last_check < self.check_interval:
            return self.is_throttled
        
        result = self.check_resources()
        return result.get("throttled", False)
    
    def get_throttle_factor(self) -> float:
        """Get throttle factor for processing.
        
        Returns:
            Throttle factor (1.0 = normal, >1.0 = throttled)
        """
        if not self.enabled or not self.is_throttled:
            return 1.0
        
        return 1.0 / self.throttle_factor
    
    def get_status(self) -> Dict[str, Any]:
        """Get current resource monitoring status.
        
        Returns:
            Dictionary with monitoring status
        """
        return {
            "enabled": self.enabled,
            "max_cpu_usage": self.max_cpu_usage,
            "max_memory_usage_mb": self.max_memory_usage_mb,
            "check_interval": self.check_interval,
            "throttle_on_high_usage": self.throttle_on_high_usage,
            "throttle_factor": self.throttle_factor,
            "is_throttled": self.is_throttled,
            "last_check": self.last_check
        }
