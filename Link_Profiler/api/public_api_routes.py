import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from fastapi.security import OAuth2PasswordRequestForm
from datetime import datetime, timedelta # Import datetime and timedelta
import json # Import json

from Link_Profiler.core.models import User, CrawlStatus
from Link_Profiler.api.schemas import UserCreate, UserResponse, LinkProfileResponse, DomainResponse
from Link_Profiler.api.dependencies import get_current_user
from Link_Profiler.database.database import db
from Link_Profiler.services.domain_service import domain_service_instance
from Link_Profiler.monitoring.prometheus_metrics import get_metrics_text

logger = logging.getLogger(__name__)

public_api_router = APIRouter(tags=["Public API"])

@public_api_router.get("/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Retrieves information about the current authenticated user.
    Requires authentication.
    """
    return UserResponse.from_user(current_user)

@public_api_router.get("/health")
async def health_check():
    """
    Performs a basic health check of the API and its database connection.
    """
    db_status = db.ping()
    return {"status": "ok", "database_connected": db_status}

@public_api_router.get("/metrics")
async def metrics():
    """
    Exposes Prometheus metrics for the application.
    """
    return Response(content=get_metrics_text(), media_type="text/plain")

@public_api_router.get("/link_profile/{target_url:path}", response_model=LinkProfileResponse)
async def get_link_profile(target_url: str, current_user: User = Depends(get_current_user)):
    """
    Retrieves the link profile for a given target URL.
    Requires authentication.
    """
    profile = db.get_link_profile(target_url)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link profile not found")
    return LinkProfileResponse.from_link_profile(profile)

@public_api_router.get("/domain/info/{domain_name}", response_model=DomainResponse)
async def get_domain_info(domain_name: str, current_user: User = Depends(get_current_user)):
    """
    Retrieves comprehensive information about a domain.
    Requires authentication.
    """
    domain = db.get_domain(domain_name)
    if not domain:
        # DomainService now uses smart_api_router_service internally
        async with domain_service_instance as ds:
            domain = await ds.get_domain_info(domain_name)
            if domain:
                db.save_domain(domain)
            else:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain info not found")
    return DomainResponse.from_domain(domain)
