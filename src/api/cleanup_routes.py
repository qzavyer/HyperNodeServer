"""API routes for cleanup functionality."""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, Any, Optional
from pydantic import BaseModel

from src.cleanup.directory_cleaner import DirectoryCleaner

router = APIRouter()

# Global instance (will be initialized in main.py)
directory_cleaner: Optional[DirectoryCleaner] = None

# Import from main to access global instance
import src.main

def get_directory_cleaner() -> DirectoryCleaner:
    """Get directory cleaner instance."""
    if src.main.directory_cleaner is None:
        raise HTTPException(status_code=500, detail="Directory cleaner not initialized")
    return src.main.directory_cleaner

class CleanupRequest(BaseModel):
    """Request model for cleanup operations."""
    dry_run: bool = False
    force: bool = False

class CleanupResponse(BaseModel):
    """Response model for cleanup operations."""
    success: bool
    message: str
    removed_directories: int
    removed_files: int
    dry_run: bool
    execution_time_seconds: float

class CleanupReportResponse(BaseModel):
    """Response model for cleanup reports."""
    success: bool
    report: Dict[str, Any]
    dry_run: bool

class CleanupStatsResponse(BaseModel):
    """Response model for cleanup statistics."""
    success: bool
    stats: Dict[str, Any]

@router.post("/cleanup/run", response_model=CleanupResponse)
async def run_cleanup_async(
    request: CleanupRequest,
    cleaner: DirectoryCleaner = Depends(get_directory_cleaner)
) -> CleanupResponse:
    """Run cleanup operation.
    
    Args:
        request: Cleanup request parameters
        cleaner: Directory cleaner instance
        
    Returns:
        Cleanup operation results
    """
    import time
    
    try:
        start_time = time.time()
        
        if request.dry_run:
            cleaner.logger.info("🔍 Starting dry-run cleanup operation")
        else:
            cleaner.logger.info("🧹 Starting cleanup operation")
        
        # Run cleanup
        removed_dirs, removed_files = await cleaner.cleanup_async(dry_run=request.dry_run)
        
        execution_time = time.time() - start_time
        
        if request.dry_run:
            message = f"Dry-run completed: would remove {removed_dirs} directories, {removed_files} files"
        else:
            message = f"Cleanup completed: removed {removed_dirs} directories, {removed_files} files"
        
        return CleanupResponse(
            success=True,
            message=message,
            removed_directories=removed_dirs,
            removed_files=removed_files,
            dry_run=request.dry_run,
            execution_time_seconds=round(execution_time, 2)
        )
        
    except Exception as e:
        cleaner.logger.error(f"❌ Cleanup operation failed: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Cleanup operation failed: {str(e)}"
        )

@router.get("/cleanup/report", response_model=CleanupReportResponse)
async def get_cleanup_report_async(
    dry_run: bool = Query(True, description="Generate report in dry-run mode"),
    cleaner: DirectoryCleaner = Depends(get_directory_cleaner)
) -> CleanupReportResponse:
    """Get cleanup report.
    
    Args:
        dry_run: Whether to generate report in dry-run mode
        cleaner: Directory cleaner instance
        
    Returns:
        Cleanup report
    """
    try:
        cleaner.logger.info(f"📊 Generating cleanup report (dry_run={dry_run})")
        
        # Generate report
        report = cleaner.get_cleanup_report(dry_run=dry_run)
        
        return CleanupReportResponse(
            success=True,
            report=report,
            dry_run=dry_run
        )
        
    except Exception as e:
        cleaner.logger.error(f"❌ Failed to generate cleanup report: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to generate cleanup report: {str(e)}"
        )

@router.get("/cleanup/stats", response_model=CleanupStatsResponse)
async def get_cleanup_stats_async(
    cleaner: DirectoryCleaner = Depends(get_directory_cleaner)
) -> CleanupStatsResponse:
    """Get cleanup statistics.
    
    Args:
        cleaner: Directory cleaner instance
        
    Returns:
        Cleanup statistics
    """
    try:
        cleaner.logger.info("📈 Getting cleanup statistics")
        
        # Get basic stats
        stats = cleaner.get_cleanup_stats()
        
        # Add additional information
        stats.update({
            "cleanup_interval_hours": cleaner.cleanup_interval_hours,
            "file_retention_hours": cleaner.file_retention_hours,
            "target_cleanup_path": str(cleaner.target_cleanup_path),
            "config_loaded": cleaner.config is not None,
            "config_path": str(cleaner.config_path) if cleaner.config_path else None
        })
        
        return CleanupStatsResponse(
            success=True,
            stats=stats
        )
        
    except Exception as e:
        cleaner.logger.error(f"❌ Failed to get cleanup statistics: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get cleanup statistics: {str(e)}"
        )

