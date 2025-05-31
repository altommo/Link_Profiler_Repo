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
import redis.asyncio as redis

from playwright.async_api import Browser # New: Import Playwright Browser type

from Link_Profiler.core.models import (
    URL, Backlink, CrawlConfig, CrawlStatus, LinkType, 
    CrawlJob, ContentType, serialize_model, SEOMetrics, SpamLevel, CrawlError,
    SERPResult, KeywordSuggestion, LinkProfile
)
from Link_Profiler.crawlers.web_crawler import WebCrawler, CrawlResult
from Link_Profiler.crawlers.technical_auditor import TechnicalAuditor
from Link_Profiler.database.database import Database
from Link_Profiler.database.clickhouse_loader import ClickHouseLoader
from Link_Profiler.services.domain_service import DomainService
from Link_Profiler.services.backlink_service import BacklinkService
from Link_Profiler.services.serp_service import SERPService
from Link_Profiler.services.keyword_service import KeywordService
from Link_Profiler.services.link_health_service import LinkHealthService
from Link_Profiler.services.domain_analyzer_service import DomainAnalyzerService
from Link_Profiler.services.ai_service import AIService
from Link_Profiler.utils.content_validator import ContentValidator
from Link_Profiler.utils.anomaly_detector import anomaly_detector
from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.monitoring.prometheus_metrics import (
    JOBS_IN_PROGRESS, JOBS_PENDING, JOBS_COMPLETED_SUCCESS_TOTAL, JOBS_FAILED_TOTAL,
    CRAWLED_URLS_TOTAL, BACKLINKS_FOUND_TOTAL, JOB_ERRORS_TOTAL
)


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
        link_health_service: LinkHealthService,
        clickhouse_loader: Optional[ClickHouseLoader],
        redis_client: Optional[redis.Redis],
        technical_auditor: TechnicalAuditor,
        domain_analyzer_service: DomainAnalyzerService,
        ai_service: AIService,
        playwright_browser: Optional[Browser] = None # New: Accept playwright_browser
    ):
        self.db = database
        self.logger = logging.getLogger(__name__)
        self.active_crawlers: Dict[str, WebCrawler] = {}
        self.domain_service = domain_service
        self.backlink_service = backlink_service
        self.serp_service = serp_service
        self.keyword_service = keyword_service
        self.link_health_service = link_health_service
        self.clickhouse_loader = clickhouse_loader
        self.redis = redis_client
        self.technical_auditor = technical_auditor
        self.domain_analyzer_service = domain_analyzer_service
        self.ai_service = ai_service
        self.content_validator = ContentValidator()
        self.deduplication_set_key = "processed_backlinks_dedup"
        self.dead_letter_queue_name = os.getenv("DEAD_LETTER_QUEUE_NAME", "dead_letter_queue")
        self.playwright_browser = playwright_browser # New: Store playwright_browser

    async def _is_duplicate_backlink(self, source_url: str, target_url: str) -> bool:
        """
        Checks if a backlink (source_url, target_url pair) has already been processed
        using a Redis set for deduplication.
        Returns True if it's a duplicate (already in set), False otherwise.
        """
        if not self.redis:
            self.logger.warning("Redis client not available for deduplication. Skipping backlink deduplication.")
            return False
        
        try:
            backlink_id = f"{source_url}|{target_url}"
            is_new = await self.redis.sadd(self.deduplication_set_key, backlink_id)
            
            if is_new == 0:
                self.logger.debug(f"Duplicate backlink detected: {source_url} -> {target_url}")
                return True
            else:
                return False
        except Exception as e:
            self.logger.error(f"Error during Redis deduplication for {source_url} -> {target_url}: {e}. Skipping deduplication for this link.", exc_info=True)
            return False

    async def _send_to_dead_letter_queue(self, job: CrawlJob, error_message: str):
        """Sends a failed job's details to a Redis dead-letter queue."""
        if not self.redis:
            self.logger.error(f"Redis client not available. Cannot send job {job.id} to dead-letter queue.")
            return
        
        try:
            job_data = serialize_model(job)
            job_data['dead_letter_reason'] = error_message
            job_data['dead_letter_timestamp'] = datetime.now().isoformat()
            
            await self.redis.rpush(self.dead_letter_queue_name, json.dumps(job_data))
            self.logger.warning(f"Job {job.id} sent to dead-letter queue. Reason: {error_message}")
        except Exception as e:
            self.logger.error(f"Failed to send job {job.id} to dead-letter queue: {e}", exc_info=True)

    async def create_and_start_crawl_job(
        self, 
        job_type: str,
        target_url: Optional[str] = None,
        initial_seed_urls: Optional[List[str]] = None,
        keyword: Optional[str] = None,
        num_results: Optional[int] = None,
        source_urls_to_audit: Optional[List[str]] = None,
        urls_to_audit_tech: Optional[List[str]] = None,
        domain_names_to_analyze: Optional[List[str]] = None,
        min_value_score: Optional[float] = None,
        limit: Optional[int] = None,
        config: Optional[CrawlConfig] = None
    ) -> CrawlJob:
        """
        Creates a new crawl job of a specified type and starts it.
        
        Args:
            job_type: The type of job ('backlink_discovery', 'serp_analysis', 'keyword_research', 'link_health_audit', 'technical_audit', 'domain_analysis', 'full_seo_audit').
            target_url: The primary URL relevant to the job (e.g., for backlink discovery).
            initial_seed_urls: Optional list of URLs to start crawling from (for backlink discovery).
            keyword: Optional keyword for SERP or keyword research jobs.
            num_results: Optional number of results/suggestions to fetch for SERP/keyword jobs.
            source_urls_to_audit: Optional list of URLs whose outgoing links should be audited (for link_health_audit).
            urls_to_audit_tech: Optional list of URLs for technical audit.
            domain_names_to_analyze: Optional list of domain names for domain analysis.
            min_value_score: Optional minimum value score for domain analysis.
            limit: Optional limit for domain analysis results.
            config: Optional CrawlConfig object. If None, a default config is used.
        
        Returns:
            The created CrawlJob object.
        """
        job_id = str(uuid4())
        if config is None:
            config = CrawlConfig()

        respect_robots_txt_env = os.getenv("RESPECT_ROBOTS_TXT", "true").lower()
        config.respect_robots_txt = respect_robots_txt_env == "true"

        if job_type == 'backlink_discovery' and target_url:
            parsed_target_domain = urlparse(target_url).netloc
            if config.allowed_domains and parsed_target_domain not in config.allowed_domains:
                config.allowed_domains.add(parsed_target_domain)

        job = CrawlJob(
            id=job_id,
            target_url=target_url or keyword or (urls_to_audit_tech[0] if urls_to_audit_tech else None) or (domain_names_to_analyze[0] if domain_names_to_analyze else "N/A"),
            job_type=job_type,
            status=CrawlStatus.PENDING,
            config=serialize_model(config)
        )
        self.db.add_crawl_job(job)
        self.logger.info(f"Created {job_type} job {job_id} for {job.target_url}")
        JOBS_PENDING.labels(job_type=job_type).inc()

        if job_type == 'backlink_discovery':
            if not initial_seed_urls or not target_url:
                raise ValueError("initial_seed_urls and target_url must be provided for 'backlink_discovery' job type.")
            asyncio.create_task(self._run_backlink_crawl(job, initial_seed_urls, config))
        elif job_type == 'serp_analysis':
            if not keyword:
                raise ValueError("keyword must be provided for 'serp_analysis' job type.")
            asyncio.create_task(self._run_serp_analysis_job(job, keyword, num_results, config))
        elif job_type == 'keyword_research':
            if not keyword:
                raise ValueError("keyword must be provided for 'keyword_research' job type.")
            asyncio.create_task(self._run_keyword_research_job(job, keyword, num_results))
        elif job_type == 'link_health_audit':
            if not source_urls_to_audit:
                raise ValueError("source_urls_to_audit must be provided for 'link_health_audit' job type.")
            asyncio.create_task(self._run_link_health_audit_job(job, source_urls_to_audit))
        elif job_type == 'technical_audit':
            if not urls_to_audit_tech:
                raise ValueError("urls_to_audit_tech must be provided for 'technical_audit' job type.")
            asyncio.create_task(self._run_technical_audit_job(job, urls_to_audit_tech, config))
        elif job_type == 'domain_analysis':
            if not domain_names_to_analyze:
                raise ValueError("domain_names_to_analyze must be provided for 'domain_analysis' job type.")
            asyncio.create_task(self._run_domain_analysis_job(job, domain_names_to_analyze, min_value_score, limit))
        elif job_type == 'full_seo_audit':
            if not urls_to_audit_tech:
                raise ValueError("urls_to_audit_full_seo must be provided for 'full_seo_audit' job type.")
            asyncio.create_task(self._run_full_seo_audit_job(job, urls_to_audit_tech, config))
        else:
            raise ValueError(f"Unknown job type: {job_type}")
        
        return job

    async def execute_predefined_job(
        self,
        job: CrawlJob,
        initial_seed_urls: Optional[List[str]] = None,
        keyword: Optional[str] = None,
        num_results: Optional[int] = None,
        source_urls_to_audit: Optional[List[str]] = None,
        urls_to_audit_tech: Optional[List[str]] = None,
        domain_names_to_analyze: Optional[List[str]] = None,
        min_value_score: Optional[float] = None,
        limit: Optional[int] = None
    ):
        """
        Executes a pre-defined CrawlJob object. This method is intended to be called
        by the JobCoordinator or SatelliteCrawler after a job is dequeued.
        """
        config = CrawlConfig.from_dict(job.config)

        JOBS_PENDING.labels(job_type=job.job_type).dec()
        JOBS_IN_PROGRESS.labels(job_type=job.job_type).inc()

        job.status = CrawlStatus.IN_PROGRESS
        job.started_date = datetime.now()
        self.db.update_crawl_job(job)
        self.logger.info(f"Executing {job.job_type} job {job.id} for {job.target_url}")

        try:
            if config.anomaly_detection_enabled:
                anomaly_detector.reset_history()

            if job.job_type == 'backlink_discovery':
                initial_seed_urls_from_config = job.config.get("initial_seed_urls", [])
                if not initial_seed_urls_from_config or not job.target_url:
                    raise ValueError("initial_seed_urls and target_url must be provided for 'backlink_discovery' job type.")
                await self._run_backlink_crawl(job, initial_seed_urls_from_config, config)
            elif job.job_type == 'serp_analysis':
                keyword_from_config = job.config.get("keyword")
                num_results_from_config = job.config.get("num_results")
                if not keyword_from_config:
                    raise ValueError("keyword must be provided for 'serp_analysis' job type.")
                await self._run_serp_analysis_job(job, keyword_from_config, num_results_from_config, config)
            elif job.job_type == 'keyword_research':
                seed_keyword_from_config = job.config.get("seed_keyword")
                num_suggestions_from_config = job.config.get("num_suggestions")
                if not seed_keyword_from_config:
                    raise ValueError("seed_keyword must be provided for 'keyword_research' job type.")
                await self._run_keyword_research_job(job, seed_keyword_from_config, num_suggestions_from_config)
            elif job.job_type == 'link_health_audit':
                source_urls_to_audit_from_config = job.config.get("source_urls_to_audit", [])
                if not source_urls_to_audit_from_config:
                    raise ValueError("source_urls_to_audit must be provided for 'link_health_audit' job type.")
                await self._run_link_health_audit_job(job, source_urls_to_audit_from_config)
            elif job.job_type == 'technical_audit':
                urls_to_audit_tech_from_config = job.config.get("urls_to_audit_tech", [])
                if not urls_to_audit_tech_from_config:
                    raise ValueError("urls_to_audit_tech must be provided for 'technical_audit' job type.")
                await self._run_technical_audit_job(job, urls_to_audit_tech_from_config, config)
            elif job.job_type == 'domain_analysis':
                domain_names_to_analyze_from_config = job.config.get("domain_names_to_analyze", [])
                min_value_score_from_config = job.config.get("min_value_score")
                limit_from_config = job.config.get("limit")
                if not domain_names_to_analyze_from_config:
                    raise ValueError("domain_names_to_analyze must be provided for 'domain_analysis' job type.")
                await self._run_domain_analysis_job(job, domain_names_to_analyze_from_config, min_value_score_from_config, limit_from_config)
            elif job.job_type == 'full_seo_audit':
                urls_to_audit_full_seo = job.config.get("urls_to_audit_full_seo", [])
                if not urls_to_audit_full_seo:
                    raise ValueError("urls_to_audit_full_seo must be provided for 'full_seo_audit' job type.")
                await self._run_full_seo_audit_job(job, urls_to_audit_full_seo, config)
            else:
                raise ValueError(f"Unknown job type: {job.job_type}")
            
            job.status = CrawlStatus.COMPLETED
            self.logger.info(f"Job {job.id} completed successfully.")
            JOBS_IN_PROGRESS.labels(job_type=job.job_type).dec()
            JOBS_COMPLETED_SUCCESS_TOTAL.labels(job_type=job.job_type).inc()

        except Exception as e:
            job.status = CrawlStatus.FAILED
            job.add_error(url="N/A", error_type=f"{job.job_type}Error", message=f"Job execution failed: {str(e)}", details=str(e))
            self.logger.error(f"Job {job.id} failed: {e}", exc_info=True)
            JOBS_IN_PROGRESS.labels(job_type=job.job_type).dec()
            JOBS_FAILED_TOTAL.labels(job_type=job.job_type).inc()
            JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type=f"{job.job_type}Error").inc()
            await self._send_to_dead_letter_queue(job, f"Job execution failed: {str(e)}")
        finally:
            job.completed_date = datetime.now()
            self.db.update_crawl_job(job)
            if job.id in self.active_crawlers:
                del self.active_crawlers[job.id]

    async def _filter_and_score_backlinks(self, backlinks: List[Backlink], config: CrawlConfig) -> List[Backlink]:
        """
        Applies quality filtering and scoring to a list of backlinks based on configuration.
        """
        filtered_backlinks: List[Backlink] = []
        
        spam_filtering_enabled = config_loader.get("quality_assurance.spam_filtering", False)
        data_quality_scoring_enabled = config_loader.get("quality_assurance.data_quality_scoring", False)
        
        if not spam_filtering_enabled and not data_quality_scoring_enabled:
            self.logger.debug("Backlink quality assurance and spam filtering are disabled. Returning all backlinks.")
            return backlinks

        for backlink in backlinks:
            is_valid = True
            reasons_for_filtering = []

            if spam_filtering_enabled:
                if backlink.spam_level == SpamLevel.CONFIRMED_SPAM:
                    is_valid = False
                    reasons_for_filtering.append(f"Confirmed spam ({backlink.spam_level.value})")
                elif backlink.spam_level == SpamLevel.LIKELY_SPAM and backlink.source_domain_metrics.get("spam_score", 0) > 40:
                    is_valid = False
                    reasons_for_filtering.append(f"Likely spam ({backlink.spam_level.value}, score {backlink.source_domain_metrics.get('spam_score')})")
                elif backlink.spam_level == SpamLevel.SUSPICIOUS and backlink.source_domain_metrics.get("spam_score", 0) > 70:
                    is_valid = False
                    reasons_for_filtering.append(f"Highly suspicious ({backlink.spam_level.value}, score {backlink.source_domain_metrics.get('spam_score')})")

            if data_quality_scoring_enabled and is_valid:
                source_domain_authority = backlink.source_domain_metrics.get("authority_score", 0.0)
                source_domain_trust = backlink.source_domain_metrics.get("trust_score", 0.0)
                
                if source_domain_authority < 5.0:
                    is_valid = False
                    reasons_for_filtering.append(f"Very low source domain authority ({source_domain_authority:.1f})")
                
            if is_valid:
                filtered_backlinks.append(backlink)
            else:
                self.logger.info(f"Filtered out backlink {backlink.source_url} -> {backlink.target_url}. Reasons: {', '.join(reasons_for_filtering)}")

        self.logger.info(f"Filtered {len(backlinks) - len(filtered_backlinks)} backlinks. {len(filtered_backlinks)} remaining after quality checks.")
        return filtered_backlinks

    async def _run_backlink_crawl(self, job: CrawlJob, initial_seed_urls: List[str], config: CrawlConfig):
        """
        Internal method to execute the backlink crawl.
        """
        self.logger.info(f"Starting backlink crawl logic for job {job.id} for {job.target_url}")

        # Pass playwright_browser to WebCrawler
        crawler = WebCrawler(config, self.db, job.id, self.ai_service, playwright_browser=self.playwright_browser)
        self.active_crawlers[job.id] = crawler

        discovered_backlinks: List[Backlink] = []
        urls_crawled_count = 0
        
        debug_file_path = os.path.join("data", f"crawl_results_debug_{job.id}.jsonl")
        os.makedirs(os.path.dirname(debug_file_path), exist_ok=True)

        self.logger.info(f"Attempting to fetch backlinks for {job.target_url} from API.")
        async with self.backlink_service as bs:
            api_backlinks = await bs.get_backlinks_from_api(job.target_url)
                
            if api_backlinks:
                self.logger.info(f"Found {len(api_backlinks)} backlinks from API for {job.target_url}.")
                
                deduplicated_api_backlinks = []
                for bl in api_backlinks:
                    if not await self._is_duplicate_backlink(bl.source_url, bl.target_url):
                        deduplicated_api_backlinks.append(bl)
                
                filtered_api_backlinks = await self._filter_and_score_backlinks(deduplicated_api_backlinks, config)

                if filtered_api_backlinks:
                    discovered_backlinks.extend(filtered_api_backlinks)
                    job.links_found = len(discovered_backlinks)
                    try:
                        self.db.add_backlinks(filtered_api_backlinks)
                        if self.clickhouse_loader:
                            await self.clickhouse_loader.bulk_insert_backlinks(filtered_api_backlinks)
                        BACKLINKS_FOUND_TOTAL.labels(job_type=job.job_type).inc(len(filtered_api_backlinks))
                        self.logger.info(f"Successfully added {len(filtered_api_backlinks)} new API backlinks to the database after filtering.")
                    except Exception as db_e:
                        self.logger.error(f"Error adding API backlinks to database: {db_e}", exc_info=True)
                        job.add_error(url="N/A", error_type="DatabaseError", message=f"DB error adding API backlinks: {str(db_e)}", details=str(db_e))
                        JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="DatabaseError").inc()
                else:
                    self.logger.info(f"All {len(api_backlinks)} API backlinks for {job.target_url} were either duplicates or filtered out.")
            else:
                self.logger.info(f"No backlinks found from API for {job.target_url}. Proceeding with web crawl.")

            with open(debug_file_path, 'a', encoding='utf-8') as debug_file:
                async with crawler as wc:
                    urls_to_crawl_queue = asyncio.Queue()
                    for url in initial_seed_urls:
                        await urls_to_crawl_queue.put((url, 0))

                    crawled_urls_set = set()

                    while not urls_to_crawl_queue.empty() and urls_crawled_count < config.max_pages:
                        
                        url, current_depth = await urls_to_crawl_queue.get()

                        if url in crawled_urls_set:
                            continue
                        if current_depth >= config.max_depth:
                            self.logger.debug(f"Skipping {url} due to max depth ({current_depth})")
                            continue
                        
                        crawled_urls_set.add(url)
                        urls_crawled_count += 1
                        job.urls_crawled = urls_crawled_count
                        CRAWLED_URLS_TOTAL.labels(job_type=job.job_type).inc()

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
                                            JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="CrawlError").inc()
                                    elif crawl_result.error_message in ["CAPTCHA_DETECTED_AND_SOLVING_ATTEMPTED", "CAPTCHA_DETECTED_AND_SOLVING_DISABLED"]:
                                        self.logger.warning(f"Crawl for {url} stopped due to CAPTCHA: {crawl_result.error_message}")
                                        job.add_error(url=url, error_type="CAPTCHA_BLOCKED", message=f"Crawl blocked by CAPTCHA: {crawl_result.error_message}", details=crawl_result.error_message)
                                        JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="CAPTCHA_BLOCKED").inc()
                                    else:
                                        self.logger.warning(f"Failed to crawl {url}: {crawl_result.error_message}")
                                        job.add_error(url=url, error_type="CrawlError", message=f"Non-retryable crawl error: {crawl_result.error_message}", details=crawl_result.error_message)
                                        JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="CrawlError").inc()
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
                                    JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="UnexpectedError").inc()
                            crawl_result = None

                        if crawl_result:
                            try:
                                crawl_result_dict = serialize_model(crawl_result)
                                debug_file.write(json.dumps(crawl_result_dict) + '\n')
                                debug_file.flush()
                            except Exception as e:
                                self.logger.error(f"Error writing crawl result to debug file for {crawl_result.url}: {e}")
                                job.add_error(url=crawl_result.url, error_type="FileWriteError", message=f"Error writing debug data: {str(e)}", details=str(e))
                                JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="FileWriteError").inc()

                            if crawl_result.anomaly_flags:
                                job.anomalies_detected.extend(crawl_result.anomaly_flags)
                                job.anomalies_detected = list(set(job.anomalies_detected))

                            if crawl_result.links_found:
                                self.logger.info(f"Found {len(crawl_result.links_found)} backlinks on {crawl_result.url} via crawl.")
                                
                                deduplicated_crawled_backlinks = []
                                for bl in crawl_result.links_found:
                                    if not await self._is_duplicate_backlink(bl.source_url, bl.target_url):
                                        deduplicated_crawled_backlinks.append(bl)

                                filtered_crawled_backlinks = await self._filter_and_score_backlinks(deduplicated_crawled_backlinks, config)

                                if filtered_crawled_backlinks:
                                    discovered_backlinks.extend(filtered_crawled_backlinks)
                                    job.links_found = len(discovered_backlinks)
                                    try:
                                        self.db.add_backlinks(filtered_crawled_backlinks) 
                                        if self.clickhouse_loader:
                                            await self.clickhouse_loader.bulk_insert_backlinks(filtered_crawled_backlinks)
                                        BACKLINKS_FOUND_TOTAL.labels(job_type=job.job_type).inc(len(filtered_crawled_backlinks))
                                    except Exception as db_e:
                                        self.logger.error(f"Error adding crawled backlinks to database for {crawl_result.url}: {db_e}", exc_info=True)
                                        job.add_error(url=crawl_result.url, error_type="DatabaseError", message=f"DB error adding crawled backlinks: {str(db_e)}", details=str(db_e))
                                        JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="DatabaseError").inc()
                                else:
                                    self.logger.info(f"All {len(crawl_result.links_found)} crawled backlinks from {crawl_result.url} were either duplicates or filtered out.")
                            
                            self.logger.debug(f"CrawlResult.seo_metrics for {crawl_result.url}: {crawl_result.seo_metrics}")
                            if crawl_result.seo_metrics:
                                if crawl_result.validation_issues:
                                    crawl_result.seo_metrics.validation_issues.extend(crawl_result.validation_issues)
                                    crawl_result.seo_metrics.calculate_seo_score()
                                try:
                                    self.db.save_seo_metrics(crawl_result.seo_metrics)
                                    if self.clickhouse_loader:
                                        await self.clickhouse_loader.bulk_insert_seo_metrics([crawl_result.seo_metrics])
                                    self.logger.info(f"Saved SEO metrics for {crawl_result.url}.")
                                except Exception as seo_e:
                                    self.logger.error(f"Error saving SEO metrics for {crawl_result.url}: {seo_e}", exc_info=True)
                                    job.add_error(url=crawl_result.url, error_type="DatabaseError", message=f"DB error saving SEO metrics: {str(seo_e)}", details=str(seo_e))
                                    JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="DatabaseError").inc()

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
                    self.logger.warning(f"Could not retrieve domain info for target domain: {target_domain_name}.")
                    job.add_error(url=target_domain_name, error_type="DomainInfoError", message=f"Could not retrieve domain info for target domain.", details="Domain info API returned None.")
                    JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="DomainInfoError").inc()

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
                            self.logger.warning(f"Could not retrieve domain info for referring domain: {referring_domain_obj.name if referring_domain_obj else 'N/A'}.")

            if discovered_backlinks:
                self.logger.info("Enriching discovered backlinks with source domain metrics and updating in DB.")
                for backlink in discovered_backlinks:
                    source_domain_obj = self.db.get_domain(backlink.source_domain)
                    if source_domain_obj:
                        backlink.source_domain_metrics = {
                            "authority_score": source_domain_obj.authority_score,
                            "trust_score": source_domain_obj.trust_score,
                            "spam_score": source_domain_obj.spam_score,
                            "age_days": source_domain_obj.age_days,
                            "total_pages": source_domain_obj.total_pages,
                            "total_backlinks": source_domain_obj.total_backlinks,
                            "referring_domains": source_domain_obj.referring_domains,
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

            if job.anomalies_detected:
                self.logger.critical(f"Job {job.id} completed with detected anomalies: {job.anomalies_detected}. ALERTING SYSTEM TRIGGERED (simulated).")

    async def _run_serp_analysis_job(self, job: CrawlJob, keyword: str, num_results: Optional[int], config: CrawlConfig):
        """
        Internal method to execute a SERP analysis job.
        """
        self.logger.info(f"Starting SERP analysis logic for job {job.id} for keyword: '{keyword}'")

        async with self.serp_service as ss:
            serp_results = await ss.get_serp_data(keyword, num_results or 10)
        
        if serp_results:
            self.logger.info(f"Found {len(serp_results)} SERP results for '{keyword}'.")
            try:
                await self.db.add_serp_results(serp_results)
                if self.clickhouse_loader:
                    await self.clickhouse_loader.bulk_insert_serp_results(serp_results)
                self.logger.info(f"Successfully added {len(serp_results)} SERP results to the database.")
            except Exception as db_e:
                self.logger.error(f"Error adding SERP results to database: {db_e}", exc_info=True)
                job.add_error(url="N/A", error_type="DatabaseError", message=f"DB error adding SERP results: {str(db_e)}", details=str(db_e))
                JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="DatabaseError").inc()
            
            job.results['serp_results'] = [serialize_model(res) for res in serp_results]
            job.urls_discovered = len(serp_results)
            job.progress_percentage = 100.0
            self.logger.info(f"SERP analysis job {job.id} completed for '{keyword}'.")
        else:
            job.results['serp_results'] = []
            job.progress_percentage = 100.0
            self.logger.info(f"No SERP results found for '{keyword}'. Job {job.id} completed.")

        if config.anomaly_detection_enabled:
            if not serp_results:
                job.anomalies_detected.append("No SERP Results Found")
            
            if job.anomalies_detected:
                self.logger.critical(f"Job {job.id} completed with detected anomalies: {job.anomalies_detected}. ALERTING SYSTEM TRIGGERED (simulated).")

    async def _run_keyword_research_job(self, job: CrawlJob, seed_keyword: str, num_suggestions: Optional[int]):
        """
        Internal method to execute a keyword research job.
        """
        self.logger.info(f"Starting keyword research logic for job {job.id} for seed: '{seed_keyword}'")

        async with self.keyword_service as ks:
            suggestions = await ks.get_keyword_data(seed_keyword, num_suggestions or 10)
        
        if suggestions:
            self.logger.info(f"Found {len(suggestions)} keyword suggestions for '{seed_keyword}'.")
            try:
                await self.db.add_keyword_suggestions(suggestions)
                if self.clickhouse_loader:
                    await self.clickhouse_loader.bulk_insert_keyword_suggestions(suggestions)
                self.logger.info(f"Successfully added {len(suggestions)} keyword suggestions to the database.")
            except Exception as db_e:
                self.logger.error(f"Error adding keyword suggestions to database: {db_e}", exc_info=True)
                job.add_error(url="N/A", error_type="DatabaseError", message=f"DB error adding keyword suggestions: {str(db_e)}", details=str(db_e))
                JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="DatabaseError").inc()
            
            job.results['keyword_suggestions'] = [serialize_model(sug) for sug in suggestions]
            job.urls_discovered = len(suggestions)
            job.progress_percentage = 100.0
            self.logger.info(f"Keyword research job {job.id} completed for '{seed_keyword}'.")
        else:
            job.results['keyword_suggestions'] = []
            job.progress_percentage = 100.0
            self.logger.info(f"No keyword suggestions found for '{seed_keyword}'. Job {job.id} completed.")

        if job.config.get("anomaly_detection_enabled", False):
            if not suggestions:
                job.anomalies_detected.append("No Keyword Suggestions Found")
            
            if job.anomalies_detected:
                self.logger.critical(f"Job {job.id} completed with detected anomalies: {job.anomalies_detected}. ALERTING SYSTEM TRIGGERED (simulated).")

    async def _run_link_health_audit_job(self, job: CrawlJob, source_urls: List[str]):
        """
        Internal method to execute a link health audit job.
        """
        self.logger.info(f"Starting link health audit logic for job {job.id} for {len(source_urls)} source URLs.")

        async with self.link_health_service as lhs:
            broken_links_found = await lhs.audit_links_for_source_urls(source_urls)
        
        job.results['broken_links_audit'] = broken_links_found
        job.urls_discovered = len(source_urls)
        job.links_found = sum(len(links) for links in broken_links_found.values())
        job.progress_percentage = 100.0
        self.logger.info(f"Link health audit job {job.id} completed. Found {job.links_found} broken links.")

        if job.config.get("anomaly_detection_enabled", False):
            if job.links_found > 0:
                job.anomalies_detected.append(f"Broken Links Detected ({job.links_found})")
            
            if job.anomalies_detected:
                self.logger.critical(f"Job {job.id} completed with detected anomalies: {job.anomalies_detected}. ALERTING SYSTEM TRIGGERED (simulated).")

    async def _run_technical_audit_job(self, job: CrawlJob, urls_to_audit: List[str], config: CrawlConfig):
        """
        Internal method to execute a technical audit job using Lighthouse.
        """
        self.logger.info(f"Starting technical audit logic for job {job.id} for {len(urls_to_audit)} URLs.")

        audited_urls_count = 0
        processed_seo_metrics: List[SEOMetrics] = []
        for url in urls_to_audit:
            current_job = self.db.get_crawl_job(job.id)
            if current_job:
                if current_job.status == CrawlStatus.PAUSED:
                    self.logger.info(f"Technical audit for job {job.id} paused. Waiting to resume...")
                    while True:
                        await asyncio.sleep(5)
                        rechecked_job = self.db.get_crawl_job(job.id)
                        if rechecked_job and rechecked_job.status == CrawlStatus.IN_PROGRESS:
                            self.logger.info(f"Technical audit for job {job.id} resumed.")
                            break
                        elif rechecked_job and rechecked_job.status == CrawlStatus.STOPPED:
                            self.logger.info(f"Technical audit for job {job.id} stopped during pause.")
                            job.status = CrawlStatus.STOPPED
                            return
                elif current_job.status == CrawlStatus.STOPPED:
                    self.logger.info(f"Technical audit for job {job.id} stopped.")
                    job.status = CrawlStatus.STOPPED
                    return

            try:
                lighthouse_metrics = await self.technical_auditor.run_lighthouse_audit(url, config)
                
                if lighthouse_metrics:
                    crawled_url_obj = self.db.get_url(url)
                    html_content = crawled_url_obj.content if crawled_url_obj and crawled_url_obj.content_type == ContentType.HTML else ""

                    if self.ai_service.enabled:
                        ai_content_analysis = await self.ai_service.score_content(html_content, job.target_url)
                        if ai_content_analysis:
                            lighthouse_metrics.ai_content_score = ai_content_analysis.get("seo_score")
                            lighthouse_metrics.ai_readability_score = ai_content_analysis.get("readability_score")
                            lighthouse_metrics.ai_semantic_keywords = ai_content_analysis.get("semantic_keywords", [])
                            lighthouse_metrics.ai_suggestions.extend(ai_content_analysis.get("improvement_suggestions", []))
                            self.logger.info(f"AI content analysis applied for {url}.")

                    existing_seo_metrics = self.db.get_seo_metrics(url)
                    if existing_seo_metrics:
                        existing_seo_metrics.performance_score = lighthouse_metrics.performance_score
                        existing_seo_metrics.accessibility_score = lighthouse_metrics.accessibility_score
                        existing_seo_metrics.audit_timestamp = lighthouse_metrics.audit_timestamp
                        existing_seo_metrics.ai_content_score = lighthouse_metrics.ai_content_score
                        existing_seo_metrics.ai_readability_score = lighthouse_metrics.ai_readability_score
                        existing_seo_metrics.ai_semantic_keywords = lighthouse_metrics.ai_semantic_keywords
                        existing_seo_metrics.ai_suggestions.extend(lighthouse_metrics.ai_suggestions)
                        existing_seo_metrics.calculate_seo_score()
                        self.db.save_seo_metrics(existing_seo_metrics)
                        processed_seo_metrics.append(existing_seo_metrics)
                        self.logger.info(f"Updated SEO metrics for {url} with Lighthouse and AI scores.")
                    else:
                        self.db.save_seo_metrics(lighthouse_metrics)
                        processed_seo_metrics.append(lighthouse_metrics)
                        self.logger.info(f"Saved new SEO metrics for {url} from Lighthouse and AI.")
                    
                    audited_urls_count += 1
                else:
                    self.logger.warning(f"Lighthouse audit failed or returned no data for {url}.")
                    job.add_error(url=url, error_type="LighthouseAuditError", message=f"Lighthouse audit failed for {url}.", details="No data returned.")
                    JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="LighthouseAuditError").inc()

            except Exception as e:
                self.logger.error(f"Error during technical audit for {url}: {e}", exc_info=True)
                job.add_error(url=url, error_type="TechnicalAuditError", message=f"Technical audit failed for {url}: {str(e)}", details=str(e))
                JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="TechnicalAuditError").inc()
            
            job.urls_crawled = audited_urls_count
            job.progress_percentage = min(99.0, (audited_urls_count / len(urls_to_audit)) * 100)
            self.db.update_crawl_job(job)

        self.logger.info(f"Technical audit job {job.id} completed. Audited {audited_urls_count} URLs.")

        if self.clickhouse_loader and processed_seo_metrics:
            try:
                await self.clickhouse_loader.bulk_insert_seo_metrics(processed_seo_metrics)
                self.logger.info(f"Successfully bulk inserted {len(processed_seo_metrics)} SEO metrics to ClickHouse for job {job.id}.")
            except Exception as e:
                self.logger.error(f"Error during final ClickHouse bulk insert for technical audit job {job.id}: {e}", exc_info=True)
                job.add_error(url="N/A", error_type="ClickHouseError", message=f"ClickHouse bulk insert failed: {str(e)}", details=str(e))
                JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="ClickHouseError").inc()

        if job.config.get("anomaly_detection_enabled", False):
            failed_audits_count = len(urls_to_audit) - audited_urls_count
            if failed_audits_count / len(urls_to_audit) > 0.2:
                job.anomalies_detected.append(f"High Technical Audit Failure Rate ({failed_audits_count}/{len(urls_to_audit)})")
            
            if job.anomalies_detected:
                self.logger.critical(f"Job {job.id} completed with detected anomalies: {job.anomalies_detected}. ALERTING SYSTEM TRIGGERED (simulated).")

    async def _run_domain_analysis_job(self, job: CrawlJob, domain_names: List[str], min_value_score: Optional[float], limit: Optional[int]):
        """
        Internal method to execute a domain analysis job.
        """
        self.logger.info(f"Starting domain analysis logic for job {job.id} for {len(domain_names)} domains.")

        analyzed_domains_count = 0
        valuable_domains_found = []
        
        for domain_name in domain_names:
            current_job = self.db.get_crawl_job(job.id)
            if current_job:
                if current_job.status == CrawlStatus.PAUSED:
                    self.logger.info(f"Domain analysis for job {job.id} paused. Waiting to resume...")
                    while True:
                        await asyncio.sleep(5)
                        rechecked_job = self.db.get_crawl_job(job.id)
                        if rechecked_job and rechecked_job.status == CrawlStatus.IN_PROGRESS:
                            self.logger.info(f"Domain analysis for job {job.id} resumed.")
                            break
                        elif rechecked_job and rechecked_job.status == CrawlStatus.STOPPED:
                            self.logger.info(f"Domain analysis for job {job.id} stopped during pause.")
                            job.status = CrawlStatus.STOPPED
                            return
                elif current_job.status == CrawlStatus.STOPPED:
                    self.logger.info(f"Domain analysis for job {job.id} stopped.")
                    job.status = CrawlStatus.STOPPED
                    return

            try:
                analysis_result = await self.domain_analyzer_service.analyze_domain_for_expiration_value(
                    domain_name,
                    min_authority_score=job.config.get("min_authority_score", 20.0),
                    min_dofollow_backlinks=job.config.get("min_dofollow_backlinks", 5),
                    min_age_days=job.config.get("min_age_days", 365),
                    max_spam_score=job.config.get("max_spam_score", 30.0)
                )
                
                if analysis_result.get("is_valuable") and \
                   (min_value_score is None or analysis_result.get("value_score", 0) >= min_value_score):
                    valuable_domains_found.append(analysis_result)
                    self.logger.info(f"Domain {domain_name} is valuable (Score: {analysis_result.get('value_score'):.2f}).")
                else:
                    self.logger.info(f"Domain {domain_name} is not valuable enough (Score: {analysis_result.get('value_score'):.2f}).")
                
                analyzed_domains_count += 1
                
                if limit and len(valuable_domains_found) >= limit:
                    self.logger.info(f"Domain analysis job {job.id} reached limit of {limit} valuable domains.")
                    break

            except Exception as e:
                self.logger.error(f"Error during domain analysis for {domain_name}: {e}", exc_info=True)
                job.add_error(url=domain_name, error_type="DomainAnalysisError", message=f"Domain analysis failed for {domain_name}: {str(e)}", details=str(e))
                JOB_ERRORS_TOTAL.labels(job_type=job.job_type, error_type="DomainAnalysisError").inc()
            
            job.urls_crawled = analyzed_domains_count
            job.progress_percentage = min(99.0, (analyzed_domains_count / len(domain_names)) * 100)
            self.db.update_crawl_job(job)

        job.results['valuable_domains_found'] = [serialize_model(d) for d in valuable_domains_found]
        job.links_found = len(valuable_domains_found)
        self.logger.info(f"Domain analysis job {job.id} completed. Analyzed {analyzed_domains_count} domains, found {len(valuable_domains_found)} valuable.")

        if job.config.get("anomaly_detection_enabled", False):
            if len(valuable_domains_found) == 0 and len(domain_names) > 0:
                job.anomalies_detected.append("No Valuable Domains Found")
            
            if job.anomalies_detected:
                self.logger.critical(f"Job {job.id} completed with detected anomalies: {job.anomalies_detected}. ALERTING SYSTEM TRIGGERED (simulated).")

    async def _run_full_seo_audit_job(self, job: CrawlJob, urls_to_audit: List[str], config: CrawlConfig):
        """
        Internal method to execute a full SEO audit job.
        This orchestrates technical audit and link health audit for the given URLs.
        """
        self.logger.info(f"Starting full SEO audit logic for job {job.id} for {len(urls_to_audit)} URLs.")

        total_urls = len(urls_to_audit)
        completed_sub_audits = 0
        
        job_results = {}
        job_errors = []

        self.logger.info(f"Running technical audit part of full SEO audit for job {job.id}.")
        try:
            await self._run_technical_audit_job(job, urls_to_audit, config)
            job_results['technical_audit'] = job.results.get('technical_audit', 'Completed')
            completed_sub_audits += 1
        except Exception as e:
            error_msg = f"Technical audit sub-job failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            job_errors.append(CrawlError(url="N/A", error_type="FullSEOAduit_TechnicalAuditError", message=error_msg))
        
        job.progress_percentage = min(99.0, (completed_sub_audits / 2) * 100)
        self.db.update_crawl_job(job)

        self.logger.info(f"Running link health audit part of full SEO audit for job {job.id}.")
        try:
            await self._run_link_health_audit_job(job, urls_to_audit)
            job_results['link_health_audit'] = job.results.get('broken_links_audit', 'Completed')
            completed_sub_audits += 1
        except Exception as e:
            error_msg = f"Link health audit sub-job failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            job_errors.append(CrawlError(url="N/A", error_type="FullSEOAduit_LinkHealthAuditError", message=error_msg))

        job.progress_percentage = min(99.0, (completed_sub_audits / 2) * 100)
        self.db.update_crawl_job(job)

        job.results['full_seo_audit_summary'] = {
            "status": "Completed with errors" if job_errors else "Completed successfully",
            "sub_audits_completed": completed_sub_audits,
            "total_urls_audited": total_urls,
            "errors": [serialize_model(err) for err in job_errors]
        }
        job.error_log.extend(job_errors)
        job.errors_count = len(job.error_log)
        
        self.logger.info(f"Full SEO audit job {job.id} completed. Sub-audits: {completed_sub_audits}/2.")

        if job.config.get("anomaly_detection_enabled", False):
            if job.anomalies_detected:
                self.logger.critical(f"Job {job.id} completed with detected anomalies: {job.anomalies_detected}. ALERTING SYSTEM TRIGGERED (simulated).")


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
            raise ValueError(f"Crawl job {job_id} cannot be stopped from status {job.status.value}.")

    def get_link_profile_for_url(self, target_url: str) -> Optional[LinkProfile]:
        """Retrieves the link profile for a given URL."""
        return self.db.get_link_profile(target_url)

    def get_backlinks_for_url(self, target_url: str) -> List[Backlink]:
        """Retrieves all raw backlinks for a given URL."""
        return self.db.get_backlinks_for_target(target_url)
