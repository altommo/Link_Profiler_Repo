import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from urllib.parse import urlparse # Added for domain extraction

# ADD these imports at the top
from utils.circuit_breaker import ResilienceManager, CircuitBreakerOpenError
from Link_Profiler.core.models import CrawlResult, CrawlConfig, Link, CrawlJob, SEOMetrics # Corrected imports, added SEOMetrics
# ADD this import
from utils.adaptive_rate_limiter import MLRateLimiter
# ADD this import
from queue_system.smart_crawler_queue import SmartCrawlQueue, Priority
# ADD these imports
from monitoring.crawler_metrics import crawler_metrics
from monitoring.health_monitor import HealthMonitor
# ADD this import for AI Service
from Link_Profiler.services.ai_service import AIService


class WebCrawler:
    def __init__(self, config: CrawlConfig, crawl_queue: SmartCrawlQueue = None, ai_service: AIService = None):
        self.config = config
        # ADD this line in __init__
        self.resilience_manager = ResilienceManager()
        # REPLACE the existing AdaptiveRateLimiter with MLRateLimiter
        self.rate_limiter = MLRateLimiter()
        # ADD this line
        self.crawl_queue = crawl_queue
        # ADD these lines
        self.metrics = crawler_metrics
        self.health_monitor = HealthMonitor(self.metrics)
        # ADD this line for AI Service
        self.ai_service = ai_service
        # ... rest of existing init code
    
    async def __aenter__(self):
        # ADD this line after existing __aenter__ code
        await self.health_monitor.start_monitoring()
        return self # Return self for context manager
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # ADD this line before existing __aexit__ code
        self.health_monitor.stop_monitoring()
        # If you have other cleanup, add it here.
        # For example, if you had an aiohttp session to close:
        # await self.session.close()
        return False # Propagate exceptions if any

    async def crawl_url(self, url: str, last_crawl_result: Optional[CrawlResult] = None) -> CrawlResult:
        """REPLACE the entire crawl_url method with this resilient version"""
        try:
            return await self.resilience_manager.execute_with_resilience(
                self._crawl_url_internal, url, last_crawl_result
            )
        except CircuitBreakerOpenError as e:
            return CrawlResult(
                url=url,
                status_code=503,
                error_message=str(e),
                crawl_time_ms=0,
                crawl_timestamp=datetime.now()
            )
        except Exception as e:
            return CrawlResult(
                url=url,
                status_code=500,
                error_message=f"Resilience manager error: {str(e)}",
                crawl_time_ms=0,
                crawl_timestamp=datetime.now()
            )
    
    async def _crawl_url_internal(self, url: str, last_crawl_result: Optional[CrawlResult] = None) -> CrawlResult:
        """ADD monitoring to existing crawl method"""
        
        # Placeholder for aiohttp client session. In a real app, this would be managed
        # at a higher level (e.g., passed in or a singleton).
        # For now, a simple session per call for demonstration.
        import aiohttp
        
        start_time = datetime.now()
        status_code = 0
        error_message = None
        content = ""
        links_found = []
        
        parsed_url = urlparse(url)
        domain = parsed_url.netloc

        # Track request start
        request_context = await self.metrics.track_request_start(url)

        # REPLACE the existing rate limiter wait with:
        await self.rate_limiter.adaptive_wait(domain) # Wait before the request

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=self.config.timeout_seconds, headers={"User-Agent": self.config.user_agent}) as response:
                    status_code = response.status
                    content = await response.text()
                    
                    # Simulate link extraction (replace with actual parsing)
                    # For now, just add some dummy links
                    
                    links_found.append(Link(target_url=f"http://{domain}/new_page_1"))
                    links_found.append(Link(target_url=f"http://{domain}/new_page_2"))
                    
                    if status_code >= 400:
                        error_message = f"HTTP Error: {status_code}"

        except aiohttp.ClientError as e:
            error_message = f"Network/Client Error: {e}"
            status_code = 0 # Indicate no HTTP status received
        except asyncio.TimeoutError:
            error_message = "Request timed out"
            status_code = 408 # Request Timeout
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            status_code = 500 # Internal Server Error
            
        crawl_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        result = CrawlResult(
            url=url,
            status_code=status_code,
            content=content,
            links_found=links_found,
            error_message=error_message,
            crawl_time_ms=crawl_time_ms,
            crawl_timestamp=datetime.now()
        )
        
        # --- New: AI Content Quality Assessment ---
        if self.ai_service and result.content and result.status_code == 200:
            ai_score, ai_classification = await self.ai_service.assess_content_quality(result.content, result.url)
            if ai_score is not None and ai_classification is not None:
                if result.seo_metrics is None:
                    result.seo_metrics = SEOMetrics(url=result.url)
                result.seo_metrics.ai_content_score = ai_score
                result.seo_metrics.ai_content_classification = ai_classification
                # Recalculate SEO score if AI metrics are added
                result.seo_metrics.calculate_seo_score()
        # --- End New: AI Content Quality Assessment ---

        # Pass the result to the rate limiter after the request
        await self.rate_limiter.adaptive_wait(domain, result) # This second call is for learning from the response

        # Track successful/failed completion
        await self.metrics.track_request_complete(url, result, request_context)

        return result

    async def start_crawl(self, target_url: str, initial_seed_urls: List[str], job_id: str) -> CrawlResult:
        """MODIFY existing start_crawl to use smart queue"""
        
        pages_crawled_count = 0 # Initialize counter
        last_crawl_result = None # Initialize for passing to crawl_url

        # REPLACE the existing URL queue logic with:
        if self.crawl_queue:
            # Use smart queue system
            # Initialize start_time for queue stats if not already present
            if 'start_time' not in self.crawl_queue.stats:
                self.crawl_queue.stats['start_time'] = datetime.now()

            try: # Add error handling for enqueue operation
                for url in initial_seed_urls:
                    await self.crawl_queue.enqueue_url(url, Priority.HIGH, job_id=job_id)
            except Exception as e:
                logger.error(f"Failed to enqueue initial URLs for job {job_id}: {e}")
                return CrawlResult(
                    url=target_url,
                    status_code=500,
                    error_message=f"Failed to enqueue initial URLs: {e}",
                    pages_crawled=0,
                    is_final_summary=True
                )
            
            while True:
                task = await self.crawl_queue.get_next_task()
                # Update queue metrics
                await self.metrics.track_queue_metrics(self.crawl_queue.get_queue_stats())

                if not task or pages_crawled_count >= self.config.max_pages:
                    print(f"Crawl finished for job {job_id}. Total pages crawled: {pages_crawled_count}")
                    break
                
                print(f"Crawling: {task.url} (Job: {job_id}, Priority: {task.priority.name})")
                result = await self.crawl_url(task.url, last_crawl_result) # Pass last_crawl_result if needed by _crawl_url_internal
                
                if result.error_message:
                    print(f"Failed to crawl {task.url}: {result.error_message}")
                    await self.crawl_queue.mark_task_completed(task, success=False)
                else:
                    print(f"Successfully crawled {task.url} (Status: {result.status_code})")
                    await self.crawl_queue.mark_task_completed(task, success=True)
                    pages_crawled_count += 1
                    last_crawl_result = result # Update last_crawl_result for next iteration
                    
                    # Add discovered links to queue
                    for link in result.links_found:
                        # Check if the link's domain is allowed by the config
                        link_domain = urlparse(link.target_url).netloc
                        if self.config.is_domain_allowed(link_domain):
                            await self.crawl_queue.enqueue_url(
                                link.target_url, 
                                Priority.NORMAL, 
                                job_id=job_id
                            )
                        else:
                            print(f"Skipping disallowed domain: {link.target_url}")
            
            # Return a summary CrawlResult for the job
            return CrawlResult(
                url=target_url,
                status_code=200, # Or a more appropriate summary status
                error_message=None,
                pages_crawled=pages_crawled_count,
                is_final_summary=True,
                crawl_duration_seconds=(datetime.now() - self.crawl_queue.stats['start_time']).total_seconds() if 'start_time' in self.crawl_queue.stats else 0.0
            )
        else:
            # Fallback to existing queue logic (or simplified version if no smart queue)
            print("No SmartCrawlQueue provided. Running simplified crawl.")
            # This is a simplified version of your original start_crawl logic
            # if you don't have a SmartCrawlQueue instance.
            # You might want to keep your original complex logic here if it's still needed
            # as a fallback, or simplify it as shown below.
            
            crawled_urls = set()
            urls_to_crawl = initial_seed_urls[:] # Copy the list
            
            while urls_to_crawl and len(crawled_urls) < self.config.max_pages:
                current_url = urls_to_crawl.pop(0)
                if current_url in crawled_urls:
                    continue
                
                print(f"Fallback crawling: {current_url}")
                result = await self.crawl_url(current_url)
                crawled_urls.add(current_url)
                
                if not result.error_message:
                    for link in result.links_found:
                        link_domain = urlparse(link.target_url).netloc
                        if self.config.is_domain_allowed(link_domain) and link.target_url not in crawled_urls:
                            urls_to_crawl.append(link.target_url)
            
            return CrawlResult(
                url=target_url,
                status_code=200,
                pages_crawled=len(crawled_urls),
                is_final_summary=True
            )
