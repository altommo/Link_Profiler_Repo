"""
Link Building Service - Identifies, scores, and manages link building prospects.
File: Link_Profiler/services/link_building_service.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
from urllib.parse import urlparse
import random
import uuid # Import the uuid module

from Link_Profiler.database.database import Database
from Link_Profiler.core.models import LinkProspect, Domain, Backlink, LinkProfile, LinkType # Import necessary models
from Link_Profiler.services.domain_service import DomainService
from Link_Profiler.services.backlink_service import BacklinkService
from Link_Profiler.services.serp_service import SERPService
from Link_Profiler.services.keyword_service import KeywordService
from Link_Profiler.services.ai_service import AIService

logger = logging.getLogger(__name__)

class LinkBuildingService:
    """
    Service for identifying, scoring, and managing link building prospects.
    """
    def __init__(
        self, 
        database: Database,
        domain_service: DomainService,
        backlink_service: BacklinkService,
        serp_service: SERPService,
        keyword_service: KeywordService,
        ai_service: AIService
    ):
        self.db = database
        self.domain_service = domain_service
        self.backlink_service = backlink_service
        self.serp_service = serp_service
        self.keyword_service = keyword_service
        self.ai_service = ai_service
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        """No specific async setup needed for this class."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific async cleanup needed for this class."""
        pass

    async def identify_and_score_prospects(
        self, 
        target_domain: str, 
        competitor_domains: List[str],
        keywords: List[str],
        min_domain_authority: float = 20.0,
        max_spam_score: float = 0.3,
        num_serp_results_to_check: int = 50,
        num_competitor_backlinks_to_check: int = 100
    ) -> List[LinkProspect]:
        """
        Identifies and scores potential link building prospects.
        
        This method combines several strategies:
        1. Competitor backlink analysis (finding domains linking to competitors but not target).
        2. SERP analysis (finding top-ranking pages for target keywords).
        3. Content analysis (identifying relevant content for outreach).
        4. Domain metrics (authority, spam score).
        """
        self.logger.info(f"Starting prospect identification for {target_domain} against {len(competitor_domains)} competitors and {len(keywords)} keywords.")
        
        identified_prospects: Dict[str, LinkProspect] = {} # Use dict to avoid duplicates by URL

        # Strategy 1: Competitor Backlink Analysis (Link Intersect)
        self.logger.info("Performing link intersect analysis to find prospects.")
        
        # Get all domains linking to competitors
        all_competitor_linking_domains: Set[str] = set()
        for comp_domain in competitor_domains:
            # In a real scenario, you'd fetch all backlinks for each competitor and extract source domains.
            # For now, we'll use the existing get_source_domains_for_target_domains which is more efficient
            # but might not capture all nuances of a full backlink profile for a competitor.
            comp_linking_domains = self.db.get_source_domains_for_target_domains([comp_domain]).get(comp_domain, set())
            all_competitor_linking_domains.update(comp_linking_domains)

        # Get all domains linking to our target domain
        target_linking_domains = self.db.get_source_domains_for_target_domains([target_domain]).get(target_domain, set())
        
        # Prospects are domains linking to competitors but NOT to our target domain
        potential_prospect_domains = all_competitor_linking_domains.difference(target_linking_domains)
        self.logger.info(f"Found {len(potential_prospect_domains)} potential prospect domains from competitor backlinks.")

        for domain_name in potential_prospect_domains:
            # Use domain_service to get domain info, which now uses APIQuotaManager
            domain_info = await self.domain_service.get_domain_info(domain_name)
            if domain_info and domain_info.authority_score >= min_domain_authority and domain_info.spam_score <= max_spam_score:
                # For now, use the root domain as the prospect URL
                prospect_url = f"https://{domain_name}"
                score = self._calculate_prospect_score(domain_info, LinkType.FOLLOW, "Links to competitor, not to target")
                if prospect_url not in identified_prospects or identified_prospects[prospect_url].score < score:
                    new_prospect = LinkProspect(
                        id=str(uuid.uuid4()), # Generate UUID for new prospect
                        target_domain=target_domain,
                        prospect_url=prospect_url,
                        prospect_seo_metrics=domain_info.seo_metrics, # Pass SEO metrics
                        score=score,
                        notes="Identified via competitor backlink analysis",
                        status="identified"
                    )
                    identified_prospects[prospect_url] = new_prospect
                    # self.db.save_link_prospect(new_prospect) # Save to DB if needed
                    self.logger.debug(f"Identified prospect: {prospect_url} (Score: {score})")

        # Strategy 2: SERP Analysis for Keywords
        self.logger.info("Performing SERP analysis for keywords to find prospects.")
        for keyword in keywords:
            # Use serp_service to get SERP data, which now uses APIQuotaManager
            serp_results = await self.serp_service.get_serp_data(keyword, num_serp_results_to_check)
            for result in serp_results:
                parsed_url = urlparse(result.url) # Use result.url
                result_domain = parsed_url.netloc
                
                # Skip if it's our target domain or a competitor domain
                if result_domain == target_domain or result_domain in competitor_domains:
                    continue
                
                # Use domain_service to get domain info, which now uses APIQuotaManager
                domain_info = await self.domain_service.get_domain_info(result_domain)
                if domain_info and domain_info.authority_score >= min_domain_authority and domain_info.spam_score <= max_spam_score:
                    score = self._calculate_prospect_score(domain_info, LinkType.FOLLOW, f"Ranks for '{keyword}'")
                    if result.url not in identified_prospects or identified_prospects[result.url].score < score:
                        new_prospect = LinkProspect(
                            id=str(uuid.uuid4()), # Generate UUID for new prospect
                            target_domain=target_domain,
                            prospect_url=result.url,
                            prospect_seo_metrics=domain_info.seo_metrics, # Pass SEO metrics
                            score=score,
                            notes=f"Identified via SERP analysis for keyword '{keyword}' (Pos: {result.rank})",
                            status="identified"
                        )
                        identified_prospects[result.url] = new_prospect
                        # self.db.save_link_prospect(new_prospect) # Save to DB if needed
                        self.logger.debug(f"Identified prospect: {result.url} (Score: {score})")

        # Strategy 3: Content-based identification (e.g., finding blogs/resources)
        # This would typically involve crawling relevant content and using AI to assess fit.
        # For now, simulate finding some content-based prospects.
        self.logger.info("Simulating content-based prospect identification.")
        if self.ai_service.enabled:
            simulated_content_ideas = await self.ai_service.generate_content_ideas(f"best {target_domain} alternatives", 3)
            for idea in simulated_content_ideas:
                # Create a plausible URL for the simulated content idea
                simulated_prospect_url = f"https://blog.{idea.replace(' ', '').lower()}.com/review-{random.randint(100,999)}"
                domain_name = urlparse(simulated_prospect_url).netloc
                
                # Ensure we don't add our own domain or competitors as prospects
                if domain_name == target_domain or domain_name in competitor_domains:
                    continue

                # Use domain_service to get domain info, which now uses APIQuotaManager
                domain_info = await self.domain_service.get_domain_info(domain_name)
                if domain_info and domain_info.authority_score >= min_domain_authority and domain_info.spam_score <= max_spam_score:
                    score = self._calculate_prospect_score(domain_info, LinkType.FOLLOW, f"Relevant content idea: '{idea}'")
                    if simulated_prospect_url not in identified_prospects or identified_prospects[simulated_prospect_url].score < score:
                        new_prospect = LinkProspect(
                            id=str(uuid.uuid4()), # Generate UUID for new prospect
                            target_domain=target_domain,
                            prospect_url=simulated_prospect_url,
                            prospect_seo_metrics=domain_info.seo_metrics, # Pass SEO metrics
                            score=score,
                            notes=f"Identified via AI content idea: '{idea}'",
                            status="identified"
                        )
                        identified_prospects[simulated_prospect_url] = new_prospect
                        # self.db.save_link_prospect(new_prospect) # Save to DB if needed
                        self.logger.debug(f"Identified prospect: {simulated_prospect_url} (Score: {score})")


        self.logger.info(f"Finished prospect identification. Total unique prospects: {len(identified_prospects)}")
        return sorted(list(identified_prospects.values()), key=lambda p: p.score, reverse=True)

    def _calculate_prospect_score(self, domain_info: Domain, link_type: LinkType, reason: str) -> float:
        """
        Calculates a numerical score for a link prospect based on various factors.
        This is a simplified scoring model.
        """
        score = 0.0

        # Base score from domain authority
        score += domain_info.authority_score * 0.5 # Max 50 points

        # Adjust for trust and spam
        score += domain_info.trust_score * 20 # Max 20 points
        score -= domain_info.spam_score * 30 # Max -15 points

        # Adjust for link type (dofollow preferred)
        if link_type == LinkType.DOFOLLOW:
            score += 10
        elif link_type == LinkType.NOFOLLOW:
            score += 2 # Still some value
        
        # Adjust for age (older domains might be more stable)
        if domain_info.registered_date: # Use registered_date from Domain dataclass
            age_days = (datetime.now() - domain_info.registered_date).days
            if age_days > 365 * 3: # Older than 3 years
                score += 5
        
        # Add points for specific reasons (e.g., ranking for keyword, competitor link)
        if "Ranks for" in reason:
            score += 15
        if "Links to competitor" in reason:
            score += 10

        # Ensure score is within a reasonable range
        return max(0.0, min(100.0, score))

    async def get_all_prospects(self, status_filter: Optional[str] = None) -> List[LinkProspect]:
        """
        Retrieves all stored link prospects, optionally filtered by status.
        """
        # This method would typically query the database for LinkProspects
        # For now, it's a placeholder.
        self.logger.warning("get_all_prospects is a placeholder and does not query DB.")
        return []

    async def update_prospect_status(self, url: str, new_status: str, last_outreach_date: Optional[datetime] = None) -> Optional[LinkProspect]:
        """
        Updates the status and last outreach date of a link prospect.
        """
        # This method would typically update a LinkProspect in the database
        # For now, it's a placeholder.
        self.logger.warning("update_prospect_status is a placeholder and does not update DB.")
        return None
