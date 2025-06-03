import logging
from typing import Annotated, Dict, List, Any

from fastapi import APIRouter, Depends, HTTPException, status

# Import globally initialized instances from main.py
try:
    from Link_Profiler.main import logger, ai_service_instance
except ImportError:
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    # Dummy instances for testing or if main.py is not fully initialized
    class DummyAIService:
        enabled = False
        async def generate_content_ideas(self, topic, num_ideas): return []
        async def analyze_competitors(self, primary_domain, competitor_domains): return {}
    ai_service_instance = DummyAIService()


# Import shared Pydantic models and dependencies
from Link_Profiler.api.schemas import (
    ContentGenerationRequest, CompetitorStrategyAnalysisRequest
)
from Link_Profiler.api.dependencies import get_current_user

# Import core models
from Link_Profiler.core.models import User


ai_router = APIRouter(prefix="/api/ai", tags=["AI Services"])

@ai_router.post("/content_ideas", response_model=List[str])
async def generate_content_ideas_endpoint(
    request: ContentGenerationRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Generates content ideas for a given topic using AI.
    """
    logger.info(f"API: Received request for content ideas for topic '{request.topic}' by user: {current_user.username}.")
    if not request.topic:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Topic must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")

    try:
        ideas = await ai_service_instance.generate_content_ideas(request.topic, request.num_ideas)
        if not ideas:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No content ideas generated for '{request.topic}'.")
        return ideas
    except Exception as e:
        logger.error(f"API: Error generating content ideas for '{request.topic}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate content ideas: {e}")

@ai_router.post("/competitor_strategy", response_model=Dict[str, Any])
async def analyze_competitor_strategy_endpoint(
    request: CompetitorStrategyAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Analyzes competitor strategies using AI.
    """
    logger.info(f"API: Received request for AI competitor strategy analysis for {request.primary_domain} by user: {current_user.username}.")
    if not request.primary_domain or not request.competitor_domains:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Primary domain and competitor domains must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")

    try:
        analysis_result = await ai_service_instance.analyze_competitors(request.primary_domain, request.competitor_domains)
        if not analysis_result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AI could not perform competitor strategy analysis for {request.primary_domain}.")
        return analysis_result
    except Exception as e:
        logger.error(f"API: Error performing AI competitor strategy analysis for {request.primary_domain}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to perform AI competitor strategy analysis: {e}")
