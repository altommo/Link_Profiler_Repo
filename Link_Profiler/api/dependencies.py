import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated

# Import required modules directly instead of from main.py to avoid circular import
from Link_Profiler.services.auth_service import AuthService
from Link_Profiler.database.database import db # Use the global db instance
from Link_Profiler.config.config_loader import config_loader # Use the global config_loader instance
from Link_Profiler.core.models import User

# Initialize logger
logger = logging.getLogger(__name__)

# OAuth2PasswordBearer for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Initialize auth service locally to avoid circular imports
# These are already singletons initialized in main.py, so just reference them
auth_service_instance = AuthService(db) # Pass the db singleton

# --- Dependency for current user authentication ---
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    """
    Retrieves the current authenticated user based on the provided token.
    """
    try:
        # Ensure auth_service_instance is not None before calling its method
        if auth_service_instance is None:
            logger.error("AuthService instance is None in dependencies.py. It might not have been initialized in main.py.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service not available."
            )
        user = await auth_service_instance.get_current_user(token)
        return user
    except HTTPException: # Re-raise HTTPException from auth_service
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_current_user: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication.",
            headers={"WWW-Authenticate": "Bearer"},
        )

