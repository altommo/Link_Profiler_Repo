"""
User Agent Manager - Provides realistic user agents and request headers for rotation.
File: Link_Profiler/utils/user_agent_manager.py
"""

import random
from typing import Dict, List, Any

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
            # Chrome on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # Firefox on macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
            # Safari on macOS
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            # Edge on Windows
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            # Chrome on Linux
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # Firefox on Linux
            "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0",
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

# Create a singleton instance
user_agent_manager = UserAgentManager()
