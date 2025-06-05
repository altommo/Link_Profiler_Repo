"""
User Agent Manager - Provides realistic user agents and request headers for rotation.
File: Link_Profiler/utils/user_agent_manager.py
"""

import random
import logging
import time # Import time for time.time()
from typing import Dict, List, Any, Optional

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

        self.logger = logging.getLogger(__name__ + ".UserAgentManager")
        self.user_agents = self._load_user_agents()
        self.current_user_agent: Optional[str] = None
        self.current_headers: Dict[str, str] = {}
        self.last_rotation_time: float = 0.0
        self.rotation_interval: int = 300 # Rotate every 5 minutes by default

        if not self.user_agents:
            self.logger.warning("No user agents loaded. Using a default user agent.")
            self.user_agents = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"]
        
        self.rotate_user_agent() # Set initial user agent and headers

    def _load_user_agents(self) -> List[str]:
        """
        Loads user agents from a predefined list or a file.
        For simplicity, we'll use a hardcoded list here.
        In a real application, this might load from a JSON/TXT file.
        """
        # A small selection of common user agents
        return [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/108.0.1462.54",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64; rv:107.0) Gecko/20100101 Firefox/107.0",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
            "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
            "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)",
            "Mozilla/5.0 (compatible; SemrushBot/7~bl; +http://www.semrush.com/bot.html)"
        ]

    def get_random_user_agent(self) -> str:
        """Returns a random user agent from the pool."""
        return random.choice(self.user_agents)

    def get_random_headers(self) -> Dict[str, str]:
        """
        Returns a set of random, realistic HTTP headers including a user agent.
        This can be expanded with more headers like Accept, Accept-Language, etc.
        """
        user_agent = self.get_random_user_agent()
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }
        # Add some common browser-specific headers
        if "Chrome" in user_agent:
            headers["Sec-Fetch-Dest"] = "document"
            headers["Sec-Fetch-Mode"] = "navigate"
            headers["Sec-Fetch-Site"] = "none"
            headers["Sec-Fetch-User"] = "?1"
        elif "Firefox" in user_agent:
            headers["DNT"] = "1" # Do Not Track
        
        return headers

    def rotate_user_agent(self) -> str:
        """
        Rotates the current user agent and associated headers.
        This method is called periodically or when a new request is made.
        """
        self.current_user_agent = self.get_random_user_agent()
        self.current_headers = self.get_random_headers()
        self.last_rotation_time = time.time()
        self.logger.debug(f"User agent rotated to: {self.current_user_agent}")
        return self.current_user_agent

    def get_current_user_agent(self) -> str:
        """Returns the currently active user agent."""
        if not self.current_user_agent or (time.time() - self.last_rotation_time > self.rotation_interval):
            self.rotate_user_agent()
        return self.current_user_agent

    def get_current_headers(self) -> Dict[str, str]:
        """Returns the currently active set of headers."""
        if not self.current_headers or (time.time() - self.last_rotation_time > self.rotation_interval):
            self.rotate_user_agent()
        return self.current_headers

# Create a singleton instance
user_agent_manager = UserAgentManager()
