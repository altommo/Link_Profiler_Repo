import logging
from typing import Annotated, Dict, List, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status

# Import globally initialized instances from main.py
try:
    import logging
logger = logging.getLogger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    # Dummy instances for testing or if main.py is not fully initialized
    class DummyAIService:
        enabled = False
        async def generate_content_ideas(self, topic, num_ideas): return []
        async def analyze_competitors(self, primary_domain, competitor_domains): return {}
        async def suggest_semantic_keywords(self, keyword): return []
        async def analyze_domain_value(self, domain_name, domain_info, link_profile_summary): return {"value_adjustment": 0, "reasons": ["AI disabled"], "details": {}}
        async def analyze_content_gaps(self, target_url, competitor_urls): return {"missing_topics": [], "missing_keywords": [], "content_format_gaps": [], "actionable_insights": ["AI disabled"]}
        async def score_content(self, content, target_keyword): return {"seo_score": 50, "keyword_density_score": 50, "readability_score": 50, "semantic_keywords": [], "improvement_suggestions": ["AI disabled"]}
        async def classify_content(self, content, target_keyword): return "unknown"
        async def analyze_technical_seo(self, url, html_content, lighthouse_report): return {"technical_issues": [], "technical_suggestions": [], "overall_technical_score": 50}
        async def analyze_content_nlp(self, content): return {"entities": [], "sentiment": "neutral", "topics": []}
        async def analyze_video_content(self, video_url, video_data): raise NotImplementedError("AI disabled")
        async def assess_content_quality(self, content, url): return (None, "AI disabled")
        async def perform_topic_clustering(self, texts, num_clusters): return {}
    ai_service_instance = DummyAIService()


# Import shared Pydantic models and dependencies
from Link_Profiler.api.schemas import (
    ContentGenerationRequest, CompetitorStrategyAnalysisRequest,
    ContentGapAnalysisRequest, TopicClusteringRequest,
    DomainAnalysisResponse, # Re-use for domain value analysis
    SEOMetricsResponse, # Re-use for technical SEO analysis
    ContentGapAnalysisResultResponse # Re-use for content gap analysis
)
from Link_Profiler.api.dependencies import get_current_user

# Import core models
from Link_Profiler.core.models import User


ai_router = APIRouter(prefix="/api/ai", tags=["AI Services"])

