"""
Enhanced API main file with queue endpoints integrated
"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Import the existing main app
try:
    from .main import app as base_app
except ImportError:
    # If running directly, try different import
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent))
    from main import app as base_app

# Import queue endpoints
from .queue_endpoints import (
    set_coordinator_dependencies,
    submit_crawl_to_queue,
    QueueCrawlRequest,
    get_coordinator,
    add_queue_endpoints
)

logger = logging.getLogger(__name__)

# Add the queue endpoints to the base app
add_queue_endpoints(base_app)

# Export the enhanced app
app = base_app

# Add additional queue-specific routes if needed
@app.get("/queue/health")
async def queue_health():
    """Check if queue system is healthy"""
    try:
        coordinator = await get_coordinator()
        return {"status": "healthy", "message": "Queue system operational"}
    except Exception as e:
        logger.error(f"Queue health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
