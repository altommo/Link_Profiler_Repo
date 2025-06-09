import logging
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import time # For performance timing
import random # For simulation

import redis.asyncio as redis # Import the module for type hinting
from sqlalchemy import text  # Import text function for raw SQL queries

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.database.database import db # Access db singleton directly
from Link_Profiler.queue_system.smart_crawler_queue import SmartCrawlQueue # Import the concrete SmartCrawlQueue
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import the concrete APIQuotaManager
from Link_Profiler.services.dashboard_alert_service import DashboardAlertService # Import the concrete DashboardAlertService
from Link_Profiler.api.schemas import (
    CrawlerMissionStatus, BacklinkDiscoveryMetrics, ApiQuotaStatus,
    DomainIntelligenceMetrics, PerformanceOptimizationMetrics, DashboardAlert,
    DashboardRealtimeUpdates, SatelliteFleetStatus, CrawlStatus, CrawlErrorResponse, SpamLevel, # Corrected CrawlError to CrawlErrorResponse
    ApiPerformanceMetrics # Import ApiPerformanceMetrics
)
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
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MissionControlService, cls).__new__(cls)
        return cls._instance

    def __init__(self, 
                 redis_client: Optional[redis.Redis] = None, # Explicitly accept redis_client
                 smart_crawl_queue: Optional[SmartCrawlQueue] = None,
                 api_quota_manager: Optional[APIQuotaManager] = None,
                 dashboard_alert_service: Optional[DashboardAlertService] = None):
        
        if self._initialized:
            return
        self._initialized = True
        
        self.logger = logging.getLogger(__name__ + ".MissionControlService")
        
        self.redis = redis_client # Store the provided redis_client
        self.smart_crawl_queue = smart_crawl_queue
        self.api_quota_manager = api_quota_manager
        self.dashboard_alert_service = dashboard_alert_service
        self.db = db # Access db singleton directly

        # Fallback for redis_client if not directly provided
        if not self.redis:
            if self.smart_crawl_queue and hasattr(self.smart_crawl_queue, 'redis'): # Check for 'redis' attribute in smart_crawl_queue
                self.redis = self.smart_crawl_queue.redis
            
            if not self.redis:
                self.logger.warning("No Redis client provided to MissionControlService. Creating fallback connection.")
                self.redis = redis.from_url(config_loader.get("redis.url", "redis://localhost:6379/0"))
        
        if not self.redis:
            raise ValueError("MissionControlService requires a Redis client.")

        # Convert string values to appropriate types with defaults
        refresh_rate = config_loader.get("mission_control.dashboard_refresh_rate", "1000")
        self.dashboard_refresh_rate_seconds = float(refresh_rate) / 1000 if isinstance(refresh_rate, (str, int, float)) else 1.0
        
        websocket_enabled = config_loader.get("mission_control.websocket_enabled", "true")
        self.websocket_enabled = str(websocket_enabled).lower() in ('true', '1', 'yes', 'on')
        
        max_connections = config_loader.get("mission_control.max_websocket_connections", "100")
        self.max_websocket_connections = int(max_connections) if isinstance(max_connections, (str, int)) else 100
        
        cache_ttl = config_loader.get("mission_control.cache_ttl", "60")
        self.cache_ttl_seconds = int(cache_ttl) if isinstance(cache_ttl, (str, int)) else 60
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
        
        start_time = time.monotonic() # Define start_time here
        
        # Refresh materialized views before querying for fresh data
        self.db.refresh_materialized_views()

        # Fetch all data concurrently with individual error handling
        try:
            (
                crawler_mission_status_data,
                backlink_discovery_metrics_data,
                api_quota_statuses_data_raw,
                domain_intelligence_metrics_data,
                performance_optimization_metrics_data,
                alerts_data,
                satellite_fleet_status_data,
            ) = await asyncio.gather(
                self._get_crawler_mission_status(),
                self._get_backlink_discovery_metrics(),
                self._safe_get_api_status(),
                self._get_domain_intelligence_metrics(),
                self._get_performance_optimization_metrics(),
                self._safe_get_alerts(),
                self._get_satellite_fleet_status(),
                return_exceptions=True
            )
            
            # Handle exception objects returned by gather
            if isinstance(crawler_mission_status_data, Exception):
                self.logger.error(f"Crawler mission status error: {crawler_mission_status_data}")
                crawler_mission_status_data = self._get_fallback_crawler_status()
            
            if isinstance(backlink_discovery_metrics_data, Exception):
                self.logger.error(f"Backlink discovery metrics error: {backlink_discovery_metrics_data}")
                backlink_discovery_metrics_data = self._get_fallback_backlink_metrics()
            
            if isinstance(api_quota_statuses_data_raw, Exception):
                self.logger.error(f"API quota status error: {api_quota_statuses_data_raw}")
                api_quota_statuses_data_raw = {}
            
            if isinstance(domain_intelligence_metrics_data, Exception):
                self.logger.error(f"Domain intelligence metrics error: {domain_intelligence_metrics_data}")
                domain_intelligence_metrics_data = self._get_fallback_domain_metrics()
            
            if isinstance(performance_optimization_metrics_data, Exception):
                self.logger.error(f"Performance optimization metrics error: {performance_optimization_metrics_data}")
                performance_optimization_metrics_data = self._get_fallback_performance_metrics()
            
            if isinstance(alerts_data, Exception):
                self.logger.error(f"Alerts data error: {alerts_data}")
                alerts_data = []
            
            if isinstance(satellite_fleet_status_data, Exception):
                self.logger.error(f"Satellite fleet status error: {satellite_fleet_status_data}")
                satellite_fleet_status_data = []
                
        except Exception as e:
            self.logger.error(f"Error gathering dashboard data: {e}. Using fallback values.")
            # Provide fallback values
            crawler_mission_status_data = self._get_fallback_crawler_status()
            backlink_discovery_metrics_data = self._get_fallback_backlink_metrics()
            api_quota_statuses_data_raw = {}
            domain_intelligence_metrics_data = self._get_fallback_domain_metrics()
            performance_optimization_metrics_data = self._get_fallback_performance_metrics()
            alerts_data = []
            satellite_fleet_status_data = []

        # Convert raw API status dict to list of ApiQuotaStatus Pydantic models
        api_quota_statuses_converted: List[ApiQuotaStatus] = []
        for api_name, status_data in api_quota_statuses_data_raw.items():
            try:
                # Ensure performance data has all required fields with defaults
                performance_data = status_data.get('performance', {})
                performance_metrics = ApiPerformanceMetrics(
                    total_calls=performance_data.get('total_calls', 0),
                    successful_calls=performance_data.get('successful_calls', 0),
                    average_response_time_ms=performance_data.get('average_response_time_ms', 0.0),
                    success_rate=performance_data.get('success_rate', 0.0),
                    circuit_breaker_state=performance_data.get('circuit_breaker_state', 'CLOSED')
                )
                
                api_quota_statuses_converted.append(ApiQuotaStatus(
                    api_name=api_name,
                    limit=status_data.get('limit', 0),
                    used=status_data.get('used', 0),
                    remaining=status_data.get('remaining', 0),
                    reset_date=status_data.get('last_reset_date', datetime.utcnow().isoformat()),
                    percentage_used=(status_data.get('used', 0) / status_data.get('limit', 1) * 100) if status_data.get('limit', 1) > 0 else 0,
                    status="OK" if status_data.get('remaining') is None or status_data.get('remaining', 0) > status_data.get('limit', 1) * 0.2 else "Warning" if status_data.get('remaining', 0) > 0 else "Critical",
                    predicted_exhaustion_date=status_data.get('predicted_exhaustion_date'),
                    recommended_action=None,  # Placeholder for recommendation logic
                    performance=performance_metrics
                ))
            except Exception as e:
                self.logger.error(f"Error creating ApiQuotaStatus for {api_name}: {e}")
                # Create a minimal valid entry so the dashboard doesn't crash
                api_quota_statuses_converted.append(ApiQuotaStatus(
                    api_name=api_name,
                    limit=0,
                    used=0,
                    remaining=0,
                    reset_date=datetime.utcnow().isoformat(),
                    percentage_used=0.0,
                    status="Unknown",
                    predicted_exhaustion_date=None,
                    recommended_action="Check API configuration",
                    performance=ApiPerformanceMetrics(
                        total_calls=0,
                        successful_calls=0,
                        average_response_time_ms=0.0,
                        success_rate=0.0,
                        circuit_breaker_state='UNKNOWN'
                    )
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
        self._cached_data = updates
        self._last_cache_update = now
        return updates

    async def _get_crawler_mission_status(self) -> CrawlerMissionStatus:
        """
        Gathers metrics for the Crawler Mission Status module.
        """
        start_time = time.monotonic()
        
        now = datetime.utcnow()
        twenty_four_hours_ago = timedelta(hours=24)

        # Use new database methods for efficiency
        active_jobs_count = self.db.get_active_jobs_count()
        queued_jobs_count = self.db.get_queued_jobs_count()
        
        completed_jobs_24h_count = len(self.db.get_crawl_jobs_by_status_and_time(CrawlStatus.COMPLETED, twenty_four_hours_ago))
        failed_jobs_24h_count = len(self.db.get_crawl_jobs_by_status_and_time(CrawlStatus.FAILED, twenty_four_hours_ago))
        
        total_pages_crawled_24h = self.db.get_total_pages_crawled_in_time_period(twenty_four_hours_ago)
        avg_job_completion_time_seconds = self.db.get_avg_job_completion_time_in_time_period(twenty_four_hours_ago)
        
        recent_job_errors_dataclasses = self.db.get_recent_job_errors(twenty_four_hours_ago, limit=10)
        recent_job_errors_pydantic = [CrawlErrorResponse.from_crawl_error(err) for err in recent_job_errors_dataclasses]

        # Get queue stats with error handling
        try:
            queue_stats = await self.smart_crawl_queue.get_queue_stats()
            queue_depth = queue_stats.get("total_tasks_overall", 0)
        except Exception as e:
            self.logger.warning(f"Could not get queue stats: {e}. Using default values.")
            queue_depth = 0
        
        # Get satellite status for utilization calculation
        active_satellites_count = 0
        total_satellites_count = 0
        
        # Attempt to get from JobCoordinator if available
        try:
            from Link_Profiler.queue_system.job_coordinator import get_coordinator
            coordinator = get_coordinator()  # Remove await since get_coordinator is not async
            coordinator_stats = await coordinator.get_queue_stats()
            active_satellites_count = coordinator_stats.get("active_crawlers", 0)
            total_satellites_count = len(coordinator_stats.get("satellite_crawlers", {}))
        except Exception as e:
            self.logger.warning(f"Could not get active satellite count from JobCoordinator: {e}. Using 0.")

        satellite_utilization_percentage = (active_satellites_count / total_satellites_count * 100) if total_satellites_count > 0 else 0

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
            recent_job_errors=recent_job_errors_pydantic
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
            latest_log_for_satellite = db.get_latest_satellite_performance_logs(satellite_id=satellite_id, limit=1)
            
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
        
        # Try to query materialized view, fallback to defaults if it doesn't exist
        try:
            daily_backlink_stats_orm = db.get_session().execute(
                text("SELECT * FROM mv_daily_backlink_stats ORDER BY day DESC LIMIT 1")
            ).fetchone()
            
            total_backlinks_discovered = daily_backlink_stats_orm.total_backlinks_discovered if daily_backlink_stats_orm else 0
            unique_domains_discovered = daily_backlink_stats_orm.unique_domains_discovered if daily_backlink_stats_orm else 0
            potential_spam_links_24h = daily_backlink_stats_orm.potential_spam_links if daily_backlink_stats_orm else 0
            avg_authority_score = daily_backlink_stats_orm.avg_authority_passed if daily_backlink_stats_orm else 0
        except Exception as e:
            self.logger.warning(f"Could not query mv_daily_backlink_stats: {e}. Using default values.")
            total_backlinks_discovered = 0
            unique_domains_discovered = 0
            potential_spam_links_24h = 0
            avg_authority_score = 0

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
        
        # Try to query materialized view, fallback to defaults if it doesn't exist
        try:
            daily_domain_stats_orm = db.get_session().execute(
                text("SELECT * FROM mv_daily_domain_stats ORDER BY day DESC LIMIT 1")
            ).fetchone()

            total_domains_analyzed = daily_domain_stats_orm.total_domains_analyzed if daily_domain_stats_orm else 0
            valuable_expired_domains_found = daily_domain_stats_orm.valuable_domains_found if daily_domain_stats_orm else 0
            avg_domain_value_score = daily_domain_stats_orm.avg_domain_authority_score if daily_domain_stats_orm else 0
        except Exception as e:
            self.logger.warning(f"Could not query mv_daily_domain_stats: {e}. Using default values.")
            total_domains_analyzed = 0
            valuable_expired_domains_found = 0
            avg_domain_value_score = 0
            
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
        
        # Try to query materialized view, fallback to defaults if it doesn't exist
        try:
            daily_satellite_performance_orm = db.get_session().execute(
                text("SELECT * FROM mv_daily_satellite_performance ORDER BY day DESC LIMIT 1")
            ).fetchone()

            avg_crawl_speed_pages_per_minute = daily_satellite_performance_orm.avg_crawl_speed_ppm if daily_satellite_performance_orm else 0
            avg_success_rate_percentage = daily_satellite_performance_orm.avg_success_rate if daily_satellite_performance_orm else 0
            avg_response_time_ms = daily_satellite_performance_orm.avg_response_time_ms if daily_satellite_performance_orm else 0
        except Exception as e:
            self.logger.warning(f"Could not query mv_daily_satellite_performance: {e}. Using default values.")
            avg_crawl_speed_pages_per_minute = 0
            avg_success_rate_percentage = 0
            avg_response_time_ms = 0
            
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

    async def _safe_get_api_status(self) -> Dict[str, Any]:
        """Safely get API status with error handling"""
        try:
            if self.api_quota_manager:
                return await self.api_quota_manager.get_api_status()
            else:
                return {}
        except Exception as e:
            self.logger.warning(f"Could not get API quota status: {e}. Using empty dict.")
            return {}
    
    async def _safe_get_alerts(self) -> List[DashboardAlert]:
        """Safely get alerts with error handling"""
        try:
            if self.dashboard_alert_service:
                return await self.dashboard_alert_service.check_critical_alerts()
            else:
                return []
        except Exception as e:
            self.logger.warning(f"Could not get alerts: {e}. Using empty list.")
            return []
    
    def _get_fallback_crawler_status(self) -> CrawlerMissionStatus:
        """Fallback crawler mission status"""
        return CrawlerMissionStatus(
            active_jobs_count=0,
            queued_jobs_count=0,
            completed_jobs_24h_count=0,
            failed_jobs_24h_count=0,
            total_pages_crawled_24h=0,
            queue_depth=0,
            active_satellites_count=0,
            total_satellites_count=0,
            satellite_utilization_percentage=0.0,
            avg_job_completion_time_seconds=0.0,
            recent_job_errors=[]
        )
    
    def _get_fallback_backlink_metrics(self) -> BacklinkDiscoveryMetrics:
        """Fallback backlink discovery metrics"""
        return BacklinkDiscoveryMetrics(
            total_backlinks_discovered=0,
            unique_domains_discovered=0,
            new_backlinks_24h=0,
            avg_authority_score=0.0,
            top_linking_domains=[],
            top_target_urls=[],
            potential_spam_links_24h=0
        )
    
    def _get_fallback_domain_metrics(self) -> DomainIntelligenceMetrics:
        """Fallback domain intelligence metrics"""
        return DomainIntelligenceMetrics(
            total_domains_analyzed=0,
            valuable_expired_domains_found=0,
            avg_domain_value_score=0.0,
            new_domains_added_24h=0,
            top_niches_identified=[]
        )
    
    def _get_fallback_performance_metrics(self) -> PerformanceOptimizationMetrics:
        """Fallback performance optimization metrics"""
        return PerformanceOptimizationMetrics(
            avg_crawl_speed_pages_per_minute=0.0,
            avg_success_rate_percentage=0.0,
            avg_response_time_ms=0.0,
            bottlenecks_detected=[],
            top_performing_satellites=[],
            worst_performing_satellites=[]
        )

# Singleton instance (will be initialized in main.py)
mission_control_service: Optional['MissionControlService'] = None

def initialize_mission_control_service(redis_client, smart_crawl_queue, api_quota_manager, dashboard_alert_service):
    """Initialize the global mission control service instance."""
    global mission_control_service
    mission_control_service = MissionControlService(
        redis_client=redis_client,
        smart_crawl_queue=smart_crawl_queue,
        api_quota_manager=api_quota_manager,
        dashboard_alert_service=dashboard_alert_service
    )
    return mission_control_service

def get_mission_control_service():
    """Get the global mission control service instance."""
    return mission_control_service
