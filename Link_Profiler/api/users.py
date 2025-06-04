import logging
from fastapi import APIRouter, Depends
from typing import Annotated

# Import the globally initialized logger from main.py
from Link_Profiler.main import logger

# Import Pydantic models from the shared schemas file
from Link_Profiler.api.schemas import UserResponse

# Import common dependencies
from Link_Profiler.api.dependencies import get_current_user

# Import core models
from Link_Profiler.core.models import User

users_router = APIRouter(prefix="/users", tags=["Users"])

@users_router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    """
    Retrieves the current authenticated user's information.
    """
    return UserResponse.from_user(current_user)
