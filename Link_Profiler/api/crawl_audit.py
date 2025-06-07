import logging
from typing import Annotated, Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks

# Import globally initialized instances from main.py
# This pattern is used for singletons initialized at application startup.
try:
    from Link_Profiler.main import logger, db, ai_service_instance
except ImportError:
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    # Dummy instances for testing or if main.py is not fully initialized
    class DummyDB:
        def get_content_gap_analysis_result(self, url): return None
    db = DummyDB()
    class DummyAIService:
        enabled = False
    ai_service_instance = DummyAIService()


# Import shared Pydantic models and dependencies
from Link_Profiler.api.schemas import (
    CrawlConfigRequest, StartCrawlRequest, LinkHealthAuditRequest, TechnicalAuditRequest,
    DomainAnalysisJobRequest, FullSEOAuditRequest, Web3CrawlRequest, SocialMediaCrawlRequest, # Corrected FullSEOAduitRequest to FullSEOAuditRequest
    ContentGapAnalysisRequest, ContentGapAnalysisResultResponse, TopicClusteringRequest
)
from Link_Profiler.api.dependencies import get_current_user

# Import queue-related functions and models
from Link_Profiler.api.queue_endpoints import submit_crawl_to_queue, QueueCrawlRequest

# Import Prometheus metrics
from Link_Profiler.monitoring.prometheus_metrics import JOBS_CREATED_TOTAL

# Import core models
from Link_Profiler.core.models import User


crawl_audit_router = APIRouter(prefix="/api", tags=["Crawl & Audit Jobs"])

