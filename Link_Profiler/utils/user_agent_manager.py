"""
User Agent Manager - Provides realistic user agents and request headers for rotation.
File: Link_Profiler/utils/user_agent_manager.py
"""

import random
from typing import Dict, List, Any, Tuple
import logging # Import logging

logger = logging.getLogger(__name__)

class UserAgentManager:
    """
    Manages a pool of realistic user agents and associated HTTP headers.
    Implemented as a singleton.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UserAgentManager, cls).__new__(cls)
            cls._instance._initialized = False # Flag to ensure __init__ runs only once
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.user_agents = [
            # Chrome (Windows)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            
            # Chrome (Mac)
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            
            # Firefox (Windows)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            
            # Firefox (Mac)
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
            
            # Safari (Mac)
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            
            # Edge (Windows)
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            
            # Mobile Chrome (Android)
            "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            
            # Mobile Safari (iOS)
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
            
            # Googlebot (for specific cases where you want to identify as a search engine bot)
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            # Bingbot
            "Mozilla/5.0 (compatible; Bingbot/2.0; +http://www.bing.com/bingbot.htm)"
        ]

        self.accept_headers = [
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "application/json, text/javascript, */*; q=0.01" # For API calls
        ]

        self.accept_languages = [
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9",
            "en-CA,en;q=0.9",
            "es-ES,es;q=0.9",
            "fr-FR,fr;q=0.9"
        ]
        self.domain_rotation: Dict[str, str] = {}  # Track which UA was used for each domain
        self.last_used_index = 0

    def get_random_user_agent(self) -> str:
        """Returns a random user agent string."""
        return random.choice(self.user_agents)

    def get_random_headers(self) -> Dict[str, str]:
        """
        Returns a dictionary of realistic HTTP headers including a random User-Agent,
        Accept, and Accept-Language.
        """
        headers = {
            "User-Agent": self.get_random_user_agent(),
            "Accept": random.choice(self.accept_headers),
            "Accept-Language": random.choice(self.accept_languages),
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }
        return headers

    def get_user_agent_for_domain(self, domain: str) -> str:
        """Get consistent user agent for a domain to avoid detection"""
        if domain not in self.domain_rotation:
            # Assign a random but consistent UA for this domain
            self.domain_rotation[domain] = random.choice(self.user_agents)
            logger.info(f"Assigned user agent for {domain}: {self.domain_rotation[domain][:50]}...")
        
        return self.domain_rotation[domain]
    
    def rotate_user_agent(self) -> str:
        """Get next user agent in rotation"""
        ua = self.user_agents[self.last_used_index]
        self.last_used_index = (self.last_used_index + 1) % len(self.user_agents)
        return ua

# Create a singleton instance
user_agent_manager = UserAgentManager()
