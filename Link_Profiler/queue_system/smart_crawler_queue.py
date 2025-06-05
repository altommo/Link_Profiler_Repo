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
    """Manages crawling for a specific domain"""
    def __init__(self, domain: str, max_concurrent: int, crawl_delay: float):
        self.domain = domain
        self.max_concurrent = max_concurrent
        self.crawl_delay = crawl_delay
        self.queue: Deque[CrawlTask] = deque()
        self.active_crawls: int = 0
        self.last_crawl_time: float = 0.0 # Unix timestamp
        self.logger = logging.getLogger(f"{__name__}.DomainBucket.{domain}")

    def can_crawl_now(self) -> bool:
        """Checks if a crawl can be initiated for this domain."""
        return (self.active_crawls < self.max_concurrent and
                (time.monotonic() - self.last_crawl_time) >= self.crawl_delay)

    def add_task(self, task: CrawlTask):
        """Adds a task to the domain's queue, maintaining priority."""
        # Simple insertion sort for priority (higher priority = lower value)
        # For small queues, this is fine. For large, consider heapq.
        inserted = False
        for i, existing_task in enumerate(self.queue):
            if task.priority.value < existing_task.priority.value:
                self.queue.insert(i, task)
                inserted = True
                break
        if not inserted:
            self.queue.append(task)
        self.logger.debug(f"Added task {task.url} to {self.domain}. Queue size: {len(self.queue)}")

    def get_next_task(self) -> Optional[CrawlTask]:
        """Retrieves the next task if available and conditions allow."""
        if self.queue and self.can_crawl_now():
            task = self.queue.popleft()
            self.active_crawls += 1
            self.last_crawl_time = time.monotonic()
            self.logger.debug(f"Issued task {task.url} for {self.domain}. Active crawls: {self.active_crawls}")
            return task
        return None

    def mark_task_completed(self, task: CrawlTask, success: bool = True):
        """Marks a task as completed, decrementing active crawls."""
        if self.active_crawls > 0:
            self.active_crawls -= 1
        self.logger.debug(f"Task {task.url} completed for {self.domain}. Active crawls: {self.active_crawls}")

    def next_priority(self) -> int:
        """Returns the priority of the next task in the queue, or a default if empty."""
        return self.queue[0].priority.value if self.queue else Priority.MEDIUM.value

