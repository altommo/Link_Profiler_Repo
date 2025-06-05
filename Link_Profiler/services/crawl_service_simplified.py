"""
Simplified Crawl Service - Compatible with existing Link Profiler
File: Link_Profiler/services/crawl_service_simplified.py
"""

import asyncio
import logging
from typing import List, Dict, Optional
from uuid import uuid4
from datetime import datetime
from urllib.parse import urlparse

from Link_Profiler.core.models import CrawlJob, CrawlConfig, CrawlStatus, Backlink, LinkProfile, create_link_profile_from_backlinks, serialize_model
from Link_Profiler.crawlers.web_crawler import WebCrawler, CrawlResult
from Link_Profiler.database.database import Database
from Link_Profiler.services.domain_service import DomainService


class LegacyCrawlService:
    """
    Legacy simplified crawl service for backward compatibility.
    """
    def __init__(self, database: Database, backlink_service=None, domain_service=None):
        self.db = database
        self.logger = logging.getLogger(__name__)
        self.active_crawlers: Dict[str, WebCrawler] = {}
        self.domain_service = domain_service

    async def create_and_start_backlink_crawl_job(
        self, 
        target_url: str, 
        initial_seed_urls: List[str], 
        config: Optional[CrawlConfig] = None
    ) -> CrawlJob:
        """
        Creates a new backlink crawl job and starts it.
        """
        job_id = str(uuid4())
        if config is None:
            config = CrawlConfig()

        # Ensure target domain is in allowed domains if specified
        parsed_target_domain = urlparse(target_url).netloc
        if config.allowed_domains and parsed_target_domain not in config.allowed_domains:
            config.allowed_domains.add(parsed_target_domain)

        job = CrawlJob(
            id=job_id,
            target_url=target_url,
            job_type='backlink_discovery',
            status=CrawlStatus.PENDING,
            config=serialize_model(config)
        )
        self.db.add_crawl_job(job)
        self.logger.info(f"Created crawl job {job_id} for {target_url}")

        # Start the crawl in a separate task
        asyncio.create_task(self._run_backlink_crawl(job, initial_seed_urls, config))
        
        return job

    async def _run_backlink_crawl(self, job: CrawlJob, initial_seed_urls: List[str], config: CrawlConfig):
        """
        Internal method to execute the backlink crawl.
        """
        job.status = CrawlStatus.IN_PROGRESS
        job.started_date = datetime.now()
        self.db.update_crawl_job(job)
        self.logger.info(f"Starting crawl job {job.id} for {job.target_url}")

        crawler = WebCrawler(config)
        self.active_crawlers[job.id] = crawler

        discovered_backlinks: List[Backlink] = []
        urls_crawled_count = 0
        
        try:
            async with crawler as wc:
                async for crawl_result in wc.crawl_for_backlinks(job.target_url, initial_seed_urls):
                    urls_crawled_count += 1
                    job.urls_crawled = urls_crawled_count
                    
                    if crawl_result.links_found:
                        self.logger.info(f"Found {len(crawl_result.links_found)} backlinks on {crawl_result.url}")
                        discovered_backlinks.extend(crawl_result.links_found)
                        job.links_found = len(discovered_backlinks)
                        self.db.add_backlinks(crawl_result.links_found)
                    
                    # Update job progress
                    job.progress_percentage = min(99.0, (urls_crawled_count / config.max_pages) * 100)
                    self.db.update_crawl_job(job)

            # After crawl completes, create/update LinkProfile
            if discovered_backlinks:
                link_profile = create_link_profile_from_backlinks(job.target_url, discovered_backlinks)
                self.db.save_link_profile(link_profile)
                job.results['link_profile_summary'] = serialize_model(link_profile)
                self.logger.info(f"Link profile created for {job.target_url} with {len(discovered_backlinks)} backlinks.")
            else:
                self.logger.info(f"No backlinks found for {job.target_url}.")

            # Fetch and store Domain information for the target domain
            if self.domain_service:
                target_domain_name = urlparse(job.target_url).netloc
                self.logger.info(f"Fetching domain info for target domain: {target_domain_name}")
                async with self.domain_service as ds:
                    target_domain_obj = await ds.get_domain_info(target_domain_name)
                    if target_domain_obj:
                        self.db.save_domain(target_domain_obj)
                        job.results['target_domain_info'] = serialize_model(target_domain_obj)
                        self.logger.info(f"Saved domain info for {target_domain_name}.")
                    else:
                        self.logger.warning(f"Could not retrieve domain info for {target_domain_name}.")

                    # Fetch domain info for referring domains
                    if discovered_backlinks:
                        unique_referring_domains = {bl.source_domain for bl in discovered_backlinks}
                        self.logger.info(f"Fetching domain info for {len(unique_referring_domains)} unique referring domains.")
                        
                        domain_info_tasks = [
                            ds.get_domain_info(referring_domain_name)
                            for referring_domain_name in unique_referring_domains
                            if referring_domain_name != target_domain_name
                        ]
                        
                        referring_domain_objs = await asyncio.gather(*domain_info_tasks)
                        
                        for referring_domain_obj in referring_domain_objs:
                            if referring_domain_obj:
                                self.db.save_domain(referring_domain_obj)
                                self.logger.info(f"Saved domain info for referring domain: {referring_domain_obj.name}.")

            job.status = CrawlStatus.COMPLETED
            self.logger.info(f"Crawl job {job.id} completed.")

        except Exception as e:
            job.status = CrawlStatus.FAILED
            job.add_error(url="N/A", error_type="CrawlFailure", message=f"Crawl failed: {str(e)}")
            self.logger.error(f"Crawl job {job.id} failed: {e}", exc_info=True)
        finally:
            job.completed_date = datetime.now()
            self.db.update_crawl_job(job)
            if job.id in self.active_crawlers:
                del self.active_crawlers[job.id]

    async def pause_crawl_job(self, job_id: str) -> CrawlJob:
        """Pauses an in-progress crawl job."""
        job = self.db.get_crawl_job(job_id)
        if not job:
            raise ValueError(f"Crawl job {job_id} not found.")
        if job.status == CrawlStatus.IN_PROGRESS:
            job.status = CrawlStatus.PAUSED
            self.db.update_crawl_job(job)
            self.logger.info(f"Crawl job {job.id} paused.")
            return job
        else:
            raise ValueError(f"Crawl job {job_id} cannot be paused from status {job.status.value}.")

    async def resume_crawl_job(self, job_id: str) -> CrawlJob:
        """Resumes a paused crawl job."""
        job = self.db.get_crawl_job(job_id)
        if not job:
            raise ValueError(f"Crawl job {job_id} not found.")
        if job.status == CrawlStatus.PAUSED:
            job.status = CrawlStatus.IN_PROGRESS
            self.db.update_crawl_job(job)
            self.logger.info(f"Crawl job {job.id} resumed.")
            return job
        else:
            raise ValueError(f"Crawl job {job_id} cannot be resumed from status {job.status.value}.")

    async def stop_crawl_job(self, job_id: str) -> CrawlJob:
        """Stops an active or paused crawl job."""
        job = self.db.get_crawl_job(job_id)
        if not job:
            raise ValueError(f"Crawl job {job_id} not found.")
        if job.status in [CrawlStatus.IN_PROGRESS, CrawlStatus.PAUSED]:
            job.status = CrawlStatus.STOPPED
            job.completed_date = datetime.now()
            self.db.update_crawl_job(job)
            self.logger.info(f"Crawl job {job.id} stopped.")
            return job
        else:
            raise ValueError(f"Crawl job {job.id} cannot be stopped from status {job.status.value}.")

    def get_job_status(self, job_id: str) -> Optional[CrawlJob]:
        """Retrieves the current status of a crawl job."""
        return self.db.get_crawl_job(job_id)

    def get_link_profile_for_url(self, target_url: str) -> Optional[LinkProfile]:
        """Retrieves the link profile for a given URL."""
        return self.db.get_link_profile(target_url)

    def get_backlinks_for_url(self, target_url: str) -> List[Backlink]:
        """Retrieves all raw backlinks for a given URL."""
        return self.db.get_backlinks_for_target(target_url)
