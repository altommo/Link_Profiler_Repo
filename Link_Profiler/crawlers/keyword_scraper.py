import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import aiohttp
from urllib.parse import urlencode

from Link_Profiler.core.models import KeywordSuggestion
from Link_Profiler.utils.user_agent_manager import user_agent_manager
from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager
from Link_Profiler.utils.api_rate_limiter import api_rate_limited # Import the rate limiter

logger = logging.getLogger(__name__)

class KeywordScraper:
    """
    A web scraper for keyword suggestions from public sources (e.g., Google Autocomplete, related searches).
    This is a simplified example and would typically involve more complex scraping logic.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None):
        self.logger = logging.getLogger(__name__ + ".KeywordScraper")
        self.enabled = config_loader.get("keyword_scraper.enabled", False)
        self.session_manager = session_manager
        if self.session_manager is None:
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager
            self.session_manager = global_session_manager
            self.logger.warning("No SessionManager provided to KeywordScraper. Falling back to global SessionManager.")
        
        self.resilience_manager = resilience_manager
        if self.enabled and self.resilience_manager is None:
            raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")

        if not self.enabled:
            self.logger.info("Keyword Scraper is disabled by configuration.")

    async def __aenter__(self):
        """Initialise aiohttp session."""
        if self.enabled:
            self.logger.info("Entering KeywordScraper context.")
            await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        if self.enabled:
            self.logger.info("Exiting KeywordScraper context. Closing aiohttp session.")
            await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    @api_rate_limited(service="keyword_scraper", api_client_type="generic_scraper", endpoint="get_keyword_data")
    async def get_keyword_data(self, seed_keyword: str, num_suggestions: int = 10) -> List[KeywordSuggestion]:
        """
        Simulates scraping keyword suggestions from a search engine's autocomplete.
        """
        if not self.enabled:
            self.logger.warning(f"Keyword Scraper is disabled. Skipping scrape for '{seed_keyword}'.")
            return []

        self.logger.info(f"Simulating scraping keyword suggestions for seed: '{seed_keyword}' (Limit: {num_suggestions})...")
        
        # Simulate network request using resilience manager
        try:
            await self.resilience_manager.execute_with_resilience(
                lambda: self.session_manager.get(f"http://localhost:8080/simulate_keyword_scrape/{seed_keyword}"),
                url=f"http://localhost:8080/simulate_keyword_scrape/{seed_keyword}"
            )
        except aiohttp.ClientConnectorError:
            pass # Expected if dummy server not running
        except Exception as e:
            self.logger.warning(f"Unexpected error during simulated keyword scrape: {e}")

        suggestions = []
        for i in range(num_suggestions):
            suggested_keyword = f"{seed_keyword} {random.choice(['best', 'how to', 'guide', 'review'])} {i+1}"
            search_volume = random.randint(100, 10000)
            cpc_estimate = round(random.uniform(0.5, 5.0), 2)
            
            suggestions.append(
                KeywordSuggestion(
                    keyword=suggested_keyword,
                    search_volume=search_volume,
                    cpc=cpc_estimate,
                    competition=random.uniform(0.1, 0.9),
                    difficulty=random.randint(1, 100),
                    relevance=random.uniform(0.5, 1.0),
                    source="Scraped Autocomplete",
                    last_fetched_at=datetime.utcnow()
                )
            )
        self.logger.info(f"Simulated {len(suggestions)} scraped keyword suggestions for '{seed_keyword}'.")
        return suggestions
