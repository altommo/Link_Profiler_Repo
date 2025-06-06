import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import time # For performance timing
import random # For simulation

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.database.database import Database
import redis.asyncio as redis
from Link_Profiler.api.schemas import (
    CrawlerMissionStatus, BacklinkDiscoveryMetrics, APIQuotaStatus,
    DomainIntelligenceMetrics, PerformanceOptimizationMetrics, DashboardAlert,
    DashboardRealtimeUpdates, SatelliteStatus, CrawlStatus, CrawlError, SpamLevel
)
from Link_Profiler.services.api_quota_manager_service import APIQuotaManagerService
from Link_Profiler.services.dashboard_alert_service import DashboardAlertService
from Link_Profiler.monitoring.prometheus_metrics import (
    DASHBOARD_MODULE_REFRESH_DURATION_SECONDS, SATELLITE_STATUS_GAUGE
)

logger = logging.getLogger(__name__)

class MissionControlService:
    """
    Provides real-time aggregated data for the Mission Control Dashboard.
    Aggregates data from database, Redis, and other services.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MissionControlService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db: Database, redis_client: redis.Redis, api_quota_manager: APIQuotaManagerService, dashboard_alert_service: DashboardAlertService):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".MissionControlService")
        self.db = db
        self.redis = redis_client
        self.api_quota_manager = api_quota_manager
        self.dashboard_alert_service = dashboard_alert_service

        self.dashboard_history_retention_days = config_loader.get("mission_control_dashboard.dashboard_history_retention_days", 30)
        self.websocket_refresh_rate_seconds = config_loader.get("mission_control_dashboard.websocket_refresh_rate_seconds", 1)
        self.satellite_heartbeat_threshold_seconds = config_loader.get("satellite.heartbeat_interval", 5) * 2 # 2 missed heartbeats for 'idle' status

    async def __aenter__(self):
        """No specific async setup needed for this class, dependencies are already entered."""
        self.logger.info("MissionControlService entered context.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific async cleanup needed for this class."""
        self.logger.info("MissionControlService exited context.")
        pass

    async def get_realtime_updates(self) -> DashboardRealtimeUpdates:
        """
        Aggregates all real-time data for the dashboard.
        """
        start_time = time.monotonic()
        
        # Fetch all data concurrently
        (
            crawler_mission_status,
            backlink_discovery_metrics,
            api_quota_statuses,
            domain_intelligence_metrics,
            performance_optimization_metrics,
            alerts,
            satellite_fleet_status,
        ) = await asyncio.gather(
            self._get_crawler_mission_status(),
            self._get_backlink_discovery_metrics(),
            self.api_quota_manager.get_all_api_quota_statuses(),
            self._get_domain_intelligence_metrics(),
            self._get_performance_optimization_metrics(),
            self.dashboard_alert_service.check_critical_alerts(),
            self._get_satellite_fleet_status(),
        )

        updates = DashboardRealtimeUpdates(
            crawler_mission_status=crawler_mission_status,
            backlink_discovery_metrics=backlink_discovery_metrics,
            api_quota_statuses=[APIQuotaStatus(**s) for s in api_quota_statuses], # Ensure Pydantic model conversion
            domain_intelligence_metrics=domain_intelligence_metrics,
            performance_optimization_metrics=performance_optimization_metrics,
            alerts=alerts,
            satellite_fleet_status=satellite_fleet_status,
        )
        
        duration = time.monotonic() - start_time
        DASHBOARD_MODULE_REFRESH_DURATION_SECONDS.labels(module_name="all_dashboard_updates").observe(duration)
        self.logger.debug(f"Aggregated real-time updates in {duration:.4f} seconds.")
        return updates

    async def _get_crawler_mission_status(self) -> CrawlerMissionStatus:
        """
        Gathers metrics for the Crawler Mission Status module.
        """
        start_time = time.monotonic()
        all_jobs = self.db.get_all_crawl_jobs()
        
        active_jobs_count = 0
        queued_jobs_count = 0
        completed_jobs_24h_count = 0
        failed_jobs_24h_count = 0
        total_pages_crawled_24h = 0
        total_job_completion_time = 0
        completed_job_count = 0
        recent_job_errors: List[CrawlError] = []

        now = datetime.utcnow()
        twenty_four_hours_ago = now - timedelta(hours=24)

        for job in all_jobs:
            if job.status == CrawlStatus.IN_PROGRESS:
                active_jobs_count += 1
            elif job.status == CrawlStatus.PENDING or job.status == CrawlStatus.SCHEDULED:
                queued_jobs_count += 1
            
            if job.completed_date and job.completed_date >= twenty_four_hours_ago:
                if job.status == CrawlStatus.COMPLETED:
                    completed_jobs_24h_count += 1
                    if job.started_date:
                        duration = (job.completed_date - job.started_date).total_seconds()
                        total_job_completion_time += duration
                        completed_job_count += 1
                elif job.status == CrawlStatus.FAILED:
                    failed_jobs_24h_count += 1
                
                total_pages_crawled_24h += job.urls_crawled
            
            # Collect recent errors
            for error in job.error_log:
                if error.timestamp >= twenty_four_hours_ago:
                    recent_job_errors.append(error)

        queue_depth = await self.redis.llen(config_loader.get("queue.job_queue_name"))
        
        # Get satellite status for utilization calculation
        satellite_fleet_status = await self._get_satellite_fleet_status()
        active_satellites_count = sum(1 for s in satellite_fleet_status if s.status == "active")
        total_satellites_count = len(satellite_fleet_status)
        satellite_utilization_percentage = (active_satellites_count / total_satellites_count * 100) if total_satellites_count > 0 else 0

        avg_job_completion_time_seconds = (total_job_completion_time / completed_job_count) if completed_job_count > 0 else 0

        status = CrawlerMissionStatus(
            active_jobs_count=active_jobs_count,
            queued_jobs_count=queued_jobs_count,
            completed_jobs_24h_count=completed_jobs_24h_count,
            failed_jobs_24h_count=failed_jobs_24h_count,
            total_pages_crawled_24h=total_pages_crawled_24h,
            queue_depth=queue_depth,
            active_satellites_count=active_satellites_count,
            total_satellites_count=total_satellites_count,
            satellite_utilization_percentage=round(satellite_utilization_percentage, 2),
            avg_job_completion_time_seconds=round(avg_job_completion_time_seconds, 2),
            recent_job_errors=recent_job_errors
        )
        duration = time.monotonic() - start_time
        DASHBOARD_MODULE_REFRESH_DURATION_SECONDS.labels(module_name="crawler_mission_status").observe(duration)
        return status

    async def _get_satellite_fleet_status(self) -> List[SatelliteStatus]:
        """
        Retrieves the real-time status of satellite crawlers.
        """
        start_time = time.monotonic()
        heartbeat_key = config_loader.get("queue.heartbeat_queue_sorted_name")
        
        now_timestamp = datetime.utcnow().timestamp()
        min_timestamp_active = now_timestamp - self.satellite_heartbeat_threshold_seconds
        min_timestamp_known = now_timestamp - timedelta(days=self.dashboard_history_retention_days).total_seconds()

        # Get all satellites that have sent a heartbeat within the retention period
        all_known_satellites_raw = await self.redis.zrangebyscore(heartbeat_key, min_timestamp_known, now_timestamp, withscores=True)
        
        satellite_statuses: List[SatelliteStatus] = []
        for satellite_id_bytes, last_heartbeat_ts in all_known_satellites_raw:
            satellite_id = satellite_id_bytes.decode('utf-8')
            last_heartbeat = datetime.fromtimestamp(last_heartbeat_ts)
            
            status = "unresponsive"
            if last_heartbeat_ts >= min_timestamp_active:
                status = "active"
            elif last_heartbeat_ts >= now_timestamp - timedelta(minutes=5).total_seconds(): # Recently active, but now idle
                status = "idle"

            # Fetch current job info if available (this is a simplification, actual job assignment is complex)
            current_job_id = None
            current_job_type = None
            current_job_progress = None
            # In a real system, the satellite would report its current job ID and progress
            # For now, simulate or fetch from a dedicated Redis key if satellites store it.
            # Example: await self.redis.hgetall(f"satellite:{satellite_id}:current_job")

            # Placeholder for jobs_completed_24h and errors_24h
            jobs_completed_24h = random.randint(5, 50) # Simulate
            errors_24h = random.randint(0, 5) # Simulate

            satellite_statuses.append(SatelliteStatus(
                satellite_id=satellite_id,
                status=status,
                last_heartbeat=last_heartbeat,
                jobs_completed_24h=jobs_completed_24h,
                errors_24h=errors_24h,
                avg_job_duration_seconds=random.uniform(30, 300), # Simulate
                current_job_id=current_job_id,
                current_job_type=current_job_type,
                current_job_progress=current_job_progress
            ))
            # Update Prometheus gauge for each satellite
            SATELLITE_STATUS_GAUGE.labels(satellite_id=satellite_id, status_type=status).set(1) # Set to 1 if active/idle/unresponsive
            if status == "unresponsive":
                SATELLITE_STATUS_GAUGE.labels(satellite_id=satellite_id, status_type="active").set(0)
                SATELLITE_STATUS_GAUGE.labels(satellite_id=satellite_id, status_type="idle").set(0)
            else: # active or idle
                SATELLITE_STATUS_GAUGE.labels(satellite_id=satellite_id, status_type="unresponsive").set(0)


        duration = time.monotonic() - start_time
        DASHBOARD_MODULE_REFRESH_DURATION_SECONDS.labels(module_name="satellite_fleet_status").observe(duration)
        return satellite_statuses

    async def _get_backlink_discovery_metrics(self) -> BacklinkDiscoveryMetrics:
        """
        Gathers metrics for the Backlink Discovery Operations module.
        """
        start_time = time.monotonic()
        all_backlinks = self.db.get_all_backlinks() # This might be a large query
        
        total_backlinks_discovered = len(all_backlinks)
        unique_domains_discovered = len({bl.source_domain for bl in all_backlinks})
        
        now = datetime.utcnow()
        twenty_four_hours_ago = now - timedelta(hours=24)
        
        new_backlinks_24h = 0
        total_authority_score = 0.0
        authority_counted_links = 0
        potential_spam_links_24h = 0
        
        top_linking_domains_counts: Dict[str, int] = {}
        top_target_urls_counts: Dict[str, int] = {}

        for bl in all_backlinks:
            if bl.discovered_date and bl.discovered_date >= twenty_four_hours_ago:
                new_backlinks_24h += 1
            
            if bl.authority_passed is not None:
                total_authority_score += bl.authority_passed
                authority_counted_links += 1
            
            if bl.spam_level in [SpamLevel.SUSPICIOUS, SpamLevel.LIKELY_SPAM, SpamLevel.CONFIRMED_SPAM]:
                if bl.discovered_date and bl.discovered_date >= twenty_four_hours_ago:
                    potential_spam_links_24h += 1

            top_linking_domains_counts[bl.source_domain] = top_linking_domains_counts.get(bl.source_domain, 0) + 1
            top_target_urls_counts[bl.target_url] = top_target_urls_counts.get(bl.target_url, 0) + 1

        avg_authority_score = (total_authority_score / authority_counted_links) if authority_counted_links > 0 else 0.0

        top_linking_domains = sorted(top_linking_domains_counts.items(), key=lambda item: item[1], reverse=True)[:10]
        top_target_urls = sorted(top_target_urls_counts.items(), key=lambda item: item[1], reverse=True)[:10]

        metrics = BacklinkDiscoveryMetrics(
            total_backlinks_discovered=total_backlinks_discovered,
            unique_domains_discovered=unique_domains_discovered,
            new_backlinks_24h=new_backlinks_24h,
            avg_authority_score=round(avg_authority_score, 2),
            top_linking_domains=[d[0] for d in top_linking_domains],
            top_target_urls=[u[0] for u in top_target_urls],
            potential_spam_links_24h=potential_spam_links_24h
        )
        duration = time.monotonic() - start_time
        DASHBOARD_MODULE_REFRESH_DURATION_SECONDS.labels(module_name="backlink_discovery_metrics").observe(duration)
        return metrics

    async def _get_domain_intelligence_metrics(self) -> DomainIntelligenceMetrics:
        """
        Gathers metrics for the Domain Intelligence Command Center module.
        """
        start_time = time.monotonic()
        all_domains = self.db.get_all_domains() # This might be a large query
        
        total_domains_analyzed = len(all_domains)
        valuable_expired_domains_found = 0
        total_domain_value_score = 0.0
        new_domains_added_24h = 0
        
        now = datetime.utcnow()
        twenty_four_hours_ago = now - timedelta(hours=24)

        # This part needs actual DomainIntelligence objects to be stored in DB
        # For now, we'll simulate based on the Domain object's properties
        for domain in all_domains:
            # Simulate 'is_valuable' from DomainAnalyzerService
            is_valuable = domain.authority_score >= 20 and domain.spam_score <= 0.3
            if is_valuable:
                valuable_expired_domains_found += 1
                total_domain_value_score += domain.authority_score # Use authority as proxy for value

            if domain.last_checked and domain.last_checked >= twenty_four_hours_ago:
                new_domains_added_24h += 1 # Assuming last_checked indicates recent addition/update

        avg_domain_value_score = (total_domain_value_score / valuable_expired_domains_found) if valuable_expired_domains_found > 0 else 0.0

        # Top niches identified - this would come from AI analysis or specific tagging
        top_niches_identified = ["SEO Tools", "Digital Marketing", "Link Building", "Content Creation"] # Simulate

        metrics = DomainIntelligenceMetrics(
            total_domains_analyzed=total_domains_analyzed,
            valuable_expired_domains_found=valuable_expired_domains_found,
            avg_domain_value_score=round(avg_domain_value_score, 2),
            new_domains_added_24h=new_domains_added_24h,
            top_niches_identified=top_niches_identified
        )
        duration = time.monotonic() - start_time
        DASHBOARD_MODULE_REFRESH_DURATION_SECONDS.labels(module_name="domain_intelligence_metrics").observe(duration)
        return metrics

    async def _get_performance_optimization_metrics(self) -> PerformanceOptimizationMetrics:
        """
        Gathers metrics for the Performance Optimization Center module.
        """
        start_time = time.monotonic()
        # These metrics would typically come from a dedicated performance logging system
        # or aggregated from satellite performance logs.
        # For now, we'll simulate or derive from existing job data.

        all_jobs = self.db.get_all_crawl_jobs()
        
        total_pages_crawled = 0
        total_crawl_duration = 0 # For active jobs
        total_successful_jobs = 0
        total_jobs_processed = 0
        total_response_time_ms = 0
        response_time_count = 0

        for job in all_jobs:
            if job.status == CrawlStatus.COMPLETED and job.started_date and job.completed_date:
                duration = (job.completed_date - job.started_date).total_seconds()
                if duration > 0:
                    total_pages_crawled += job.urls_crawled
                    total_crawl_duration += duration
                    total_successful_jobs += 1
                total_jobs_processed += 1
            
            # Assuming crawl_result.seo_metrics.response_time_ms is stored in job.results
            # This is a simplification; typically, response times would be logged per URL.
            if job.results and 'crawl_results' in job.results:
                for crawl_result_data in job.results['crawl_results']:
                    if 'seo_metrics' in crawl_result_data and 'response_time_ms' in crawl_result_data['seo_metrics']:
                        total_response_time_ms += crawl_result_data['seo_metrics']['response_time_ms']
                        response_time_count += 1

        avg_crawl_speed_pages_per_minute = (total_pages_crawled / (total_crawl_duration / 60)) if total_crawl_duration > 0 else 0
        avg_success_rate_percentage = (total_successful_jobs / total_jobs_processed * 100) if total_jobs_processed > 0 else 0
        avg_response_time_ms = (total_response_time_ms / response_time_count) if response_time_count > 0 else 0

        # Bottlenecks detected - would come from anomaly detection or specific monitoring
        bottlenecks_detected = ["High Redis latency (simulated)", "Frequent API 429s (simulated)"] # Simulate

        # Top/worst performing satellites - would come from satellite_fleet_status
        satellite_fleet_status = await self._get_satellite_fleet_status()
        sorted_satellites = sorted(satellite_fleet_status, key=lambda s: s.jobs_completed_24h, reverse=True)
        top_performing_satellites = [s.satellite_id for s in sorted_satellites[:3]]
        worst_performing_satellites = [s.satellite_id for s in sorted_satellites[-3:]]

        metrics = PerformanceOptimizationMetrics(
            avg_crawl_speed_pages_per_minute=round(avg_crawl_speed_pages_per_minute, 2),
            avg_success_rate_percentage=round(avg_success_rate_percentage, 2),
            avg_response_time_ms=round(avg_response_time_ms, 2),
            bottlenecks_detected=bottlenecks_detected,
            top_performing_satellites=top_performing_satellites,
            worst_performing_satellites=worst_performing_satellites
        )
        duration = time.monotonic() - start_time
        DASHBOARD_MODULE_REFRESH_DURATION_SECONDS.labels(module_name="performance_optimization_metrics").observe(duration)
        return metrics

# Singleton instance (will be initialized in main.py)
mission_control_service: Optional[MissionControlService] = None
