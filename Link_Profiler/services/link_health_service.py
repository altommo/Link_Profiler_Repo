"""
Link Health Service - Audits the health of outgoing links from crawled pages.
File: Link_Profiler/services/link_health_service.py
"""

import asyncio
import logging
from typing import List, Dict, Optional, Tuple
import aiohttp
from urllib.parse import urlparse
import random # New: Import random for human-like delays

from Link_Profiler.database.database import Database
from Link_Profiler.core.models import SEOMetrics, Backlink, CrawlConfig
from Link_Profiler.utils.user_agent_manager import user_agent_manager # New: Import UserAgentManager
from Link_Profiler.config.config_loader import config_loader # New: Import config_loader
from Link_Profiler.utils.session_manager import SessionManager # New: Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # New: Import DistributedResilienceManager

logger = logging.getLogger(__name__)

class LinkHealthService:
    """
    Service responsible for auditing the health of outgoing links (backlinks)
    from a given set of source URLs. It checks for broken links (4xx/5xx status codes)
    and updates the SEOMetrics for the source pages.
    """
    def __init__(self, database: Database, session_manager: SessionManager, resilience_manager: Optional[DistributedResilienceManager] = None): # New: Accept resilience_manager
        self.db = database
        self.logger = logging.getLogger(__name__)
        self.session_manager = session_manager # Store session manager instance
        self.resilience_manager = resilience_manager # New: Store resilience_manager
        # Removed problematic fallback import
        if self.resilience_manager is None:
            raise ValueError(f"{self.__class__.__name__} requires a DistributedResilienceManager.")

        # Use a default crawl config for link checking, or allow it to be passed
        self.default_crawl_config = CrawlConfig(
            max_depth=0, # Only check the given URLs, no further crawling
            max_pages=10000, # High limit for batch processing
            delay_seconds=0.1, # Be gentle
            timeout_seconds=10, # Quick timeout for link checks
            user_agent="LinkHealthAuditor/1.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            respect_robots_txt=True,
            follow_redirects=True, # Follow redirects to find final status
            max_retries=1, # Only one retry for link checks
            retry_delay_seconds=2.0
        )

    async def __aenter__(self):
        """Async context manager entry for aiohttp session."""
        self.logger.debug("Entering LinkHealthService context.")
        # The session_manager is already entered by the caller (main.py lifespan)
        # No need to manage a separate session here.
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for aiohttp session."""
        self.logger.debug("Exiting LinkHealthService context.")
        # The session_manager is exited by the caller (main.py lifespan)
        pass

    async def _check_link_status(self, url: str) -> Tuple[int, Optional[str]]:
        """
        Performs a HEAD request to check the HTTP status of a link.
        Returns (status_code, error_message).
        """
        # Add human-like delays if configured
        if config_loader.get("anti_detection.human_like_delays", False):
            await asyncio.sleep(random.uniform(0.1, 0.5))

        try:
            # Use HEAD request for efficiency, fall back to GET if HEAD is not allowed
            response = await self.resilience_manager.execute_with_resilience( # Use resilience_manager
                lambda: self.session_manager.head(url, allow_redirects=self.default_crawl_config.follow_redirects),
                url=url # Use the URL for circuit breaker naming
            )
            return response.status, None
        except aiohttp.ClientError as e:
            # Catch network errors, DNS issues, etc.
            return 0, f"Network or client error: {str(e)}"
        except asyncio.TimeoutError:
            return 408, "Request timeout"
        except Exception as e:
            # Catch any other unexpected errors
            return 500, f"Unexpected error: {str(e)}"

    async def audit_links_for_source_urls(self, source_urls: List[str]) -> Dict[str, List[str]]:
        """
        Audits all outgoing links from a list of source URLs for brokenness.
        Updates the 'broken_links' field in the SEOMetrics for the source pages.

        Args:
            source_urls: A list of URLs (pages) whose outgoing links should be audited.

        Returns:
            A dictionary where keys are source URLs and values are lists of broken links found.
        """
        self.logger.info(f"Starting link health audit for {len(source_urls)} source URLs.")
        broken_links_by_source: Dict[str, List[str]] = {}
        
        for source_url in source_urls:
            self.logger.debug(f"Auditing outgoing links from: {source_url}")
            outgoing_backlinks = self.db.get_backlinks_from_source(source_url)
            
            if not outgoing_backlinks:
                self.logger.info(f"No outgoing links found for {source_url}. Skipping audit.")
                continue

            # Filter out internal links if desired, or only check external ones
            # For now, check all outgoing links
            
            # Prepare tasks for concurrent link checking
            link_check_tasks = []
            for backlink in outgoing_backlinks:
                # Avoid checking canonical links or redirects as broken links
                if backlink.link_type in [Backlink.CANONICAL, Backlink.REDIRECT]:
                    continue
                link_check_tasks.append(self._check_link_status(backlink.target_url))
            
            if not link_check_tasks:
                self.logger.info(f"No checkable outgoing links for {source_url}. Skipping audit.")
                continue

            # Execute checks concurrently
            results = await asyncio.gather(*link_check_tasks, return_exceptions=True)
            
            current_broken_links: List[str] = []
            for i, result in enumerate(results):
                target_url = outgoing_backlinks[i].target_url # Assuming order is preserved
                
                if isinstance(result, Exception):
                    self.logger.error(f"Exception during link check for {target_url}: {result}")
                    current_broken_links.append(f"{target_url} (Error: {result})")
                    continue

                status_code, error_message = result
                
                if status_code >= 400 or status_code == 0: # 0 for network errors
                    self.logger.warning(f"Broken link found: {target_url} (Status: {status_code}, Error: {error_message})")
                    current_broken_links.append(target_url)
                else:
                    self.logger.debug(f"Link OK: {target_url} (Status: {status_code})")
            
            if current_broken_links:
                broken_links_by_source[source_url] = current_broken_links
                self.logger.info(f"Found {len(current_broken_links)} broken links for {source_url}.")
            
            # Update SEOMetrics for the source URL
            seo_metrics = self.db.get_seo_metrics(source_url)
            if seo_metrics:
                seo_metrics.broken_links = current_broken_links
                try:
                    self.db.save_seo_metrics(seo_metrics)
                    self.logger.info(f"Updated SEOMetrics for {source_url} with broken links.")
                except Exception as e:
                    self.logger.error(f"Failed to save SEOMetrics for {source_url}: {e}", exc_info=True)
            else:
                self.logger.warning(f"No SEOMetrics found for {source_url}. Cannot update broken links.")

        self.logger.info("Link health audit completed.")
        return broken_links_by_source
