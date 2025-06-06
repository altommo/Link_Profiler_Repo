import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated, Optional

# Import required modules directly instead of from main.py to avoid circular import
from Link_Profiler.services.auth_service import AuthService
from Link_Profiler.database.database import db # Use the global db instance
from Link_Profiler.config.config_loader import config_loader # Use the global config_loader instance
from Link_Profiler.core.models import User

# Initialize logger
logger = logging.getLogger(__name__)

# OAuth2PasswordBearer for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Global variable to hold the initialized AuthService instance
_auth_service_instance: Optional[AuthService] = None

def set_auth_service_instance(instance: AuthService):
    """
    Sets the global AuthService instance for use in dependencies.
    This function should be called once during application startup (e.g., in main.py's lifespan).
    """
    global _auth_service_instance
    _auth_service_instance = instance
    logger.info("AuthService instance set in dependencies.")

# --- Dependency for current user authentication ---
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    """
    Retrieves the current authenticated user based on the provided token.
    """
    try:
        # Ensure _auth_service_instance is not None before calling its method
        if _auth_service_instance is None:
            logger.error("AuthService instance is None in dependencies.py. It might not have been initialized or set in main.py.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service not available."
            )
        user = await _auth_service_instance.get_current_user(token)
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

