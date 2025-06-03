import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated

# Import the globally initialized instances from main.py
# This is generally acceptable for global singletons initialized early in main.py
# as long as main.py doesn't import this file at the top level before these are defined.
# main.py will import the routers, which in turn import this file.
try:
    from Link_Profiler.main import auth_service_instance, logger
except ImportError:
    # Fallback for testing or if main.py is not yet fully initialized
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)
    # Create a dummy auth_service_instance for testing if needed
    class DummyAuthService:
        async def get_current_user(self, token: str):
            raise NotImplementedError("AuthService not initialized for testing.")
    auth_service_instance = DummyAuthService()


from Link_Profiler.core.models import User

# OAuth2PasswordBearer for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# --- Dependency for current user authentication ---
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    """
    Retrieves the current authenticated user based on the provided token.
    """
    try:
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
