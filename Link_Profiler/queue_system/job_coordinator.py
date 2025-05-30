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

from Link_Profiler.core.models import CrawlJob, CrawlConfig, CrawlStatus

logger = logging.getLogger(__name__)

class JobCoordinator:
    """Manages distributed crawling jobs via Redis queues"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_pool = redis.ConnectionPool.from_url(redis_url)
        self.redis = redis.Redis(connection_pool=self.redis_pool)
        
        # Queue names
        self.job_queue = "crawl_jobs"
        self.result_queue = "crawl_results" 
        self.heartbeat_queue = "crawler_heartbeats"
        
        # Job tracking
        self.active_jobs: Dict[str, CrawlJob] = {}
        self.satellite_crawlers: Dict[str, datetime] = {}
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.redis.close()
    
    async def submit_crawl_job(
        self, 
        target_url: str, 
        initial_seed_urls: List[str],
        config: Optional[CrawlConfig] = None,
        priority: int = 5
    ) -> str:
        """Submit a new crawl job to the queue"""
        
        job_id = str(uuid.uuid4())
        if not config:
            config = CrawlConfig()
        
        # Create job
        job = CrawlJob(
            id=job_id,
            target_url=target_url,
            job_type='backlink_discovery',
            status=CrawlStatus.PENDING,
            priority=priority,
            config=asdict(config)
        )
        
        # Create job message for queue
        job_message = {
            "job_id": job_id,
            "target_url": target_url,
            "initial_seed_urls": initial_seed_urls,
            "config": asdict(config),
            "priority": priority,
            "created_at": datetime.now().isoformat(),
            "max_retries": 3,
            "retry_count": 0
        }
        
        # Store job tracking info
        self.active_jobs[job_id] = job
        
        # Add to Redis queue with priority
        await self.redis.zadd(
            self.job_queue, 
            {json.dumps(job_message): priority}
        )
        
        logger.info(f"Submitted crawl job {job_id} for {target_url}")
        return job_id
    
    async def get_job_status(self, job_id: str) -> Optional[CrawlJob]:
        """Get current status of a crawl job"""
        return self.active_jobs.get(job_id)
    
    async def process_results(self):
        """Process results from satellite crawlers"""
        while True:
            try:
                # Pop result from queue (blocking with timeout)
                result = await self.redis.blpop(self.result_queue, timeout=1)
                
                if result:
                    _, result_data = result
                    result_json = json.loads(result_data)
                    
                    job_id = result_json.get("job_id")
                    if job_id in self.active_jobs:
                        await self._update_job_progress(job_id, result_json)
                
            except Exception as e:
                logger.error(f"Error processing results: {e}")
                await asyncio.sleep(1)
    
    async def _update_job_progress(self, job_id: str, result_data: Dict):
        """Update job progress from satellite results"""
        job = self.active_jobs.get(job_id)
        if not job:
            return
        
        # Update job metrics
        job.urls_crawled += result_data.get("urls_crawled", 0)
        job.links_found += result_data.get("links_found", 0)
        job.progress_percentage = min(99.0, result_data.get("progress_percentage", 0))
        
        # Handle job completion
        if result_data.get("status") == "completed":
            job.status = CrawlStatus.COMPLETED
            job.completed_date = datetime.now()
            job.results = result_data.get("results", {})
            logger.info(f"Job {job_id} completed successfully")
        
        elif result_data.get("status") == "failed":
            job.status = CrawlStatus.FAILED
            job.completed_date = datetime.now()
            job.add_error(
                url=result_data.get("failed_url", ""),
                error_type="CrawlFailure",
                message=result_data.get("error_message", "Unknown error")
            )
            logger.error(f"Job {job_id} failed: {result_data.get('error_message')}")
    
    async def monitor_satellites(self):
        """Monitor satellite crawler health via heartbeats"""
        while True:
            try:
                # Check for heartbeats
                heartbeat = await self.redis.blpop(self.heartbeat_queue, timeout=5)
                
                if heartbeat:
                    _, heartbeat_data = heartbeat
                    hb_json = json.loads(heartbeat_data)
                    
                    crawler_id = hb_json.get("crawler_id")
                    self.satellite_crawlers[crawler_id] = datetime.now()
                
                # Remove stale crawlers (no heartbeat in 60 seconds)
                cutoff = datetime.now() - timedelta(seconds=60)
                stale_crawlers = [
                    cid for cid, last_seen in self.satellite_crawlers.items()
                    if last_seen < cutoff
                ]
                
                for crawler_id in stale_crawlers:
                    del self.satellite_crawlers[crawler_id]
                    logger.warning(f"Satellite crawler {crawler_id} marked as offline")
                
            except Exception as e:
                logger.error(f"Error monitoring satellites: {e}")
                await asyncio.sleep(5)
    
    async def get_queue_stats(self) -> Dict:
        """Get current queue statistics"""
        pending_jobs = await self.redis.zcard(self.job_queue)
        active_crawlers = len(self.satellite_crawlers)
        
        return {
            "pending_jobs": pending_jobs,
            "active_crawlers": active_crawlers,
            "total_jobs": len(self.active_jobs),
            "completed_jobs": len([j for j in self.active_jobs.values() if j.is_completed])
        }

# Usage example
async def main():
    async with JobCoordinator() as coordinator:
        # Start monitoring tasks
        asyncio.create_task(coordinator.process_results())
        asyncio.create_task(coordinator.monitor_satellites())
        
        # Submit a test job
        job_id = await coordinator.submit_crawl_job(
            target_url="https://example.com",
            initial_seed_urls=["https://competitor1.com", "https://competitor2.com"]
        )
        
        print(f"Submitted job: {job_id}")
        
        # Monitor stats
        while True:
            stats = await coordinator.get_queue_stats()
            print(f"Queue stats: {stats}")
            await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
