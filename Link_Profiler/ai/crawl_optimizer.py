"""
ML-Driven Crawl Optimizer - Provides intelligent crawling decisions.
This module integrates with the AI service and metrics to:
- Predict optimal crawling patterns
- Score content priority
- Suggest optimal crawling paths
- Optimize resource allocation
"""

import logging
import asyncio
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import random
from urllib.parse import urlparse # Import urlparse
from Link_Profiler.config.config_loader import config_loader # Import config_loader

from Link_Profiler.services.ai_service import AIService
from Link_Profiler.monitoring.crawler_metrics import CrawlerMetrics
from Link_Profiler.core.models import CrawlResult, CrawlConfig, SEOMetrics # Assuming these models are available
from Link_Profiler.utils.adaptive_rate_limiter import MLRateLimiter # Re-use MLRateLimiter concepts

logger = logging.getLogger(__name__)

class CrawlOptimizer:
    """
    Applies machine learning and heuristic rules to optimize crawling behavior.
    """
    def __init__(self, ai_service: AIService, metrics: CrawlerMetrics, rate_limiter: MLRateLimiter):
        self.ai_service = ai_service
        self.metrics = metrics
        self.rate_limiter = rate_limiter
        self.logger = logging.getLogger(__name__ + ".CrawlOptimizer")

        # Configuration for optimization (can be loaded from config_loader)
        self.content_priority_threshold = config_loader.get("ai.content_priority_threshold", 0.7) # Minimum AI content score for high priority
        self.anomaly_penalty_factor = config_loader.get("ai.anomaly_penalty_factor", 2.0) # Multiply delay by this if anomaly detected
        self.max_crawl_depth_adjustment = config_loader.get("crawler.max_crawl_depth_adjustment", 2) # Max additional depth for high-value content

    async def prioritize_urls(self, urls: List[str], current_depth: int, crawl_config: CrawlConfig) -> List[Tuple[str, int]]:
        """
        Prioritizes a list of URLs based on predicted value, content quality, and crawl history.
        Returns a list of (url, priority_score) tuples, higher score means higher priority.
        """
        prioritized_urls: List[Tuple[str, int]] = []
        
        for url in urls:
            priority_score = 100 # Base priority
            
            # 1. Depth-based decay
            priority_score -= (current_depth * 10) # Deeper URLs get lower priority

            # 2. Content Quality Prediction (if AI is enabled)
            if self.ai_service.enabled:
                # This would ideally be a lightweight model or a cached prediction
                # For now, we'll simulate or use a simplified AI call
                try:
                    # Simulate content quality score for unseen URLs
                    # In a real scenario, this might involve a quick AI model inference
                    # based on URL patterns, historical data, or a very small content snippet.
                    simulated_quality_score = random.uniform(0.4, 0.9) # Simulate a score
                    
                    if simulated_quality_score >= self.content_priority_threshold:
                        priority_score += 50 # Boost for high-quality content
                        self.logger.debug(f"Boosting priority for {url} due to predicted high content quality.")
                        
                        # Potentially increase max depth for high-value content
                        if current_depth < crawl_config.max_depth + self.max_crawl_depth_adjustment:
                            self.logger.debug(f"Allowing deeper crawl for high-value content: {url}")
                            # This would need to be handled by the queue/scheduler, not just priority
                            # For now, it's a conceptual flag.
                except Exception as e:
                    self.logger.warning(f"AI content quality prediction failed for {url}: {e}")

            # 3. Historical Performance (from rate limiter/metrics)
            domain = urlparse(url).netloc
            domain_profile = self.rate_limiter.get_domain_profile(domain)
            
            if domain_profile.error_rate > 0.1: # Penalize domains with high error rates
                priority_score -= (domain_profile.error_rate * 100)
                self.logger.debug(f"Penalizing {url} due to high error rate on its domain.")
            
            if domain_profile.avg_response_time > 5.0: # Penalize slow domains
                priority_score -= (domain_profile.avg_response_time * 5)
                self.logger.debug(f"Penalizing {url} due to slow response time on its domain.")

            # 4. Anomaly Detection (if anomaly_detector is integrated)
            # This would typically happen *after* a crawl, but could influence future crawls
            # if a domain is flagged for anomalies.
            # For now, we'll assume anomalies are detected and stored in metrics.
            # If a domain has recent anomalies, reduce its priority.
            # This would require a more sophisticated anomaly tracking in CrawlerMetrics.
            # if domain_profile.has_recent_anomalies: # Placeholder
            #     priority_score -= 30
            #     self.logger.warning(f"Penalizing {url} due to recent anomalies on its domain.")

            prioritized_urls.append((url, max(0, priority_score))) # Ensure score is not negative
        
        # Sort by priority score (descending)
        prioritized_urls.sort(key=lambda x: x[1], reverse=True)
        
        return prioritized_urls

    async def adjust_crawl_config_dynamically(self, crawl_config: CrawlConfig, recent_crawl_results: List[CrawlResult]) -> CrawlConfig:
        """
        Dynamically adjusts crawl configuration based on recent performance and content analysis.
        This is a conceptual method; actual implementation would modify the CrawlConfig object.
        """
        self.logger.info("Dynamically adjusting crawl configuration...")
        
        # Analyze recent crawl results
        total_crawled = len(recent_crawl_results)
        if total_crawled == 0:
            self.logger.info("No recent crawl results to analyze for dynamic config adjustment.")
            return crawl_config

        successful_crawls = [r for r in recent_crawl_results if 200 <= r.status_code < 400]
        failed_crawls = [r for r in recent_crawl_results if r.status_code >= 400 or r.error_message]
        
        success_rate = len(successful_crawls) / total_crawled
        avg_crawl_time = sum(r.crawl_time_ms for r in recent_crawl_results) / total_crawled / 1000.0 if total_crawled > 0 else 0

        # Adjust delay based on overall success rate and response times
        if success_rate < 0.8 or avg_crawl_time > 5.0:
            # If performance is poor, increase delay to be more polite
            crawl_config.delay_seconds = min(crawl_config.delay_seconds * 1.2, self.rate_limiter.global_config['max_delay'])
            self.logger.warning(f"Adjusting delay to {crawl_config.delay_seconds:.2f}s due to poor performance (success: {success_rate:.1%}, avg_time: {avg_crawl_time:.2f}s).")
        elif success_rate > 0.95 and avg_crawl_time < 2.0:
            # If performance is excellent, decrease delay to be more aggressive
            crawl_config.delay_seconds = max(crawl_config.delay_seconds * 0.9, self.rate_limiter.global_config['min_delay'])
            self.logger.info(f"Adjusting delay to {crawl_config.delay_seconds:.2f}s due to excellent performance.")

        # Adjust render_javascript based on content validation issues
        js_required_issues = [r for r in recent_crawl_results if "Page requires JavaScript" in r.validation_issues]
        if len(js_required_issues) / total_crawled > 0.3 and not crawl_config.render_javascript:
            self.logger.warning("Many pages require JavaScript. Suggesting enabling render_javascript.")
            # crawl_config.render_javascript = True # This would be a strong recommendation, not auto-change

        # Adjust proxy usage based on bot detection issues
        bot_detection_issues = [r for r in recent_crawl_results if any("Bot detection indicator" in issue for issue in r.validation_issues)]
        if len(bot_detection_issues) / total_crawled > 0.1 and not crawl_config.use_proxies:
            self.logger.warning("Many pages triggered bot detection. Suggesting enabling proxies.")
            # crawl_config.use_proxies = True # Strong recommendation

        self.logger.info(f"Dynamic config adjustment complete. New delay: {crawl_config.delay_seconds:.2f}s.")
        return crawl_config

    async def optimize_resource_allocation(self, active_jobs: List[Any], available_resources: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimizes resource allocation (e.g., concurrent workers, memory limits) based on system load
        and job priorities.
        This is a conceptual method; actual implementation would involve adjusting worker pools.
        """
        self.logger.info("Optimizing resource allocation...")
        
        # Example: Adjust max concurrent crawls based on CPU/Memory
        cpu_usage = available_resources.get("cpu_usage_percent", 0)
        memory_usage = available_resources.get("memory_usage_percent", 0)
        
        current_max_concurrent = config_loader.get("queue_system.domain_max_concurrent", 2) # Example from config
        
        if cpu_usage > 80 or memory_usage > 80:
            new_max_concurrent = max(1, current_max_concurrent - 1)
            self.logger.warning(f"High resource usage (CPU: {cpu_usage}%, Mem: {memory_usage}%). Reducing max concurrent crawls to {new_max_concurrent}.")
            # config_loader.set("queue_system.domain_max_concurrent", new_max_concurrent) # This would require config_loader to be mutable
        elif cpu_usage < 50 and memory_usage < 50:
            new_max_concurrent = min(5, current_max_concurrent + 1) # Cap at 5 for example
            self.logger.info(f"Low resource usage. Increasing max concurrent crawls to {new_max_concurrent}.")
            # config_loader.set("queue_system.domain_max_concurrent", new_max_concurrent)

        # Prioritize resources for high-priority jobs
        # This would involve signaling the job scheduler or satellite crawlers
        # to allocate more threads/connections to specific job IDs.
        
        return {"message": "Resource allocation optimization applied (simulated)."}
