"""
Smart Crawl Queue - Intelligent crawl queue with Redis persistence.
File: Link_Profiler/queue_system/smart_crawler_queue.py
"""

import asyncio
import json
import logging
import time # Import time for time.monotonic()
from datetime import datetime, timedelta
from enum import IntEnum
from typing import Dict, Any, Optional, List, Deque
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urlparse # Import urlparse

import redis.asyncio as redis

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.core.models import CrawlJob, CrawlStatus, serialize_model # Assuming CrawlJob and CrawlStatus are defined

logger = logging.getLogger(__name__)

class Priority(IntEnum):
    HIGH = 1
    MEDIUM = 5
    LOW = 10

@dataclass
class CrawlTask:
    """Represents a single crawl task"""
    job_id: str
    url: str
    priority: Priority = Priority.MEDIUM
    depth: int = 0
    retries: int = 0
    last_attempt: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict) # For any extra data needed by crawler

    def to_dict(self) -> Dict:
        return {
            "job_id": self.job_id,
            "url": self.url,
            "priority": self.priority.value,
            "depth": self.depth,
            "retries": self.retries,
            "last_attempt": self.last_attempt.isoformat() if self.last_attempt else None,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlTask':
        return cls(
            job_id=data["job_id"],
            url=data["url"],
            priority=Priority(data.get("priority", Priority.MEDIUM.value)),
            depth=data.get("depth", 0),
            retries=data.get("retries", 0),
            last_attempt=datetime.fromisoformat(data["last_attempt"]) if data.get("last_attempt") else None,
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            metadata=data.get("metadata", {})
        )

class DomainBucket:
    """
    Manages crawling for a specific domain, with Redis-backed queue and rate limiting.
    Note: max_concurrent is handled by the overall job distribution, not per bucket here.
    """
    def __init__(self, domain: str, redis_client: redis.Redis, config_loader: ConfigLoader):
        self.domain = domain
        self.redis = redis_client
        self.config_loader = config_loader
        self.queue_key = f"smart_crawl_queue:domain:{domain}:tasks" # Redis list for tasks
        self.last_crawl_time_key = f"smart_crawl_queue:domain:{domain}:last_crawl_time" # Redis string for last crawl time
        self.crawl_delay = self.config_loader.get("crawler.delay_seconds", 1.0) # Default delay

        self.logger = logging.getLogger(f"{__name__}.DomainBucket.{domain}")
        self.logger.debug(f"DomainBucket for {domain} initialized with delay {self.crawl_delay}s.")

    async def can_crawl_now(self) -> bool:
        """Checks if a crawl can be initiated for this domain based on crawl delay."""
        last_crawl_time_str = await self.redis.get(self.last_crawl_time_key)
        if last_crawl_time_str:
            try:
                last_crawl_time = datetime.fromisoformat(last_crawl_time_str.decode('utf-8'))
                if (datetime.now() - last_crawl_time).total_seconds() < self.crawl_delay:
                    return False
            except ValueError:
                self.logger.warning(f"Invalid last_crawl_time format for {self.domain}: {last_crawl_time_str}. Assuming ready.")
                return True # If format is bad, assume ready to avoid blocking indefinitely
        return True # No last crawl time recorded, so ready to crawl

    async def add_task(self, task: CrawlTask):
        """Adds a task to the domain's Redis queue."""
        # For priority, we could use a sorted set, but for simplicity with lpush/rpop,
        # we'll assume tasks are added in a way that respects priority externally
        # or that the consumer handles priority. For now, simple LIFO.
        await self.redis.lpush(self.queue_key, json.dumps(task.to_dict()))
        self.logger.debug(f"Added task {task.url} to Redis queue for {self.domain}.")

    async def get_next_task(self) -> Optional[CrawlTask]:
        """Retrieves the next task from the domain's Redis queue."""
        task_json = await self.redis.rpop(self.queue_key) # RPOP for LIFO, or BLPOP for blocking
        if task_json:
            task = CrawlTask.from_dict(json.loads(task_json))
            await self.redis.set(self.last_crawl_time_key, datetime.now().isoformat()) # Update last crawl time
            self.logger.debug(f"Issued task {task.url} from Redis queue for {self.domain}.")
            return task
        return None

    async def mark_task_completed(self, task: CrawlTask, success: bool = True):
        """Marks a task as completed (no direct action on Redis queue, just for logging/metrics)."""
        # The task is already removed from the queue by get_next_task.
        # This method is for post-processing, e.g., updating job status in DB.
        self.logger.debug(f"Task {task.url} completed for {self.domain}. Success: {success}")
        # Requeue logic for failed tasks would go here, adding back to the queue with updated retries/priority.

    async def get_queue_size(self) -> int:
        """Returns the current size of the domain's Redis queue."""
        return await self.redis.llen(self.queue_key)

    def next_priority(self) -> int:
        """Returns the priority of the next task (placeholder for Redis-backed priority)."""
        # With simple Redis lists, we don't know the priority without peeking.
        # For a true priority queue, Redis sorted sets would be used.
        return Priority.MEDIUM.value

class SmartCrawlQueue:
    """Intelligent crawl queue with Redis persistence"""
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(SmartCrawlQueue, cls).__new__(cls)
        return cls._instance

    def __init__(self, redis_client: redis.Redis, config_loader: Optional[ConfigLoader] = None):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".SmartCrawlQueue")
        self.redis = redis_client
        self.config_loader = config_loader if config_loader is not None else ConfigLoader() # Ensure config_loader is available

        self.domain_buckets: Dict[str, DomainBucket] = {} # Cache of DomainBucket instances
        self.main_queue_name = self.config_loader.get("queue.smart_crawl_queue.main_queue_name", "smart_crawl_main_queue")
        self.domain_keys_pattern = "smart_crawl_queue:domain:*:tasks" # Pattern to find all domain queues

        self.logger.info("SmartCrawlQueue initialized.")

    async def __aenter__(self):
        """Loads persisted tasks (domain queues) from Redis on startup."""
        self.logger.info("SmartCrawlQueue entering async context. Loading domain buckets from Redis...")
        await self.load_persisted_tasks()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific async teardown needed for this service beyond its dependencies."""
        self.logger.info("SmartCrawlQueue exiting async context.")
        pass

    async def add_task(self, task: CrawlTask):
        """Adds a crawl task to the queue, managing domain-specific buckets."""
        domain = urlparse(task.url).netloc
        if not domain:
            self.logger.warning(f"Invalid URL for task: {task.url}. Cannot determine domain.")
            return

        if domain not in self.domain_buckets:
            self.domain_buckets[domain] = DomainBucket(domain, self.redis, self.config_loader)
            self.logger.info(f"Created new domain bucket instance for {domain}.")
        
        await self.domain_buckets[domain].add_task(task)
        self.logger.debug(f"Added task {task.url} to domain bucket {domain}.")

    async def get_next_task(self) -> Optional[CrawlTask]:
        """
        Retrieves the next available crawl task based on priority and domain limits.
        Prioritizes domains that are ready to crawl and have high-priority tasks.
        """
        # Get all domain keys from Redis that match our pattern
        all_domain_queue_keys = []
        async for key in self.redis.scan_iter(self.domain_keys_pattern):
            all_domain_queue_keys.append(key.decode('utf-8'))

        eligible_domains_info = [] # List of (priority, domain_name, domain_bucket_instance)

        for key in all_domain_queue_keys:
            # Extract domain name from key: "smart_crawl_queue:domain:example.com:tasks"
            domain_name = key.split(':')[3]
            
            if domain_name not in self.domain_buckets:
                # Create a new DomainBucket instance if not already in cache
                self.domain_buckets[domain_name] = DomainBucket(domain_name, self.redis, self.config_loader)
            
            bucket = self.domain_buckets[domain_name]
            
            if await bucket.can_crawl_now() and await bucket.get_queue_size() > 0:
                # For now, use a placeholder priority. A real priority would involve ZRANGE on a sorted set.
                eligible_domains_info.append((bucket.next_priority(), domain_name, bucket))
        
        if not eligible_domains_info:
            # If no domain buckets have tasks or can crawl, check the main queue as a fallback
            task_json = await self.redis.rpop(self.main_queue_name)
            if task_json:
                task = CrawlTask.from_dict(json.loads(task_json))
                self.logger.info(f"Retrieved task {task.url} from main queue (fallback).")
                return task
            return None

        # Sort by priority (lowest value first), then by domain name for stable order
        eligible_domains_info.sort()

        for _, domain_name, bucket in eligible_domains_info:
            task = await bucket.get_next_task()
            if task:
                return task
        
        # Fallback if no task was retrieved despite eligible domains (e.g., race condition)
        return None

    async def mark_task_completed(self, task: CrawlTask, success: bool = True):
        """Marks a task as completed and updates domain bucket status."""
        domain = urlparse(task.url).netloc
        if domain and domain in self.domain_buckets:
            await self.domain_buckets[domain].mark_task_completed(task, success)
            # Requeue logic for failed tasks would go here, adding back to the queue with updated retries/priority.
        else:
            self.logger.warning(f"Completed task {task.url} for unknown or missing domain bucket {domain}.")

    async def load_persisted_tasks(self):
        """
        Loads all domain queue keys from Redis into memory (as DomainBucket instances).
        Actual tasks remain in Redis.
        """
        self.logger.info("Discovering domain buckets from Redis...")
        try:
            # Find all keys matching the domain queue pattern
            async for key in self.redis.scan_iter(self.domain_keys_pattern):
                domain_name = key.decode('utf-8').split(':')[3]
                if domain_name not in self.domain_buckets:
                    self.domain_buckets[domain_name] = DomainBucket(domain_name, self.redis, self.config_loader)
                    self.logger.debug(f"Discovered and instantiated DomainBucket for {domain_name}.")
            self.logger.info(f"Discovered {len(self.domain_buckets)} domain buckets.")
        except Exception as e:
            self.logger.error(f"Failed to discover domain buckets from Redis: {e}", exc_info=True)

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Returns statistics about the Redis-backed queue."""
        main_queue_size = await self.redis.llen(self.main_queue_name)
        
        domain_bucket_stats = {}
        total_tasks_in_buckets = 0
        
        # Iterate through instantiated domain buckets (which reflect Redis keys)
        for domain, bucket in self.domain_buckets.items():
            queue_size = await bucket.get_queue_size()
            total_tasks_in_buckets += queue_size
            domain_bucket_stats[domain] = {
                "queue_size": queue_size,
                "can_crawl_now": await bucket.can_crawl_now()
            }
        
        return {
            "main_queue_size": main_queue_size,
            "domain_bucket_stats": domain_bucket_stats,
            "total_tasks_in_domain_buckets": total_tasks_in_buckets,
            "total_tasks_overall": main_queue_size + total_tasks_in_buckets,
            "unique_domains_in_queue": len(self.domain_buckets)
        }

    async def get_total_queue_depth(self) -> int:
        """Returns the total number of tasks across all queues."""
        stats = await self.get_queue_stats()
        return stats.get("total_tasks_overall", 0)

    async def get_active_worker_count(self) -> int:
        """Placeholder for getting active worker count (from JobCoordinator/heartbeats)."""
        # This information is typically managed by JobCoordinator's heartbeat monitoring.
        # For now, return a dummy value or integrate with JobCoordinator's stats.
        return 0 # Placeholder

    async def get_registered_worker_count(self) -> int:
        """Placeholder for getting total registered worker count."""
        return 0 # Placeholder
