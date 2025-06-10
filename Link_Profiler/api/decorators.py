import logging
from functools import wraps
from typing import Callable, Any, Optional, Annotated
from fastapi import Depends, HTTPException, status, Query
from Link_Profiler.utils.auth_utils import get_current_user
from Link_Profiler.core.models import User

logger = logging.getLogger(__name__)

def require_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to ensure an API endpoint requires authentication.
    It injects the `current_user` dependency.
    """
    @wraps(func)
    async def wrapper(*args, current_user: Annotated[User, Depends(get_current_user)], **kwargs) -> Any:
        # The get_current_user dependency already handles raising HTTPException for unauthorized access.
        # We just need to ensure current_user is passed to the decorated function.
        # FastAPI handles injecting `current_user` based on the Depends(get_current_user) annotation.
        # We explicitly pass it here to ensure the decorated function receives it.
        kwargs['current_user'] = current_user
        return await func(*args, **kwargs)
    return wrapper

def cache_first_route(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to enforce a cache-first pattern with an optional 'live' data source.
    It expects the decorated function to accept a `source` parameter (Query) and `current_user` (Depends).
    The actual cache/live logic is handled within the service layer. This decorator primarily
    serves for consistent parameter injection and potential logging/analytics.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        # Ensure 'source' and 'current_user' are present in kwargs, injected by FastAPI
        # If they are not, it means the endpoint signature is not correctly defined.
        source: Optional[str] = kwargs.get('source', 'cache')
        current_user: Optional[User] = kwargs.get('current_user') # This should be injected by @require_auth or directly

        # Log API usage for analytics (placeholder)
        user_id = current_user.id if current_user else "anonymous"
        logger.info(f"API Usage: Endpoint '{func.__name__}' called by user '{user_id}' with source='{source}'.")
        
        # The core cache-first/live logic and access validation is handled by the service layer.
        # This decorator simply ensures the parameters are passed correctly.
        return await func(*args, **kwargs)
    
    return wrapper
