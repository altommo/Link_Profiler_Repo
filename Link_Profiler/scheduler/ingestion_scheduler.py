import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import asyncio
import uuid
import json # Added missing import for json.dumps

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.redis import RedisJobStore # Assuming Redis is used for job store
import redis.asyncio as redis # Added import for redis.asyncio

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.database.database import db, clickhouse_client
from Link_Profiler.monitoring.prometheus_metrics import (
    INGESTION_JOB_RUNS_TOTAL, INGESTION_JOB_DURATION_SECONDS, INGESTION_DATA_VOLUME_RECORDS
)
from Link_Profiler.core.models import TrackedDomain, TrackedKeyword, GSCBacklink, KeywordTrend, SEOMetrics, SERPResult, Backlink, Domain # Import necessary dataclasses
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager

# Import all necessary clients and services
from Link_Profiler.clients.google_trends_client import GoogleTrendsClient
from Link_Profiler.clients.google_search_console_client import GoogleSearchConsoleClient
from Link_Profiler.clients.news_api_client import NewsAPIClient
from Link_Profiler.clients.nominatim_client import NominatimClient
from Link_Profiler.clients.reddit_client import RedditClient
from Link_Profiler.clients.security_trails_client import SecurityTrailsClient
from Link_Profiler.clients.ssl_labs_client import SSLLabsClient
from Link_Profiler.clients.common_crawl_client import CommonCrawlClient
from Link_Profiler.clients.whois_client import WHOISClient
from Link_Profiler.clients.dns_client import DNSClient
from Link_Profiler.clients.youtube_client import YouTubeClient
from Link_Profiler.clients.google_pagespeed_client import PageSpeedClient

from Link_Profiler.services.domain_service import DomainService # For technical audits, WHOIS & DNS
from Link_Profiler.services.backlink_service import BacklinkService # For backlink crawler
from Link_Profiler.services.serp_service import SerpService # For SERP scraper
from Link_Profiler.services.keyword_service import KeywordService # For keyword scraper
from Link_Profiler.services.social_media_service import SocialMediaService # For NewsAPI/Reddit
from Link_Profiler.services.historical_data_service import HistoricalDataService # For Common Crawl

logger = logging.getLogger(__name__)

