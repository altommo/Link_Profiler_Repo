"""
Competitive Analysis Service - Provides insights into competitor strategies.
File: Link_Profiler/services/competitive_analysis_service.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Set
from urllib.parse import urlparse
from datetime import datetime # Import datetime for analysis_date

from Link_Profiler.database.database import Database
from Link_Profiler.core.models import LinkIntersectResult, CompetitiveKeywordAnalysisResult
from Link_Profiler.services.backlink_service import BacklinkService
from Link_Profiler.services.serp_service import SERPService

logger = logging.getLogger(__name__)

class CompetitiveAnalysisService:
    """
    Service for performing various competitive analyses, such as link intersect
    and competitive keyword analysis.
    """
    def __init__(
        self, 
        database: Database,
        backlink_service: BacklinkService,
        serp_service: SERPService
    ):
        self.db = database
        self.backlink_service = backlink_service
        self.serp_service = serp_service
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        """No specific async setup needed for this class."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific async cleanup needed for this class."""
        pass

    async def perform_link_intersect_analysis(self, primary_domain: str, competitor_domains: List[str]) -> LinkIntersectResult:
        """
        Performs a link intersect analysis to find common linking domains.
        Finds source domains that link to the primary domain AND at least one of the competitor domains.
        """
        self.logger.info(f"Starting link intersect analysis for {primary_domain} against {competitor_domains}.")
        
        # The core logic for this is already in BacklinkService, so we delegate.
        result = await self.backlink_service.perform_link_intersect_analysis(primary_domain, competitor_domains)
        
        # Ensure analysis_date is set
        result.analysis_date = datetime.utcnow()
        result.last_fetched_at = datetime.utcnow() # Ensure last_fetched_at is set
        
        self.logger.info(f"Link intersect analysis completed. Found {len(result.common_linking_domains)} common linking domains.")
        return result

    async def perform_competitive_keyword_analysis(self, primary_domain: str, competitor_domains: List[str]) -> CompetitiveKeywordAnalysisResult:
        """
        Performs a competitive keyword analysis.
        Identifies common keywords, keyword gaps (competitors rank for but primary doesn't),
        and primary's unique keywords.
        """
        self.logger.info(f"Starting competitive keyword analysis for {primary_domain} against {competitor_domains}.")

        all_domains = [primary_domain] + competitor_domains
        
        # Fetch all keywords ranked by each domain from the database
        # This assumes SERP results have been previously stored for these domains.
        ranked_keywords_map: Dict[str, Set[str]] = self.db.get_keywords_ranked_for_domains(all_domains)

        primary_keywords = ranked_keywords_map.get(primary_domain, set())
        
        common_keywords: Set[str] = set()
        keyword_gaps: Dict[str, List[str]] = {comp: [] for comp in competitor_domains}
        
        # Initialize common_keywords with primary's keywords to start intersection
        if primary_keywords:
            common_keywords.update(primary_keywords)

        for comp_domain in competitor_domains:
            comp_keywords = ranked_keywords_map.get(comp_domain, set())
            
            # Find keywords unique to this competitor (gap for primary)
            gap_for_this_comp = list(comp_keywords.difference(primary_keywords))
            if gap_for_this_comp:
                keyword_gaps[comp_domain] = sorted(gap_for_this_comp)
            
            # Update common keywords (intersection across all)
            if common_keywords: # Only intersect if common_keywords is not empty
                common_keywords = common_keywords.intersection(comp_keywords)
            else: # If common_keywords was empty, and this is the first competitor, initialize it
                common_keywords.update(comp_keywords)

        # Keywords unique to primary domain (not ranked by any competitor)
        primary_unique_keywords: Set[str] = set(primary_keywords)
        for comp_domain in competitor_domains:
            primary_unique_keywords = primary_unique_keywords.difference(ranked_keywords_map.get(comp_domain, set()))

        result = CompetitiveKeywordAnalysisResult(
            primary_domain=primary_domain,
            competitor_domains=competitor_domains,
            common_keywords=sorted(list(common_keywords)),
            keyword_gaps=keyword_gaps,
            primary_unique_keywords=sorted(list(primary_unique_keywords)),
            analysis_date=datetime.utcnow(), # Set analysis_date
            last_fetched_at=datetime.utcnow() # Set last_fetched_at
        )
        
        self.logger.info(f"Competitive keyword analysis completed for {primary_domain}. Common: {len(result.common_keywords)}, Primary Unique: {len(result.primary_unique_keywords)}.")
        return result
