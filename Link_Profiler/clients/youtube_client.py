"""
YouTube Client - Interacts with the YouTube Data API v3.
File: Link_Profiler/clients/youtube_client.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import aiohttp
import random

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited

logger = logging.getLogger(__name__)

class YouTubeClient:
    """
    Client for fetching data from the YouTube Data API v3.
    Requires a Google Cloud API Key.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".YouTubeClient")
        self.api_key = config_loader.get("social_media_crawler.youtube_api.api_key")
        self.base_url = config_loader.get("social_media_crawler.youtube_api.base_url")
        self.enabled = config_loader.get("social_media_crawler.youtube_api.enabled", False)
        self._session: Optional[aiohttp.ClientSession] = None

        if not self.enabled:
            self.logger.info("YouTube Data API is disabled by configuration.")
        elif not self.api_key:
            self.logger.warning("YouTube Data API is enabled but API key is missing. Functionality will be simulated.")
            self.enabled = False # Effectively disable if key is missing

    async def __aenter__(self):
        """Initialise aiohttp session."""
        if self.enabled:
            self.logger.info("Entering YouTubeClient context.")
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        if self.enabled and self._session and not self._session.closed:
            self.logger.info("Exiting YouTubeClient context. Closing aiohttp session.")
            await self._session.close()
            self._session = None

    @api_rate_limited(service="youtube_api", api_client_type="youtube_client", endpoint="search_videos")
    async def search_videos(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Searches for YouTube videos based on a query.
        
        Args:
            query (str): The search query.
            limit (int): Maximum number of videos to retrieve.
            
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a video.
        """
        if not self.enabled:
            self.logger.warning(f"YouTube Data API is disabled. Simulating video search for '{query}'.")
            return self._simulate_videos(query, limit)

        endpoint = f"{self.base_url}/search"
        params = {
            'part': 'snippet',
            'q': query,
            'type': 'video',
            'maxResults': limit,
            'key': self.api_key
        }

        self.logger.info(f"Calling YouTube Data API for video search: '{query}' (limit: {limit})...")
        results = []
        try:
            async with self._session.get(endpoint, params=params, timeout=15) as response:
                response.raise_for_status()
                data = await response.json()
                
                for item in data.get('items', []):
                    video_id = item['id']['videoId']
                    snippet = item['snippet']
                    results.append({
                        'platform': 'youtube',
                        'video_id': video_id,
                        'title': snippet.get('title'),
                        'description': snippet.get('description'),
                        'published_at': snippet.get('publishedAt'),
                        'channel_title': snippet.get('channelTitle'),
                        'url': f"https://www.youtube.com/watch?v={video_id}"
                    })
            self.logger.info(f"Found {len(results)} YouTube videos for '{query}'.")
            return results
        except aiohttp.ClientError as e:
            self.logger.error(f"Network/API error searching YouTube for '{query}': {e}", exc_info=True)
            return self._simulate_videos(query, limit) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error searching YouTube for '{query}': {e}", exc_info=True)
            return self._simulate_videos(query, limit) # Fallback to simulation on error

    @api_rate_limited(service="youtube_api", api_client_type="youtube_client", endpoint="get_video_stats")
    async def get_video_stats(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetches statistics for a specific YouTube video.
        
        Args:
            video_id (str): The ID of the video.
            
        Returns:
            Optional[Dict[str, Any]]: Dictionary of video statistics, or None.
        """
        if not self.enabled:
            self.logger.warning(f"YouTube Data API is disabled. Simulating video stats for {video_id}.")
            return self._simulate_video_stats(video_id)

        endpoint = f"{self.base_url}/videos"
        params = {
            'part': 'statistics,snippet', # Request snippet for title/description
            'id': video_id,
            'key': self.api_key
        }

        self.logger.info(f"Calling YouTube Data API for video stats: {video_id}...")
        try:
            async with self._session.get(endpoint, params=params, timeout=10) as response:
                response.raise_for_status()
                data = await response.json()
                
                items = data.get('items', [])
                if not items:
                    self.logger.warning(f"No video found for ID: {video_id}.")
                    return None
                
                video_data = items[0]
                stats = video_data.get('statistics', {})
                snippet = video_data.get('snippet', {})

                result = {
                    'video_id': video_id,
                    'title': snippet.get('title'),
                    'description': snippet.get('description'),
                    'published_at': snippet.get('publishedAt'),
                    'view_count': int(stats.get('viewCount', 0)),
                    'like_count': int(stats.get('likeCount', 0)),
                    'comment_count': int(stats.get('commentCount', 0)),
                    'url': f"https://www.youtube.com/watch?v={video_id}"
                }
                self.logger.info(f"Fetched stats for YouTube video {video_id}.")
                return result
        except aiohttp.ClientError as e:
            self.logger.error(f"Network/API error fetching YouTube video stats for {video_id}: {e}", exc_info=True)
            return self._simulate_video_stats(video_id) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error fetching YouTube video stats for {video_id}: {e}", exc_info=True)
            return self._simulate_video_stats(video_id) # Fallback to simulation on error

    def _simulate_videos(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """Helper to generate simulated video search results."""
        self.logger.info(f"Simulating YouTube video search for '{query}' (limit: {limit}).")
        simulated_results = []
        for i in range(limit):
            video_id = f"sim_video_{random.randint(100000, 999999)}"
            simulated_results.append({
                'platform': 'youtube',
                'video_id': video_id,
                'title': f"Simulated Video about {query} #{i+1}",
                'description': f"This is a simulated description for a video about {query}.",
                'published_at': (datetime.now() - timedelta(days=random.randint(1, 730))).isoformat(),
                'channel_title': f"Simulated Channel {random.randint(1, 50)}",
                'url': f"https://www.youtube.com/watch?v={video_id}"
            })
        return simulated_results

    def _simulate_video_stats(self, video_id: str) -> Dict[str, Any]:
        """Helper to generate simulated video statistics."""
        self.logger.info(f"Simulating YouTube video stats for {video_id}.")
        return {
            'video_id': video_id,
            'title': f"Simulated Video Title for {video_id}",
            'description': "A simulated video description.",
            'published_at': (datetime.now() - timedelta(days=random.randint(1, 730))).isoformat(),
            'view_count': random.randint(1000, 1000000),
            'like_count': random.randint(10, 50000),
            'comment_count': random.randint(0, 5000),
            'url': f"https://www.youtube.com/watch?v={video_id}"
        }
