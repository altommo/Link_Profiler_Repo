import logging
from typing import Annotated, Dict, List, Any

from fastapi import APIRouter, Depends, HTTPException, status

# Import globally initialized instances from main.py
try:
    from Link_Profiler.main import logger, competitive_analysis_service_instance
except ImportError:
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    # Dummy instances for testing or if main.py is not fully initialized
    class DummyCompetitiveAnalysisService:
        async def perform_link_intersect_analysis(self, primary_domain, competitor_domains): return None
        async def perform_competitive_keyword_analysis(self, primary_domain, competitor_domains): return None
    competitive_analysis_service_instance = DummyCompetitiveAnalysisService()


# Import shared Pydantic models and dependencies
from Link_Profiler.api.schemas import (
    LinkIntersectRequest, LinkIntersectResponse,
    CompetitiveKeywordAnalysisRequest, CompetitiveKeywordAnalysisResponse
)
from Link_Profiler.api.dependencies import get_current_user

# Import core models
from Link_Profiler.core.models import User


competitive_analysis_router = APIRouter(prefix="/api/competitor", tags=["Competitive Analysis"])

@competitive_analysis_router.post("/link_intersect", response_model=LinkIntersectResponse)
async def get_link_intersect(request: LinkIntersectRequest, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Performs a link intersect analysis to find common linking domains between a primary domain and competitors.
    """
    logger.info(f"API: Received request for link intersect analysis for {request.primary_domain} by user: {current_user.username}.")
    if not request.primary_domain or not request.competitor_domains:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary domain and at least one competitor domain must be provided.")
    
    try:
        result = await competitive_analysis_service_instance.perform_link_intersect_analysis(
            primary_domain=request.primary_domain,
            competitor_domains=request.competitor_domains
        )
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No link intersect data found for {request.primary_domain} and its competitors.")
        return LinkIntersectResponse.from_link_intersect_result(result)
    except Exception as e:
        logger.error(f"API: Error performing link intersect analysis: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to perform link intersect analysis: {e}")

@competitive_analysis_router.post("/keyword_analysis", response_model=CompetitiveKeywordAnalysisResponse)
async def get_competitive_keyword_analysis(request: CompetitiveKeywordAnalysisRequest, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Performs a competitive keyword analysis, identifying common keywords, keyword gaps, and unique keywords.
    """
    logger.info(f"API: Received request for competitive keyword analysis for {request.primary_domain} by user: {current_user.username}.")
    if not request.primary_domain or not request.competitor_domains:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary domain and at least one competitor domain must be provided.")
    
    try:
        result = await competitive_analysis_service_instance.perform_competitive_keyword_analysis(
            primary_domain=request.primary_domain,
            competitor_domains=request.competitor_domains
        )
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No competitive keyword analysis data found for {request.primary_domain} and its competitors.")
        return CompetitiveKeywordAnalysisResponse.from_competitive_keyword_analysis_result(result)
    except Exception as e:
        logger.error(f"API: Error performing competitive keyword analysis: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to perform competitive keyword analysis: {e}")
