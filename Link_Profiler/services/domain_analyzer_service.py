"""
Domain Analyzer Service - Provides logic for analyzing domain value, especially for expired domains.
File: Link_Profiler/services/domain_analyzer_service.py
"""

import logging
from typing import Optional, Dict, Any
import json # Import json for AI response parsing

from Link_Profiler.core.models import Domain, LinkProfile, SpamLevel, serialize_model # Changed to absolute import
from Link_Profiler.services.domain_service import DomainService # Changed to absolute import
from Link_Profiler.database.database import Database # Changed to absolute import
from Link_Profiler.services.ai_service import AIService # New: Import AIService

class DomainAnalyzerService:
    """
    Service for analyzing the potential value of a domain, particularly for expired domains.
    """
    def __init__(self, database: Database, domain_service: DomainService, ai_service: AIService): # New: Accept ai_service
        self.db = database
        self.domain_service = domain_service
        self.ai_service = ai_service # Store AI service
        self.logger = logging.getLogger(__name__)

    async def analyze_domain_for_expiration_value(
        self, 
        domain_name: str,
        min_authority_score: float = 20.0,
        min_dofollow_backlinks: int = 5,
        min_age_days: int = 365,
        max_spam_score: float = 30.0
    ) -> Dict[str, Any]:
        """
        Analyzes a domain to determine its potential value if it were an expired domain.
        
        Args:
            domain_name: The name of the domain to analyze.
            min_authority_score: Minimum authority score for a valuable domain.
            min_dofollow_backlinks: Minimum dofollow backlinks for a valuable domain.
            min_age_days: Minimum age in days for a valuable domain.
            max_spam_score: Maximum spam score for a valuable domain.
            
        Returns:
            A dictionary containing the analysis results, including a value score
            and reasons for the score.
        """
        self.logger.info(f"Analyzing domain {domain_name} for expiration value.")
        
        domain_obj = self.db.get_domain(domain_name)
        
        # Ensure domain_service is used as a context manager to ensure its internal
        # aiohttp session is active for API calls.
        async with self.domain_service as ds: 
            if not domain_obj:
                # If not found in DB, try to fetch fresh info and save it
                self.logger.info(f"Domain {domain_name} not found in DB, fetching fresh info and saving.")
                domain_obj = await ds.get_domain_info(domain_name) # Use ds from context manager
                if domain_obj:
                    self.db.save_domain(domain_obj) # Save the newly fetched domain info
                else:
                    return {
                        "domain_name": domain_name,
                        "value_score": 0,
                        "is_valuable": False,
                        "reasons": ["Domain information could not be retrieved."],
                        "details": {}
                    }

            # Check availability (crucial for expired domains)
            is_available = await ds.check_domain_availability(domain_name) # Use ds from context manager
        
        # Retrieve link profile if available
        link_profile = self.db.get_link_profile(f"https://{domain_name}/") # Assuming root URL for profile
        
        value_score = 0
        reasons = []
        
        details = {
            "domain_info": serialize_model(domain_obj),
            "link_profile_info": serialize_model(link_profile) if link_profile else None,
            "is_available": is_available
        }

        if not is_available:
            reasons.append("Domain is not available for registration.")
            value_score -= 100 # Significantly reduce score if not available
        else:
            value_score += 20 # Bonus for availability
            reasons.append("Domain is available for registration.")

        # Rule 1: Authority Score (using domain_obj's score)
        if domain_obj.authority_score >= min_authority_score:
            value_score += 30
            reasons.append(f"High authority score ({domain_obj.authority_score:.2f}).")
        else:
            reasons.append(f"Low authority score ({domain_obj.authority_score:.2f}).")

        # Rule 2: Spam Score (using domain_obj's score)
        if domain_obj.spam_score <= max_spam_score:
            value_score += 25
            reasons.append(f"Acceptable spam score ({domain_obj.spam_score:.2f}).")
        else:
            reasons.append(f"High spam score ({domain_obj.spam_score:.2f}).")

        # Rule 3: Age (using domain_obj's age)
        if domain_obj.age_days and domain_obj.age_days >= min_age_days:
            value_score += 15
            reasons.append(f"Domain is old ({domain_obj.age_days} days).")
        else:
            reasons.append(f"Domain is relatively new or age unknown ({domain_obj.age_days or 'N/A'} days).")

        # Rule 4: Backlinks (if link profile exists)
        if link_profile:
            if link_profile.dofollow_links >= min_dofollow_backlinks:
                value_score += 40
                reasons.append(f"Sufficient dofollow backlinks ({link_profile.dofollow_links}).")
            else:
                reasons.append(f"Insufficient dofollow backlinks ({link_profile.dofollow_links}).")
            
            # Further check on backlink quality (e.g., unique referring domains)
            if link_profile.unique_domains > 0.5 * min_dofollow_backlinks: # Arbitrary rule
                value_score += 10
                reasons.append(f"Good number of unique referring domains ({link_profile.unique_domains}).")
            else:
                reasons.append(f"Low number of unique referring domains ({link_profile.unique_domains}).")
        else:
            reasons.append("No link profile available for analysis.")
            value_score -= 20 # Penalty for no link profile

        # New: AI-driven analysis for more nuanced insights
        if self.ai_service.enabled:
            self.logger.info(f"Performing AI-driven analysis for domain: {domain_name}")
            ai_analysis_result = await self.ai_service.analyze_domain_value(
                domain_name=domain_name,
                domain_info=domain_obj,
                link_profile_summary=link_profile
            )
            if ai_analysis_result:
                ai_value_adjustment = ai_analysis_result.get("value_adjustment", 0)
                ai_reasons = ai_analysis_result.get("reasons", [])
                ai_details = ai_analysis_result.get("details", {})

                value_score += ai_value_adjustment
                reasons.extend([f"AI Insight: {r}" for r in ai_reasons])
                details["ai_analysis"] = ai_details
                self.logger.info(f"AI adjusted score for {domain_name} by {ai_value_adjustment}. New score: {value_score}")
            else:
                reasons.append("AI domain analysis failed or unavailable.")
                self.logger.warning(f"AI domain analysis failed for {domain_name}.")

        is_valuable = value_score >= 50 # Threshold for "valuable"

        return {
            "domain_name": domain_name,
            "value_score": max(0, value_score), # Ensure score is not negative
            "is_valuable": is_valuable,
            "reasons": reasons,
            "details": details
        }
