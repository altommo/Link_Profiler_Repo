import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

# Import the globally initialized instances from main.py
# Removed try...except ImportError block
from Link_Profiler.main import auth_service_instance, logger, config_loader


# Import Pydantic models from the shared schemas file
from Link_Profiler.api.schemas import UserCreate, UserResponse, Token

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])

@auth_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user_endpoint(user_data: UserCreate):
    """
    Registers a new user.
    """
    try:
        user = await auth_service_instance.register_user(
            username=user_data.username,
            email=user_data.email,
            password=user_data.password
        )
        return UserResponse.from_user(user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException: # Re-raise HTTPException from auth_service
        raise
    except Exception as e:
        logger.error(f"Error during user registration: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error during registration.")

@auth_router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticates a user and returns an token.
    """
    user = await auth_service_instance.authenticate_user(form_data.username, form_data.password)
    if not user:
        logger.warning(f"Authentication failed for user: '{form_data.username}'. Incorrect username or password.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info(f"User '{form_data.username}' successfully authenticated and received token.")
    access_token_expires = timedelta(minutes=auth_service_instance.access_token_expire_minutes)
    access_token = auth_service_instance.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