class IngestionScheduler:
    """
    Manages scheduled ingestion jobs for various data types using APScheduler.
    Each job reads from tracked entities, calls hardened clients, upserts results,
    and emits Prometheus metrics.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(IngestionScheduler, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self,
                 session_manager: SessionManager,
                 resilience_manager: DistributedResilienceManager,
                 api_quota_manager: APIQuotaManager,
                 redis_url: str,
                 redis_client: redis.Redis): # Added redis_client to init signature
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".IngestionScheduler")

        # Initialize APScheduler
        jobstores = {
            'default': RedisJobStore(jobs_key='apscheduler.jobs', run_times_key='apscheduler.run_times', host=redis_url.split('@')[-1].split(':')[0], port=int(redis_url.split(':')[-1].split('/')[0]), db=int(redis_url.split('/')[-1]))
        }
        self.scheduler = AsyncIOScheduler(jobstores=jobstores)

        # Initialize clients and services
        self.session_manager = session_manager
        self.resilience_manager = resilience_manager
        self.api_quota_manager = api_quota_manager
        self.redis_client = redis_client # Stored redis_client as instance variable

        # Clients (passed to services)
        self.google_trends_client = GoogleTrendsClient(session_manager, resilience_manager, api_quota_manager)
        self.google_search_console_client = GoogleSearchConsoleClient(session_manager, resilience_manager, api_quota_manager)
        self.news_api_client = NewsAPIClient(session_manager, resilience_manager, api_quota_manager)
        self.nominatim_client = NominatimClient(session_manager, resilience_manager, api_quota_manager)
        self.reddit_client = RedditClient(session_manager, resilience_manager, api_quota_manager)
        self.security_trails_client = SecurityTrailsClient(session_manager, resilience_manager, api_quota_manager)
        self.ssl_labs_client = SSLLabsClient(session_manager, resilience_manager, api_quota_manager)
        self.common_crawl_client = CommonCrawlClient(session_manager, resilience_manager, api_quota_manager)
        self.whois_client = WHOISClient(session_manager, resilience_manager, api_quota_manager)
        self.dns_client = DNSClient(session_manager, resilience_manager, api_quota_manager)
        self.youtube_client = YouTubeClient(session_manager, resilience_manager, api_quota_manager)
        self.pagespeed_client = PageSpeedClient(session_manager, resilience_manager, api_quota_manager)

        # Services (orchestrate clients and DB operations)
        # Passed self.redis_client to services that need it
        self.domain_service = DomainService(db, None, session_manager, resilience_manager, api_quota_manager, self.redis_client) # SmartAPIRouterService is None for now
        self.backlink_service = BacklinkService(db, None, session_manager, resilience_manager, api_quota_manager) # SmartAPIRouterService is None for now
        self.serp_service = SerpService(db, None, session_manager, resilience_manager, api_quota_manager) # SmartAPIRouterService is None for now
        self.keyword_service = KeywordService(db, None, session_manager, resilience_manager, api_quota_manager) # SmartAPIRouterService is None for now
        self.social_media_service = SocialMediaService(db, None, session_manager, resilience_manager, api_quota_manager) # SmartAPIRouterService is None for now
        self.historical_data_service = HistoricalDataService(db, None, session_manager, resilience_manager, api_quota_manager) # SmartAPIRouterService is None for now

        self._add_jobs()

    def _add_jobs(self):
        """Adds all scheduled jobs to the scheduler."""
        self.logger.info("Adding ingestion jobs to scheduler.")

        # Google Trends (daily @ 02:00 UTC)
        self.scheduler.add_job(self._run_google_trends_ingestion, CronTrigger(hour=2, minute=0, timezone='UTC'), id='google_trends_daily', replace_existing=True)

        # GSC analytics (hourly/daily) - Example: daily at 02:30 UTC
        self.scheduler.add_job(self._run_gsc_analytics_ingestion, CronTrigger(hour=2, minute=30, timezone='UTC'), id='gsc_analytics_daily', replace_existing=True)

        # Backlink crawler (every 6h)
        self.scheduler.add_job(self._run_backlink_crawler_ingestion, CronTrigger(hour='*/6', timezone='UTC'), id='backlink_crawler_6h', replace_existing=True)

        # SERP scraper (every 3h)
        self.scheduler.add_job(self._run_serp_scraper_ingestion, CronTrigger(hour='*/3', timezone='UTC'), id='serp_scraper_3h', replace_existing=True)

        # Technical audits (daily @ 03:00 UTC)
        self.scheduler.add_job(self._run_technical_audits_ingestion, CronTrigger(hour=3, minute=0, timezone='UTC'), id='technical_audits_daily', replace_existing=True)

        # Keyword scraper (daily @ 04:00 UTC)
        self.scheduler.add_job(self._run_keyword_scraper_ingestion, CronTrigger(hour=4, minute=0, timezone='UTC'), id='keyword_scraper_daily', replace_existing=True)

        # SSL Labs (weekly) - Example: every Sunday at 05:00 UTC
        self.scheduler.add_job(self._run_ssl_labs_ingestion, CronTrigger(day_of_week='sun', hour=5, minute=0, timezone='UTC'), id='ssl_labs_weekly', replace_existing=True)

        # WHOIS & DNS (weekly) - Example: every Sunday at 05:30 UTC
        self.scheduler.add_job(self._run_whois_dns_ingestion, CronTrigger(day_of_week='sun', hour=5, minute=30, timezone='UTC'), id='whois_dns_weekly', replace_existing=True)

        # NewsAPI/Reddit (daily/hourly) - Example: hourly
        self.scheduler.add_job(self._run_newsapi_reddit_ingestion, CronTrigger(hour='*', minute=0, timezone='UTC'), id='newsapi_reddit_hourly', replace_existing=True)

        # Common Crawl (weekly) - Example: every Sunday at 06:00 UTC
        self.scheduler.add_job(self._run_common_crawl_ingestion, CronTrigger(day_of_week='sun', hour=6, minute=0, timezone='UTC'), id='common_crawl_weekly', replace_existing=True)

    async def start(self):
        """Starts the APScheduler."""
        self.logger.info("Starting Ingestion Scheduler.")
        self.scheduler.start()

    async def shutdown(self):
        """Shuts down the APScheduler."""
        self.logger.info("Shutting down Ingestion Scheduler.")
        self.scheduler.shutdown()

    async def _execute_ingestion_job(self, job_name: str, ingestion_func):
        """Helper to execute an ingestion job and record metrics."""
        start_time = datetime.now()
        try:
            self.logger.info(f"Starting ingestion job: {job_name}")
            records_processed = await ingestion_func()
            duration = (datetime.now() - start_time).total_seconds()
            
            INGESTION_JOB_RUNS_TOTAL.labels(job_name=job_name, status='success').inc()
            INGESTION_JOB_DURATION_SECONDS.labels(job_name=job_name).observe(duration)
            INGESTION_DATA_VOLUME_RECORDS.labels(job_name=job_name, data_type='records').inc(records_processed)
            
            self.logger.info(f"Completed ingestion job: {job_name} in {duration:.2f}s. Processed {records_processed} records.")
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            INGESTION_JOB_RUNS_TOTAL.labels(job_name=job_name, status='failure').inc()
            INGESTION_JOB_DURATION_SECONDS.labels(job_name=job_name).observe(duration)
            self.logger.error(f"Ingestion job {job_name} failed after {duration:.2f}s: {e}", exc_info=True)

    async def _run_google_trends_ingestion(self):
        """Ingests Google Trends data for tracked keywords."""
        async def ingestion_logic():
            tracked_keywords = db.get_tracked_keywords()
            records_processed = 0
            for tk in tracked_keywords:
                trends_data = await self.google_trends_client.get_interest_over_time([tk.keyword])
                if trends_data and trends_data.get("trends_data"):
                    for keyword, data_points in trends_data["trends_data"].items():
                        for date_str, trend_index in data_points.items():
                            kt = KeywordTrend(
                                keyword=keyword,
                                date=datetime.fromisoformat(date_str),
                                trend_index=float(trend_index),
                                source="Google Trends",
                                user_id=tk.user_id,
                                organization_id=tk.organization_id
                            )
                            clickhouse_client.insert_keyword_trends_analytical([kt])
                            records_processed += 1
                    tk.last_tracked_google_trends = datetime.utcnow()
                    db.update_tracked_keyword(tk)
            return records_processed
        await self._execute_ingestion_job("google_trends", ingestion_logic)

    async def _run_gsc_analytics_ingestion(self):
        """Ingests GSC analytics data for tracked domains."""
        async def ingestion_logic():
            tracked_domains = db.get_tracked_domains()
            records_processed = 0
            async with self.google_search_console_client as gsc_client:
                for td in tracked_domains:
                    # Fetch search analytics for the last day
                    end_date = datetime.utcnow().strftime('%Y-%m-%d')
                    start_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
                    
                    gsc_data = await gsc_client.get_search_analytics(td.domain_name, start_date, end_date)
                    if gsc_data:
                        # GSC API does not provide backlinks directly, but search analytics can be useful.
                        # For backlink data, we'd use a dedicated backlink API.
                        # If we were to store GSC search analytics in ClickHouse, it would be here.
                        # For now, let's simulate storing it as SEOMetrics for simplicity.
                        for row in gsc_data:
                            # Example: Convert GSC data to a simplified SEOMetrics for analytical storage
                            seo_metric = SEOMetrics(
                                url=row.get('keys', [''])[0], # Assuming first key is URL
                                organic_keywords=row.get('clicks'), # Clicks as organic keywords
                                organic_traffic=row.get('impressions'), # Impressions as organic traffic
                                audit_timestamp=datetime.utcnow(),
                                user_id=td.user_id,
                                organization_id=td.organization_id
                            )
                            clickhouse_client.insert_seo_metrics_analytical([seo_metric])
                            records_processed += 1
                        td.last_tracked_gsc_analytics = datetime.utcnow()
                        db.update_tracked_domain(td)
            return records_processed
        await self._execute_ingestion_job("gsc_analytics", ingestion_logic)

    async def _run_backlink_crawler_ingestion(self):
        """Ingests backlink data for tracked domains."""
        async def ingestion_logic():
            tracked_domains = db.get_tracked_domains()
            records_processed = 0
            async with self.backlink_service as bs:
                for td in tracked_domains:
                    # This would trigger a crawl or external API call to find backlinks
                    # For now, let's assume backlink_service.get_backlinks fetches from external sources
                    # and returns Backlink dataclasses.
                    backlinks = await bs.get_backlinks(td.domain_name)
                    if backlinks:
                        clickhouse_client.insert_backlinks_analytical(backlinks)
                        records_processed += len(backlinks)
                        td.last_tracked_backlinks = datetime.utcnow() # Update tracked field
                        db.update_tracked_domain(td)
            return records_processed
        await self._execute_ingestion_job("backlink_crawler", ingestion_logic)

    async def _run_serp_scraper_ingestion(self):
        """Ingests SERP data for tracked keywords."""
        async def ingestion_logic():
            tracked_keywords = db.get_tracked_keywords()
            records_processed = 0
            async with self.serp_service as ss:
                for tk in tracked_keywords:
                    serp_results = await ss.get_serp_results(tk.keyword)
                    if serp_results:
                        clickhouse_client.insert_serp_results_analytical(serp_results)
                        records_processed += len(serp_results)
                        tk.last_tracked_serp = datetime.utcnow()
                        db.update_tracked_keyword(tk)
            return records_processed
        await self._execute_ingestion_job("serp_scraper", ingestion_logic)

    async def _run_technical_audits_ingestion(self):
        """Performs technical audits for tracked domains."""
        async def ingestion_logic():
            tracked_domains = db.get_tracked_domains()
            records_processed = 0
            async with self.domain_service as ds: # Assuming domain_service handles technical audits
                for td in tracked_domains:
                    # This would trigger a Lighthouse audit or similar
                    seo_metrics = await ds.get_seo_audit(td.domain_name)
                    if seo_metrics:
                        clickhouse_client.insert_seo_metrics_analytical([seo_metrics])
                        records_processed += 1
                        td.last_tracked_technical_audit = datetime.utcnow()
                        db.update_tracked_domain(td)
            return records_processed
        await self._execute_ingestion_job("technical_audits", ingestion_logic)

    async def _run_keyword_scraper_ingestion(self):
        """Ingests keyword suggestions data for tracked keywords."""
        async def ingestion_logic():
            tracked_keywords = db.get_tracked_keywords()
            records_processed = 0
            async with self.keyword_service as ks:
                for tk in tracked_keywords:
                    suggestions = await ks.get_keyword_suggestions(tk.keyword)
                    if suggestions:
                        clickhouse_client.insert_keyword_suggestions_analytical(suggestions)
                        records_processed += len(suggestions)
                        tk.last_tracked_keyword_suggestions = datetime.utcnow()
                        db.update_tracked_keyword(tk)
            return records_processed
        await self._execute_ingestion_job("keyword_scraper", ingestion_logic)

    async def _run_ssl_labs_ingestion(self):
        """Ingests SSL Labs data for tracked domains."""
        async def ingestion_logic():
            tracked_domains = db.get_tracked_domains()
            records_processed = 0
            async with self.ssl_labs_client as ssl_client:
                for td in tracked_domains:
                    ssl_data = await ssl_client.analyze_ssl(td.domain_name)
                    if ssl_data:
                        # Convert SSL data to SEOMetrics or a dedicated SSLMetrics dataclass
                        # For simplicity, let's assume we extract a score and store as SEOMetrics
                        ssl_seo_metric = SEOMetrics(
                            url=f"https://{td.domain_name}",
                            seo_score=ssl_data.get('endpoints', [{}])[0].get('grade', 'F') == 'A+' and 100 or 50, # Simplified score
                            audit_timestamp=datetime.utcnow(),
                            user_id=td.user_id,
                            organization_id=td.organization_id
                        )
                        clickhouse_client.insert_seo_metrics_analytical([ssl_seo_metric])
                        records_processed += 1
                        td.last_tracked_ssl_labs = datetime.utcnow()
                        db.update_tracked_domain(td)
            return records_processed
        await self._execute_ingestion_job("ssl_labs", ingestion_logic)

    async def _run_whois_dns_ingestion(self):
        """Ingests WHOIS and DNS data for tracked domains."""
        async def ingestion_logic():
            tracked_domains = db.get_tracked_domains()
            records_processed = 0
            async with self.whois_client as wc, self.dns_client as dc:
                for td in tracked_domains:
                    whois_data = await wc.get_domain_info(td.domain_name)
                    dns_records = await dc.get_all_records(td.domain_name)
                    
                    if whois_data or dns_records:
                        # Update the Domain object in PostgreSQL
                        domain_obj = db.get_domain(td.domain_name)
                        if not domain_obj:
                            domain_obj = Domain(name=td.domain_name)
                        
                        if whois_data:
                            domain_obj.registered_date = datetime.fromisoformat(whois_data['creation_date']) if whois_data.get('creation_date') else None
                            domain_obj.expiration_date = datetime.fromisoformat(whois_data['expiration_date']) if whois_data.get('expiration_date') else None
                            domain_obj.registrar = whois_data.get('registrar')
                            domain_obj.whois_raw = json.dumps(whois_data)
                        
                        if dns_records:
                            # Convert list of dicts to dict of lists for dns_records field
                            domain_obj.dns_records = {rtype: [rec['data'] for rec in dns_records if rec['type'] == rtype] for rtype in set(rec['type'] for rec in dns_records)}
                            # Attempt to get IP address from A record
                            a_records = [rec['data'] for rec in dns_records if rec['type'] == 'A']
                            if a_records:
                                domain_obj.ip_address = a_records[0]
                        
                        domain_obj.last_checked = datetime.utcnow()
                        db.save_domain(domain_obj)
                        records_processed += 1
                        td.last_tracked_whois_dns = datetime.utcnow()
                        db.update_tracked_domain(td)
            return records_processed
        await self._execute_ingestion_job("whois_dns", ingestion_logic)

    async def _run_newsapi_reddit_ingestion(self):
        """Ingests NewsAPI and Reddit data for tracked keywords."""
        async def ingestion_logic():
            tracked_keywords = db.get_tracked_keywords()
            records_processed = 0
            async with self.news_api_client as nac, self.reddit_client as rc:
                for tk in tracked_keywords:
                    # NewsAPI
                    news_articles = await nac.search_news(tk.keyword, limit=10)
                    for article in news_articles:
                        # Store as SocialMention or similar
                        # For simplicity, we'll just count them for now
                        records_processed += 1
                    
                    # Reddit
                    reddit_mentions = await rc.search_mentions(tk.keyword, limit=10)
                    for mention in reddit_mentions:
                        # Store as SocialMention or similar
                        records_processed += 1
                    
                    if news_articles or reddit_mentions:
                        tk.last_tracked_news_reddit = datetime.utcnow()
                        db.update_tracked_keyword(tk)
            return records_processed
        await self._execute_ingestion_job("newsapi_reddit", ingestion_logic)

    async def _run_common_crawl_ingestion(self):
        """Ingests Common Crawl data for tracked domains."""
        async def ingestion_logic():
            tracked_domains = db.get_tracked_domains()
            records_processed = 0
            async with self.common_crawl_client as ccc:
                for td in tracked_domains:
                    # Fetch recent records from Common Crawl
                    records = await ccc.search_domain(td.domain_name, limit=100)
                    if records:
                        # Process and store relevant data, e.g., new URLs, changes
                        # For simplicity, just count records
                        records_processed += len(records)
                        td.last_tracked_common_crawl = datetime.utcnow()
                        db.update_tracked_domain(td)
            return records_processed
        await self._execute_ingestion_job("common_crawl", ingestion_logic)

# Global instance for the scheduler, initialized during app startup
ingestion_scheduler: Optional[IngestionScheduler] = None

async def get_ingestion_scheduler(
    session_manager: SessionManager,
    resilience_manager: DistributedResilienceManager,
    api_quota_manager: APIQuotaManager,
    redis_url: str,
    redis_client: redis.Redis # Added redis_client to get_ingestion_scheduler signature
) -> IngestionScheduler:
    global ingestion_scheduler
    if ingestion_scheduler is None:
        ingestion_scheduler = IngestionScheduler(
            session_manager=session_manager,
            resilience_manager=resilience_manager,
            api_quota_manager=api_quota_manager,
            redis_url=redis_url,
            redis_client=redis_client # Passed redis_client to IngestionScheduler constructor
        )
    return ingestion_scheduler
