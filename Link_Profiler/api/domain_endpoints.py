import logging
from typing import Annotated, Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body

# Import core models
from Link_Profiler.core.models import User
from Link_Profiler.api.schemas import BacklinkResponse, SEOMetricsResponse, ContentGapAnalysisResultResponse, LinkProspectResponse # Import new schemas

# Import decorators and data_service
from Link_Profiler.api.decorators import require_auth, cache_first_route
from Link_Profiler.services.data_service import data_service

logger = logging.getLogger(__name__)

domain_router = APIRouter(prefix="/api/domains", tags=["Domain Data"])

@domain_router.get("/{domain}/overview", response_model=Dict[str, Any], summary="Get comprehensive domain overview (cache-first)")
@require_auth
@cache_first_route
async def get_domain_overview_api(
    domain: Annotated[str, Path(..., description="Domain to analyze", example="example.com")],
    current_user: User, # Injected by @require_auth
    source: Annotated[Optional[str], Query(
        "cache", 
        description="""Data source for the request:
        - `cache`: Returns cached data (default, fastest response)
        - `live`: Returns real-time data (slower, requires appropriate user tier)""",
        enum=["cache", "live"],
        example="cache"
    )] = "cache"
) -> Dict[str, Any]:
    """
    Retrieves a comprehensive overview for a given domain, including authority, health, and key metrics.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"User {current_user.username} requesting domain overview for {domain} (source: {source}).")
    try:
        overview_data = await data_service.get_domain_overview(domain, source=source, current_user=current_user)
        if not overview_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain overview not found.")
        return overview_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving domain overview for {domain}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve domain overview: {e}")

@domain_router.get("/{domain}/backlinks", response_model=List[BacklinkResponse], summary="Get backlinks for a domain (cache-first)")
@require_auth
@cache_first_route
async def get_domain_backlinks_api(
    domain: Annotated[str, Path(..., description="Domain to analyze", example="example.com")],
    current_user: User, # Injected by @require_auth
    source: Annotated[Optional[str], Query(
        "cache", 
        description="""Data source for the request:
        - `cache`: Returns cached data (default, fastest response)
        - `live`: Returns real-time data (slower, requires appropriate user tier)""",
        enum=["cache", "live"],
        example="cache"
    )] = "cache"
) -> List[BacklinkResponse]:
    """
    Retrieves a list of backlinks pointing to the specified domain.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"User {current_user.username} requesting backlinks for {domain} (source: {source}).")
    try:
        backlinks_data = await data_service.get_domain_backlinks(domain, source=source, current_user=current_user)
        if not backlinks_data:
            return [] # Return empty list if no backlinks found
        return [BacklinkResponse(**bl) for bl in backlinks_data]
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving backlinks for {domain}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve backlinks: {e}")

