"""
Lightweight Satellite Crawler - Consumes jobs from Redis queue
"""
import asyncio
import redis.asyncio as redis
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional
import socket
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Link_Profiler.crawlers.web_crawler import WebCrawler
from Link_Profiler.core.models import CrawlConfig, Backlink

logger = logging.getLogger(__name__)

class SatelliteCrawler:
    """Lightweight satellite crawler that processes jobs from Redis queue"""
    
    def __init__(
        self, 
        redis_url: str = "redis://localhost:6379",
        crawler_id: Optional[str] = None,
        region: str = "default"
    ):
        self.redis_pool = redis.ConnectionPool.from_url(redis_url)
        self.redis = redis.Redis(connection_pool=self.redis_pool)
        
        # Unique crawler identification
        self.crawler_id = crawler_id or f"crawler-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
        self.region = region
        
        # Queue names (must match coordinator)
        self.job_queue = "crawl_jobs"
        self.result_queue = "crawl_results"
        self.heartbeat_queue = "crawler_heartbeats"
        
        # Crawler state
        self.is_running = False
        self.current_job_id = None
        self.stats = {
            "jobs_processed": 0,
            "total_urls_crawled": 0,
            "total_links_found": 0,
            "start_time": datetime.now()
        }
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.redis.close()
    
    async def start(self):
        """Start the satellite crawler"""
        self.is_running = True
        logger.info(f"Starting satellite crawler {self.crawler_id} in region {self.region}")
        
        # Start background tasks
        heartbeat_task = asyncio.create_task(self._send_heartbeats())
        worker_task = asyncio.create_task(self._process_jobs())
        
        try:
            # Wait for both tasks
            await asyncio.gather(heartbeat_task, worker_task)
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            self.is_running = False
            await self._cleanup()
    
    async def _process_jobs(self):
        """Main job processing loop"""
        while self.is_running:
            try:
                # Get highest priority job from queue
                job_data = await self.redis.bzpopmax(self.job_queue, timeout=5)
                
                if job_data:
                    _, job_json, priority = job_data
                    job = json.loads(job_json)
                    
                    logger.info(f"Received job {job['job_id']} with priority {priority}")
                    await self._execute_crawl_job(job)
                    
            except Exception as e:
                logger.error(f"Error processing job: {e}")
                await asyncio.sleep(1)
    
    async def _execute_crawl_job(self, job: Dict):
        """Execute a single crawl job"""
        job_id = job["job_id"]
        self.current_job_id = job_id
        
        try:
            # Parse job parameters
            target_url = job["target_url"]
            initial_seed_urls = job["initial_seed_urls"]
            config_dict = job["config"]
            
            # Create crawl config
            config = CrawlConfig.from_dict(config_dict)
            
            # Send job start notification
            await self._send_job_update(job_id, {
                "status": "started",
                "crawler_id": self.crawler_id,
                "start_time": datetime.now().isoformat()
            })
            
            # Execute crawl
            discovered_backlinks = []
            urls_crawled = 0
            
            async with WebCrawler(config) as crawler:
                async for crawl_result in crawler.crawl_for_backlinks(target_url, initial_seed_urls):
                    urls_crawled += 1
                    
                    if crawl_result.links_found:
                        discovered_backlinks.extend(crawl_result.links_found)
                        
                        # Send progress update every 10 URLs
                        if urls_crawled % 10 == 0:
                            progress = min(99.0, (urls_crawled / config.max_pages) * 100)
                            await self._send_job_update(job_id, {
                                "status": "in_progress",
                                "urls_crawled": urls_crawled,
                                "links_found": len(discovered_backlinks),
                                "progress_percentage": progress
                            })
            
            # Send completion result
            await self._send_job_result(job_id, {
                "status": "completed",
                "urls_crawled": urls_crawled,
                "links_found": len(discovered_backlinks),
                "progress_percentage": 100.0,
                "backlinks": [self._serialize_backlink(bl) for bl in discovered_backlinks],
                "completed_at": datetime.now().isoformat(),
                "crawler_id": self.crawler_id
            })
            
            # Update stats
            self.stats["jobs_processed"] += 1
            self.stats["total_urls_crawled"] += urls_crawled
            self.stats["total_links_found"] += len(discovered_backlinks)
            
            logger.info(f"Completed job {job_id}: {urls_crawled} URLs, {len(discovered_backlinks)} backlinks")
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            await self._send_job_result(job_id, {
                "status": "failed",
                "error_message": str(e),
                "failed_at": datetime.now().isoformat(),
                "crawler_id": self.crawler_id
            })
        finally:
            self.current_job_id = None
    
    def _serialize_backlink(self, backlink: Backlink) -> Dict:
        """Convert backlink to JSON-serializable dict"""
        return {
            "source_url": backlink.source_url,
            "target_url": backlink.target_url,
            "anchor_text": backlink.anchor_text,
            "link_type": backlink.link_type.value,
            "context_text": backlink.context_text,
            "discovered_date": backlink.discovered_date.isoformat()
        }
    
    async def _send_job_update(self, job_id: str, update_data: Dict):
        """Send job progress update"""
        update_data.update({
            "job_id": job_id,
            "type": "progress_update",
            "timestamp": datetime.now().isoformat()
        })
        
        await self.redis.lpush(self.result_queue, json.dumps(update_data))
    
    async def _send_job_result(self, job_id: str, result_data: Dict):
        """Send final job result"""
        result_data.update({
            "job_id": job_id,
            "type": "job_result",
            "timestamp": datetime.now().isoformat()
        })
        
        await self.redis.lpush(self.result_queue, json.dumps(result_data))
    
    async def _send_heartbeats(self):
        """Send periodic heartbeats to coordinator"""
        while self.is_running:
            try:
                heartbeat = {
                    "crawler_id": self.crawler_id,
                    "region": self.region,
                    "timestamp": datetime.now().isoformat(),
                    "current_job": self.current_job_id,
                    "stats": self.stats
                }
                
                await self.redis.lpush(self.heartbeat_queue, json.dumps(heartbeat))
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}")
                await asyncio.sleep(5)
    
    async def _cleanup(self):
        """Cleanup resources on shutdown"""
        logger.info(f"Shutting down satellite crawler {self.crawler_id}")
        
        # Send final heartbeat
        final_heartbeat = {
            "crawler_id": self.crawler_id,
            "status": "shutting_down",
            "timestamp": datetime.now().isoformat(),
            "final_stats": self.stats
        }
        
        try:
            await self.redis.lpush(self.heartbeat_queue, json.dumps(final_heartbeat))
        except Exception as e:
            logger.error(f"Error sending final heartbeat: {e}")


# CLI interface for easy deployment
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Satellite Crawler")
    parser.add_argument("--redis-url", default="redis://localhost:6379", help="Redis connection URL")
    parser.add_argument("--crawler-id", help="Unique crawler identifier")
    parser.add_argument("--region", default="default", help="Crawler region/zone")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Start satellite crawler
    async with SatelliteCrawler(
        redis_url=args.redis_url,
        crawler_id=args.crawler_id,
        region=args.region
    ) as crawler:
        await crawler.start()

if __name__ == "__main__":
    asyncio.run(main())
