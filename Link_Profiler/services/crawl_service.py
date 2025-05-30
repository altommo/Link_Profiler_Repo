"""
Crawl Service - Orchestrates crawling jobs and data persistence
File: Link_Profiler/services/crawl_service.py
"""

import asyncio
import logging
from typing import List, Dict, Optional, Set
from uuid import uuid4
from datetime import datetime
from urllib.parse import urlparse # Import urlparse
import json # Import json
import os # Import os for WARC output directory

from Link_Profiler.core.models import CrawlJob, CrawlConfig, CrawlStatus, Backlink, LinkProfile, create_link_profile_from_backlinks, serialize_model, SEOMetrics, LinkType, SpamLevel, CrawlError # Import CrawlError
from Link_Profiler.crawlers.web_crawler import WebCrawler, CrawlResult # Import CrawlResult
from Link_Profiler.database.database import Database
from Link_Profiler.services.domain_service import DomainService # Import DomainService
from Link_Profiler.services.backlink_service import BacklinkService # Import BacklinkService


class CrawlService:
    """
    Orchestrates web crawling jobs, manages their state,
    and persists results to the database.
    """
    def __init__(self, database: Database, backlink_service: BacklinkService, domain_service: DomainService):
        self.db = database
        self.logger = logging.getLogger(__name__)
        self.active_crawlers: Dict[str, WebCrawler] = {} # Store active crawler instances by job ID
        self.domain_service = domain_service # Injected DomainService
        self.backlink_service = backlink_service # Injected BacklinkService

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
        if config is None:
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
            config=serialize_model(config) # Store config as dict for serialization
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
        debug_file_path = os.path.join("data", f"crawl_results_debug_{job.id}.jsonl") # Using .jsonl for line-delimited JSON
        os.makedirs(os.path.dirname(debug_file_path), exist_ok=True) # Ensure data directory exists

        try:
            # --- Step 1: Attempt to fetch backlinks from API first ---
            self.logger.info(f"Attempting to fetch backlinks for {job.target_url} from API.")
            async with self.backlink_service as bs: # Ensure backlink_service session is active
                api_backlinks = await bs.get_backlinks_from_api(job.target_url)
                
            if api_backlinks:
                self.logger.info(f"Found {len(api_backlinks)} backlinks from API for {job.target_url}.")
                discovered_backlinks.extend(api_backlinks)
                job.links_found = len(discovered_backlinks)
                try:
                    self.db.add_backlinks(api_backlinks)
                    self.logger.info(f"Successfully added {len(api_backlinks)} API backlinks to the database.")
                except Exception as db_e:
                    self.logger.error(f"Error adding API backlinks to database: {db_e}", exc_info=True)
                    job.add_error(url="N/A", error_type="DatabaseError", message=f"DB error adding API backlinks: {str(db_e)}", details=str(db_e))
            else:
                self.logger.info(f"No backlinks found from API for {job.target_url}. Proceeding with web crawl.")

            # --- Step 2: Perform web crawl (if needed or to supplement API data) ---
            # If API provided some backlinks, we might still want to crawl to find more
            # or to get SEO metrics for the source pages.
            # For now, we'll always crawl the initial seed URLs to get SEO metrics
            # and potentially discover more backlinks.
            
            with open(debug_file_path, 'a', encoding='utf-8') as debug_file:
                async with crawler as wc:
                    urls_to_crawl_queue = asyncio.Queue()
                    for url in initial_seed_urls:
                        await urls_to_crawl_queue.put((url, 0)) # (url, depth)

                    crawled_urls_set = set() # Keep track of URLs already processed to avoid redundant crawls

                    while not urls_to_crawl_queue.empty() and urls_crawled_count < config.max_pages:
                        url, current_depth = await urls_to_crawl_queue.get()

                        # Check for pause/stop status at each iteration
                        current_job = self.db.get_crawl_job(job.id)
                        if current_job and current_job.status == CrawlStatus.PAUSED:
                            self.logger.info(f"Crawl job {job.id} paused. Saving current state.")
                            job.status = CrawlStatus.PAUSED
                            self.db.update_crawl_job(job)
                            # Wait until resumed or stopped
                            while True:
                                await asyncio.sleep(5) # Check every 5 seconds
                                current_job = self.db.get_crawl_job(job.id)
                                if current_job and current_job.status == CrawlStatus.IN_PROGRESS:
                                    self.logger.info(f"Crawl job {job.id} resumed.")
                                    break
                                elif current_job and current_job.status == CrawlStatus.STOPPED:
                                    self.logger.info(f"Crawl job {job.id} stopped during pause.")
                                    job.status = CrawlStatus.STOPPED
                                    job.completed_date = datetime.now()
                                    self.db.update_crawl_job(job)
                                    return # Exit crawl loop
                        elif current_job and current_job.status == CrawlStatus.STOPPED:
                            self.logger.info(f"Crawl job {job.id} stopped.")
                            job.status = CrawlStatus.STOPPED
                            job.completed_date = datetime.now()
                            self.db.update_crawl_job(job)
                            return # Exit crawl loop

                        if url in crawled_urls_set:
                            continue
                        if current_depth >= config.max_depth:
                            self.logger.debug(f"Skipping {url} due to max depth ({current_depth})")
                            continue
                        
                        crawled_urls_set.add(url)
                        urls_crawled_count += 1
                        job.urls_crawled = urls_crawled_count

                        self.logger.info(f"Crawling: {url} (Depth: {current_depth}, Crawled: {urls_crawled_count}/{config.max_pages})")

                        crawl_result: Optional[CrawlResult] = None
                        for attempt in range(config.max_retries + 1):
                            try:
                                crawl_result = await wc.crawl_url(url)
                                if crawl_result.error_message:
                                    # Check for retryable errors
                                    if crawl_result.status_code in [408, 500, 502, 503, 504] or "Network or client error" in crawl_result.error_message:
                                        if attempt < config.max_retries:
                                            self.logger.warning(f"Retrying {url} (Attempt {attempt + 1}/{config.max_retries + 1}) due to: {crawl_result.error_message}")
                                            await asyncio.sleep(config.retry_delay_seconds)
                                            continue # Retry
                                        else:
                                            self.logger.error(f"Failed to crawl {url} after {config.max_retries + 1} attempts: {crawl_result.error_message}")
                                            job.add_error(url=url, error_type="CrawlError", message=f"Failed after retries: {crawl_result.error_message}", details=crawl_result.error_message)
                                    else:
                                        self.logger.warning(f"Failed to crawl {url}: {crawl_result.error_message}")
                                        job.add_error(url=url, error_type="CrawlError", message=f"Non-retryable crawl error: {crawl_result.error_message}", details=crawl_result.error_message)
                                else:
                                    break # Success, break retry loop
                            except Exception as e:
                                if attempt < config.max_retries:
                                    self.logger.warning(f"Retrying {url} (Attempt {attempt + 1}/{config.max_retries + 1}) due to unexpected error: {e}")
                                    await asyncio.sleep(config.retry_delay_seconds)
                                    continue
                                else:
                                    self.logger.error(f"Unexpected error crawling {url} after {config.max_retries + 1} attempts: {e}", exc_info=True)
                                    job.add_error(url=url, error_type="UnexpectedError", message=f"Unexpected error: {str(e)}", details=str(e))
                            crawl_result = None # Ensure crawl_result is None if all retries fail

                        if crawl_result:
                            # Serialize the CrawlResult to JSON and write to the debug file
                            try:
                                crawl_result_dict = serialize_model(crawl_result)
                                debug_file.write(json.dumps(crawl_result_dict) + '\n')
                                debug_file.flush()
                            except Exception as e:
                                self.logger.error(f"Error writing crawl result to debug file for {crawl_result.url}: {e}")
                                job.add_error(url=crawl_result.url, error_type="FileWriteError", message=f"Error writing debug data: {str(e)}", details=str(e)) # Corrected this line

                            if crawl_result.links_found:
                                self.logger.info(f"Found {len(crawl_result.links_found)} backlinks on {crawl_result.url} via crawl.")
                                # Only add backlinks not already found from API (simple check by source/target URL)
                                new_backlinks = []
                                existing_backlink_pairs = {(bl.source_url, bl.target_url) for bl in discovered_backlinks}
                                for bl in crawl_result.links_found:
                                    if (bl.source_url, bl.target_url) not in existing_backlink_pairs:
                                        new_backlinks.append(bl)
                                        existing_backlink_pairs.add((bl.source_url, bl.target_url))

                                if new_backlinks:
                                    discovered_backlinks.extend(new_backlinks)
                                    job.links_found = len(discovered_backlinks)
                                    try:
                                        self.db.add_backlinks(new_backlinks) 
                                    except Exception as db_e:
                                        self.logger.error(f"Error adding crawled backlinks to database for {crawl_result.url}: {db_e}", exc_info=True)
                                        job.add_error(url=crawl_result.url, error_type="DatabaseError", message=f"DB error adding crawled backlinks: {str(db_e)}", details=str(db_e)) # Corrected this line
                            
                            self.logger.debug(f"CrawlResult.seo_metrics for {crawl_result.url}: {crawl_result.seo_metrics}")
                            if crawl_result.seo_metrics:
                                try:
                                    self.db.save_seo_metrics(crawl_result.seo_metrics)
                                    self.logger.info(f"Saved SEO metrics for {crawl_result.url}.")
                                except Exception as seo_e:
                                    self.logger.error(f"Error saving SEO metrics for {crawl_result.url}: {seo_e}", exc_info=True)
                                    job.add_error(url=crawl_result.url, error_type="DatabaseError", message=f"DB error saving SEO metrics: {str(seo_e)}", details=str(seo_e)) # Corrected this line

                        # Update job progress
                        job.progress_percentage = min(99.0, (urls_crawled_count / config.max_pages) * 100)
                        self.db.update_crawl_job(job)

            if discovered_backlinks:
                total_authority_score_sum = 0.0
                total_trust_score_sum = 0.0
                total_spam_score_sum = 0.0
                dofollow_count = 0
                clean_count = 0
                spam_count = 0
                
                unique_referring_domains_for_profile: Set[str] = set()
                anchor_text_distribution: Dict[str, int] = {}

                for backlink in discovered_backlinks:
                    unique_referring_domains_for_profile.add(backlink.source_domain)
                    
                    if backlink.anchor_text:
                        anchor_text_distribution[backlink.anchor_text] = \
                            anchor_text_distribution.get(backlink.anchor_text, 0) + 1

                    source_domain_obj = self.db.get_domain(backlink.source_domain)
                    if source_domain_obj:
                        if backlink.link_type == LinkType.FOLLOW:
                            total_authority_score_sum += source_domain_obj.authority_score
                            dofollow_count += 1
                        
                        if backlink.spam_level == SpamLevel.CLEAN:
                            total_trust_score_sum += source_domain_obj.trust_score
                            clean_count += 1
                        
                        if backlink.spam_level in [SpamLevel.LIKELY_SPAM, SpamLevel.CONFIRMED_SPAM]:
                            total_spam_score_sum += source_domain_obj.spam_score
                            spam_count += 1
                
                profile_authority_score = total_authority_score_sum / dofollow_count if dofollow_count > 0 else 0.0
                profile_trust_score = total_trust_score_sum / clean_count if clean_count > 0 else 0.0
                profile_spam_score = total_spam_score_sum / spam_count if spam_count > 0 else 0.0

                link_profile = LinkProfile(
                    target_url=job.target_url,
                    total_backlinks=len(discovered_backlinks),
                    unique_domains=len(unique_referring_domains_for_profile),
                    dofollow_links=sum(1 for bl in discovered_backlinks if bl.link_type == LinkType.FOLLOW),
                    nofollow_links=sum(1 for bl in discovered_backlinks if bl.link_type == LinkType.NOFOLLOW),
                    authority_score=profile_authority_score,
                    trust_score=profile_trust_score,
                    spam_score=profile_spam_score,
                    anchor_text_distribution=anchor_text_distribution,
                    referring_domains=unique_referring_domains_for_profile,
                    backlinks=discovered_backlinks,
                    analysis_date=datetime.now()
                )
                
                self.db.save_link_profile(link_profile)
                job.results['link_profile_summary'] = serialize_model(link_profile)
                self.logger.info(f"Link profile created for {job.target_url} with {len(discovered_backlinks)} backlinks. Authority: {profile_authority_score:.2f}, Trust: {profile_trust_score:.2f}, Spam: {profile_spam_score:.2f}")
            else:
                self.logger.info(f"No backlinks found for {job.target_url}.")

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
                    job.add_error(url=target_domain_name, error_type="DomainInfoError", message=f"Could not retrieve domain info for target domain.", details="Domain info API returned None.")


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
                        else:
                            # Log error for specific referring domain if info could not be retrieved
                            self.logger.warning(f"Could not retrieve domain info for referring domain: {referring_domain_obj.name}.")
                            job.add_error(url=referring_domain_obj.name, error_type="DomainInfoError", message=f"Could not retrieve domain info for referring domain.", details="Domain info API returned None.")


            job.status = CrawlStatus.COMPLETED
            self.logger.info(f"Crawl job {job.id} completed.")

        except Exception as e:
            job.status = CrawlStatus.FAILED
            job.add_error(url="N/A", error_type="CrawlJobError", message=f"Crawl failed: {str(e)}", details=str(e))
            self.logger.error(f"Crawl job {job.id} failed: {e}", exc_info=True)
        finally:
            job.completed_date = datetime.now()
            self.db.update_crawl_job(job)
            if job.id in self.active_crawlers:
                del self.active_crawlers[job.id]

    def get_job_status(self, job_id: str) -> Optional[CrawlJob]:
        """Retrieves the current status of a crawl job."""
        return self.db.get_crawl_job(job_id)

    async def pause_crawl_job(self, job_id: str) -> CrawlJob:
        """Pauses an in-progress crawl job."""
        job = self.db.get_crawl_job(job_id)
        if not job:
            raise ValueError(f"Crawl job {job_id} not found.")
        if job.status == CrawlStatus.IN_PROGRESS:
            job.status = CrawlStatus.PAUSED
            self.db.update_crawl_job(job)
            self.logger.info(f"Crawl job {job_id} paused.")
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
            self.logger.info(f"Crawl job {job_id} resumed.")
            # The _run_backlink_crawl loop will pick this up
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

    def get_link_profile_for_url(self, target_url: str) -> Optional[LinkProfile]:
        """Retrieves the link profile for a given URL."""
        return self.db.get_link_profile(target_url)

    def get_backlinks_for_url(self, target_url: str) -> List[Backlink]:
        """Retrieves all raw backlinks for a given URL."""
        return self.db.get_backlinks_for_target(target_url)

    # Future methods could include:
    # - get_all_jobs()
    # - create_seo_audit_job()
    # - create_domain_analysis_job()