class SmartCrawlQueue:
    """Intelligent crawl queue with Redis persistence"""
    def __init__(self, redis_client: redis.Redis):
        self.logger = logging.getLogger(__name__ + ".SmartCrawlQueue")
        self.redis = redis_client
        self.domain_buckets: Dict[str, DomainBucket] = {}
        self.max_queue_size = config_loader.get("queue_system.max_queue_size", 100000)
        self.domain_max_concurrent = config_loader.get("queue_system.domain_max_concurrent", 2)
        self.default_crawl_delay = config_loader.get("crawler.delay_seconds", 1.0) # Fallback to crawler delay
        self.persisted_tasks_key = "smart_crawl_queue:persisted_tasks" # Redis key for tasks

        self.logger.info("SmartCrawlQueue initialized.")

    async def add_task(self, task: CrawlTask):
        """Adds a crawl task to the queue, managing domain-specific buckets."""
        if len(self.domain_buckets) >= self.max_queue_size: # Simple check, could be more granular
            self.logger.warning(f"Queue is full ({self.max_queue_size} domains). Task {task.url} rejected.")
            return

        domain = self._extract_domain(task.url)
        if not domain:
            self.logger.error(f"Could not extract domain from URL: {task.url}. Task rejected.")
            return

        if domain not in self.domain_buckets:
            # Fetch domain-specific crawl delay (e.g., from robots.txt or adaptive rate limiter)
            # For now, use default. This is where integration with RobotsParser/RateLimiter would happen.
            crawl_delay = self.default_crawl_delay # Use default_crawl_delay
            self.domain_buckets[domain] = DomainBucket(domain, self.domain_max_concurrent, crawl_delay)
            self.logger.info(f"Created new domain bucket for {domain} with delay {crawl_delay}s.")

        self.domain_buckets[domain].add_task(task)
        await self._persist_task(task) # Persist to Redis

    async def get_next_task(self) -> Optional[CrawlTask]:
        """
        Retrieves the next available crawl task based on priority and domain limits.
        Prioritizes domains that are ready to crawl and have high-priority tasks.
        """
        eligible_domains = []
        for domain, bucket in self.domain_buckets.items():
            if bucket.can_crawl_now() and bucket.queue:
                eligible_domains.append((bucket.next_priority(), domain))
        
        if not eligible_domains:
            return None

        # Sort by priority (lowest value first), then by domain name for stable order
        eligible_domains.sort()

        for _, domain in eligible_domains:
            task = self.domain_buckets[domain].get_next_task()
            if task:
                return task
        return None

    async def mark_task_completed(self, task: CrawlTask, success: bool = True):
        """Marks a task as completed and updates domain bucket status."""
        domain = self._extract_domain(task.url)
        if domain and domain in self.domain_buckets:
            self.domain_buckets[domain].mark_task_completed(task, success)
            await self._remove_persisted_task(task) # Remove from Redis persistence
            if not success:
                await self._requeue_failed_task(task)
        else:
            self.logger.warning(f"Completed task {task.url} for unknown or missing domain bucket {domain}.")

    async def _requeue_failed_task(self, task: CrawlTask):
        """Requeues a failed task with increased retry count and lower priority."""
        if task.retries < config_loader.get("crawler.max_retries", 3):
            task.retries += 1
            task.priority = Priority(min(Priority.LOW.value, task.priority.value + 1)) # Lower priority
            task.last_attempt = datetime.now()
            self.logger.warning(f"Requeuing failed task {task.url}. Retries: {task.retries}, New Priority: {task.priority.name}")
            await self.add_task(task) # Re-add to queue
        else:
            self.logger.error(f"Task {task.url} failed after {task.retries} retries. Moving to dead letter queue (not implemented).")
            # In a real system, push to a dead letter queue or notify.

    def _extract_domain(self, url: str) -> Optional[str]:
        """Helper to extract domain from a URL."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except Exception:
            return None

    def _calculate_next_crawl_time(self, domain: str) -> float:
        """
        Calculates the appropriate crawl delay for a domain.
        This is where robots.txt crawl-delay or adaptive rate limiting logic would go.
        For now, returns a default.
        """
        # In a real scenario, this would query a RobotsParser or AdaptiveRateLimiter
        # For example: self.robots_parser.get_crawl_delay(domain)
        # Or: self.adaptive_rate_limiter.get_delay(domain)
        return self.default_crawl_delay

    async def _persist_task(self, task: CrawlTask):
        """Persists a task to Redis for recovery after restart."""
        try:
            await self.redis.sadd(self.persisted_tasks_key, json.dumps(task.to_dict()))
            self.logger.debug(f"Persisted task {task.url}.")
        except Exception as e:
            self.logger.error(f"Failed to persist task {task.url}: {e}")

    async def _remove_persisted_task(self, task: CrawlTask):
        """Removes a task from Redis persistence."""
        try:
            await self.redis.srem(self.persisted_tasks_key, json.dumps(task.to_dict()))
            self.logger.debug(f"Removed persisted task {task.url}.")
        except Exception as e:
            self.logger.error(f"Failed to remove persisted task {task.url}: {e}")

    async def load_persisted_tasks(self):
        """Loads all persisted tasks from Redis into memory on startup."""
        self.logger.info("Loading persisted tasks from Redis...")
        try:
            tasks_json = await self.redis.smembers(self.persisted_tasks_key)
            for task_json in tasks_json:
                try:
                    task_data = json.loads(task_json)
                    task = CrawlTask.from_dict(task_data)
                    # Re-add to queue, but don't persist again
                    domain = self._extract_domain(task.url)
                    if domain:
                        if domain not in self.domain_buckets:
                            crawl_delay = self.default_crawl_delay # Use default_crawl_delay
                            self.domain_buckets[domain] = DomainBucket(domain, self.domain_max_concurrent, crawl_delay)
                        self.domain_buckets[domain].add_task(task)
                        self.logger.debug(f"Loaded and re-added persisted task {task.url}.")
                    else:
                        self.logger.warning(f"Could not load persisted task (invalid URL): {task_json}")
                        await self.redis.srem(self.persisted_tasks_key, task_json) # Remove invalid
                except Exception as e:
                    self.logger.error(f"Error loading single persisted task: {task_json} - {e}")
                    await self.redis.srem(self.persisted_tasks_key, task_json) # Remove problematic entry
            self.logger.info(f"Loaded {len(tasks_json)} persisted tasks.")
        except Exception as e:
            self.logger.error(f"Failed to load persisted tasks from Redis: {e}", exc_info=True)

    def get_queue_stats(self) -> Dict[str, Any]:
        """Returns statistics about the in-memory queue."""
        total_tasks = sum(len(bucket.queue) for bucket in self.domain_buckets.values())
        active_crawls = sum(bucket.active_crawls for bucket in self.domain_buckets.values())
        unique_domains = len(self.domain_buckets)
        
        return {
            "total_tasks_in_queue": total_tasks,
            "active_crawls": active_crawls,
            "unique_domains_in_queue": unique_domains,
            "domain_buckets_info": {
                domain: {
                    "queue_size": len(bucket.queue),
                    "active_crawls": bucket.active_crawls,
                    "last_crawl_time": bucket.last_crawl_time,
                    "can_crawl_now": bucket.can_crawl_now()
                } for domain, bucket in self.domain_buckets.items()
            }
        }
