import logging
from typing import Optional
from Link_Profiler.utils.session_manager import SessionManager
from datetime import datetime # Import datetime

class BaseAPIClient:
    """
    Base class for all API clients to provide common functionality
    like session management and logging.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session_manager = session_manager
        if self.session_manager is None:
            # Fallback to the global singleton if not explicitly provided
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager
            self.session_manager = global_session_manager
            self.logger.warning(f"No SessionManager provided for {self.__class__.__name__}. Using global singleton.")

    async def __aenter__(self):
        """Ensure the session manager is entered when using the client as an async context manager."""
        if self.session_manager:
            await self.session_manager.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ensure the session manager is exited when using the client as an async context manager."""
        if self.session_manager:
            await self.session_manager.__aexit__(exc_type, exc_val, exc_tb)

    async def _make_request(self, method: str, url: str, **kwargs):
        """
        Internal helper to make requests using the shared session manager.
        Handles common errors and logging.
        """
        if not self.session_manager:
            self.logger.error("SessionManager is not initialized for this client.")
            raise RuntimeError("SessionManager is not initialized.")

        try:
            response = await self.session_manager.request(method, url, **kwargs)
            response.raise_for_status()  # Raise an exception for bad status codes
            
            # Add last_fetched_at to the response object if it's a dict/json
            try:
                json_data = await response.json()
                json_data['last_fetched_at'] = datetime.utcnow().isoformat()
                return json_data
            except Exception:
                # If response is not JSON, return the response object itself
                return response
        except Exception as e:
            self.logger.error(f"Request to {url} failed: {e}")
            raise
