# api/admin.py
"""
Admin API endpoints — system statistics and logs.
User management removed (auth system removed).
"""
import os
import logging
from fastapi import APIRouter
import database
import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/stats")
async def global_stats():
    """Get global system statistics."""
    db_stats = database.get_global_stats()

    # Get cache stats
    try:
        from engine.cache import get_stats as cache_stats
        cache = cache_stats()
    except Exception:
        cache = {"total_entries": 0, "active_entries": 0}

    return {
        **db_stats,
        "cache": cache,
    }


@router.get("/logs")
async def get_system_logs(lines: int = 100):
    """Read the last N lines of the system log."""
    log_file = config.LOG_FILE
    if not os.path.exists(log_file):
        return {"logs": [], "message": "No log file found"}

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        return {"logs": all_lines[-lines:], "total_lines": len(all_lines)}
    except Exception as e:
        logger.error(f"Failed to read logs: {e}")
        return {"logs": [], "error": "Could not read log file"}
