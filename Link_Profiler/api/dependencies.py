import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated

# Import required modules directly instead of from main.py to avoid circular import
from Link_Profiler.services.auth_service import AuthService
from Link_Profiler.database.database import Database
from Link_Profiler.config.config_loader import ConfigLoader
from Link_Profiler.core.models import User

# Initialize logger
logger = logging.getLogger(__name__)

# OAuth2PasswordBearer for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# Initialize auth service locally to avoid circular imports
config_loader = ConfigLoader()
if not config_loader._is_loaded:
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_loader.load_config(config_dir=os.path.join(project_root, "Link_Profiler", "config"), env_var_prefix="LP_")

DATABASE_URL = config_loader.get("database.url")
db = Database(db_url=DATABASE_URL)
auth_service_instance = AuthService(db)

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
