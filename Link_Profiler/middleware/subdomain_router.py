import logging
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class SubdomainRouterMiddleware(BaseHTTPMiddleware):
    """
    Middleware to detect subdomains and set request context.
    It identifies if a request is for the 'customer' dashboard or 'mission-control'
    (admin) dashboard based on predefined subdomains.
    """
    def __init__(self, app: ASGIApp, customer_subdomain: str, mission_control_subdomain: str):
        super().__init__(app)
        self.customer_subdomain = customer_subdomain
        self.mission_control_subdomain = mission_control_subdomain
        logger.info(f"SubdomainRouterMiddleware initialized: Customer='{customer_subdomain}', MissionControl='{mission_control_subdomain}'")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        host = request.headers.get("host")
        request.state.is_customer_dashboard = False
        request.state.is_mission_control_dashboard = False
        request.state.is_api_request = False # Default for API requests
        request.state.subdomain = None

        if host:
            parsed_host = urlparse(f"http://{host}") # Prepend scheme for urlparse
            hostname_parts = parsed_host.hostname.split('.')
            
            if len(hostname_parts) > 2: # e.g., customer.example.com
                subdomain = hostname_parts[0]
                request.state.subdomain = subdomain

                if subdomain == self.customer_subdomain:
                    request.state.is_customer_dashboard = True
                    logger.debug(f"Request for customer dashboard detected from host: {host}")
                elif subdomain == self.mission_control_subdomain:
                    request.state.is_mission_control_dashboard = True
                    logger.debug(f"Request for mission control dashboard detected from host: {host}")
            
            # Determine if it's an API request (e.g., api.example.com or example.com/api)
            # This is a simplified check; a more robust solution might involve checking path prefixes
            # or having a dedicated API subdomain. For now, assume if it's not a dashboard subdomain,
            # and the path starts with /api, it's an API request.
            if not request.state.is_customer_dashboard and not request.state.is_mission_control_dashboard:
                if request.url.path.startswith("/api"):
                    request.state.is_api_request = True
                    logger.debug(f"API request detected from host: {host}, path: {request.url.path}")
                else:
                    # If no specific subdomain and not /api, it's likely the root domain serving the main API docs or default UI
                    logger.debug(f"Default/root domain request from host: {host}, path: {request.url.path}")

        response = await call_next(request)
        return response
