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

        # Added: Comprehensive debugging logs
        logger.debug(f"Processing request - Host: {host}, Path: {request.url.path}")

        if host:
            parsed_host = urlparse(f"http://{host}") # Prepend scheme for urlparse
            # Fixed: Better subdomain detection with null checking
            hostname_parts = parsed_host.hostname.split('.') if parsed_host.hostname else []
            
            # Added: Comprehensive debugging logs
            logger.debug(f"Hostname parts: {hostname_parts}")
            
            # FIXED: Check for API requests FIRST, regardless of subdomain
            # API requests should be handled by FastAPI routers, not served as dashboard
            if (request.url.path.startswith("/api") or 
                request.url.path.startswith("/ws") or 
                request.url.path.startswith("/health") or 
                request.url.path.startswith("/metrics") or
                request.url.path.startswith("/token") or
                request.url.path.startswith("/register")):
                request.state.is_api_request = True
                logger.debug(f"🔧 API/WebSocket request detected from host: {host}, path: {request.url.path}")
                # Reset dashboard flags for API requests
                request.state.is_customer_dashboard = False
                request.state.is_mission_control_dashboard = False
            elif len(hostname_parts) > 2:  # Dashboard requests only if not API
                subdomain = hostname_parts[0]
                request.state.subdomain = subdomain
                logger.debug(f"Detected subdomain: {subdomain}")

                if subdomain == self.customer_subdomain:
                    request.state.is_customer_dashboard = True
                    logger.info(f"✅ Customer dashboard request detected from host: {host}")
                elif subdomain == self.mission_control_subdomain:
                    request.state.is_mission_control_dashboard = True
                    logger.info(f"✅ Mission control dashboard request detected from host: {host}")
                else:
                    logger.debug(f"Unknown subdomain '{subdomain}' from host: {host}")
            else:
                logger.debug(f"No subdomain detected in host: {host} (parts: {hostname_parts})")
        else:
            logger.warning("No host header found in request")

        # Log final state
        logger.debug(f"Request routing state - Customer: {request.state.is_customer_dashboard}, Mission Control: {request.state.is_mission_control_dashboard}, API: {request.state.is_api_request}")

        response = await call_next(request)
        return response
