#!/usr/bin/env python3
"""
Quick fix script for missing YSPANEL components
Creates the missing files identified in system verification
"""

import os
from pathlib import Path

def create_missing_api_file(base_path):
    """Create the missing main_with_queue.py file"""
    api_path = Path(base_path) / "Link_Profiler" / "api"
    main_with_queue_content = '''"""
Enhanced API main file with queue endpoints integrated
"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import the existing main app
from .main import app as base_app

# Import queue endpoints
from .queue_endpoints import (
    set_coordinator_dependencies,
    submit_crawl_to_queue,
    QueueCrawlRequest,
    get_coordinator
)

logger = logging.getLogger(__name__)

# Add queue endpoints to the existing app
def add_queue_endpoints(app: FastAPI):
    """Add queue-related endpoints to the FastAPI app"""
    
    @app.post("/queue/submit_crawl")
    async def submit_crawl(request: QueueCrawlRequest):
        """Submit a crawl job to the queue"""
        try:
            result = await submit_crawl_to_queue(request)
            return result
        except Exception as e:
            logger.error(f"Error submitting crawl job: {e}")
            return {"error": str(e)}
    
    @app.get("/queue/stats")
    async def get_queue_stats():
        """Get queue statistics"""
        try:
            coordinator = await get_coordinator()
            stats = await coordinator.get_queue_stats()
            return stats
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            return {"error": str(e)}
    
    @app.get("/queue/job_status/{job_id}")
    async def get_job_status(job_id: str):
        """Get status of a specific job"""
        try:
            coordinator = await get_coordinator()
            status = await coordinator.get_job_status(job_id)
            return {"job_id": job_id, "status": status}
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return {"error": str(e)}

# Add the queue endpoints to the base app
add_queue_endpoints(base_app)

# Export the enhanced app
app = base_app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''
    
    with open(api_path / "main_with_queue.py", "w") as f:
        f.write(main_with_queue_content)
    print(f"✅ Created: {api_path / 'main_with_queue.py'}")

def create_missing_requirements_file(base_path):
    """Create the missing requirements-satellite.txt file"""
    requirements_content = '''# Minimal requirements for satellite crawlers
redis>=4.0.0
aiohttp>=3.8.0
asyncio-mqtt>=0.11.0
pydantic>=1.8.0
python-dotenv>=0.19.0
requests>=2.25.0

# Optional but recommended
playwright>=1.20.0
beautifulsoup4>=4.10.0
lxml>=4.6.0
'''
    
    with open(Path(base_path) / "requirements-satellite.txt", "w") as f:
        f.write(requirements_content)
    print(f"✅ Created: {Path(base_path) / 'requirements-satellite.txt'}")

def fix_queue_endpoints_function(base_path):
    """Add the missing add_queue_endpoints function"""
    queue_endpoints_path = Path(base_path) / "Link_Profiler" / "api" / "queue_endpoints.py"
    
    # Read existing content
    with open(queue_endpoints_path, "r") as f:
        content = f.read()
    
    # Add the missing function at the end
    additional_content = '''

# --- Function to add queue endpoints to FastAPI app ---
def add_queue_endpoints(app):
    """
    Add queue-related endpoints to a FastAPI application.
    This function should be called during app initialization.
    """
    from fastapi import HTTPException
    
    @app.post("/queue/submit_crawl")
    async def submit_crawl_endpoint(request: QueueCrawlRequest):
        """Submit a crawl job to the queue"""
        try:
            result = await submit_crawl_to_queue(request)
            return result
        except Exception as e:
            logger.error(f"Error submitting crawl job: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/queue/stats")
    async def get_queue_stats():
        """Get queue statistics"""
        try:
            coordinator = await get_coordinator()
            stats = await coordinator.get_queue_stats()
            return stats
        except Exception as e:
            logger.error(f"Error getting queue stats: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/queue/job_status/{job_id}")
    async def get_job_status(job_id: str):
        """Get status of a specific job"""
        try:
            coordinator = await get_coordinator()
            status = await coordinator.get_job_status(job_id)
            return {"job_id": job_id, "status": status}
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    logger.info("Queue endpoints added to FastAPI app")
'''
    
    # Write updated content
    with open(queue_endpoints_path, "w") as f:
        f.write(content + additional_content)
    print(f"✅ Updated: {queue_endpoints_path}")

def main():
    print("🔧 Fixing missing YSPANEL components...")
    
    # Use the actual path from your system
    base_path = "C:/Users/hp/Documents/Projects/Domain_Research/Link_Profiler_Repo"
    
    if not Path(base_path).exists():
        print(f"❌ Base path not found: {base_path}")
        print("Please update the base_path variable in this script to match your actual path")
        return
    
    try:
        create_missing_api_file(base_path)
        create_missing_requirements_file(base_path)
        fix_queue_endpoints_function(base_path)
        
        print("\n🎉 All fixes applied successfully!")
        print("\nNext steps:")
        print("1. Copy these files to your VPS at /opt/Link_Profiler_Repo/")
        print("2. Run the verification script again")
        print("3. Test your API endpoints")
        
    except Exception as e:
        print(f"❌ Error during fix: {e}")

if __name__ == "__main__":
    main()