@domain_router.get("/{domain}/metrics", response_model=Dict[str, Any], summary="Get SEO metrics for a domain (cache-first)")
@require_auth
@cache_first_route
async def get_domain_metrics_api(
    domain: Annotated[str, Path(..., description="Domain to analyze", example="example.com")],
    current_user: User, # Injected by @require_auth
    source: Annotated[Optional[str], Query(
        "cache", 
        description="""Data source for the request:
        - `cache`: Returns cached data (default, fastest response)
        - `live`: Returns real-time data (slower, requires appropriate user tier)""",
        enum=["cache", "live"],
        example="cache"
    )] = "cache"
) -> Dict[str, Any]:
    """
    Retrieves various SEO metrics for a given domain, such as Domain Authority, Trust Flow, etc.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"User {current_user.username} requesting domain metrics for {domain} (source: {source}).")
    try:
        metrics_data = await data_service.get_domain_metrics(domain, source=source, current_user=current_user)
        if not metrics_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain metrics not found.")
        return metrics_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving domain metrics for {domain}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve domain metrics: {e}")

@domain_router.get("/{domain}/competitors", response_model=List[Dict[str, Any]], summary="Get top competitors for a domain (cache-first)")
@require_auth
@cache_first_route
async def get_domain_competitors_api(
    domain: Annotated[str, Path(..., description="Domain to analyze", example="example.com")],
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
    Retrieves a list of top organic search competitors for the specified domain.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"User {current_user.username} requesting competitors for {domain} (source: {source}).")
    try:
        competitors_data = await data_service.get_domain_competitors(domain, source=source, current_user=current_user)
        if not competitors_data:
            return [] # Return empty list if no competitors found
        return competitors_data
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving competitors for {domain}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve competitors: {e}")

@domain_router.get("/{domain}/seo-audit", response_model=SEOMetricsResponse, summary="Get SEO audit results for a domain (cache-first)")
@require_auth
@cache_first_route
async def get_domain_seo_audit_api(
    domain: Annotated[str, Path(..., description="Domain to audit", example="example.com")],
    current_user: User, # Injected by @require_auth
    source: Annotated[Optional[str], Query(
        "cache", 
        description="""Data source for the request:
        - `cache`: Returns cached data (default, fastest response)
        - `live`: Returns real-time data (slower, requires appropriate user tier)""",
        enum=["cache", "live"],
        example="cache"
    )] = "cache"
) -> SEOMetricsResponse:
    """
    Retrieves SEO audit results for a given domain.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"User {current_user.username} requesting SEO audit for {domain} (source: {source}).")
    try:
        seo_audit_data = await data_service.get_domain_seo_audit(domain, source=source, current_user=current_user)
        if not seo_audit_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SEO audit results not found for this domain.")
        return SEOMetricsResponse(**seo_audit_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving SEO audit for {domain}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve SEO audit: {e}")

@domain_router.post("/{domain}/content-gaps", response_model=ContentGapAnalysisResultResponse, summary="Perform content gap analysis for a domain (cache-first)")
@require_auth
@cache_first_route
async def perform_content_gap_analysis_api(
    domain: Annotated[str, Path(..., description="Target domain for content gap analysis", example="example.com")],
    competitor_domains: Annotated[List[str], Body(..., description="List of competitor domains to compare against", example=["competitor1.com", "competitor2.com"])],
    current_user: User, # Injected by @require_auth
    source: Annotated[Optional[str], Query(
        "cache", 
        description="""Data source for the request:
        - `cache`: Returns cached data (default, fastest response)
        - `live`: Returns real-time data (slower, requires appropriate user tier)""",
        enum=["cache", "live"],
        example="cache"
    )] = "cache"
) -> ContentGapAnalysisResultResponse:
    """
    Performs a content gap analysis for the target domain against specified competitor domains.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"User {current_user.username} requesting content gap analysis for {domain} against {competitor_domains} (source: {source}).")
    try:
        content_gap_data = await data_service.get_domain_content_gaps(domain, competitor_domains, source=source, current_user=current_user)
        if not content_gap_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content gap analysis results not found.")
        return ContentGapAnalysisResultResponse(**content_gap_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error performing content gap analysis for {domain}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to perform content gap analysis: {e}")

@domain_router.get("/{domain}/link-prospects", response_model=List[LinkProspectResponse], summary="Get link prospects for a domain (cache-first)")
@require_auth
@cache_first_route
async def get_domain_link_prospects_api(
    domain: Annotated[str, Path(..., description="Domain to find link prospects for", example="example.com")],
    current_user: User, # Injected by @require_auth
    source: Annotated[Optional[str], Query(
        "cache", 
        description="""Data source for the request:
        - `cache`: Returns cached data (default, fastest response)
        - `live`: Returns real-time data (slower, requires appropriate user tier)""",
        enum=["cache", "live"],
        example="cache"
    )] = "cache"
) -> List[LinkProspectResponse]:
    """
    Retrieves a list of potential link building prospects for the specified domain.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"User {current_user.username} requesting link prospects for {domain} (source: {source}).")
    try:
        prospects_data = await data_service.get_domain_link_prospects(domain, source=source, current_user=current_user)
        if not prospects_data:
            return [] # Return empty list if no prospects found
        return [LinkProspectResponse(**p) for p in prospects_data]
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving link prospects for {domain}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve link prospects: {e}")

@domain_router.post("/{domain}/custom-analysis", response_model=Dict[str, Any], summary="Perform custom analysis for a domain (live only)")
@require_auth
async def perform_custom_analysis_api(
    domain: Annotated[str, Path(..., description="Domain to perform custom analysis on", example="example.com")],
    analysis_type: Annotated[str, Body(..., description="Type of custom analysis to perform", example="deep_crawl_and_audit")],
    config: Annotated[Dict[str, Any], Body(..., description="Configuration for the custom analysis", example={"max_depth": 5, "render_js": True})],
    current_user: User # Injected by @require_auth
) -> Dict[str, Any]:
    """
    Triggers a custom analysis job for the specified domain. This is always a live operation
    and will consume live data credits if applicable.
    """
    logger.info(f"User {current_user.username} requesting custom analysis '{analysis_type}' for {domain}.")
    try:
        # Custom analysis is inherently a live operation, so we don't need a 'source' parameter.
        # The data_service.perform_custom_analysis method will handle live access validation.
        result = await data_service.perform_custom_analysis(domain, analysis_type, config, current_user=current_user)
        return result
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error performing custom analysis for {domain}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to perform custom analysis: {e}")
