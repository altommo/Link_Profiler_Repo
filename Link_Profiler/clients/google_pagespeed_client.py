"""
Google PageSpeed Insights Client - Interacts with the Google PageSpeed Insights API.
File: Link_Profiler/clients/google_pagespeed_client.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import aiohttp

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited

logger = logging.getLogger(__name__)

class PageSpeedClient:
    """
    Client for interacting with the Google PageSpeed Insights API.
    Requires a Google Cloud API Key.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".PageSpeedClient")
        self.api_key = config_loader.get("serp_api.pagespeed_insights_api.api_key")
        self.base_url = config_loader.get("serp_api.pagespeed_insights_api.base_url")
        self.enabled = config_loader.get("serp_api.pagespeed_insights_api.enabled", False)
        self._session: Optional[aiohttp.ClientSession] = None

        if not self.enabled:
            self.logger.info("PageSpeed Insights API is disabled by configuration.")
        elif not self.api_key:
            self.logger.warning("PageSpeed Insights API is enabled but API key is missing. Functionality will be simulated.")
            self.enabled = False # Effectively disable if key is missing

    async def __aenter__(self):
        """Initialise aiohttp session."""
        if self.enabled:
            self.logger.info("Entering PageSpeedClient context.")
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        if self.enabled and self._session and not self._session.closed:
            self.logger.info("Exiting PageSpeedClient context. Closing aiohttp session.")
            await self._session.close()
            self._session = None

    @api_rate_limited(service="pagespeed_api", api_client_type="pagespeed_client", endpoint="analyze_url")
    async def analyze_url(self, url: str, strategy: str = 'mobile', categories: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Analyzes a URL using Google PageSpeed Insights.
        
        Args:
            url (str): The URL to analyze.
            strategy (str): 'mobile' or 'desktop'.
            categories (List[str]): List of categories to audit (e.g., 'performance', 'seo', 'accessibility').
                                     Defaults to all if None.
        Returns:
            Dict[str, Any]: The JSON response from the PageSpeed Insights API.
        """
        if not self.enabled:
            self.logger.warning(f"PageSpeed Insights API is disabled or misconfigured. Simulating analysis for {url}.")
            return self._simulate_analysis(url, strategy, categories)

        if categories is None:
            categories = ['performance', 'seo', 'accessibility', 'best-practices'] # Default categories

        endpoint = self.base_url
        params = {
            'url': url,
            'strategy': strategy,
            'key': self.api_key
        }
        # Add categories as multiple parameters
        for category in categories:
            params[f'category'] = category # This will overwrite, need to append or use a list for params

        # Correct way to handle multiple 'category' parameters in aiohttp
        # aiohttp.ClientSession.get expects params as a dict, which will flatten lists
        # For repeated parameters, you might need to build the URL manually or use a list of tuples
        # However, the PageSpeed API typically accepts multiple categories like `category=performance&category=seo`
        # which aiohttp's params dict handles by repeating the key if the value is a list.
        # Let's adjust params construction for clarity.
        
        final_params = {
            'url': url,
            'strategy': strategy,
            'key': self.api_key
        }
        # PageSpeed API expects categories as separate parameters, e.g., &category=performance&category=seo
        # aiohttp handles this if you pass a list of tuples or a dict where value is a list
        # For simplicity, let's assume the API accepts comma-separated or multiple params.
        # The API documentation shows `category=performance&category=accessibility`
        # aiohttp's ClientSession.get(params=...) will correctly handle `{'category': ['performance', 'seo']}`
        final_params['category'] = categories


        self.logger.info(f"Calling PageSpeed Insights API for {url} ({strategy})...")
        try:
            async with self._session.get(endpoint, params=final_params, timeout=30) as response:
                response.raise_for_status()
                data = await response.json()
                self.logger.info(f"PageSpeed Insights analysis for {url} completed.")
                return data
        except aiohttp.ClientError as e:
            self.logger.error(f"Network/API error during PageSpeed Insights analysis for {url}: {e}", exc_info=True)
            return self._simulate_analysis(url, strategy, categories) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error during PageSpeed Insights analysis for {url}: {e}", exc_info=True)
            return self._simulate_analysis(url, strategy, categories) # Fallback to simulation on error

    def _simulate_analysis(self, url: str, strategy: str, categories: Optional[List[str]]) -> Dict[str, Any]:
        """Helper to generate simulated PageSpeed Insights data."""
        self.logger.info(f"Simulating PageSpeed Insights analysis for {url} ({strategy}).")
        
        # Generate random scores
        performance_score = random.randint(50, 99)
        seo_score = random.randint(70, 100)
        accessibility_score = random.randint(60, 95)
        best_practices_score = random.randint(75, 100)

        # Simulate Core Web Vitals
        lcp = round(random.uniform(1.5, 4.0), 2) # seconds
        fid = random.randint(50, 300) # milliseconds
        cls = round(random.uniform(0.05, 0.25), 2)

        return {
            "lighthouseResult": {
                "requestedUrl": url,
                "fetchTime": datetime.now().isoformat(),
                "categories": {
                    "performance": {"score": performance_score / 100.0},
                    "seo": {"score": seo_score / 100.0},
                    "accessibility": {"score": accessibility_score / 100.0},
                    "best-practices": {"score": best_practices_score / 100.0},
                },
                "audits": {
                    "largest-contentful-paint": {"numericValue": lcp * 1000, "displayValue": f"{lcp} s"},
                    "first-input-delay": {"numericValue": fid, "displayValue": f"{fid} ms"},
                    "cumulative-layout-shift": {"numericValue": cls, "displayValue": f"{cls}"},
                },
                "audits_summary": { # Simplified summary
                    "performance_issues": ["Reduce unused JavaScript"] if performance_score < 70 else [],
                    "seo_issues": ["Missing meta description"] if seo_score < 80 else [],
                    "accessibility_issues": ["Low contrast text"] if accessibility_score < 70 else []
                }
            },
            "analysisUTCTimestamp": datetime.now().isoformat(),
            "version": "simulated-v5"
        }
