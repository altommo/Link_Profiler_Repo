import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import time # For performance timing
import random # For simulation

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.database.database import db # Access db singleton directly
import redis.asyncio as redis # Import the module for type hinting
from Link_Profiler.api.schemas import (
    CrawlerMissionStatus, BacklinkDiscoveryMetrics, ApiQuotaStatus,
    DomainIntelligenceMetrics, PerformanceOptimizationMetrics, DashboardAlert,
    DashboardRealtimeUpdates, SatelliteFleetStatus, CrawlStatus, CrawlError, SpamLevel
)
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import the concrete APIQuotaManager
from Link_Profiler.services.dashboard_alert_service import DashboardAlertService # Import the concrete DashboardAlertService
from Link_Profiler.queue_system.smart_crawler_queue import SmartCrawlQueue # Import the concrete SmartCrawlQueue
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

    def __init__(self, smart_crawl_queue: SmartCrawlQueue, api_quota_manager: APIQuotaManager, dashboard_alert_service: DashboardAlertService):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".MissionControlService")
        self.db = db # Access db singleton directly
        self.redis = smart_crawl_queue.redis_client # Access redis client from smart_crawl_queue
        self.smart_crawl_queue = smart_crawl_queue
        self.api_quota_manager = api_quota_manager
        self.dashboard_alert_service = dashboard_alert_service

        self.dashboard_refresh_rate_seconds = config_loader.get("mission_control.dashboard_refresh_rate", 1000) / 1000
        self.websocket_enabled = config_loader.get("mission_control.websocket_enabled", False)
        self.max_websocket_connections = config_loader.get("mission_control.max_websocket_connections", 100)
        self.cache_ttl_seconds = config_loader.get("mission_control.cache_ttl", 60)
        self.history_retention_days = config_loader.get("mission_control.history_retention_days", 30)
        self.satellite_heartbeat_threshold_seconds = config_loader.get("satellite.heartbeat_interval", 5) * 2 # 2 missed heartbeats for 'idle' status

        self._cached_data: Optional[DashboardRealtimeUpdates] = None
        self._last_cache_update: Optional[datetime] = None

        logger.info("MissionControlService initialized.")

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
        Caches results to prevent excessive database/Redis queries.
        """
        now = datetime.utcnow()
        if self._cached_data and (now - self._last_cache_update) < timedelta(seconds=self.cache_ttl_seconds):
            return self._cached_data

        logger.debug("Aggregating new dashboard data...")
        
        # Refresh materialized views before querying for fresh data
        self.db.refresh_materialized_views()

        # Fetch all data concurrently
        (
            crawler_mission_status_data,
            backlink_discovery_metrics_data,
            api_quota_statuses_data,
            domain_intelligence_metrics_data,
            performance_optimization_metrics_data,
            alerts_data,
            satellite_fleet_status_data,
        ) = await asyncio.gather(
            self._get_crawler_mission_status(),
            self._get_backlink_discovery_metrics(),
            self.api_quota_manager.get_api_status(), # This returns a dict, needs conversion to list of Pydantic models
            self._get_domain_intelligence_metrics(),
            self._get_performance_optimization_metrics(),
            self.dashboard_alert_service.check_critical_alerts(), # This returns list of DashboardAlert
            self._get_satellite_fleet_status(),
        )

        # Convert raw API status dict to list of ApiQuotaStatus Pydantic models
        api_quota_statuses_converted: List[ApiQuotaStatus] = []
        for api_name, status_data in api_quota_statuses_data.items():
            api_quota_statuses_converted.append(ApiQuotaStatus(
                api_name=api_name,
                limit=status_data['limit'],
                used=status_data['used'],
                remaining=status_data['remaining'],
                reset_date=status_data['last_reset_date'], # Already ISO format from manager
                percentage_used=(status_data['used'] / status_data['limit'] * 100) if status_data['limit'] > 0 else 0,
                status="OK" if status_data['remaining'] is None or status_data['remaining'] > status_data['limit'] * 0.2 else "Warning" if status_data['remaining'] > 0 else "Critical",
                predicted_exhaustion_date=None, # Placeholder for prediction logic
                recommended_action=None # Placeholder for recommendation logic
            ))

        updates = DashboardRealtimeUpdates(
            timestamp=now.isoformat(),
            crawler_mission_status=crawler_mission_status_data,
            backlink_discovery_metrics=backlink_discovery_metrics_data,
            api_quota_statuses=api_quota_statuses_converted,
            domain_intelligence_metrics=domain_intelligence_metrics_data,
            performance_optimization_metrics=performance_optimization_metrics_data,
            alerts=alerts_data,
            satellite_fleet_status=satellite_fleet_status_data,
        )
        
        duration = time.monotonic() - start_time
        DASHBOARD_MODULE_REFRESH_DURATION_SECONDS.labels(module_name="all_dashboard_updates").observe(duration)
        self.logger.debug(f"Aggregated real-time updates in {duration:.4f} seconds.")
        self._cached_data = updates
        self._last_cache_update = now
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
            elif job.status == CrawlStatus.PENDING or job.status == CrawlStatus.QUEUED: # Include QUEUED for dashboard
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
            
            # Collect recent errors from job.errors (list of CrawlError dataclasses)
            for error in job.errors: # Assuming job.errors is a list of CrawlError dataclasses
                if error.timestamp >= twenty_four_hours_ago:
                    recent_job_errors.append(error)

        queue_depth = await self.smart_crawl_queue.get_total_queue_depth()
        
        # Get satellite status for utilization calculation
        # This will be fetched by _get_satellite_fleet_status and passed to the main aggregation
        # For this specific function, we can get a quick count
        active_satellites_count = await self.smart_crawl_queue.get_active_worker_count()
        total_satellites_count = await self.smart_crawl_queue.get_registered_worker_count()
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
            recent_job_errors=[err.model_dump() for err in recent_job_errors[:10]] # Convert CrawlError to dict for Pydantic schema
        )
        duration = time.monotonic() - start_time
        DASHBOARD_MODULE_REFRESH_DURATION_SECONDS.labels(module_name="crawler_mission_status").observe(duration)
        return status

    async def _get_satellite_fleet_status(self) -> List[SatelliteFleetStatus]:
        """
        Retrieves the real-time status of satellite crawlers.
        """
        start_time = time.monotonic()
        heartbeat_key = config_loader.get("queue.heartbeat_queue_sorted_name")
        
        now_timestamp = datetime.utcnow().timestamp()
        min_timestamp_active = now_timestamp - self.satellite_heartbeat_threshold_seconds
        min_timestamp_known = now_timestamp - timedelta(days=self.history_retention_days).total_seconds()

        # Get all satellites that have sent a heartbeat within the retention period
        all_known_satellites_raw = await self.redis.zrangebyscore(heartbeat_key, min_timestamp_known, now_timestamp, withscores=True)
        
        satellite_statuses: List[SatelliteFleetStatus] = []
        for satellite_id_bytes, last_heartbeat_ts in all_known_satellites_raw:
            satellite_id = satellite_id_bytes.decode('utf-8')
            last_heartbeat = datetime.fromtimestamp(last_heartbeat_ts)
            
            status = "unresponsive"
            if last_heartbeat_ts >= min_timestamp_active:
                status = "active"
            elif last_heartbeat_ts >= now_timestamp - timedelta(minutes=5).total_seconds(): # Recently active, but now idle
                status = "idle"

            # Fetch latest performance log for this satellite
            # Ensure db.get_latest_satellite_performance_logs can filter by satellite_id
            latest_log_for_satellite = self.db.get_latest_satellite_performance_logs(satellite_id=satellite_id, limit=1)
            
            jobs_completed_24h = latest_log_for_satellite[0].pages_crawled if latest_log_for_satellite else 0
            errors_24h = latest_log_for_satellite[0].errors_logged if latest_log_for_satellite else 0
            avg_job_duration_seconds = None # Not directly available from SatellitePerformanceLog
            current_job_id = None # Not directly available
            current_job_type = None # Not directly available
            current_job_progress = None # Not directly available

            satellite_statuses.append(SatelliteFleetStatus(
                satellite_id=satellite_id,
                status=status,
                last_heartbeat=last_heartbeat,
                jobs_completed_24h=jobs_completed_24h,
                errors_24h=errors_24h,
                avg_job_duration_seconds=avg_job_duration_seconds,
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
        # Query the materialized view for daily backlink stats
        daily_backlink_stats_orm = self.db.get_session().execute(
            self.db.text("SELECT * FROM mv_daily_backlink_stats ORDER BY day DESC LIMIT 1")
        ).fetchone()
        
        total_backlinks_discovered = daily_backlink_stats_orm.total_backlinks_discovered if daily_backlink_stats_orm else 0
        unique_domains_discovered = daily_backlink_stats_orm.unique_domains_discovered if daily_backlink_stats_orm else 0
        potential_spam_links_24h = daily_backlink_stats_orm.potential_spam_links if daily_backlink_stats_orm else 0
        avg_authority_score = daily_backlink_stats_orm.avg_authority_passed if daily_backlink_stats_orm else 0

        # Placeholder for top linking domains and target URLs (would need more complex queries)
        # For now, simulate or fetch from a pre-aggregated source if available
        top_linking_domains = ["simulated-domain-a.com", "simulated-domain-b.org"]
        top_target_urls = ["https://yourdomain.com/page-x", "https://yourdomain.com/page-y"]
        new_backlinks_24h = random.randint(10, 100) # Simulate new backlinks

        metrics = BacklinkDiscoveryMetrics(
            total_backlinks_discovered=total_backlinks_discovered,
            unique_domains_discovered=unique_domains_discovered,
            new_backlinks_24h=new_backlinks_24h,
            avg_authority_score=round(avg_authority_score, 2),
            top_linking_domains=top_linking_domains,
            top_target_urls=top_target_urls,
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
        # Query the materialized view for daily domain stats
        daily_domain_stats_orm = self.db.get_session().execute(
            self.db.text("SELECT * FROM mv_daily_domain_stats ORDER BY day DESC LIMIT 1")
        ).fetchone()

        total_domains_analyzed = daily_domain_stats_orm.total_domains_analyzed if daily_domain_stats_orm else 0
        valuable_expired_domains_found = daily_domain_stats_orm.valuable_domains_found if daily_domain_stats_orm else 0
        avg_domain_value_score = daily_domain_stats_orm.avg_domain_authority_score if daily_domain_stats_orm else 0
        new_domains_added_24h = random.randint(1, 20) # Simulate new domains
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
        # Query the materialized view for daily satellite performance
        daily_satellite_performance_orm = self.db.get_session().execute(
            self.db.text("SELECT * FROM mv_daily_satellite_performance ORDER BY day DESC LIMIT 1")
        ).fetchone()

        avg_crawl_speed_pages_per_minute = daily_satellite_performance_orm.avg_crawl_speed_ppm if daily_satellite_performance_orm else 0
        avg_success_rate_percentage = daily_satellite_performance_orm.avg_success_rate if daily_satellite_performance_orm else 0
        avg_response_time_ms = daily_satellite_performance_orm.avg_response_time_ms if daily_satellite_performance_orm else 0
        bottlenecks_detected = ["High Redis latency (simulated)", "Frequent API 429s (simulated)"] # Simulate
        top_performing_satellites = ["satellite-us-east-1", "satellite-eu-west-1"] # Placeholder
        worst_performing_satellites = ["satellite-us-west-1"] # Placeholder

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
mission_control_service: Optional['MissionControlService'] = None
