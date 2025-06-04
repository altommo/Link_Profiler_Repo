"""
Smart Crawl Queue System with Priority and Domain Management
Handles unlimited scale crawling with intelligent scheduling
"""

import asyncio
import heapq
import time
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from urllib.parse import urlparse
from enum import IntEnum
import redis.asyncio as redis
import json
import logging

logger = logging.getLogger(__name__)

class Priority(IntEnum):
    """Priority levels for crawl tasks"""
    CRITICAL = 1    # Immediate crawling needed
    HIGH = 2        # Important URLs
    NORMAL = 3      # Standard crawling
    LOW = 4         # Background crawling
    BULK = 5        # Mass crawling operations

@dataclass
class CrawlTask:
    """Represents a single crawl task"""
    url: str
    priority: Priority = Priority.NORMAL
    scheduled_time: float = field(default_factory=time.time)
    retry_count: int = 0
    max_retries: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    job_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    
    def __lt__(self, other):
        """For priority queue sorting"""
        # First by priority, then by scheduled time
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.scheduled_time < other.scheduled_time
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary"""
        return {
            'url': self.url, # Corrected from 'self' to 'self.url'
            'priority': self.priority.value,
            'scheduled_time': self.scheduled_time,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'metadata': self.metadata,
            'job_id': self.job_id,
            'created_at': self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlTask':
        """Deserialize from dictionary"""
        return cls(
            url=data['url'],
            priority=Priority(data['priority']),
            scheduled_time=data['scheduled_time'],
            retry_count=data['retry_count'],
            max_retries=data['max_retries'],
            metadata=data['metadata'],
            job_id=data.get('job_id'),
            created_at=data['created_at']
        )

class DomainBucket:
    """Manages crawling for a specific domain"""
    
    def __init__(self, domain: str, min_delay: float = 1.0):
        self.domain = domain
        self.min_delay = min_delay
        self.last_crawl_time = 0.0
        self.queue: List[CrawlTask] = []
        self.active_count = 0
        self.max_concurrent = 2  # Max concurrent requests per domain
        
    def can_crawl_now(self) -> bool:
        """Check if this domain can be crawled now"""
        now = time.time()
        time_since_last = now - self.last_crawl_time
        
        return (time_since_last >= self.min_delay and 
                self.active_count < self.max_concurrent and 
                len(self.queue) > 0)
    
    def add_task(self, task: CrawlTask):
        """Add task to domain queue"""
        heapq.heappush(self.queue, task)
    
    def get_next_task(self) -> Optional[CrawlTask]:
        """Get next task if available"""
        if self.can_crawl_now():
            task = heapq.heappop(self.queue)
            self.last_crawl_time = time.time()
            self.active_count += 1
            return task
        return None
    
    def mark_task_completed(self):
        """Mark a task as completed"""
        self.active_count = max(0, self.active_count - 1)
    
    def next_priority(self) -> int:
        """Get priority of next task"""
        return self.queue[0].priority.value if self.queue else Priority.BULK.value

class SmartCrawlQueue:
    """Intelligent crawl queue with Redis persistence"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.domain_buckets: Dict[str, DomainBucket] = {}
        self.processed_urls: Set[str] = set()
        self.stats = {
            'total_enqueued': 0,
            'total_processed': 0,
            'total_failed': 0,
            'queue_size': 0,
            'start_time': time.time() # Added start_time for queue's operational duration
        }
        
    async def enqueue_url(self, url: str, priority: Priority = Priority.NORMAL, 
                         metadata: Dict = None, job_id: str = None) -> bool:
        """Add URL to crawl queue"""
        # Skip if already processed
        if url in self.processed_urls:
            logger.debug(f"URL already processed: {url}")
            return False
        
        domain = urlparse(url).netloc
        if not domain:
            logger.warning(f"Invalid URL: {url}")
            return False
        
        # Create domain bucket if needed
        if domain not in self.domain_buckets:
            self.domain_buckets[domain] = DomainBucket(domain)
        
        # Calculate next crawl time based on domain rate limiting
        next_crawl_time = self._calculate_next_crawl_time(domain)
        
        task = CrawlTask(
            url=url,
            priority=priority,
            scheduled_time=next_crawl_time,
            metadata=metadata or {},
            job_id=job_id
        )
        
        # Add to domain bucket
        self.domain_buckets[domain].add_task(task)
        
        # Persist to Redis
        await self._persist_task(task)
        
        self.stats['total_enqueued'] += 1
        self.stats['queue_size'] += 1
        
        logger.debug(f"Enqueued {url} for domain {domain} with priority {priority}")
        return True
    
    async def get_next_task(self) -> Optional[CrawlTask]:
        """Get next available task respecting domain limits"""
        # Find domains that can be crawled now
        available_domains = [
            domain for domain, bucket in self.domain_buckets.items()
            if bucket.can_crawl_now()
        ]
        
        if not available_domains:
            return None
        
        # Select domain with highest priority task
        selected_domain = min(available_domains, 
                            key=lambda d: self.domain_buckets[d].next_priority())
        
        task = self.domain_buckets[selected_domain].get_next_task()
        if task:
            self.processed_urls.add(task.url)
            await self._remove_persisted_task(task)
            self.stats['queue_size'] -= 1
            
        return task
    
    async def mark_task_completed(self, task: CrawlTask, success: bool = True):
        """Mark task as completed"""
        domain = urlparse(task.url).netloc
        if domain in self.domain_buckets:
            self.domain_buckets[domain].mark_task_completed()
        
        if success:
            self.stats['total_processed'] += 1
        else:
            self.stats['total_failed'] += 1
            # Re-queue if retries available
            if task.retry_count < task.max_retries:
                await self._requeue_failed_task(task)
    
    async def _requeue_failed_task(self, task: CrawlTask):
        """Re-queue failed task with backoff"""
        task.retry_count += 1
        # Exponential backoff for retry delay
        delay = min(300, 30 * (2 ** task.retry_count))  # Max 5 minutes
        task.scheduled_time = time.time() + delay
        task.priority = Priority(min(task.priority.value + 1, Priority.BULK.value))
        
        domain = urlparse(task.url).netloc
        if domain in self.domain_buckets:
            self.domain_buckets[domain].add_task(task)
            await self._persist_task(task)
            self.stats['queue_size'] += 1
    
    def _calculate_next_crawl_time(self, domain: str) -> float:
        """Calculate when domain can next be crawled"""
        if domain not in self.domain_buckets:
            return time.time()
        
        bucket = self.domain_buckets[domain]
        return max(time.time(), bucket.last_crawl_time + bucket.min_delay)
    
    async def _persist_task(self, task: CrawlTask):
        """Persist task to Redis"""
        key = f"crawl_queue:{task.job_id or 'default'}:{urlparse(task.url).netloc}"
        await self.redis.lpush(key, json.dumps(task.to_dict()))
    
    async def _remove_persisted_task(self, task: CrawlTask):
        """Remove task from Redis"""
        key = f"crawl_queue:{task.job_id or 'default'}:{urlparse(task.url).netloc}"
        await self.redis.lrem(key, 1, json.dumps(task.to_dict()))
    
    async def load_persisted_tasks(self):
        """Load tasks from Redis on startup"""
        pattern = "crawl_queue:*"
        async for key in self.redis.scan_iter(match=pattern):
            tasks_data = await self.redis.lrange(key, 0, -1)
            for task_data in tasks_data:
                try:
                    task = CrawlTask.from_dict(json.loads(task_data))
                    domain = urlparse(task.url).netloc
                    if domain not in self.domain_buckets:
                        self.domain_buckets[domain] = DomainBucket(domain)
                    self.domain_buckets[domain].add_task(task)
                    self.stats['queue_size'] += 1
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"Failed to load persisted task: {e}")
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics"""
        domain_stats = {}
        for domain, bucket in self.domain_buckets.items():
            domain_stats[domain] = {
                'queue_size': len(bucket.queue),
                'active_tasks': bucket.active_count,
                'last_crawl': bucket.last_crawl_time,
                'can_crawl_now': bucket.can_crawl_now()
            }
        
        return {
            **self.stats,
            'domains': domain_stats,
            'total_domains': len(self.domain_buckets)
        }
    
    async def bulk_enqueue(self, urls: List[str], priority: Priority = Priority.BULK, 
                          job_id: str = None) -> int:
        """Efficiently enqueue many URLs"""
        enqueued_count = 0
        for url in urls:
            if await self.enqueue_url(url, priority, job_id=job_id):
                enqueued_count += 1
        
        logger.info(f"Bulk enqueued {enqueued_count}/{len(urls)} URLs")
        return enqueued_count
