import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import aiohttp # Import aiohttp

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.clients.base_client import BaseAPIClient
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

logger = logging.getLogger(__name__)

class YouTubeClient(BaseAPIClient):
    """
    Client for interacting with the YouTube Data API v3.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None):
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Pass api_quota_manager to base class
        self.logger = logging.getLogger(__name__ + ".YouTubeClient")
        self.base_url = config_loader.get("social_media_crawler.youtube_api.base_url")
        self.api_key = config_loader.get("social_media_crawler.youtube_api.api_key")
        self.enabled = config_loader.get("social_media_crawler.youtube_api.enabled", False)

        # Removed redundant check as BaseAPIClient handles resilience_manager validation
        # if self.enabled and self.resilience_manager is None:
        #     raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")

        if not self.enabled:
            self.logger.info("YouTube Data API is disabled by configuration.")
        elif not self.api_key:
            self.logger.warning("YouTube Data API key is missing. YouTube API will be disabled.")
            self.enabled = False

    @api_rate_limited(service="youtube_api", api_client_type="youtube_client", endpoint="search_videos")
    async def search_videos(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Searches YouTube for videos matching a query.
        
        Args:
            query (str): The search query.
            limit (int): Maximum number of results to retrieve.
            
        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each representing a video.
        """
        if not self.enabled:
            self.logger.warning(f"YouTube client not enabled. Skipping search for '{query}'.")
            return []

        endpoint = f"{self.base_url}/search"
        all_videos = []
        next_page_token = None
        
        # YouTube Data API maxResults is 50 per request
        max_results_per_page = 50

        while len(all_videos) < limit:
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "key": self.api_key,
                "maxResults": min(max_results_per_page, limit - len(all_videos)) # Request only what's needed
            }
            if next_page_token:
                params["pageToken"] = next_page_token

            self.logger.info(f"Searching YouTube for query: '{query}' (Current results: {len(all_videos)}/{limit})...")
            
            try:
                # _make_request now handles resilience and adds 'last_fetched_at'
                response_data = await self._make_request("GET", endpoint, params=params)
                
                articles_on_page = response_data.get("items", [])
                for item in articles_on_page:
                    video_id = item["id"]["videoId"]
                    all_videos.append({
                        "platform": "youtube",
                        "id": video_id,
                        "title": item["snippet"]["title"],
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "text": item["snippet"]["description"],
                        "author": item["snippet"]["channelTitle"],
                        "published_at": item["snippet"]["publishedAt"],
                        "raw_data": item,
                        "last_fetched_at": response_data.get('last_fetched_at') # Get from _make_request
                    })
                
                next_page_token = response_data.get("nextPageToken")
                if not next_page_token or not articles_on_page: # No more pages or no articles on this page
                    break
                
                # Enforce 1s throttle between calls
                await asyncio.sleep(1)

            except aiohttp.ClientResponseError as e:
                if e.status == 429:
                    self.logger.error(f"YouTube API quota exceeded (429) for '{query}'. Skipping further results for this query.", exc_info=True)
                    break # Stop on quota error
                else:
                    self.logger.error(f"Network/API error searching YouTube for '{query}' (Status: {e.status}): {e}", exc_info=True)
                    break # Break on other errors
            except Exception as e:
                self.logger.error(f"Error searching YouTube for '{query}': {e}", exc_info=True)
                break # Break on general error

        self.logger.info(f"Found {len(all_videos)} YouTube videos for '{query}'.")
        return all_videos[:limit] # Ensure we don't exceed the requested limit
