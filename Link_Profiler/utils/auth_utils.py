"""
Authentication utilities - Helper functions for authentication and authorization.
File: Link_Profiler/utils/auth_utils.py
"""

import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from Link_Profiler.core.models import User
from Link_Profiler.services.auth_service import auth_service_instance

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Retrieves the current authenticated user based on the JWT token.
    Raises HTTPException if authentication fails.
    """
    try:
        user = await auth_service_instance.get_current_user(token)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except HTTPException:
        # Re-raise FastAPI's own HTTPExceptions (e.g., 401 from auth_service_instance.get_current_user)
        raise
    except ValueError as ve:
        logger.error(f"Authentication service configuration error: {ve}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service misconfigured or unavailable.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error(f"Unexpected error during user authentication: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during authentication.",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_user_tier(user: User) -> str:
    """
    Determines the user tier based on their role.
    Maps user roles to subscription tiers for API access control.
    
    Args:
        user: User object
        
    Returns:
        str: User tier ("free", "basic", "pro", "enterprise")
    """
    if not user:
        return "free"
    
    # Map user roles to tiers
    role_to_tier_map = {
        "free": "free",
        "customer": "basic",  # Default customer role gets basic tier
        "premium_customer": "pro",
        "enterprise_customer": "enterprise",
        "admin": "enterprise",  # Admins get full access
        "analyst": "pro",  # Internal analysts get pro access
    }
    
    # Get user role - check if it's a string (role name) or Role object
    user_role = user.role
    if hasattr(user_role, 'name'):
        # Role is a Role dataclass object
        role_name = user_role.name
    elif isinstance(user_role, str):
        # Role is just a string
        role_name = user_role
    else:
        # Fallback to free if role is None or unknown type
        logger.warning(f"User {user.username} has unknown role type: {type(user_role)}")
        return "free"
    
    # Return corresponding tier, default to "free" if role not found
    tier = role_to_tier_map.get(role_name, "free")
    
    logger.debug(f"User {user.username} with role '{role_name}' mapped to tier '{tier}'")
    return tier

def can_access_live_data(user: User, feature: str = None) -> bool:
    """
    Check if a user can access live data for a specific feature.
    
    Args:
        user: User object
        feature: Optional specific feature to check
        
    Returns:
        bool: True if user can access live data
    """
    tier = get_user_tier(user)
    
    # Free tier cannot access live data
    if tier == "free":
        return False
    
    # Premium features that require pro tier or higher
    premium_features = [
        "domain_content_gaps", "custom_analysis", "domain_link_prospects",
        "competitive_analysis", "keyword_trends_analytical"
    ]
    
    # Basic tier users cannot access premium features
    if tier == "basic" and feature in premium_features:
        return False
    
    # Pro and enterprise tiers can access all live features
    return tier in ["pro", "enterprise"]

async def increment_live_api_usage(user_id: str, feature: str = None) -> None:
    """
    Increments the live API usage counter for a user.
    Delegates to the auth_service_instance for Redis tracking.
    
    Args:
        user_id: User ID
        feature: Feature that was accessed
    """
    await auth_service_instance.increment_user_api_usage(user_id, feature)
    logger.debug(f"Live API usage recorded for user {user_id}, feature: {feature}")

def validate_live_access(user: User, feature: str) -> None:
    """
    Validates if a user can access live data for a specific feature.
    Raises HTTPException if access is denied.
    
    Args:
        user: User object
        feature: Feature name to check access for
        
    Raises:
        HTTPException: If user doesn't have access
    """
    if not can_access_live_data(user, feature):
        tier = get_user_tier(user)
        
        if tier == "free":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Live data requires a paid plan. Please upgrade your subscription."
            )
        elif tier == "basic":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Live {feature} requires Pro plan or higher. Please upgrade your subscription."
            )
        else:
            # This shouldn't happen, but handle it gracefully
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied for live data."
            )
