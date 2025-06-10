import logging
from typing import Annotated, Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path

# Import core models
from Link_Profiler.core.models import User
from Link_Profiler.api.schemas import KeywordSuggestionResponse # Import schemas

# Import decorators and data_service
from Link_Profiler.api.decorators import require_auth, cache_first_route
from Link_Profiler.services.data_service import data_service

logger = logging.getLogger(__name__)

keyword_router = APIRouter(prefix="/api/keywords", tags=["Keyword Data"])

@keyword_router.get("/{keyword}/analysis", response_model=List[KeywordSuggestionResponse], summary="Get keyword analysis (cache-first)")
@require_auth
@cache_first_route
async def get_keyword_analysis_api(
    keyword: Annotated[str, Path(..., description="Keyword to analyze", example="seo tools")],
    current_user: User, # Injected by @require_auth
    source: Annotated[Optional[str], Query(
        "cache", 
        description="""Data source for the request:
        - `cache`: Returns cached data (default, fastest response)
        - `live`: Returns real-time data (slower, requires appropriate user tier)""",
        enum=["cache", "live"],
        example="cache"
    )] = "cache"
) -> List[KeywordSuggestionResponse]:
    """
    Retrieves comprehensive analysis for a given keyword, including suggestions, trends, and metrics.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"User {current_user.username} requesting keyword analysis for '{keyword}' (source: {source}).")
    try:
        analysis_data = await data_service.get_keyword_analysis(keyword, source=source, current_user=current_user)
        if not analysis_data:
            return [] # Return empty list if no analysis found
        return [KeywordSuggestionResponse(**s) for s in analysis_data]
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving keyword analysis for '{keyword}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve keyword analysis: {e}")

@keyword_router.get("/{keyword}/competitors", response_model=List[Dict[str, Any]], summary="Get top competitors for a keyword (cache-first)")
@require_auth
@cache_first_route
async def get_keyword_competitors_api(
    keyword: Annotated[str, Path(..., description="Keyword to find competitors for", example="best seo software")],
    current_user: User, # Injected by @require_auth
    source: Annotated[Optional[str], Query(
        "cache", 
        description="""Data source for the request:
        - `cache`: Returns cached data (default, fastest response)
        - `live`: Returns real-time data (slower, requires appropriate user tier)""",
        enum=["cache", "live"],
        example="cache"
    )] = "cache"
) -> List[Dict[str, Any]]:
    """
    Retrieves a list of top organic search competitors for the specified keyword.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"User {current_user.username} requesting keyword competitors for '{keyword}' (source: {source}).")
    try:
        competitors_data = await data_service.get_keyword_competitors(keyword, source=source, current_user=current_user)
        if not competitors_data:
            return [] # Return empty list if no competitors found
        return competitors_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving keyword competitors for '{keyword}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve keyword competitors: {e}")
