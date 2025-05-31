"""
Central Job Coordinator - Distributes crawl jobs to satellite crawlers
"""
import asyncio
import redis.asyncio as redis
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import asdict
import logging

from Link_Profiler.core.models import CrawlJob, CrawlConfig, CrawlStatus, serialize_model, CrawlError
from Link_Profiler.database.database import Database # Import Database

logger = logging.getLogger(__name__)

class JobCoordinator:
    """Manages distributed crawling jobs via Redis queues"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", database: Database = None):
        self.redis_pool = redis.ConnectionPool.from_url(redis_url)
        self.redis = redis.Redis(connection_pool=self.redis_pool)
        self.db = database # Store the database instance
        
        # Queue names
        self.job_queue = "crawl_jobs"
        self.result_queue = "crawl_results" 
        self.heartbeat_queue_sorted = "crawler_heartbeats_sorted" # Changed to sorted set
        
        # Job tracking (authoritative state is in DB, this is for quick in-memory lookup of active jobs)
        self.active_jobs_cache: Dict[str, CrawlJob] = {} # Stores CrawlJob objects for quick access
        self.satellite_crawlers: Dict[str, datetime] = {} # Stores crawler_id -> last_seen datetime
        
    async def __aenter__(self):
        # Ensure Redis connection is active
        try:
            await self.redis.ping()
            logger.info("JobCoordinator connected to Redis successfully.")
        except Exception as e:
            logger.error(f"JobCoordinator failed to connect to Redis: {e}", exc_info=True)
            raise # Re-raise to prevent coordinator from starting without Redis
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.redis.close()
        logger.info("JobCoordinator Redis connection closed.")
    
    async def submit_crawl_job(self, job: CrawlJob) -> str:
        """Submit a new crawl job to the queue"""
        
        # Add job to database first (authoritative source)
        self.db.add_crawl_job(job)
        
        # Add to Redis queue with priority
        # Serialize the CrawlJob dataclass to JSON string
        job_message = serialize_model(job)
        
        await self.redis.zadd(
            self.job_queue, 
            {json.dumps(job_message): job.priority}
        )
        
        # Add to in-memory cache for quick lookup by get_job_status
        self.active_jobs_cache[job.id] = job
        
        logger.info(f"Submitted crawl job {job.id} (type: {job.job_type}) for {job.target_url} with priority {job.priority}")
        return job.id
    
    async def get_job_status(self, job_id: str) -> Optional[CrawlJob]:
        """Get current status of a crawl job from the database."""
        # Query the database for the authoritative status
        job = self.db.get_crawl_job(job_id)
        if job:
            # Update cache if found in DB
            self.active_jobs_cache[job_id] = job
        return job
    
    async def process_results(self):
        """Process results from satellite crawlers"""
        logger.info("Starting result processing loop.")
        while True:
            try:
                # Pop result from queue (blocking with timeout)
                result = await self.redis.blpop(self.result_queue, timeout=1)
                
                if result:
                    _, result_data = result
                    result_json = json.loads(result_data)
                    
                    job_id = result_json.get("job_id")
                    # Fetch job from DB to ensure we have the latest authoritative state
                    job = self.db.get_crawl_job(job_id)
                    
                    if job:
                        await self._update_job_progress(job, result_json)
                        # Update in-memory cache after DB update
                        self.active_jobs_cache[job_id] = job
                    else:
                        logger.warning(f"Received result for unknown or deleted job ID: {job_id}. Data: {result_json}")
                
            except Exception as e:
                logger.error(f"Error processing results: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def _update_job_progress(self, job: CrawlJob, result_data: Dict):
        """Update job progress from satellite results and persist to DB"""
        
        # Update job metrics
        job.urls_crawled = result_data.get("urls_crawled", job.urls_crawled)
        job.links_found = result_data.get("links_found", job.links_found)
        job.progress_percentage = min(100.0, result_data.get("progress_percentage", job.progress_percentage))
        
        # Handle job status updates
        status_str = result_data.get("status")
        if status_str:
            job.status = CrawlStatus(status_str) # Convert string back to Enum
        
        if job.status == CrawlStatus.COMPLETED:
            job.completed_date = datetime.now()
            job.results = result_data.get("results", {})
            logger.info(f"Job {job.id} completed successfully")
        
        elif job.status == CrawlStatus.FAILED:
            job.completed_date = datetime.now()
            error_message = result_data.get("error_message", "Unknown error")
            failed_url = result_data.get("failed_url", "N/A")
            error_log_data = result_data.get("error_log", [])
            
            # Reconstruct error_log if provided by satellite
            if error_log_data:
                job.error_log = [CrawlError.from_dict(err_data) for err_data in error_log_data]
                job.errors_count = len(job.error_log)
            else:
                job.add_error(url=failed_url, error_type="SatelliteFailure", message=error_message)
            
            logger.error(f"Job {job.id} failed: {error_message}")
        
        # Persist updated job state to DB
        self.db.update_crawl_job(job)
    
    async def monitor_satellites(self):
        """Monitor satellite crawler health via heartbeats"""
        logger.info("Starting satellite monitoring loop.")
        while True:
            try:
                # Get all heartbeats from the sorted set that are recent (e.g., last 60 seconds)
                cutoff = (datetime.now() - timedelta(seconds=60)).timestamp()
                recent_heartbeats = await self.redis.zrangebyscore(
                    self.heartbeat_queue_sorted, 
                    cutoff, 
                    "+inf", 
                    withscores=True
                )
                
                current_active_crawlers = {}
                for heartbeat_data, timestamp in recent_heartbeats:
                    try:
                        hb = json.loads(heartbeat_data)
                        crawler_id = hb.get("crawler_id")
                        if crawler_id:
                            current_active_crawlers[crawler_id] = datetime.fromtimestamp(timestamp)
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid heartbeat data: {heartbeat_data}")
                        continue
                
                # Update internal state
                self.satellite_crawlers = current_active_crawlers
                
                # Clean up old heartbeats from Redis (optional, but good for memory)
                await self.redis.zremrangebyscore(self.heartbeat_queue_sorted, 0, cutoff)
                
            except Exception as e:
                logger.error(f"Error monitoring satellites: {e}", exc_info=True)
            finally:
                await asyncio.sleep(10) # Check every 10 seconds
    
    async def get_queue_stats(self) -> Dict:
        """Get current queue statistics"""
        pending_jobs = await self.redis.zcard(self.job_queue)
        active_crawlers = len(self.satellite_crawlers)
        
        # Total and completed jobs should ideally come from DB for accuracy
        total_jobs_db = len(self.db.get_all_crawl_jobs()) # This can be slow for many jobs
        completed_jobs_db = len([j for j in self.db.get_all_crawl_jobs() if j.is_completed])
        
        return {
            "pending_jobs": pending_jobs,
            "active_crawlers": active_crawlers,
            "total_jobs": total_jobs_db,
            "completed_jobs": completed_jobs_db
        }

# Usage example (for running coordinator as a standalone process)
async def main():
    logging.basicConfig(level=logging.INFO)
    # Initialize Database for standalone coordinator if needed
    db_instance = Database() 
    async with JobCoordinator(database=db_instance) as coordinator:
        # Start monitoring tasks
        asyncio.create_task(coordinator.process_results())
        asyncio.create_task(coordinator.monitor_satellites())
        
        logger.info("Job Coordinator started. Press Ctrl+C to exit.")
        # Keep the main task alive
        while True:
            await asyncio.sleep(3600) # Sleep for an hour, or until interrupted

if __name__ == "__main__":
    asyncio.run(main())