@crawl_audit_router.post("/jobs", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
async def submit_job_api(
    request: QueueCrawlRequest,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Submits a general job to the queue. This acts as a unified entry point
    for various job types (e.g., backlink_discovery, technical_audit, etc.)
    by setting the 'job_type' in the config.
    """
    logger.info(f"API: Received general job submission for {request.target_url} (type: {request.config.get('job_type', 'N/A')}) by user: {current_user.username}.")
    JOBS_CREATED_TOTAL.labels(job_type=request.config.get('job_type', 'general_job')).inc()
    
    logger.debug(f"API: Passing QueueCrawlRequest to submit_crawl_to_queue: {request.dict()}")
    return await submit_crawl_to_queue(request)

@crawl_audit_router.post("/crawl/start_backlink_discovery", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
async def start_backlink_discovery(
    request: StartCrawlRequest, 
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Submits a new backlink discovery job to the queue.
    """
    logger.info(f"API: Received request to submit backlink discovery for {request.target_url} by user: {current_user.username}.")
    JOBS_CREATED_TOTAL.labels(job_type='backlink_discovery').inc()
    
    queue_request = QueueCrawlRequest(
        target_url=request.target_url,
        initial_seed_urls=request.initial_seed_urls,
        config=request.config.dict() if request.config else {},
        priority=5
    )
    
    return await submit_crawl_to_queue(queue_request)

@crawl_audit_router.post("/audit/link_health", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
async def start_link_health_audit(
    request: LinkHealthAuditRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Submits a new link health audit job to the queue.
    """
    logger.info(f"API: Received request to submit link health audit for {len(request.source_urls)} URLs by user: {current_user.username}.")
    JOBS_CREATED_TOTAL.labels(job_type='link_health_audit').inc()

    if not request.source_urls:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one source URL must be provided for link health audit.")
    
    target_url = request.source_urls[0] if request.source_urls else "N/A"

    queue_request = QueueCrawlRequest(
        target_url=target_url,
        initial_seed_urls=request.source_urls,
        config={"job_specific_param": "source_urls_to_audit"},
        priority=5
    )
    queue_request.config["source_urls_to_audit"] = request.source_urls
    queue_request.config["job_type"] = "link_health_audit"

    return await submit_crawl_to_queue(queue_request)

@crawl_audit_router.post("/audit/technical_audit", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
async def start_technical_audit(
    request: TechnicalAuditRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Submits a new technical audit job to the queue.
    """
    logger.info(f"API: Received request to submit technical audit for {len(request.urls_to_audit)} URLs by user: {current_user.username}.")
    JOBS_CREATED_TOTAL.labels(job_type='technical_audit').inc()

    if not request.urls_to_audit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one URL must be provided for technical audit.")
    
    target_url = request.urls_to_audit[0] if request.urls_to_audit else "N/A"

    queue_request = QueueCrawlRequest(
        target_url=target_url,
        initial_seed_urls=request.urls_to_audit,
        config=request.config.dict() if request.config else {},
        priority=5
    )
    queue_request.config["urls_to_audit_tech"] = request.urls_to_audit
    queue_request.config["job_type"] = "technical_audit"

    return await submit_crawl_to_queue(queue_request)

@crawl_audit_router.post("/audit/full_seo_audit", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
async def start_full_seo_audit(
    request: FullSEOAuditRequest, # Corrected FullSEOAduitRequest to FullSEOAuditRequest
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Submits a new full SEO audit job to the queue.
    This job orchestrates technical and link health audits.
    """
    logger.info(f"API: Received request to submit full SEO audit for {len(request.urls_to_audit)} URLs by user: {current_user.username}.")
    JOBS_CREATED_TOTAL.labels(job_type='full_seo_audit').inc()

    if not request.urls_to_audit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one URL must be provided for full SEO audit.")
    
    target_url = request.urls_to_audit[0] if request.urls_to_audit else "N/A"

    queue_request = QueueCrawlRequest(
        target_url=target_url,
        initial_seed_urls=request.urls_to_audit,
        config=request.config.dict() if request.config else {},
        priority=5
    )
    queue_request.config["urls_to_audit_full_seo"] = request.urls_to_audit
    queue_request.config["job_type"] = "full_seo_audit"

    return await submit_crawl_to_queue(queue_request)

@crawl_audit_router.post("/domain/analyze_batch", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
async def start_domain_analysis_job(
    request: DomainAnalysisJobRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Submits a new batch domain analysis job to the queue.
    """
    logger.info(f"API: Received request to submit domain analysis for {len(request.domain_names)} domains by user: {current_user.username}.")
    JOBS_CREATED_TOTAL.labels(job_type='domain_analysis').inc()

    if not request.domain_names:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one domain name must be provided for analysis.")
    
    target_url = request.domain_names[0] if request.domain_names else "N/A"

    queue_request = QueueCrawlRequest(
        target_url=target_url,
        initial_seed_urls=[],
        config=request.config.dict() if request.config else {},
        priority=5
    )
    queue_request.config["domain_names_to_analyze"] = request.domain_names
    queue_request.config["min_value_score"] = request.min_value_score
    queue_request.config["limit"] = request.limit
    queue_request.config["job_type"] = "domain_analysis"

    return await submit_crawl_to_queue(queue_request)

@crawl_audit_router.post("/web3/crawl", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
async def start_web3_crawl(
    request: Web3CrawlRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Submits a new Web3 content crawl job to the queue.
    """
    logger.info(f"API: Received request to submit Web3 crawl for identifier: {request.web3_content_identifier} by user: {current_user.username}.")
    JOBS_CREATED_TOTAL.labels(job_type='web3_crawl').inc()

    queue_request = QueueCrawlRequest(
        target_url=request.web3_content_identifier,
        initial_seed_urls=[],
        config=request.config.dict() if request.config else {},
        priority=5
    )
    queue_request.config["web3_content_identifier"] = request.web3_content_identifier
    queue_request.config["job_type"] = "web3_crawl"

    return await submit_crawl_to_queue(queue_request)

@crawl_audit_router.post("/social_media/crawl", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
async def start_social_media_crawl(
    request: SocialMediaCrawlRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Submits a new social media content crawl job to the queue.
    """
    logger.info(f"API: Received request to submit social media crawl for query: {request.social_media_query} by user: {current_user.username}.")
    JOBS_CREATED_TOTAL.labels(job_type='social_media_crawl').inc()

    queue_request = QueueCrawlRequest(
        target_url=request.social_media_query,
        initial_seed_urls=[],
        config=request.config.dict() if request.config else {},
        priority=5
    )
    queue_request.config["social_media_query"] = request.social_media_query
    queue_request.config["platforms"] = request.platforms
    queue_request.config["job_type"] = "social_media_crawl"

    return await submit_crawl_to_queue(queue_request)

@crawl_audit_router.post("/content/gap_analysis", response_model=Dict[str, str], status_code=status.HTTP_202_ACCEPTED)
async def start_content_gap_analysis(
    request: ContentGapAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """
    Submits a new content gap analysis job to the queue.
    """
    logger.info(f"API: Received request to submit content gap analysis for {request.target_url} by user: {current_user.username}.")
    JOBS_CREATED_TOTAL.labels(job_type='content_gap_analysis').inc()

    if not request.target_url or not request.competitor_urls:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target URL and at least one competitor URL must be provided for content gap analysis.")
    
    queue_request = QueueCrawlRequest(
        target_url=request.target_url,
        initial_seed_urls=[],
        config=request.config.dict() if request.config else {},
        priority=5
    )
    queue_request.config["target_url_for_content_gap"] = request.target_url
    queue_request.config["competitor_urls_for_content_gap"] = request.competitor_urls
    queue_request.config["job_type"] = "content_gap_analysis"

    return await submit_crawl_to_queue(queue_request)

@crawl_audit_router.get("/content/gap_analysis/{target_url:path}", response_model=ContentGapAnalysisResultResponse)
async def get_content_gap_analysis_result(target_url: str, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Retrieves the content gap analysis result for a given target URL.
    """
    logger.info(f"API: Received request for content gap analysis result for {target_url} by user: {current_user.username}.")
    if not urlparse(target_url).scheme or not urlparse(target_url).netloc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target_url provided. Must be a full URL (e.g., https://example.com).")

    result = db.get_content_gap_analysis_result(target_url)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content gap analysis result not found for this URL. A job might not have been completed yet.")
    return ContentGapAnalysisResultResponse.from_content_gap_analysis_result(result)

@crawl_audit_router.post("/content/topic_clustering", response_model=List[str])
async def perform_topic_clustering_endpoint(request: TopicClusteringRequest, current_user: Annotated[User, Depends(get_current_user)]):
    """
    Performs topic clustering on a list of provided texts using AI.
    """
    logger.info(f"API: Received request for topic clustering by user: {current_user.username}.")
    if not request.texts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one text document must be provided for topic clustering.")
    
    if not ai_service_instance.enabled:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AI Service is not enabled or configured.")

    try:
        clustered_topics = await ai_service_instance.perform_topic_clustering(
            texts=request.texts,
            num_clusters=request.num_clusters
        )
        return clustered_topics
    except Exception as e:
        logger.error(f"API: Error performing topic clustering: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to perform topic clustering: {e}")