@router.get("/cleanup/config/summary")
async def get_cleanup_config_summary_async(
    cleaner: DirectoryCleaner = Depends(get_directory_cleaner)
) -> Dict[str, Any]:
    """Get cleanup configuration summary.
    
    Args:
        cleaner: Directory cleaner instance
        
    Returns:
        Configuration summary
    """
    try:
        cleaner.logger.info("⚙️ Getting cleanup configuration summary")
        
        if cleaner.config is None:
            return {
                "success": False,
                "message": "No configuration loaded",
                "config_loaded": False
            }
        
        # Get configuration summary
        summary = cleaner.get_config_summary()
        
        return {
            "success": True,
            "config_loaded": True,
            "summary": summary
        }
        
    except Exception as e:
        cleaner.logger.error(f"❌ Failed to get configuration summary: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to get configuration summary: {str(e)}"
        )

@router.post("/cleanup/config/load")
async def load_cleanup_config_async(
    config_path: str,
    cleaner: DirectoryCleaner = Depends(get_directory_cleaner)
) -> Dict[str, Any]:
    """Load cleanup configuration from file.
    
    Args:
        config_path: Path to configuration file
        cleaner: Directory cleaner instance
        
    Returns:
        Load result
    """
    try:
        cleaner.logger.info(f"📁 Loading cleanup configuration from: {config_path}")
        
        # Load configuration
        cleaner.load_config(config_path)
        
        # Get summary
        summary = cleaner.get_config_summary()
        
        return {
            "success": True,
            "message": f"Configuration loaded from {config_path}",
            "config_path": config_path,
            "summary": summary
        }
        
    except Exception as e:
        cleaner.logger.error(f"❌ Failed to load configuration: {e}")
        raise HTTPException(
            status_code=400, 
            detail=f"Failed to load configuration: {str(e)}"
        )

@router.post("/cleanup/config/apply")
async def apply_cleanup_config_async(
    dry_run: bool = Query(False, description="Apply rules in dry-run mode"),
    cleaner: DirectoryCleaner = Depends(get_directory_cleaner)
) -> Dict[str, Any]:
    """Apply cleanup rules from configuration.
    
    Args:
        dry_run: Whether to apply rules in dry-run mode
        cleaner: Directory cleaner instance
        
    Returns:
        Apply result
    """
    try:
        if cleaner.config is None:
            raise HTTPException(
                status_code=400, 
                detail="No configuration loaded. Please load configuration first."
            )
        
        cleaner.logger.info(f"🔧 Applying cleanup rules (dry_run={dry_run})")
        
        # Apply configuration rules
        removed_dirs, removed_files = await cleaner.apply_config_rules_async(dry_run=dry_run)
        
        if dry_run:
            message = f"Dry-run completed: would remove {removed_dirs} directories, {removed_files} files"
        else:
            message = f"Configuration rules applied: removed {removed_dirs} directories, {removed_files} files"
        
        return {
            "success": True,
            "message": message,
            "removed_directories": removed_dirs,
            "removed_files": removed_files,
            "dry_run": dry_run
        }
        
    except Exception as e:
        cleaner.logger.error(f"❌ Failed to apply configuration rules: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to apply configuration rules: {str(e)}"
        )

@router.get("/cleanup/health")
async def get_cleanup_health_async(
    cleaner: DirectoryCleaner = Depends(get_directory_cleaner)
) -> Dict[str, Any]:
    """Get cleanup system health status.
    
    Args:
        cleaner: Directory cleaner instance
        
    Returns:
        Health status
    """
    try:
        # Check basic health
        health_status = {
            "status": "healthy",
            "timestamp": cleaner.logger.handlers[0].formatter.formatTime(cleaner.logger.handlers[0].formatter.converter.now()) if cleaner.logger.handlers else "unknown",
            "cleaner_initialized": True,
            "config_loaded": cleaner.config is not None,
            "target_path_exists": cleaner.target_cleanup_path.exists(),
            "target_path_writable": cleaner.target_cleanup_path.is_dir() and cleaner.target_cleanup_path.stat().st_mode & 0o200,
            "cleanup_interval_hours": cleaner.cleanup_interval_hours,
            "file_retention_hours": cleaner.file_retention_hours
        }
        
        # Check for any issues
        issues = []
        if not cleaner.target_cleanup_path.exists():
            issues.append("Target cleanup path does not exist")
        elif not cleaner.target_cleanup_path.is_dir():
            issues.append("Target cleanup path is not a directory")
        
        if issues:
            health_status["status"] = "degraded"
            health_status["issues"] = issues
        
        return {
            "success": True,
            "health": health_status
        }
        
    except Exception as e:
        cleaner.logger.error(f"❌ Failed to get health status: {e}")
        return {
            "success": False,
            "health": {
                "status": "unhealthy",
                "error": str(e)
            }
        }