@ai_router.post("/generate_content_ideas", response_model=List[str])
async def generate_content_ideas_endpoint(
    request: ContentGenerationRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Generates content ideas based on a given topic using AI.
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

@ai_router.post("/suggest_semantic_keywords", response_model=List[str])
async def suggest_semantic_keywords_endpoint(
    keyword: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Suggests semantically related keywords for a primary keyword using AI.
    """
    logger.info(f"API: Received request for semantic keywords for '{keyword}' by user: {current_user.username}.")
    if not keyword:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Keyword must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")

    try:
        keywords = await ai_service_instance.suggest_semantic_keywords(keyword)
        if not keywords:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No semantic keywords suggested for '{keyword}'.")
        return keywords
    except Exception as e:
        logger.error(f"API: Error suggesting semantic keywords for '{keyword}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to suggest semantic keywords.")

@ai_router.post("/analyze_domain_value", response_model=DomainAnalysisResponse)
async def analyze_domain_value_endpoint(
    domain_name: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Performs an AI-driven analysis of a domain's potential value.
    """
    logger.info(f"API: Received request for AI domain value analysis for '{domain_name}' by user: {current_user.username}.")
    if not domain_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Domain name must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")
    
    # This endpoint would typically fetch domain_info and link_profile from DB/services
    # For simplicity, we'll pass None for now, assuming AI can work with just domain_name
    # or that the AI service itself fetches necessary data.
    try:
        analysis_result = await ai_service_instance.analyze_domain_value(domain_name, None, None)
        if not analysis_result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AI could not perform domain value analysis for {domain_name}.")
        # Map AI service's raw dict output to DomainAnalysisResponse schema
        return DomainAnalysisResponse(
            domain_name=domain_name,
            value_score=analysis_result.get("value_adjustment", 0), # Re-using value_adjustment as score
            is_valuable=analysis_result.get("value_adjustment", 0) > 0, # Simple heuristic
            reasons=analysis_result.get("reasons", []),
            details=analysis_result.get("details", {})
        )
    except Exception as e:
        logger.error(f"API: Error analyzing domain value for '{domain_name}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to analyze domain value.")

@ai_router.post("/analyze_content_gaps", response_model=ContentGapAnalysisResultResponse)
async def analyze_content_gaps_endpoint(
    request: ContentGapAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Analyzes content gaps between a target URL and its competitors using AI.
    """
    logger.info(f"API: Received request for AI content gap analysis for '{request.target_url}' by user: {current_user.username}.")
    if not request.target_url or not request.competitor_urls:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target URL and competitor URLs must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")
    
    try:
        result = await ai_service_instance.analyze_content_gaps(request.target_url, request.competitor_urls)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AI could not perform content gap analysis for {request.target_url}.")
        return result # ContentGapAnalysisResult is already a dataclass, should map directly
    except Exception as e:
        logger.error(f"API: Error analyzing content gaps for '{request.target_url}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to analyze content gaps.")

@ai_router.post("/score_content", response_model=Dict[str, Any]) # Returns raw AI dict
async def score_content_endpoint(
    content: str,
    target_keyword: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Analyzes and scores content for SEO optimization using AI.
    """
    logger.info(f"API: Received request for AI content scoring for '{target_keyword}' by user: {current_user.username}.")
    if not content or not target_keyword:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content and target keyword must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")
    
    try:
        result = await ai_service_instance.score_content(content, target_keyword)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AI could not score content for {target_keyword}.")
        return result
    except Exception as e:
        logger.error(f"API: Error scoring content for '{target_keyword}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to score content.")

@ai_router.post("/classify_content", response_model=str)
async def classify_content_endpoint(
    content: str,
    target_keyword: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Classifies content based on quality and relevance using AI.
    """
    logger.info(f"API: Received request for AI content classification for '{target_keyword}' by user: {current_user.username}.")
    if not content or not target_keyword:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content and target keyword must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")
    
    try:
        classification = await ai_service_instance.classify_content(content, target_keyword)
        if not classification:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AI could not classify content for {target_keyword}.")
        return classification
    except Exception as e:
        logger.error(f"API: Error classifying content for '{target_keyword}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to classify content.")

@ai_router.post("/analyze_technical_seo", response_model=SEOMetricsResponse)
async def analyze_technical_seo_endpoint(
    url: str,
    html_content: str,
    current_user: Annotated[User, Depends(get_current_user)], # Moved to be a non-default argument
    lighthouse_report: Optional[Dict[str, Any]] = None
):
    """
    Analyzes technical SEO aspects of a page using AI.
    """
    logger.info(f"API: Received request for AI technical SEO analysis for '{url}' by user: {current_user.username}.")
    if not url or not html_content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="URL and HTML content must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")
    
    try:
        result = await ai_service_instance.analyze_technical_seo(url, html_content, lighthouse_report)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AI could not perform technical SEO analysis for {url}.")
        return SEOMetricsResponse(**result) # Map raw AI dict to SEOMetricsResponse
    except Exception as e:
        logger.error(f"API: Error analyzing technical SEO for '{url}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to analyze technical SEO.")

@ai_router.post("/analyze_competitors", response_model=Dict[str, Any])
async def analyze_competitors_endpoint(
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

@ai_router.post("/analyze_content_nlp", response_model=Dict[str, Any])
async def analyze_content_nlp_endpoint(
    content: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Performs Natural Language Processing (NLP) on content using AI.
    """
    logger.info(f"API: Received request for AI content NLP analysis by user: {current_user.username}.")
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")
    
    try:
        result = await ai_service_instance.analyze_content_nlp(content)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI could not perform content NLP analysis.")
        return result
    except Exception as e:
        logger.error(f"API: Error analyzing content NLP: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to analyze content NLP.")

@ai_router.post("/analyze_video_content", response_model=Dict[str, Any])
async def analyze_video_content_endpoint(
    video_url: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Analyzes video content (transcription, topics) using AI.
    """
    logger.info(f"API: Received request for AI video content analysis for '{video_url}' by user: {current_user.username}.")
    if not video_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Video URL must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")
    
    try:
        result = await ai_service_instance.analyze_video_content(video_url)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AI could not analyze video content for {video_url}.")
        return result
    except NotImplementedError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    except Exception as e:
        logger.error(f"API: Error analyzing video content for '{video_url}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to analyze video content.")

@ai_router.post("/assess_content_quality", response_model=Dict[str, Any])
async def assess_content_quality_endpoint(
    content: str,
    url: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Assesses the quality of content using AI.
    """
    logger.info(f"API: Received request for AI content quality assessment for '{url}' by user: {current_user.username}.")
    if not content or not url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content and URL must be provided.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")
    
    try:
        score, classification = await ai_service_instance.assess_content_quality(content, url)
        if score is None or classification is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"AI could not assess content quality for {url}.")
        return {"quality_score": score, "classification": classification}
    except Exception as e:
        logger.error(f"API: Error assessing content quality for '{url}': {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to assess content quality.")

@ai_router.post("/perform_topic_clustering", response_model=Dict[str, List[str]])
async def perform_topic_clustering_endpoint(
    request: TopicClusteringRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Performs AI-powered topic clustering on a list of texts.
    """
    logger.info(f"API: Received request for AI topic clustering by user: {current_user.username}.")
    if not request.texts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Texts must be provided for topic clustering.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")
    
    try:
        result = await ai_service_instance.perform_topic_clustering(request.texts, request.num_clusters)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI could not perform topic clustering.")
        return result
    except Exception as e:
        logger.error(f"API: Error performing topic clustering: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to perform topic clustering.")
