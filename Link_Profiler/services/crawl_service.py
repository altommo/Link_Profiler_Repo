"""
Crawl Service - Orchestrates crawling jobs and data persistence
File: Link_Profiler/services/crawl_service.py
"""

import asyncio
import logging
import os
from typing import List, Dict, Optional, Set
from uuid import uuid4
from datetime import datetime
from urllib.parse import urlparse
import json

from Link_Profiler.core.models import (
    URL, Backlink, CrawlConfig, CrawlStatus, LinkType, 
    CrawlJob, ContentType, serialize_model, SEOMetrics, SpamLevel, CrawlError,
    SERPResult, KeywordSuggestion, LinkProfile # Added LinkProfile
)
from Link_Profiler.crawlers.web_crawler import WebCrawler, CrawlResult
from Link_Profiler.database.database import Database
from Link_Profiler.services.domain_service import DomainService
from Link_Profiler.services.backlink_service import BacklinkService
from Link_Profiler.services.serp_service import SERPService
from Link_Profiler.services.keyword_service import KeywordService
from Link_Profiler.services.link_health_service import LinkHealthService


class CrawlService:
    """
    Orchestrates web crawling jobs, manages their state,
    and persists results to the database.
    """
    def __init__(
        self, 
        database: Database, 
        backlink_service: BacklinkService, 
        domain_service: DomainService,
        serp_service: SERPService,
        keyword_service: KeywordService,
        link_health_service: LinkHealthService
    ):
        self.db = database
        self.logger = logging.getLogger(__name__)
        self.active_crawlers: Dict[str, WebCrawler] = {}
        self.domain_service = domain_service
        self.backlink_service = backlink_service
        self.serp_service = serp_service
        self.keyword_service = keyword_service
        self.link_health_service = link_health_service

    async def create_and_start_crawl_job(
        self, 
        job_type: str,
        target_url: Optional[str] = None,
        initial_seed_urls: Optional[List[str]] = None,
        keyword: Optional[str] = None,
        num_results: Optional[int] = None,
        source_urls_to_audit: Optional[List[str]] = None,
        config: Optional[CrawlConfig] = None
    ) -> CrawlJob:
        """
        Creates a new crawl job of a specified type and starts it.
        
        Args:
            job_type: The type of job ('backlink_discovery', 'serp_analysis', 'keyword_research', 'link_health_audit').
            target_url: The primary URL relevant to the job (e.g., for backlink discovery).
            initial_seed_urls: Optional list of URLs to start crawling from (for backlink discovery).
            keyword: Optional keyword for SERP or keyword research jobs.
            num_results: Optional number of results/suggestions to fetch for SERP/keyword jobs.
            source_urls_to_audit: Optional list of URLs whose outgoing links should be audited (for link_health_audit).
            config: Optional CrawlConfig object. If None, a default config is used.
        
        Returns:
            The created CrawlJob object.
        """
        job_id = str(uuid4())
        if config is None:
            config = CrawlConfig()

        config.respect_robots_txt = False 

        if job_type == 'backlink_discovery' and target_url:
            parsed_target_domain = urlparse(target_url).netloc
            if config.allowed_domains and parsed_target_domain not in config.allowed_domains:
                config.allowed_domains.add(parsed_target_domain)

        job = CrawlJob(
            id=job_id,
            target_url=target_url or keyword or "N/A",
            job_type=job_type,
            status=CrawlStatus.PENDING,
            config=serialize_model(config)
        )
        self.db.add_crawl_job(job)
        self.logger.info(f"Created {job_type} job {job_id} for {job.target_url}")

        if job_type == 'backlink_discovery':
            if not initial_seed_urls or not target_url:
                raise ValueError("initial_seed_urls and target_url must be provided for 'backlink_discovery' job type.")
            asyncio.create_task(self._run_backlink_crawl(job, initial_seed_urls, config))
        elif job_type == 'serp_analysis':
            if not keyword:
                raise ValueError("keyword must be provided for 'serp_analysis' job type.")
            asyncio.create_task(self._run_serp_analysis_job(job, keyword, num_results))
        elif job_type == 'keyword_research':
            if not keyword:
                raise ValueError("keyword must be provided for 'keyword_research' job type.")
            asyncio.create_task(self._run_keyword_research_job(job, keyword, num_results))
        elif job_type == 'link_health_audit':
            if not source_urls_to_audit:
                raise ValueError("source_urls_to_audit must be provided for 'link_health_audit' job type.")
            asyncio.create_task(self._run_link_health_audit_job(job, source_urls_to_audit))
        else:
            raise ValueError(f"Unknown job type: {job_type}")
        
        return job

    async def _run_backlink_crawl(self, job: CrawlJob, initial_seed_urls: List[str], config: CrawlConfig):
        """
        Internal method to execute the backlink crawl.
        """
        job.status = CrawlStatus.IN_PROGRESS
        job.started_date = datetime.now()
        self.db.update_crawl_job(job)
        self.logger.info(f"Starting backlink crawl job {job.id} for {job.target_url}")

        crawler = WebCrawler(config)
        self.active_crawlers[job.id] = crawler

        discovered_backlinks: List[Backlink] = []
        urls_crawled_count = 0
        
        debug_file_path = os.path.join("data", f"crawl_results_debug_{job.id}.jsonl")
        os.makedirs(os.path.dirname(debug_file_path), exist_ok=True)

        try:
            self.logger.info(f"Attempting to fetch backlinks for {job.target_url} from API.")
            async with self.backlink_service as bs:
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

            with open(debug_file_path, 'a', encoding='utf-8') as debug_file:
                async with crawler as wc:
                    urls_to_crawl_queue = asyncio.Queue()
                    for url in initial_seed_urls:
                        await urls_to_crawl_queue.put((url, 0))

                    crawled_urls_set = set()

                    while not urls_to_crawl_queue.empty() and urls_crawled_count < config.max_pages:
                        current_job = self.db.get_crawl_job(job.id)
                        if current_job and current_job.status == CrawlStatus.PAUSED:
                            self.logger.info(f"Crawl job {job.id} paused. Saving current state.")
                            job.status = CrawlStatus.PAUSED
                            self.db.update_crawl_job(job)
                            while True:
                                await asyncio.sleep(5)
                                current_job = self.db.get_crawl_job(job.id)
                                if current_job and current_job.status == CrawlStatus.IN_PROGRESS:
                                    self.logger.info(f"Crawl job {job.id} resumed.")
                                    break
                                elif current_job and current_job.status == CrawlStatus.STOPPED:
                                    self.logger.info(f"Crawl job {job.id} stopped during pause.")
                                    job.status = CrawlStatus.STOPPED
                                    job.completed_date = datetime.now()
                                    self.db.update_crawl_job(job)
                                    return
                        elif current_job and current_job.status == CrawlStatus.STOPPED:
                            self.logger.info(f"Crawl job {job.id} stopped.")
                            job.status = CrawlStatus.STOPPED
                            job.completed_date = datetime.now()
                            self.db.update_crawl_job(job)
                            return

                        url, current_depth = await urls_to_crawl_queue.get()

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
                                    if crawl_result.status_code in [408, 500, 502, 503, 504] or "Network or client error" in crawl_result.error_message:
                                        if attempt < config.max_retries:
                                            self.logger.warning(f"Retrying {url} (Attempt {attempt + 1}/{config.max_retries + 1}) due to: {crawl_result.error_message}")
                                            await asyncio.sleep(config.retry_delay_seconds)
                                            continue
                                        else:
                                            self.logger.error(f"Failed to crawl {url} after {config.max_retries + 1} attempts: {crawl_result.error_message}")
                                            job.add_error(url=url, error_type="CrawlError", message=f"Failed after retries: {crawl_result.error_message}", details=crawl_result.error_message)
                                    else:
                                        self.logger.warning(f"Failed to crawl {url}: {crawl_result.error_message}")
                                        job.add_error(url=url, error_type="CrawlError", message=f"Non-retryable crawl error: {crawl_result.error_message}", details=crawl_result.error_message)
                                else:
                                    break
                            except Exception as e:
                                if attempt < config.max_retries:
                                    self.logger.warning(f"Retrying {url} (Attempt {attempt + 1}/{config.max_retries + 1}) due to unexpected error: {e}")
                                    await asyncio.sleep(config.retry_delay_seconds)
                                    continue
                                else:
                                    self.logger.error(f"Unexpected error crawling {url} after {config.max_retries + 1} attempts: {e}", exc_info=True)
                                    job.add_error(url=url, error_type="UnexpectedError", message=f"Unexpected error: {str(e)}", details=str(e))
                            crawl_result = None

                        if crawl_result:
                            try:
                                crawl_result_dict = serialize_model(crawl_result)
                                debug_file.write(json.dumps(crawl_result_dict) + '\n')
                                debug_file.flush()
                            except Exception as e:
                                self.logger.error(f"Error writing crawl result to debug file for {crawl_result.url}: {e}")
                                job.add_error(url=crawl_result.url, error_type="FileWriteError", message=f"Error writing debug data: {str(e)}", details=str(e))

                            if crawl_result.links_found:
                                self.logger.info(f"Found {len(crawl_result.links_found)} backlinks on {crawl_result.url} via crawl.")
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
                                        job.add_error(url=crawl_result.url, error_type="DatabaseError", message=f"DB error adding crawled backlinks: {str(db_e)}", details=str(db_e))
                            
                            self.logger.debug(f"CrawlResult.seo_metrics for {crawl_result.url}: {crawl_result.seo_metrics}")
                            if crawl_result.seo_metrics:
                                try:
                                    self.db.save_seo_metrics(crawl_result.seo_metrics)
                                    self.logger.info(f"Saved SEO metrics for {crawl_result.url}.")
                                except Exception as seo_e:
                                    self.logger.error(f"Error saving SEO metrics for {crawl_result.url}: {seo_e}", exc_info=True)
                                    job.add_error(url=crawl_result.url, error_type="DatabaseError", message=f"DB error saving SEO metrics: {str(seo_e)}", details=str(seo_e))

                        if crawl_result and crawl_result.links_found:
                            for link in crawl_result.links_found:
                                parsed_link_url = urlparse(link.target_url)
                                if config.is_domain_allowed(parsed_link_url.netloc):
                                    if link.target_url not in crawled_urls_set and \
                                    urls_crawled_count + urls_to_crawl_queue.qsize() < config.max_pages:
                                        await urls_to_crawl_queue.put((link.target_url, current_depth + 1))

                        job.progress_percentage = min(99.0, (urls_crawled_count / config.max_pages) * 100)
                        self.db.update_crawl_job(job)

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
                            pass

            if discovered_backlinks:
                self.logger.info("Enriching discovered backlinks with source domain metrics and updating in DB.")
                for backlink in discovered_backlinks:
                    source_domain_obj = self.db.get_domain(backlink.source_domain)
                    if source_domain_obj:
                        backlink.source_domain_metrics = {
                            "authority_score": source_domain_obj.authority_score,
                            "trust_score": source_domain_obj.trust_score,
                            "spam_score": source_domain_obj.spam_score,
                        }
                        self.db.update_backlink(backlink)
                    else:
                        self.logger.warning(f"Could not find domain info for source domain {backlink.source_domain} to enrich backlink {backlink.id}.")

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

                    if backlink.source_domain_metrics:
                        if backlink.link_type == LinkType.FOLLOW:
                            total_authority_score_sum += backlink.source_domain_metrics.get("authority_score", 0.0)
                            dofollow_count += 1
                        
                        if backlink.spam_level == SpamLevel.CLEAN:
                            total_trust_score_sum += backlink.source_domain_metrics.get("trust_score", 0.0)
                            clean_count += 1
                        
                        if backlink.spam_level in [SpamLevel.LIKELY_SPAM, SpamLevel.CONFIRMED_SPAM]:
                            total_spam_score_sum += backlink.source_domain_metrics.get("spam_score", 0.0)
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

    async def _run_serp_analysis_job(self, job: CrawlJob, keyword: str, num_results: Optional[int]):
        """
        Internal method to execute a SERP analysis job.
        """
        job.status = CrawlStatus.IN_PROGRESS
        job.started_date = datetime.now()
        self.db.update_crawl_job(job)
        self.logger.info(f"Starting SERP analysis job {job.id} for keyword: '{keyword}'")

        try:
            async with self.serp_service as ss:
                serp_results = await ss.get_serp_data(keyword, num_results or 10)
            
            if serp_results:
                self.logger.info(f"Found {len(serp_results)} SERP results for '{keyword}'.")
                try:
                    await self.db.add_serp_results(serp_results)
                    self.logger.info(f"Successfully added {len(serp_results)} SERP results to the database.")
                except Exception as db_e:
                    self.logger.error(f"Error adding SERP results to database: {db_e}", exc_info=True)
                    job.add_error(url="N/A", error_type="DatabaseError", message=f"DB error adding SERP results: {str(db_e)}", details=str(db_e))
                
                job.results['serp_results'] = [serialize_model(res) for res in serp_results]
                job.urls_discovered = len(serp_results)
                job.progress_percentage = 100.0
                job.status = CrawlStatus.COMPLETED
                self.logger.info(f"SERP analysis job {job.id} completed for '{keyword}'.")
            else:
                job.results['serp_results'] = []
                job.progress_percentage = 100.0
                job.status = CrawlStatus.COMPLETED
                self.logger.info(f"No SERP results found for '{keyword}'. Job {job.id} completed.")

        except Exception as e:
            job.status = CrawlStatus.FAILED
            job.add_error(url="N/A", error_type="SERPAnalysisError", message=f"SERP analysis failed: {str(e)}", details=str(e))
            self.logger.error(f"SERP analysis job {job.id} failed: {e}", exc_info=True)
        finally:
            job.completed_date = datetime.now()
            self.db.update_crawl_job(job)

    async def _run_keyword_research_job(self, job: CrawlJob, seed_keyword: str, num_suggestions: Optional[int]):
        """
        Internal method to execute a keyword research job.
        """
        job.status = CrawlStatus.IN_PROGRESS
        job.started_date = datetime.now()
        self.db.update_crawl_job(job)
        self.logger.info(f"Starting keyword research job {job.id} for seed: '{seed_keyword}'")

        try:
            async with self.keyword_service as ks:
                suggestions = await ks.get_keyword_data(seed_keyword, num_suggestions or 10)
            
            if suggestions:
                self.logger.info(f"Found {len(suggestions)} keyword suggestions for '{seed_keyword}'.")
                try:
                    await self.db.add_keyword_suggestions(suggestions)
                    self.logger.info(f"Successfully added {len(suggestions)} keyword suggestions to the database.")
                except Exception as db_e:
                    self.logger.error(f"Error adding keyword suggestions to database: {db_e}", exc_info=True)
                    job.add_error(url="N/A", error_type="DatabaseError", message=f"DB error adding keyword suggestions: {str(db_e)}", details=str(db_e))
                
                job.results['keyword_suggestions'] = [serialize_model(sug) for sug in suggestions]
                job.urls_discovered = len(suggestions)
                job.progress_percentage = 100.0
                job.status = CrawlStatus.COMPLETED
                self.logger.info(f"Keyword research job {job.id} completed for '{seed_keyword}'.")
            else:
                job.results['keyword_suggestions'] = []
                job.progress_percentage = 100.0
                job.status = CrawlStatus.COMPLETED
                self.logger.info(f"No keyword suggestions found for '{seed_keyword}'. Job {job.id} completed.")

        except Exception as e:
            job.status = CrawlStatus.FAILED
            job.add_error(url="N/A", error_type="KeywordResearchError", message=f"Keyword research failed: {str(e)}", details=str(e))
            self.logger.error(f"Keyword research job {job.id} failed: {e}", exc_info=True)
        finally:
            job.completed_date = datetime.now()
            self.db.update_crawl_job(job)

    async def _run_link_health_audit_job(self, job: CrawlJob, source_urls: List[str]):
        """
        Internal method to execute a link health audit job.
        """
        job.status = CrawlStatus.IN_PROGRESS
        job.started_date = datetime.now()
        self.db.update_crawl_job(job)
        self.logger.info(f"Starting link health audit job {job.id} for {len(source_urls)} source URLs.")

        try:
            async with self.link_health_service as lhs:
                broken_links_found = await lhs.audit_links_for_source_urls(source_urls)
            
            job.results['broken_links_audit'] = broken_links_found
            job.urls_discovered = len(source_urls)
            job.links_found = sum(len(links) for links in broken_links_found.values())
            job.progress_percentage = 100.0
            job.status = CrawlStatus.COMPLETED
            self.logger.info(f"Link health audit job {job.id} completed. Found {job.links_found} broken links.")

        except Exception as e:
            job.status = CrawlStatus.FAILED
            job.add_error(url="N/A", error_type="LinkHealthAuditError", message=f"Link health audit failed: {str(e)}", details=str(e))
            self.logger.error(f"Link health audit job {job.id} failed: {e}", exc_info=True)
        finally:
            job.completed_date = datetime.now()
            self.db.update_crawl_job(job)

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

    def get_link_profile_for_url(self, target_url: str) -> Optional[LinkProfile]:
        """Retrieves the link profile for a given URL."""
        return self.db.get_link_profile(target_url)

    def get_backlinks_for_url(self, target_url: str) -> List[Backlink]:
        """Retrieves all raw backlinks for a given URL."""
        return self.db.get_backlinks_for_target(target_url)
