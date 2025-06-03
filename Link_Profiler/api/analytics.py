import logging
from typing import Annotated, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status, Query

# Import globally initialized instances from main.py
# This pattern is used for singletons initialized at application startup.
try:
    from Link_Profiler.main import logger, db, domain_service_instance, ai_service_instance
except ImportError:
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    # Dummy instances for testing or if main.py is not fully initialized
    class DummyDB:
        def get_backlink_counts_over_time(self, target_domain, time_unit, num_units): return {}
        def get_serp_position_history(self, target_url, keyword, num_snapshots): return []
    db = DummyDB()
    class DummyDomainService:
        def get_domain_authority_progression(self, domain_name, num_snapshots): return []
    domain_service_instance = DummyDomainService()
    class DummyAIService:
        enabled = False
        async def suggest_semantic_keywords(self, keyword): return []
    ai_service_instance = DummyAIService()


# Import shared Pydantic models and dependencies
from Link_Profiler.api.schemas import (
    LinkVelocityRequest, DomainHistoryResponse, SERPResultResponse, KeywordSuggestionResponse
)
from Link_Profiler.api.dependencies import get_current_user

# Import core models
from Link_Profiler.core.models import User


analytics_router = APIRouter(prefix="/api", tags=["Analytics & Data Retrieval"])

@analytics_router.get("/link_profile/{target_domain}/link_velocity", response_model=Dict[str, int])
async def get_link_velocity(
    target_domain: str,
    current_user: Annotated[User, Depends(get_current_user)], # Moved to come before parameter with default
    request_params: LinkVelocityRequest = Depends()
):
    """
    Retrieves the link velocity (new backlinks over time) for a given target domain.
    """
    logger.info(f"API: Received request for link velocity of {target_domain} by user: {current_user.username}.")
    if not target_domain:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target domain must be provided.")
    
    try:
        link_velocity_data = db.get_backlink_counts_over_time(
            target_domain=target_domain,
            time_unit=request_params.time_unit,
            num_units=request_params.num_units
        )
        if not link_velocity_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No link velocity data found for {target_domain} or parameters are invalid.")
        return link_velocity_data
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"API: Error retrieving link velocity for {target_domain}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve link velocity: {e}")

@analytics_router.get("/domain/{domain_name}/history", response_model=List[DomainHistoryResponse])
async def get_domain_history_endpoint(
    domain_name: str, 
    num_snapshots: Annotated[int, Query(12, gt=0, description="Number of historical snapshots to retrieve.")],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Retrieves the historical progression of a domain's authority metrics.
    """
    logger.info(f"API: Received request for domain history of {domain_name} by user: {current_user.username}.")
    if not domain_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Domain name must be provided.")
    
    try:
        history_data = domain_service_instance.get_domain_authority_progression(
            domain_name=domain_name,
            num_snapshots=num_snapshots
        )
        if not history_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No historical data found for {domain_name}.")
        return [DomainHistoryResponse.from_domain_history(h) for h in history_data]
    except Exception as e:
        logger.error(f"API: Error retrieving domain history for {domain_name}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve domain history: {e}")

@analytics_router.get("/serp/history", response_model=List[SERPResultResponse])
async def get_serp_position_history_endpoint(
    target_url: Annotated[str, Query(..., description="The URL for which to track SERP history.")],
    keyword: Annotated[str, Query(..., description="The keyword for which to track SERP history.")],
    num_snapshots: Annotated[int, Query(12, gt=0, description="The maximum number of recent historical snapshots to retrieve.")],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Retrieves the historical SERP positions for a specific URL and keyword.
    """
    logger.info(f"API: Received request for SERP history for URL '{target_url}' and keyword '{keyword}' by user: {current_user.username}.")
    if not target_url or not keyword:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target URL and keyword must be provided.")
    
    try:
        history_data = db.get_serp_position_history(target_url, keyword, num_snapshots)
        if not history_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No SERP history found for URL '{target_url}' and keyword '{keyword}'.")
        return [SERPResultResponse.from_serp_result(sr) for sr in history_data]
    except Exception as e:
        logger.error(f"API: Error retrieving SERP position history for '{target_url}' and '{keyword}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve SERP position history: {e}")

@analytics_router.post("/keyword/semantic_suggestions", response_model=List[str])
async def get_semantic_keyword_suggestions_endpoint(
    primary_keyword: Annotated[str, Query(..., description="The primary keyword to get semantic suggestions for.")],
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Generates a list of semantically related keywords using AI.
    """
    logger.info(f"API: Received request for semantic keyword suggestions for '{primary_keyword}' by user: {current_user.username}.")
    if not primary_keyword:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary keyword must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")

    try:
        suggestions = await ai_service_instance.suggest_semantic_keywords(primary_keyword)
        if not suggestions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No semantic keyword suggestions found for '{primary_keyword}'.")
        return suggestions
    except Exception as e:
        logger.error(f"API: Error generating semantic keyword suggestions for '{primary_keyword}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate semantic keyword suggestions: {e}")
