"""
Data Aggregation Service - Aggregates data from various free APIs into a unified DomainIntelligence model.
File: Link_Profiler/services/data_aggregation_service.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import redis.asyncio as redis
from collections import Counter
from urllib.parse import urljoin, urlparse
import re

from bs4 import BeautifulSoup

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.core.models import DomainIntelligence, SocialMention, serialize_model
from Link_Profiler.database.database import Database

# Import all clients and services that provide data
from Link_Profiler.clients.google_search_console_client import GSCClient
from Link_Profiler.clients.google_pagespeed_client import PageSpeedClient
from Link_Profiler.clients.google_trends_client import GoogleTrendsClient
from Link_Profiler.clients.whois_client import WHOISClient
from Link_Profiler.clients.dns_client import DNSClient
from Link_Profiler.clients.reddit_client import RedditClient
from Link_Profiler.clients.youtube_client import YouTubeClient
from Link_Profiler.clients.news_api_client import NewsAPIClient
from Link_Profiler.clients.wayback_machine_client import WaybackClient
from Link_Profiler.clients.common_crawl_client import CommonCrawlClient
from Link_Profiler.clients.nominatim_client import NominatimClient
from Link_Profiler.clients.security_trails_client import SecurityTrailsClient
from Link_Profiler.clients.ssl_labs_client import SSLLabsClient

# Import services that wrap these clients
from Link_Profiler.services.domain_service import DomainService
from Link_Profiler.services.serp_service import SERPService
from Link_Profiler.services.keyword_service import KeywordService
from Link_Profiler.services.social_media_service import SocialMediaService
from Link_Profiler.services.historical_data_service import HistoricalDataService
from Link_Profiler.services.local_seo_service import LocalSEOService
from Link_Profiler.services.security_audit_service import SecurityAuditService
from Link_Profiler.services.ai_service import AIService # For content analysis, sentiment etc.
from Link_Profiler.utils.session_manager import session_manager

logger = logging.getLogger(__name__)

class DataAggregationService:
    """
    Aggregates data from various free APIs and internal services to build a comprehensive
    DomainIntelligence profile for a given domain.
    """
    def __init__(
        self,
        database: Database,
        redis_client: Optional[redis.Redis],
        cache_ttl: int,
        gsc_client: GSCClient,
        pagespeed_client: PageSpeedClient,
        google_trends_client: GoogleTrendsClient,
        whois_client: WHOISClient,
        dns_client: DNSClient,
        reddit_client: RedditClient,
        youtube_client: YouTubeClient,
        news_api_client: NewsAPIClient,
        wayback_client: WaybackClient,
        common_crawl_client: CommonCrawlClient,
        nominatim_client: NominatimClient,
        security_trails_client: SecurityTrailsClient,
        ssl_labs_client: SSLLabsClient,
        domain_service: DomainService,
        serp_service: SERPService,
        keyword_service: KeywordService,
        social_media_service: SocialMediaService,
        historical_data_service: HistoricalDataService,
        local_seo_service: LocalSEOService,
        security_audit_service: SecurityAuditService,
        ai_service: AIService
    ):
        self.db = database
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.logger = logging.getLogger(__name__)

        # Store all clients and services
        self.gsc_client = gsc_client
        self.pagespeed_client = pagespeed_client
        self.google_trends_client = google_trends_client
        self.whois_client = whois_client
        self.dns_client = dns_client
        self.reddit_client = reddit_client
        self.youtube_client = youtube_client
        self.news_api_client = news_api_client
        self.wayback_client = wayback_client
        self.common_crawl_client = common_crawl_client
        self.nominatim_client = nominatim_client
        self.security_trails_client = security_trails_client
        self.ssl_labs_client = ssl_labs_client

        self.domain_service = domain_service
        self.serp_service = serp_service
        self.keyword_service = keyword_service
        self.social_media_service = social_media_service
        self.historical_data_service = historical_data_service
        self.local_seo_service = local_seo_service
        self.security_audit_service = security_audit_service
        self.ai_service = ai_service

    async def __aenter__(self):
        """No specific async setup needed for this class, clients/services handle their own."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific async cleanup needed for this class."""
        pass

    async def _get_cached_response(self, cache_key: str) -> Optional[Any]:
        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    self.logger.debug(f"Cache hit for {cache_key}")
                    return json.loads(cached_data)
            except Exception as e:
                self.logger.error(f"Error retrieving from cache for {cache_key}: {e}", exc_info=True)
        return None

    async def _set_cached_response(self, cache_key: str, data: Any):
        if self.redis_client:
            try:
                await self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(data))
                self.logger.debug(f"Cached {cache_key} with TTL {self.cache_ttl}")
            except Exception as e:
                self.logger.error(f"Error setting cache for {cache_key}: {e}", exc_info=True)

    async def aggregate_domain_intelligence(self, domain: str) -> DomainIntelligence:
        """
        Aggregates data from various free APIs and internal services
        to create a comprehensive DomainIntelligence profile.
        """
        self.logger.info(f"Starting comprehensive data aggregation for domain: {domain}.")
        
        # Fetch data concurrently from various sources
        tasks = [
            self.get_domain_technical_data(domain),
            self.get_domain_seo_data(domain),
            self.get_domain_social_data(domain),
            self.get_domain_historical_data(domain),
            self.get_domain_security_data(domain),
            self.get_domain_content_insights(domain) # New: Content insights via AI
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Initialize DomainIntelligence with basic info
        domain_intelligence = DomainIntelligence(
            domain_name=domain,
            last_updated=datetime.now(),
            data_sources=[]
        )

        # Merge results into the DomainIntelligence object
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"Error aggregating data for domain {domain} from task {i}: {result}", exc_info=True)
                continue # Skip this source if it failed

            if i == 0: # Technical Data
                domain_intelligence.technical_data_summary = result
                if result: domain_intelligence.data_sources.append("Technical Data")
            elif i == 1: # SEO Data
                domain_intelligence.seo_metrics = result # This is a dict, not a float
                if result: domain_intelligence.data_sources.append("SEO Data")
            elif i == 2: # Social Data
                domain_intelligence.social_data_summary = result
                if result: domain_intelligence.data_sources.append("Social Data")
                # Aggregate social mentions count and sentiment
                total_mentions = 0
                sentiment_scores = []
                top_platforms = set()
                for platform, data in result.items():
                    if data and isinstance(data, list):
                        total_mentions += len(data)
                        for item in data:
                            if 'sentiment' in item and item['sentiment'] in ['positive', 'negative', 'neutral']:
                                sentiment_scores.append({'positive': 1, 'neutral': 0, 'negative': -1}.get(item['sentiment'], 0))
                            if 'platform' in item:
                                top_platforms.add(item['platform'])
                domain_intelligence.total_social_mentions = total_mentions
                if sentiment_scores:
                    domain_intelligence.avg_sentiment_score = sum(sentiment_scores) / len(sentiment_scores)
                domain_intelligence.top_social_platforms = list(top_platforms)
            elif i == 3: # Historical Data
                domain_intelligence.historical_data_summary = result
                if result: domain_intelligence.data_sources.append("Historical Data")
            elif i == 4: # Security Data
                domain_intelligence.security_data_summary = result
                if result: domain_intelligence.data_sources.append("Security Data")
            elif i == 5: # Content Insights (AI)
                domain_intelligence.content_data_summary = result
                if result: domain_intelligence.data_sources.append("Content Insights")
                # Aggregate content quality and gaps
                domain_intelligence.avg_content_quality_score = result.get('avg_content_quality_score', 0.0)
                domain_intelligence.content_gaps_identified = result.get('content_gaps_identified', 0)

        # Calculate overall confidence score (simple sum of available sources)
        domain_intelligence.confidence_score = len(domain_intelligence.data_sources) / len(tasks) * 100 if tasks else 0

        # Save the aggregated intelligence to the database
        self.db.save_domain_intelligence(domain_intelligence)
        self.logger.info(f"Comprehensive data aggregation for {domain} completed and saved.")
        return domain_intelligence

    async def get_domain_technical_data(self, domain: str) -> Dict[str, Any]:
        """Aggregates technical data for a domain."""
        self.logger.debug(f"Fetching technical data for {domain}.")
        technical_data = {}
        
        # WHOIS data
        whois_info = await self.whois_client.get_domain_info(domain)
        technical_data['whois'] = whois_info
        
        # DNS records (A, MX, NS)
        dns_a = await self.dns_client.get_dns_records(domain, 'A')
        technical_data['dns_a'] = dns_a
        dns_mx = await self.dns_client.get_dns_records(domain, 'MX')
        technical_data['dns_mx'] = dns_mx
        dns_ns = await self.dns_client.get_dns_records(domain, 'NS')
        technical_data['dns_ns'] = dns_ns

        # PageSpeed Insights for main domain (mobile strategy)
        pagespeed_metrics = await self.serp_service.get_pagespeed_metrics_for_url(f"https://{domain}", 'mobile')
        technical_data['pagespeed_mobile'] = serialize_model(pagespeed_metrics) if pagespeed_metrics else {}
        
        # Aggregate average performance/accessibility scores
        if pagespeed_metrics:
            technical_data['avg_performance_score'] = pagespeed_metrics.performance_score
            technical_data['avg_accessibility_score'] = pagespeed_metrics.accessibility_score

        return technical_data

    async def get_domain_seo_data(self, domain: str) -> Dict[str, Any]:
        """Aggregates SEO-related data for a domain."""
        self.logger.debug(f"Fetching SEO data for {domain}.")
        seo_data = {}

        # Google Trends for the domain as a keyword
        trends = await self.google_trends_client.get_keyword_trends([domain])
        seo_data['google_trends'] = trends

        # GSC Search Analytics (if enabled and authenticated)
        if self.gsc_client.enabled:
            today = datetime.now()
            one_year_ago = today - timedelta(days=365)
            gsc_analytics = await self.gsc_client.get_search_analytics(
                site_url=f"https://{domain}/", # GSC expects verified property URL
                start_date=one_year_ago.strftime("%Y-%m-%d"),
                end_date=today.strftime("%Y-%m-%d")
            )
            seo_data['gsc_search_analytics'] = gsc_analytics
        else:
            self.logger.warning(f"GSC client not enabled for SEO data aggregation for {domain}.")

        # Subdomain discovery (from SecurityTrails, but relevant for SEO)
        subdomains = await self.security_audit_service.get_subdomain_data(domain)
        seo_data['subdomains'] = subdomains

        # You could also integrate keyword data (top keywords, etc.) here from KeywordService
        # For example, get top 10 keywords the domain ranks for from your DB
        # top_ranked_keywords = self.db.get_keywords_ranked_for_domains([domain]).get(domain, set())
        # seo_data['top_ranked_keywords'] = list(top_ranked_keywords)

        return seo_data

    async def get_domain_social_data(self, domain: str) -> Dict[str, Any]:
        """Aggregates social media mentions for a domain."""
        self.logger.debug(f"Fetching social data for {domain}.")
        social_data = {}
        
        # Search for brand mentions on Reddit
        reddit_mentions = await self.reddit_client.search_mentions(domain)
        social_data['reddit_mentions'] = [serialize_model(sm) for sm in reddit_mentions] if reddit_mentions else []
        if reddit_mentions:
            self.db.add_social_mentions([SocialMention(
                id=str(item.get('id', '')), # Reddit API might not provide a unique ID directly in search results
                query=domain,
                platform='reddit',
                mention_url=item.get('url', ''),
                mention_text=item.get('mention_text', ''), # Use mention_text from client response
                author=item.get('author', ''),
                published_date=datetime.fromisoformat(item['published_date']) if 'published_date' in item else datetime.now(),
                sentiment=item.get('sentiment'),
                engagement_score=item.get('engagement_score')
            ) for item in reddit_mentions])

        # Search for news mentions
        news_mentions = await self.news_api_client.search_news(domain)
        social_data['news_mentions'] = news_mentions
        if news_mentions:
            self.db.add_social_mentions([SocialMention(
                id=str(item.get('url', '')), # Use URL as ID for news articles
                query=domain,
                platform='newsapi',
                mention_url=item.get('url', ''),
                mention_text=item.get('title', ''),
                author=item.get('author', ''),
                published_date=datetime.fromisoformat(item['published_at']) if 'published_at' in item else datetime.now(),
                sentiment=None, # NewsAPI doesn't provide sentiment
                engagement_score=None
            ) for item in news_mentions])

        # Search for YouTube videos
        youtube_videos = await self.youtube_client.search_videos(domain)
        social_data['youtube_videos'] = youtube_videos
        if youtube_videos:
            # For YouTube, we might want to fetch stats for each video separately
            # This is a simplified approach
            self.db.add_social_mentions([SocialMention(
                id=str(item.get('video_id', '')),
                query=domain,
                platform='youtube',
                mention_url=item.get('url', ''),
                mention_text=item.get('title', ''),
                author=item.get('channel_title', ''),
                published_date=datetime.fromisoformat(item['published_at']) if 'published_at' in item else datetime.now(),
                sentiment=None,
                engagement_score=None
            ) for item in youtube_videos])

        return social_data

    async def get_domain_historical_data(self, domain: str) -> Dict[str, Any]:
        """Aggregates historical data for a domain."""
        self.logger.debug(f"Fetching historical data for {domain}.")
        historical_data = {}

        # Wayback Machine snapshots
        wayback_snapshots = await self.wayback_client.get_snapshots(f"https://{domain}", limit=5)
        historical_data['wayback_snapshots'] = wayback_snapshots

        # Common Crawl records
        common_crawl_records = await self.common_crawl_client.search_domain(domain, limit=5)
        historical_data['common_crawl_records'] = common_crawl_records

        # Estimated domain age from Wayback Machine
        earliest_snapshot_date = await self.historical_data_service.get_domain_age_from_wayback(domain)
        historical_data['estimated_first_seen'] = earliest_snapshot_date.isoformat() if earliest_snapshot_date else None

        return historical_data

    async def get_domain_security_data(self, domain: str) -> Dict[str, Any]:
        """Aggregates security-related data for a domain."""
        self.logger.debug(f"Fetching security data for {domain}.")
        security_data = {}

        # SSL analysis for main domain
        ssl_analysis = await self.ssl_labs_client.analyze_ssl(domain)
        security_data['ssl_analysis'] = ssl_analysis
        
        # Subdomain discovery
        subdomains = await self.security_trails_client.get_subdomains(domain)
        security_data['security_trails_subdomains'] = subdomains

        # DNS history (A records)
        dns_history_a = await self.security_trails_client.get_dns_history(domain, 'a')
        security_data['security_trails_dns_history_a'] = dns_history_a

        return security_data

    async def get_domain_content_insights(self, domain: str) -> Dict[str, Any]:
        """Crawl a few pages from the domain and analyse their content."""
        self.logger.debug(f"Fetching content insights for {domain}.")

        async def _fetch_page(url: str) -> Optional[str]:
            try:
                async with session_manager.get(url, timeout=10) as resp:
                    if resp.status == 200 and 'text/html' in resp.headers.get('Content-Type', ''):
                        return await resp.text()
            except Exception as e:
                self.logger.warning(f"Failed to fetch {url}: {e}")
            return None

        def _extract_internal_links(html: str, base_url: str, limit: int = 2) -> List[str]:
            soup = BeautifulSoup(html, 'lxml')
            links: List[str] = []
            for a in soup.find_all('a', href=True):
                href = urljoin(base_url, a['href'])
                if urlparse(href).netloc.endswith(domain) and href not in links:
                    links.append(href)
                if len(links) >= limit:
                    break
            return links

        def _basic_nlp(text: str) -> Dict[str, Any]:
            words = re.findall(r"\b\w+\b", text.lower())
            words = [w for w in words if len(w) > 4]
            topics = [w for w, _ in Counter(words).most_common(5)]
            return {"entities": [], "sentiment": "neutral", "topics": topics}

        await session_manager.__aenter__()
        try:
            homepage_url = f"https://{domain}"
            homepage_html = await _fetch_page(homepage_url)
            if not homepage_html:
                homepage_url = f"http://{domain}"
                homepage_html = await _fetch_page(homepage_url)
            if not homepage_html:
                self.logger.warning(f"Unable to fetch homepage for {domain}")
                return {}

            urls_to_analyze = [homepage_url]
            urls_to_analyze.extend(_extract_internal_links(homepage_html, homepage_url))

            page_details = []
            for url in urls_to_analyze:
                html = homepage_html if url == homepage_url else await _fetch_page(url)
                if not html:
                    continue
                text = BeautifulSoup(html, 'lxml').get_text(separator=' ', strip=True)
                detail = {"url": url, "word_count": len(text.split())}

                if self.ai_service.enabled:
                    try:
                        nlp_res = await self.ai_service.analyze_content_nlp(text[:4000])
                        score_res = await self.ai_service.score_content(text[:4000], domain)
                        detail.update(nlp_res)
                        detail.update(score_res)
                    except Exception as e:
                        self.logger.error(f"AI analysis failed for {url}: {e}")
                else:
                    detail.update(_basic_nlp(text))
                page_details.append(detail)

            if not page_details:
                return {}

            avg_quality = sum(d.get('seo_score', 0) for d in page_details) / len(page_details)
            avg_readability = sum(d.get('readability_score', 0) for d in page_details) / len(page_details)
            topics_counter = Counter(t for d in page_details for t in d.get('topics', []))
            content_insights = {
                'avg_content_quality_score': round(avg_quality, 2),
                'avg_readability_score': round(avg_readability, 2),
                'content_gaps_identified': sum(len(d.get('improvement_suggestions', [])) for d in page_details),
                'top_content_topics': [t for t, _ in topics_counter.most_common(5)],
                'pages_analyzed': page_details
            }
            return content_insights
        finally:
            await session_manager.__aexit__(None, None, None)

