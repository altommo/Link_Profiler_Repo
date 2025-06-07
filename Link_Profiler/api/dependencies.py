import logging
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
    user = await auth_service_instance.get_current_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to ensure the current user is an admin.
    """
    if not current_user.is_admin:
        logger.warning(f"User {current_user.username} (ID: {current_user.id}) attempted admin access without privileges.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation forbidden: Admin access required"
        )
    return current_user

async def get_current_customer_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency to ensure the current user has the 'customer' role.
    """
    if current_user.role != "customer" and not current_user.is_admin: # Admins can also access customer routes
        logger.warning(f"User {current_user.username} (ID: {current_user.id}) attempted customer access with role '{current_user.role}'.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation forbidden: Customer role required"
        )
    return current_user

async def get_current_user_with_roles(required_roles: list[str]):
    """
    A factory function to create a dependency that checks for multiple roles.
    Usage: Depends(get_current_user_with_roles(["admin", "analyst"]))
    """
    async def _get_current_user_with_roles(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in required_roles and not current_user.is_admin: # Admins bypass role checks
            logger.warning(f"User {current_user.username} (ID: {current_user.id}) attempted access with role '{current_user.role}'. Required roles: {required_roles}.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation forbidden: One of {', '.join(required_roles)} roles required"
            )
        return current_user
    return _get_current_user_with_roles
