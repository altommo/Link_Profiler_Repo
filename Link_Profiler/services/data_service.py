import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse

from fastapi import HTTPException, status # Import HTTPException and status for access control

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.database.database import db, clickhouse_client
from Link_Profiler.utils.api_cache import APICache
from Link_Profiler.core.models import (
    Domain, Backlink, SEOMetrics, SERPResult, KeywordSuggestion,
    GSCBacklink, KeywordTrend, User, CrawlJob, ReportJob, ContentGapAnalysisResult,
    CompetitiveKeywordAnalysisResult, LinkProspect, TrackedDomain, TrackedKeyword # Import LinkProspect, TrackedDomain, TrackedKeyword
)
from Link_Profiler.utils.auth_utils import get_user_tier # Import get_user_tier

# Import service instances for live data fetching (assuming they are global singletons)
# These imports are placed here to avoid circular dependencies at module load time
try:
    from Link_Profiler.main import (
        domain_service_instance, backlink_service_instance, serp_service_instance,
        keyword_service_instance, ai_service_instance, link_prospecting_service_instance # Import LinkProspectingService
    )
except ImportError:
    # Fallback for testing or if main.py is not fully initialized
    logging.getLogger(__name__).warning("Could not import service instances from main.py. Live data fetching will be simulated or unavailable.")
    class DummyDomainService:
        async def get_domain_info(self, domain_name: str) -> Optional[Domain]:
            logging.getLogger(__name__).warning(f"Simulating live domain info for {domain_name}")
            return Domain(name=domain_name, authority_score=50, last_checked=datetime.now())
        async def get_domain_metrics(self, domain_name: str) -> Optional[Dict[str, Any]]:
            logging.getLogger(__name__).warning(f"Simulating live domain metrics for {domain_name}")
            return {"domain_authority": 50, "page_authority": 60, "last_fetched_at": datetime.utcnow().isoformat()}
        async def get_seo_audit(self, domain_name: str) -> Optional[SEOMetrics]:
            logging.getLogger(__name__).warning(f"Simulating live SEO audit for {domain_name}")
            return SEOMetrics(url=f"https://{domain_name}", seo_score=75, audit_timestamp=datetime.now())
    class DummyBacklinkService:
        async def get_backlinks(self, domain_name: str) -> List[Backlink]:
            logging.getLogger(__name__).warning(f"Simulating live backlinks for {domain_name}")
            return [Backlink(source_url=f"http://example.com/{i}", target_url=f"http://{domain_name}", anchor_text="test", first_seen=datetime.now()) for i in range(3)]
    class DummySerpService:
        async def get_competitors(self, domain_name: str) -> List[Dict[str, Any]]:
            logging.getLogger(__name__).warning(f"Simulating live competitors for {domain_name}")
            return [{"domain": f"competitor{i}.com", "common_keywords": 100} for i in range(3)]
        async def get_serp_results(self, keyword: str) -> List[SERPResult]:
            logging.getLogger(__name__).warning(f"Simulating live SERP results for {keyword}")
            return [SERPResult(keyword=keyword, rank=i+1, url=f"http://example.com/{i}", title=f"Title {i}", snippet=f"Snippet {i}", domain=f"example{i}.com", timestamp=datetime.now()) for i in range(3)]
    class DummyKeywordService:
        async def get_keyword_suggestions(self, keyword: str) -> List[KeywordSuggestion]:
            logging.getLogger(__name__).warning(f"Simulating live keyword suggestions for {keyword}")
            return [KeywordSuggestion(keyword=f"{keyword} long tail {i}", search_volume=100-i, difficulty=50+i) for i in range(3)]
    class DummyAIService:
        async def analyze_content_gap(self, target_url: str, competitor_urls: List[str]) -> Optional[ContentGapAnalysisResult]:
            logging.getLogger(__name__).warning(f"Simulating live content gap analysis for {target_url}")
            return ContentGapAnalysisResult(target_url=target_url, competitor_urls=competitor_urls, missing_topics=["topic1", "topic2"])
    class DummyLinkProspectingService:
        async def find_prospects(self, target_domain: str, **kwargs) -> List[LinkProspect]:
            logging.getLogger(__name__).warning(f"Simulating live link prospects for {target_domain}")
            return [LinkProspect(id=f"lp{i}", target_domain=target_domain, prospect_url=f"http://blog.example.com/post-{i}") for i in range(3)]
        async def perform_custom_analysis(self, domain: str, analysis_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
            logging.getLogger(__name__).warning(f"Simulating custom analysis for {domain} ({analysis_type})")
            return {"domain": domain, "analysis_type": analysis_type, "result": "simulated_success", "config": config}


    domain_service_instance = DummyDomainService()
    backlink_service_instance = DummyBacklinkService()
    serp_service_instance = DummySerpService()
    keyword_service_instance = DummyKeywordService()
    ai_service_instance = DummyAIService()
    link_prospecting_service_instance = DummyLinkProspectingService()


logger = logging.getLogger(__name__)

class DataService:
    """
    Service layer for fetching and managing data, implementing cache-first logic.
    This layer orchestrates data retrieval from cache, PostgreSQL, ClickHouse,
    and external API clients.
    """
    def __init__(self, database_client=None, ch_client=None, cache_client=None):
        self.db = database_client if database_client else db
        self.ch_client = ch_client if ch_client else clickhouse_client
        self.cache = cache_client if cache_client else APICache()
        self.logger = logging.getLogger(__name__ + ".DataService")
        self.allow_live_data_fetching = config_loader.get("data_fetching.allow_live_data_fetching", False)

    async def _fetch_and_cache(self, cache_key: str, fetch_func, ttl: int, force_live: bool = False):
        """
        Generic method to fetch data, apply cache-first logic, and store in cache.
        
        Args:
            cache_key (str): The key to use for caching.
            fetch_func (callable): An async function that fetches the live data.
            ttl (int): Time-to-live for the cache entry in seconds.
            force_live (bool): If True, bypass cache and fetch live data.
        """
        if not self.cache.enabled:
            self.logger.debug(f"Cache is disabled. Fetching live data for {cache_key}.")
            return await fetch_func()

        if force_live:
            self.logger.info(f"Force live data fetch requested for {cache_key}. Bypassing cache.")
            data = await fetch_func()
            if data is not None:
                await self.cache.set(cache_key, data, service="data_service", endpoint="generic_fetch", ttl=ttl)
            return data
        
        cached_data = await self.cache.get(cache_key, service="data_service", endpoint="generic_fetch")
        if cached_data:
            self.logger.debug(f"Returning cached data for {cache_key}.")
            return cached_data
        
        self.logger.info(f"Cache miss for {cache_key}. Fetching live data.")
        data = await fetch_func()
        if data is not None:
            await self.cache.set(cache_key, data, service="data_service", endpoint="generic_fetch", ttl=ttl)
        return data

    def validate_live_access(self, user: User, feature: str):
        """
        Checks if the user has permission to access live data for a specific feature.
        Raises HTTPException if access is denied.
        """
        # Check global config
        if not self.allow_live_data_fetching:
            self.logger.warning(f"Live data fetching requested for feature '{feature}' but is globally disabled.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Live data temporarily unavailable due to system configuration."
            )
        
        user_tier = get_user_tier(user) # Get user tier from auth_utils
        
        # Define which tiers can access live data for which features
        # This is a simplified example; you might have a more granular configuration
        PREMIUM_LIVE_FEATURES = [
            "backlinks", "gsc_backlinks_analytical", "keyword_trends_analytical",
            "single_job_status", "single_report_status",
            "domain_overview", "domain_backlinks", "domain_metrics", "domain_competitors",
            "domain_seo_audit", "domain_content_gaps", "keyword_analysis", "keyword_competitors",
            "domain_link_prospects", "custom_analysis",
            "tracked_domains", "tracked_keywords" # Added new features
        ]
        
        if user_tier == "free":
            self.logger.warning(f"Live data access denied for user {user.username} (tier: {user_tier}) for feature '{feature}'.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Live data requires a paid plan."
            )
        
        if user_tier == "basic" and feature in PREMIUM_LIVE_FEATURES:
            self.logger.warning(f"Live data access denied for user {user.username} (tier: {user_tier}) for feature '{feature}'. Requires Pro plan.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Live {feature} requires a Pro plan."
            )
        
        # Placeholder for usage limits (e.g., daily live API calls)
        # if user.live_api_calls_today >= user.plan_limits.live_calls_per_day:
        #     raise HTTPException(
        #         status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        #         detail="Live data quota exceeded for today."
        #     )
        
        # If all checks pass, track usage (placeholder)
        # self.increment_live_api_usage(user.id, feature)
        self.logger.info(f"Live data access granted for user {user.username} (tier: {user_tier}) for feature '{feature}'.")

    async def get_all_crawl_jobs(self, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all crawl jobs, cache-first.
        """
        feature = "crawl_jobs"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)
        
        async def fetch_live():
            jobs = self.db.get_all_crawl_jobs()
            return [job.to_dict() for job in jobs]
        
        return await self._fetch_and_cache(f"{feature}_all", fetch_live, ttl=3600, force_live=force_live) # Cache for 1 hour

    async def get_crawl_job_by_id(self, job_id: str, source: Optional[str] = None, current_user: Optional[User] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single crawl job by ID, cache-first.
        """
        feature = "single_job_status"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_{job_id}"

        async def fetch_live():
            job = self.db.get_crawl_job(job_id)
            return job.to_dict() if job else None
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=60, force_live=force_live) # Cache for 1 minute

    async def get_all_link_profiles(self, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all link profiles, cache-first.
        """
        feature = "link_profiles"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        async def fetch_live():
            profiles = self.db.get_all_link_profiles()
            return [profile.to_dict() for profile in profiles]
        
        return await self._fetch_and_cache(f"{feature}_all", fetch_live, ttl=86400, force_live=force_live) # Cache for 24 hours

    async def get_all_domains(self, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all domains, cache-first.
        """
        feature = "domains"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        async def fetch_live():
            domains = self.db.get_all_domains()
            return [domain.to_dict() for domain in domains]
        
        return await self._fetch_and_cache(f"{feature}_all", fetch_live, ttl=86400, force_live=force_live) # Cache for 24 hours

    async def get_all_backlinks(self, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves all backlinks, cache-first.
        Note: For large datasets, this might be better served directly from ClickHouse.
        """
        feature = "backlinks"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        async def fetch_live():
            # Example of fetching from PostgreSQL
            backlinks = self.db.get_all_backlinks()
            return [bl.to_dict() for bl in backlinks]
        
        return await self._fetch_and_cache(f"{feature}_all", fetch_live, ttl=3600, force_live=force_live) # Cache for 1 hour

    async def get_gsc_backlinks_analytical(self, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves GSC backlinks from ClickHouse, cache-first.
        """
        feature = "gsc_backlinks_analytical"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        async def fetch_live():
            # This would typically involve calling the GSC client and then inserting into ClickHouse
            # For now, we'll assume data is already in ClickHouse and fetch from there.
            # In a real scenario, you'd call GoogleSearchConsoleClient.fetch_backlinks() here.
            # Since ClickHouseClient doesn't have a direct 'get_all' method, this is a placeholder.
            self.logger.warning("Direct fetch for GSC backlinks analytical data is a placeholder. Implement actual ClickHouse query.")
            # Example: return self.ch_client.get_all_gsc_backlinks() if such a method existed
            return [] # Placeholder for actual ClickHouse query results
        
        return await self._fetch_and_cache(f"{feature}_all", fetch_live, ttl=86400, force_live=force_live) # Cache for 24 hours

    async def get_keyword_trends_analytical(self, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves keyword trends from ClickHouse, cache-first.
        """
        feature = "keyword_trends_analytical"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        async def fetch_live():
            # Similar to GSC backlinks, this is a placeholder for ClickHouse query.
            self.logger.warning("Direct fetch for keyword trends analytical data is a placeholder. Implement actual ClickHouse query.")
            # Example: return self.ch_client.get_all_keyword_trends() if such a method existed
            return [] # Placeholder for actual ClickHouse query results
        
        return await self._fetch_and_cache(f"{feature}_all", fetch_live, ttl=86400, force_live=force_live) # Cache for 24 hours

    async def get_report_job_by_id(self, job_id: str, source: Optional[str] = None, current_user: Optional[User] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves a single report job by ID, cache-first.
        """
        feature = "single_report_status"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_{job_id}"

        async def fetch_live():
            report_job = self.db.get_report_job(job_id)
            return report_job.to_dict() if report_job else None
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=60, force_live=force_live) # Cache for 1 minute

    async def get_domain_overview(self, domain: str, source: Optional[str] = None, current_user: Optional[User] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves a comprehensive overview for a given domain.
        """
        feature = "domain_overview"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_{domain}"

        async def fetch_live():
            # This calls the underlying domain_service to get live data
            domain_obj = await domain_service_instance.get_domain_info(domain)
            return domain_obj.to_dict() if domain_obj else None
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=3600, force_live=force_live) # Cache for 1 hour

    async def get_domain_backlinks(self, domain: str, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves backlinks for a domain.
        """
        feature = "domain_backlinks"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_{domain}"

        async def fetch_live():
            # This calls the underlying backlink_service to get live data
            backlinks = await backlink_service_instance.get_backlinks(domain)
            return [bl.to_dict() for bl in backlinks]
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=3600, force_live=force_live) # Cache for 1 hour

    async def get_domain_metrics(self, domain: str, source: Optional[str] = None, current_user: Optional[User] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves SEO metrics for a domain.
        """
        feature = "domain_metrics"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_{domain}"

        async def fetch_live():
            # This calls the underlying domain_service (or a dedicated metrics service) to get live data
            metrics = await domain_service_instance.get_domain_metrics(domain) # Assuming domain_service has this method
            return metrics # Assuming it returns a dict or can be converted
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=3600, force_live=force_live) # Cache for 1 hour

    async def get_domain_competitors(self, domain: str, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves top competitors for a domain.
        """
        feature = "domain_competitors"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_{domain}"

        async def fetch_live():
            # This calls the underlying serp_service (or keyword_service) to get live data
            competitors = await serp_service_instance.get_competitors(domain) # Assuming serp_service has this method
            return competitors # Assuming it returns a list of dicts
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=86400, force_live=force_live) # Cache for 24 hours

    async def get_domain_seo_audit(self, domain: str, source: Optional[str] = None, current_user: Optional[User] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves SEO audit results for a domain.
        """
        feature = "domain_seo_audit"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_{domain}"

        async def fetch_live():
            # This calls the underlying domain_service (or technical_auditor_service) to get live data
            seo_metrics = await domain_service_instance.get_seo_audit(domain) # Assuming domain_service has this method
            return seo_metrics.to_dict() if seo_metrics else None
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=86400, force_live=force_live) # Cache for 24 hours

    async def get_domain_content_gaps(self, domain: str, competitor_domains: List[str], source: Optional[str] = None, current_user: Optional[User] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves content gap analysis results for a domain against competitors.
        """
        feature = "domain_content_gaps"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        # Cache key should include competitor domains for uniqueness
        cache_key = f"{feature}_{domain}_{'_'.join(sorted(competitor_domains))}"

        async def fetch_live():
            # This calls the underlying AI service to perform content gap analysis
            content_gap_result = await ai_service_instance.analyze_content_gap(domain, competitor_domains) # Assuming AI service has this method
            return content_gap_result.to_dict() if content_gap_result else None
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=86400, force_live=force_live) # Cache for 24 hours

    async def get_keyword_analysis(self, keyword: str, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves keyword analysis (suggestions, trends, etc.) for a given keyword.
        """
        feature = "keyword_analysis"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_{keyword}"

        async def fetch_live():
            # This calls the underlying keyword_service to get live data
            suggestions = await keyword_service_instance.get_keyword_suggestions(keyword) # Assuming keyword_service has this method
            return [s.to_dict() for s in suggestions]
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=86400, force_live=force_live) # Cache for 24 hours

    async def get_keyword_competitors(self, keyword: str, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves top competitors for a keyword.
        """
        feature = "keyword_competitors"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_{keyword}"

        async def fetch_live():
            # This calls the underlying serp_service to get live data
            competitors = await serp_service_instance.get_serp_results(keyword) # Assuming serp_service can derive competitors from SERP
            # For simplicity, let's just return the top domains from SERP results as competitors
            unique_domains = list(set([res.domain for res in competitors if res.domain]))
            return [{"domain": d} for d in unique_domains[:5]] # Return top 5 unique domains
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=86400, force_live=force_live) # Cache for 24 hours

    async def get_domain_link_prospects(self, domain: str, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """
        Retrieves link prospects for a given domain.
        """
        feature = "domain_link_prospects"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_{domain}"

        async def fetch_live():
            # This calls the underlying link_prospecting_service to get live data
            prospects = await link_prospecting_service_instance.find_prospects(domain) # Assuming this method exists
            return [p.to_dict() for p in prospects]
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=86400, force_live=force_live) # Cache for 24 hours

    async def perform_custom_analysis(self, domain: str, analysis_type: str, config: Dict[str, Any], current_user: Optional[User] = None) -> Dict[str, Any]:
        """
        Performs a custom analysis for a domain. This will always be a 'live' operation
        as it triggers a new job.
        """
        feature = "custom_analysis"
        # Custom analysis is inherently a live operation, so we always validate access
        if current_user:
            self.validate_live_access(current_user, feature)
        
        # This will trigger a job submission via the link_prospecting_service or a dedicated analysis service
        # For now, we'll use link_prospecting_service_instance as a placeholder for a service that can trigger jobs.
        result = await link_prospecting_service_instance.perform_custom_analysis(domain, analysis_type, config)
        return result

    # --- Tracked Entities Data Service Methods ---
    async def create_tracked_domain(self, tracked_domain: TrackedDomain, current_user: User) -> Dict[str, Any]:
        """Creates a new tracked domain."""
        # No live access validation needed for creation, but ensure user context is passed
        tracked_domain.user_id = current_user.id
        tracked_domain.organization_id = current_user.organization_id
        new_domain = self.db.create_tracked_domain(tracked_domain)
        return new_domain.to_dict()

    async def get_tracked_domain(self, domain_id: str, source: Optional[str] = None, current_user: Optional[User] = None) -> Optional[Dict[str, Any]]:
        """Retrieves a tracked domain by ID."""
        feature = "tracked_domains"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_{domain_id}"

        async def fetch_live():
            domain = self.db.get_tracked_domain(domain_id)
            # Add authorization check: ensure user owns this tracked domain or is admin
            if domain and domain.user_id != current_user.id and not current_user.is_admin:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to view this tracked domain.")
            return domain.to_dict() if domain else None
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=3600, force_live=force_live) # Cache for 1 hour

    async def get_tracked_domain_by_name(self, domain_name: str, source: Optional[str] = None, current_user: Optional[User] = None) -> Optional[Dict[str, Any]]:
        """Retrieves a tracked domain by name."""
        feature = "tracked_domains"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_by_name_{domain_name}"

        async def fetch_live():
            domain = self.db.get_tracked_domain_by_name(domain_name)
            # Add authorization check: ensure user owns this tracked domain or is admin
            if domain and domain.user_id != current_user.id and not current_user.is_admin:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to view this tracked domain.")
            return domain.to_dict() if domain else None
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=3600, force_live=force_live) # Cache for 1 hour

    async def get_all_tracked_domains(self, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """Retrieves all tracked domains for the current user/organization."""
        feature = "tracked_domains"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_all_{current_user.id}_{current_user.organization_id}"

        async def fetch_live():
            domains = self.db.get_tracked_domains(user_id=current_user.id, organization_id=current_user.organization_id)
            return [d.to_dict() for d in domains]
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=3600, force_live=force_live) # Cache for 1 hour

    async def update_tracked_domain(self, domain_id: str, update_data: Dict[str, Any], current_user: User) -> Dict[str, Any]:
        """Updates an existing tracked domain."""
        # Always live operation for updates
        feature = "tracked_domains"
        self.validate_live_access(current_user, feature) # Validate access for updates

        existing_domain = self.db.get_tracked_domain(domain_id)
        if not existing_domain:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked domain not found.")
        
        # Authorization check: ensure user owns this tracked domain or is admin
        if existing_domain.user_id != current_user.id and not current_user.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to update this tracked domain.")

        # Apply updates
        for key, value in update_data.items():
            setattr(existing_domain, key, value)
        
        updated_domain = self.db.update_tracked_domain(existing_domain)
        return updated_domain.to_dict()

    async def delete_tracked_domain(self, domain_id: str, current_user: User) -> bool:
        """Deletes a tracked domain."""
        # Always live operation for deletes
        feature = "tracked_domains"
        self.validate_live_access(current_user, feature) # Validate access for deletes

        existing_domain = self.db.get_tracked_domain(domain_id)
        if not existing_domain:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked domain not found.")
        
        # Authorization check: ensure user owns this tracked domain or is admin
        if existing_domain.user_id != current_user.id and not current_user.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to delete this tracked domain.")

        return self.db.delete_tracked_domain(domain_id)

    async def create_tracked_keyword(self, tracked_keyword: TrackedKeyword, current_user: User) -> Dict[str, Any]:
        """Creates a new tracked keyword."""
        # No live access validation needed for creation, but ensure user context is passed
        tracked_keyword.user_id = current_user.id
        tracked_keyword.organization_id = current_user.organization_id
        new_keyword = self.db.create_tracked_keyword(tracked_keyword)
        return new_keyword.to_dict()

    async def get_tracked_keyword(self, keyword_id: str, source: Optional[str] = None, current_user: Optional[User] = None) -> Optional[Dict[str, Any]]:
        """Retrieves a tracked keyword by ID."""
        feature = "tracked_keywords"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_{keyword_id}"

        async def fetch_live():
            keyword = self.db.get_tracked_keyword(keyword_id)
            # Add authorization check: ensure user owns this tracked keyword or is admin
            if keyword and keyword.user_id != current_user.id and not current_user.is_admin:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to view this tracked keyword.")
            return keyword.to_dict() if keyword else None
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=3600, force_live=force_live) # Cache for 1 hour

    async def get_tracked_keyword_by_name(self, keyword_name: str, source: Optional[str] = None, current_user: Optional[User] = None) -> Optional[Dict[str, Any]]:
        """Retrieves a tracked keyword by name."""
        feature = "tracked_keywords"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_by_name_{keyword_name}"

        async def fetch_live():
            keyword = self.db.get_tracked_keyword_by_name(keyword_name)
            # Add authorization check: ensure user owns this tracked keyword or is admin
            if keyword and keyword.user_id != current_user.id and not current_user.is_admin:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to view this tracked keyword.")
            return keyword.to_dict() if keyword else None
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=3600, force_live=force_live) # Cache for 1 hour

    async def get_all_tracked_keywords(self, source: Optional[str] = None, current_user: Optional[User] = None) -> List[Dict[str, Any]]:
        """Retrieves all tracked keywords for the current user/organization."""
        feature = "tracked_keywords"
        force_live = (source and source.lower() == "live")
        if force_live and current_user:
            self.validate_live_access(current_user, feature)

        cache_key = f"{feature}_all_{current_user.id}_{current_user.organization_id}"

        async def fetch_live():
            keywords = self.db.get_tracked_keywords(user_id=current_user.id, organization_id=current_user.organization_id)
            return [k.to_dict() for k in keywords]
        
        return await self._fetch_and_cache(cache_key, fetch_live, ttl=3600, force_live=force_live) # Cache for 1 hour

    async def update_tracked_keyword(self, keyword_id: str, update_data: Dict[str, Any], current_user: User) -> Dict[str, Any]:
        """Updates an existing tracked keyword."""
        # Always live operation for updates
        feature = "tracked_keywords"
        self.validate_live_access(current_user, feature) # Validate access for updates

        existing_keyword = self.db.get_tracked_keyword(keyword_id)
        if not existing_keyword:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked keyword not found.")
        
        # Authorization check: ensure user owns this tracked keyword or is admin
        if existing_keyword.user_id != current_user.id and not current_user.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to update this tracked keyword.")

        # Apply updates
        for key, value in update_data.items():
            setattr(existing_keyword, key, value)
        
        updated_keyword = self.db.update_tracked_keyword(existing_keyword)
        return updated_keyword.to_dict()

    async def delete_tracked_keyword(self, keyword_id: str, current_user: User) -> bool:
        """Deletes a tracked keyword."""
        # Always live operation for deletes
        feature = "tracked_keywords"
        self.validate_live_access(current_user, feature) # Validate access for deletes

        existing_keyword = self.db.get_tracked_keyword(keyword_id)
        if not existing_keyword:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked keyword not found.")
        
        # Authorization check: ensure user owns this tracked keyword or is admin
        if existing_keyword.user_id != current_user.id and not current_user.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to delete this tracked keyword.")

        return self.db.delete_tracked_keyword(keyword_id)


# Initialize the service with the singleton database clients
data_service = DataService(database_client=db, ch_client=clickhouse_client, cache_client=APICache())
