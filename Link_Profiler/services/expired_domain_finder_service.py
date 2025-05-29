"""
Expired Domain Finder Service - Identifies valuable expired domains.
File: Link_Profiler/services/expired_domain_finder_service.py
"""

import logging
from typing import List, Dict, Any, Optional

from Link_Profiler.services.domain_service import DomainService # Changed to absolute import
from Link_Profiler.services.domain_analyzer_service import DomainAnalyzerService # Changed to absolute import
from Link_Profiler.database.database import Database # Changed to absolute import


class ExpiredDomainFinderService:
    """
    Service responsible for finding and evaluating potentially valuable expired domains.
    """
    def __init__(self, database: Database, domain_service: DomainService, domain_analyzer_service: DomainAnalyzerService):
        self.db = database
        self.domain_service = domain_service
        self.domain_analyzer_service = domain_analyzer_service
        self.logger = logging.getLogger(__name__)

    async def find_valuable_expired_domains(
        self, 
        potential_domains: List[str],
        min_value_score: float = 50.0,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Iterates through a list of potential domain names, checks their availability,
        and analyzes their potential value as expired domains.
        
        Args:
            potential_domains: A list of domain names to check.
            min_value_score: The minimum value score a domain must have to be considered valuable.
            limit: Optional. The maximum number of valuable domains to return.
            
        Returns:
            A list of dictionaries, each containing the domain name and its analysis result,
            for domains that are available and meet the value criteria.
        """
        self.logger.info(f"Starting search for valuable expired domains among {len(potential_domains)} candidates.")
        
        valuable_expired_domains = []
        
        # The domain_service needs to be used as a context manager to ensure its internal
        # aiohttp session is active for API calls.
        async with self.domain_service as ds: 
            for i, domain_name in enumerate(potential_domains):
                if limit and len(valuable_expired_domains) >= limit:
                    self.logger.info(f"Reached limit of {limit} valuable expired domains.")
                    break

                self.logger.info(f"Processing domain {i+1}/{len(potential_domains)}: {domain_name}")
                
                # Step 1: Check if the domain is available
                # Use the 'ds' (domain_service) from the async context manager
                is_available = await ds.check_domain_availability(domain_name) 
                
                if not is_available:
                    self.logger.info(f"Domain {domain_name} is NOT available. Skipping analysis.")
                    continue # Skip to the next domain if not available
                
                self.logger.info(f"Domain {domain_name} IS available. Proceeding with analysis.")
                
                # Step 2: Analyze the domain's value
                # domain_analyzer_service already uses domain_service internally,
                # and it will use the same context-managed instance passed to it.
                analysis_result = await self.domain_analyzer_service.analyze_domain_for_expiration_value(domain_name)
                
                if analysis_result.get("is_valuable") and analysis_result.get("value_score", 0) >= min_value_score:
                    self.logger.info(f"Domain {domain_name} is valuable (Score: {analysis_result.get('value_score'):.2f}). Adding to results.")
                    valuable_expired_domains.append(analysis_result)
                else:
                    self.logger.info(f"Domain {domain_name} is not valuable enough (Score: {analysis_result.get('value_score'):.2f}).")
                    
        self.logger.info(f"Finished search. Found {len(valuable_expired_domains)} valuable expired domains.")
        return valuable_expired_domains
