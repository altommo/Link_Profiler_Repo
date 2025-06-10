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
from Link_Profiler.services.domain_service import get_domain_service # Import get_domain_service
from Link_Profiler.monitoring.prometheus_metrics import get_metrics_text

logger = logging.getLogger(__name__)

public_api_router = APIRouter(tags=["Public API"])

@public_api_router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await auth_service_instance.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth_service_instance.access_token_expire_minutes)
    access_token = auth_service_instance.create_access_token(
        data={"sub": user.username, "role": user.role, "organization_id": user.organization_id}, # Pass role and org_id
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@public_api_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_create: UserCreate):
    existing_user = db.get_user_by_username(user_create.username)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    existing_email = db.get_user_by_email(user_create.email)
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
    new_user = await auth_service_instance.register_user(
        username=user_create.username,
        email=user_create.email,
        password=user_create.password
    )
    return UserResponse.from_user(new_user)

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
        # Get the DomainService instance using the getter function
        domain_service = await get_domain_service()
        async with domain_service as ds:
            domain = await ds.get_domain_info(domain_name)
            if domain:
                db.save_domain(domain)
            else:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain info not found")
    return DomainResponse.from_domain(domain)
