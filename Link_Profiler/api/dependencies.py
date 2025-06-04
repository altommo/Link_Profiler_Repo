import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated

# Import the globally initialized instances from main.py
# This import should now succeed if main.py initializes auth_service_instance early enough.
# Removed the try...except ImportError block to ensure direct import.
from Link_Profiler.main import auth_service_instance, logger


from Link_Profiler.core.models import User

# OAuth2PasswordBearer for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

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
