"""
Crawl Service - Orchestrates crawling jobs and data persistence
File: Link_Profiler/services/crawl_service.py
"""

import asyncio
import logging
from typing import List, Dict, Optional
from uuid import uuid4
from datetime import datetime
from urllib.parse import urlparse # Import urlparse
import json # Import json

from Link_Profiler.core.models import CrawlJob, CrawlConfig, CrawlStatus, Backlink, LinkProfile, create_link_profile_from_backlinks, serialize_model, SEOMetrics # Import SEOMetrics
from Link_Profiler.crawlers.web_crawler import WebCrawler, CrawlResult # Import CrawlResult
from Link_Profiler.database.database import Database
from Link_Profiler.services.domain_service import DomainService, SimulatedDomainAPIClient # Import DomainService and SimulatedDomainAPIClient


class CrawlService:
    """
    Orchestrates web crawling jobs, manages their state,
    and persists results to the database.
    """
    def __init__(self, database: Database):
        self.db = database
        self.logger = logging.getLogger(__name__)
        self.active_crawlers: Dict[str, WebCrawler] = {} # Store active crawler instances by job ID
        self.domain_service = DomainService(api_client=SimulatedDomainAPIClient()) # Instantiate DomainService with explicit client

    async def create_and_start_backlink_crawl_job(
        self, 
        target_url: str, 
        initial_seed_urls: List[str], 
        config: Optional[CrawlConfig] = None
    ) -> CrawlJob:
        """
        Creates a new backlink crawl job and starts it.
        
        Args:
            target_url: The URL for which to find backlinks.
            initial_seed_urls: A list of URLs to start crawling from to discover backlinks.
            config: Optional CrawlConfig object. If None, a default config is used.
        
        Returns:
            The created CrawlJob object.
        """
        job_id = str(uuid4())
        if config is None: # Corrected from === to is
            config = CrawlConfig() # Use default config

        # For testing purposes, explicitly set respect_robots_txt to False
        # as quotes.toscrape.com's robots.txt disallows all crawling.
        config.respect_robots_txt = False 

        # Ensure target domain is in allowed domains if specified
        parsed_target_domain = urlparse(target_url).netloc
        if config.allowed_domains and parsed_target_domain not in config.allowed_domains:
            config.allowed_domains.add(parsed_target_domain)

        job = CrawlJob(
            id=job_id,
            target_url=target_url,
            job_type='backlink_discovery',
            status=CrawlStatus.PENDING,
            config=config.__dict__ # Store config as dict for serialization
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
        self.active_crawlers[job.id] = crawler # Store active crawler instance

        discovered_backlinks: List[Backlink] = []
        urls_crawled_count = 0
        
        # Define the debug file path
        debug_file_path = f"data/crawl_results_debug_{job.id}.jsonl" # Using .jsonl for line-delimited JSON

        try:
            # Open the debug file in append mode
            with open(debug_file_path, 'a', encoding='utf-8') as debug_file:
                async with crawler as wc:
                    async for crawl_result in wc.crawl_for_backlinks(job.target_url, initial_seed_urls):
                        urls_crawled_count += 1
                        job.urls_crawled = urls_crawled_count
                        
                        # Serialize the CrawlResult to JSON and write to the debug file
                        try:
                            # Convert CrawlResult dataclass to a serializable dictionary
                            crawl_result_dict = serialize_model(crawl_result)
                            debug_file.write(json.dumps(crawl_result_dict) + '\n')
                            debug_file.flush() # Ensure data is written immediately
                        except Exception as e:
                            self.logger.error(f"Error writing crawl result to debug file for {crawl_result.url}: {e}")
                            job.add_error(f"Error writing debug data for {crawl_result.url}: {str(e)}")

                        if crawl_result.links_found:
                            self.logger.info(f"Found {len(crawl_result.links_found)} backlinks on {crawl_result.url}")
                            discovered_backlinks.extend(crawl_result.links_found)
                            job.links_found = len(discovered_backlinks)
                            
                            # Persist backlinks as they are found
                            try:
                                self.db.add_backlinks(crawl_result.links_found) 
                            except Exception as db_e:
                                self.logger.error(f"Error adding backlinks to database for {crawl_result.url}: {db_e}", exc_info=True)
                                job.add_error(f"DB error adding backlinks for {crawl_result.url}: {str(db_e)}")
                        
                        self.logger.debug(f"CrawlResult.seo_metrics for {crawl_result.url}: {crawl_result.seo_metrics}") # Added debug log
                        # Persist SEO metrics if available
                        if crawl_result.seo_metrics:
                            try:
                                self.db.save_seo_metrics(crawl_result.seo_metrics)
                                self.logger.info(f"Saved SEO metrics for {crawl_result.url}.")
                            except Exception as seo_e:
                                self.logger.error(f"Error saving SEO metrics for {crawl_result.url}: {seo_e}", exc_info=True)
                                job.add_error(f"DB error saving SEO metrics for {crawl_result.url}: {str(seo_e)}")

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

            # --- Fetch and store Domain information for the target domain ---
            target_domain_name = urlparse(job.target_url).netloc
            self.logger.info(f"Fetching domain info for target domain: {target_domain_name}")
            async with self.domain_service as ds: # Use domain_service as context manager
                target_domain_obj = await ds.get_domain_info(target_domain_name)
                if target_domain_obj:
                    self.db.save_domain(target_domain_obj)
                    job.results['target_domain_info'] = serialize_model(target_domain_obj)
                    self.logger.info(f"Saved domain info for {target_domain_name}.")
                else:
                    self.logger.warning(f"Could not retrieve domain info for {target_domain_name}.")

                # --- Fetch and store Domain information for referring domains ---
                if discovered_backlinks:
                    unique_referring_domains = {bl.source_domain for bl in discovered_backlinks}
                    self.logger.info(f"Fetching domain info for {len(unique_referring_domains)} unique referring domains.")
                    
                    # Use asyncio.gather to fetch domain info concurrently for efficiency
                    domain_info_tasks = [
                        ds.get_domain_info(referring_domain_name) # Use ds from context manager
                        for referring_domain_name in unique_referring_domains
                        if referring_domain_name != target_domain_name # Avoid re-fetching target domain
                    ]
                    
                    referring_domain_objs = await asyncio.gather(*domain_info_tasks)
                    
                    for referring_domain_obj in referring_domain_objs:
                        if referring_domain_obj:
                            self.db.save_domain(referring_domain_obj)
                            self.logger.info(f"Saved domain info for referring domain: {referring_domain_obj.name}.")
                        # else: warning already logged by domain_service.get_domain_info if it returns None

            job.status = CrawlStatus.COMPLETED
            self.logger.info(f"Crawl job {job.id} completed.")

        except Exception as e:
            job.status = CrawlStatus.FAILED
            job.add_error(f"Crawl failed: {str(e)}")
            self.logger.error(f"Crawl job {job.id} failed: {e}", exc_info=True)
        finally:
            job.completed_date = datetime.now()
            self.db.update_crawl_job(job)
            if job.id in self.active_crawlers:
                del self.active_crawlers[job.id] # Remove crawler instance

    def get_job_status(self, job_id: str) -> Optional[CrawlJob]:
        """Retrieves the current status of a crawl job."""
        return self.db.get_crawl_job(job_id)

    def get_link_profile_for_url(self, target_url: str) -> Optional[LinkProfile]:
        """Retrieves the link profile for a given URL."""
        return self.db.get_link_profile(target_url)

    def get_backlinks_for_url(self, target_url: str) -> List[Backlink]:
        """Retrieves all raw backlinks for a given URL."""
        return self.db.get_backlinks_for_target(target_url)

    # Future methods could include:
    # - stop_crawl_job(job_id)
    # - get_all_jobs()
    # - create_seo_audit_job()
    # - create_domain_analysis_job()
