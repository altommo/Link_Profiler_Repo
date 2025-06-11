import logging
from typing import Annotated, Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body

# Import core models
from Link_Profiler.core.models import User, TrackedDomain, TrackedKeyword
from Link_Profiler.api.schemas import TrackedDomainCreate, TrackedDomainResponse, TrackedKeywordCreate, TrackedKeywordResponse # Import schemas

# Import decorators and data_service
from Link_Profiler.api.decorators import require_auth, cache_first_route
from Link_Profiler.services.data_service import data_service

logger = logging.getLogger(__name__)

tracked_entities_router = APIRouter(prefix="/api/tracked_entities", tags=["Tracked Entities Management"])

# --- Tracked Domains Endpoints ---
@tracked_entities_router.post("/domains", response_model=TrackedDomainResponse, status_code=status.HTTP_201_CREATED, summary="Create a new tracked domain")
@require_auth
async def create_tracked_domain_api(
    tracked_domain_create: TrackedDomainCreate,
    current_user: User # Injected by @require_auth
) -> TrackedDomainResponse:
    """
    Creates a new domain to be tracked by the system.
    """
    logger.info(f"User {current_user.username} creating new tracked domain: {tracked_domain_create.domain_name}.")
    try:
        # Check if domain already exists for this user/org
        existing_domain = await data_service.get_tracked_domain_by_name(
            tracked_domain_create.domain_name, source="live", current_user=current_user
        )
        if existing_domain:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Domain is already being tracked.")

        new_tracked_domain = TrackedDomain(
            id=str(uuid.uuid4()), # Generate UUID for new domain
            domain_name=tracked_domain_create.domain_name,
            is_active=tracked_domain_create.is_active,
            user_id=current_user.id,
            organization_id=current_user.organization_id
        )
        created_domain_data = await data_service.create_tracked_domain(new_tracked_domain, current_user)
        return TrackedDomainResponse(**created_domain_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating tracked domain: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create tracked domain: {e}")

@tracked_entities_router.get("/domains", response_model=List[TrackedDomainResponse], summary="Get all tracked domains (cache-first)")
@require_auth
@cache_first_route
async def get_all_tracked_domains_api(
    current_user: User, # Injected by @require_auth
    source: Annotated[Optional[str], Query(
        "cache", 
        description="""Data source for the request:
        - `cache`: Returns cached data (default, fastest response)
        - `live`: Returns real-time data (slower, requires appropriate user tier)""",
        enum=["cache", "live"],
        example="cache"
    )] = "cache"
) -> List[TrackedDomainResponse]:
    """
    Retrieves a list of all domains tracked by the current user/organization.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"User {current_user.username} requesting all tracked domains (source: {source}).")
    try:
        tracked_domains_data = await data_service.get_all_tracked_domains(source=source, current_user=current_user)
        return [TrackedDomainResponse(**td) for td in tracked_domains_data]
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving all tracked domains: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve tracked domains: {e}")

@tracked_entities_router.get("/domains/{domain_id}", response_model=TrackedDomainResponse, summary="Get a tracked domain by ID (cache-first)")
@require_auth
@cache_first_route
async def get_tracked_domain_by_id_api(
    domain_id: Annotated[str, Path(..., description="ID of the tracked domain")],
    current_user: User, # Injected by @require_auth
    source: Annotated[Optional[str], Query(
        "cache", 
        description="""Data source for the request:
        - `cache`: Returns cached data (default, fastest response)
        - `live`: Returns real-time data (slower, requires appropriate user tier)""",
        enum=["cache", "live"],
        example="cache"
    )] = "cache"
) -> TrackedDomainResponse:
    """
    Retrieves a specific tracked domain by its ID.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"User {current_user.username} requesting tracked domain {domain_id} (source: {source}).")
    try:
        tracked_domain_data = await data_service.get_tracked_domain(domain_id, source=source, current_user=current_user)
        if not tracked_domain_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked domain not found.")
        return TrackedDomainResponse(**tracked_domain_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving tracked domain {domain_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve tracked domain: {e}")

@tracked_entities_router.put("/domains/{domain_id}", response_model=TrackedDomainResponse, summary="Update a tracked domain")
@require_auth
async def update_tracked_domain_api(
    domain_id: Annotated[str, Path(..., description="ID of the tracked domain to update")],
    update_data: Dict[str, Any], # Use Dict[str, Any] for partial updates
    current_user: User # Injected by @require_auth
) -> TrackedDomainResponse:
    """
    Updates an existing tracked domain. Only fields provided in the request body will be updated.
    """
    logger.info(f"User {current_user.username} updating tracked domain {domain_id} with data: {update_data}.")
    try:
        updated_domain_data = await data_service.update_tracked_domain(domain_id, update_data, current_user)
        return TrackedDomainResponse(**updated_domain_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating tracked domain {domain_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update tracked domain: {e}")

@tracked_entities_router.delete("/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a tracked domain")
@require_auth
async def delete_tracked_domain_api(
    domain_id: Annotated[str, Path(..., description="ID of the tracked domain to delete")],
    current_user: User # Injected by @require_auth
):
    """
    Deletes a tracked domain from the system.
    """
    logger.info(f"User {current_user.username} deleting tracked domain {domain_id}.")
    try:
        success = await data_service.delete_tracked_domain(domain_id, current_user)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked domain not found or could not be deleted.")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting tracked domain {domain_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete tracked domain: {e}")

# --- Tracked Keywords Endpoints ---
@tracked_entities_router.post("/keywords", response_model=TrackedKeywordResponse, status_code=status.HTTP_201_CREATED, summary="Create a new tracked keyword")
@require_auth
async def create_tracked_keyword_api(
    tracked_keyword_create: TrackedKeywordCreate,
    current_user: User # Injected by @require_auth
) -> TrackedKeywordResponse:
    """
    Creates a new keyword to be tracked by the system.
    """
    logger.info(f"User {current_user.username} creating new tracked keyword: {tracked_keyword_create.keyword}.")
    try:
        # Check if keyword already exists for this user/org
        existing_keyword = await data_service.get_tracked_keyword_by_name(
            tracked_keyword_create.keyword, source="live", current_user=current_user
        )
        if existing_keyword:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Keyword is already being tracked.")

        new_tracked_keyword = TrackedKeyword(
            id=str(uuid.uuid4()), # Generate UUID for new keyword
            keyword=tracked_keyword_create.keyword,
            is_active=tracked_keyword_create.is_active,
            user_id=current_user.id,
            organization_id=current_user.organization_id
        )
        created_keyword_data = await data_service.create_tracked_keyword(new_tracked_keyword, current_user)
        return TrackedKeywordResponse(**created_keyword_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating tracked keyword: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create tracked keyword: {e}")

@tracked_entities_router.get("/keywords", response_model=List[TrackedKeywordResponse], summary="Get all tracked keywords (cache-first)")
@require_auth
@cache_first_route
async def get_all_tracked_keywords_api(
    current_user: User, # Injected by @require_auth
    source: Annotated[Optional[str], Query(
        "cache", 
        description="""Data source for the request:
        - `cache`: Returns cached data (default, fastest response)
        - `live`: Returns real-time data (slower, requires appropriate user tier)""",
        enum=["cache", "live"],
        example="cache"
    )] = "cache"
) -> List[TrackedKeywordResponse]:
    """
    Retrieves a list of all keywords tracked by the current user/organization.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"User {current_user.username} requesting all tracked keywords (source: {source}).")
    try:
        tracked_keywords_data = await data_service.get_all_tracked_keywords(source=source, current_user=current_user)
        return [TrackedKeywordResponse(**tk) for tk in tracked_keywords_data]
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving all tracked keywords: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve tracked keywords: {e}")

@tracked_entities_router.get("/keywords/{keyword_id}", response_model=TrackedKeywordResponse, summary="Get a tracked keyword by ID (cache-first)")
@require_auth
@cache_first_route
async def get_tracked_keyword_by_id_api(
    keyword_id: Annotated[str, Path(..., description="ID of the tracked keyword")],
    current_user: User, # Injected by @require_auth
    source: Annotated[Optional[str], Query(
        "cache", 
        description="""Data source for the request:
        - `cache`: Returns cached data (default, fastest response)
        - `live`: Returns real-time data (slower, requires appropriate user tier)""",
        enum=["cache", "live"],
        example="cache"
    )] = "cache"
) -> TrackedKeywordResponse:
    """
    Retrieves a specific tracked keyword by its ID.
    By default, data is served from cache. Use `?source=live` to fetch the latest data,
    subject to user permissions and configuration.
    """
    logger.info(f"User {current_user.username} requesting tracked keyword {keyword_id} (source: {source}).")
    try:
        tracked_keyword_data = await data_service.get_tracked_keyword(keyword_id, source=source, current_user=current_user)
        if not tracked_keyword_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked keyword not found.")
        return TrackedKeywordResponse(**tracked_keyword_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving tracked keyword {keyword_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve tracked keyword: {e}")

@tracked_entities_router.put("/keywords/{keyword_id}", response_model=TrackedKeywordResponse, summary="Update a tracked keyword")
@require_auth
async def update_tracked_keyword_api(
    keyword_id: Annotated[str, Path(..., description="ID of the tracked keyword to update")],
    update_data: Dict[str, Any], # Use Dict[str, Any] for partial updates
    current_user: User # Injected by @require_auth
) -> TrackedKeywordResponse:
    """
    Updates an existing tracked keyword. Only fields provided in the request body will be updated.
    """
    logger.info(f"User {current_user.username} updating tracked keyword {keyword_id} with data: {update_data}.")
    try:
        updated_keyword_data = await data_service.update_tracked_keyword(keyword_id, update_data, current_user)
        return TrackedKeywordResponse(**updated_keyword_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating tracked keyword {keyword_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update tracked keyword: {e}")

@tracked_entities_router.delete("/keywords/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a tracked keyword")
@require_auth
async def delete_tracked_keyword_api(
    keyword_id: Annotated[str, Path(..., description="ID of the tracked keyword to delete")],
    current_user: User # Injected by @require_auth
):
    """
    Deletes a tracked keyword from the system.
    """
    logger.info(f"User {current_user.username} deleting tracked keyword {keyword_id}.")
    try:
        success = await data_service.delete_tracked_keyword(keyword_id, current_user)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tracked keyword not found or could not be deleted.")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting tracked keyword {keyword_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete tracked keyword: {e}")
