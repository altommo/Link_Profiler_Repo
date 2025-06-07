"""
Auth Service - Handles user authentication, registration, and JWT token management.
File: Link_Profiler/services/auth_service.py
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import uuid
import os # New: Import os for environment variable access

from passlib.context import CryptContext # For password hashing
from jose import JWTError, jwt # For JWT token handling
from fastapi import HTTPException, status # New: Import HTTPException and status

from Link_Profiler.database.database import Database, db
from Link_Profiler.core.models import User, Token, TokenData
from Link_Profiler.config.config_loader import config_loader

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    """
    Service for user authentication, registration, and JWT token management.
    """
    def __init__(self, database: Database):
        self.db = database
        
        # Prioritize environment variable for secret_key
        env_secret = os.getenv("LP_AUTH_SECRET_KEY")
        config_secret = config_loader.get("auth.secret_key")

        if env_secret and env_secret != "PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY":
            self.secret_key = env_secret
            logger.info(f"Auth service using secret_key from environment variable (LP_AUTH_SECRET_KEY): {self.secret_key[:10]}...")
        elif config_secret and config_secret != "PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY":
            self.secret_key = config_secret
            logger.info(f"Auth service using secret_key from config.yaml: {self.secret_key[:10]}...")
        else:
            self.secret_key = None # No valid secret key found
            logger.error("AUTH_SECRET_KEY is not configured in environment (LP_AUTH_SECRET_KEY) or config.yaml, or is using the default placeholder. Authentication will not work securely.")

        self.algorithm = config_loader.get("auth.algorithm", "HS256")
        self.access_token_expire_minutes = config_loader.get("auth.access_token_expire_minutes", 30)
        self.logger = logging.getLogger(__name__)

        # The _check_secret_key method will now handle raising HTTPException if self.secret_key is None
        
    async def __aenter__(self):
        """No specific async setup needed for this class."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific async cleanup needed for this class."""
        pass

    def _check_secret_key(self):
        """Internal helper to check if the secret key is configured."""
        if self.secret_key is None or self.secret_key == "PLACEHOLDER_MUST_SET_LP_AUTH_SECRET_KEY":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service is not configured. Missing or placeholder secret key."
            )

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verifies a plain password against a hashed password."""
        self._check_secret_key()
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hashes a plain password."""
        self._check_secret_key()
        return pwd_context.hash(password)

    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """
        Creates a JWT access token.
        Includes 'sub' (username), 'role', and 'organization_id' in the payload.
        """
        self._check_secret_key()
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        # Ensure 'role' and 'organization_id' are included if present in data
        # 'sub' is typically the username
        payload = {
            "sub": to_encode.get("sub"),
            "role": to_encode.get("role"),
            "organization_id": to_encode.get("organization_id"),
            "exp": expire
        }
        encoded_jwt = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def decode_access_token(self, token: str) -> Optional[TokenData]:
        """
        Decodes and validates a JWT access token.
        Extracts 'username', 'role', and 'organization_id'.
        """
        self._check_secret_key()
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username: str = payload.get("sub")
            role: Optional[str] = payload.get("role")
            organization_id: Optional[str] = payload.get("organization_id")

            if username is None:
                return None
            token_data = TokenData(username=username, role=role, organization_id=organization_id)
        except JWTError:
            return None
        except Exception as e:
            self.logger.error(f"Error decoding access token: {e}", exc_info=True)
            return None
        return token_data

    async def register_user(self, username: str, email: str, password: str, is_admin: bool = False, role: str = "customer", organization_id: Optional[str] = None) -> User:
        """Registers a new user."""
        self._check_secret_key()
        hashed_password = self.get_password_hash(password)
        user_id = str(uuid.uuid4())
        new_user = User(
            id=user_id,
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_active=True,
            is_admin=is_admin, # Use provided is_admin
            role=role, # Use provided role
            organization_id=organization_id # Use provided organization_id
        )
        try:
            created_user = self.db.create_user(new_user)
            self.logger.info(f"User '{username}' registered successfully with role '{role}'.")
            return created_user
        except ValueError as e:
            self.logger.warning(f"User registration failed for '{username}': {e}")
            raise

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticates a user by username and password."""
        self._check_secret_key()
        user = self.db.get_user_by_username(username)
        if not user:
            return None
        if not user.is_active:
            self.logger.warning(f"Authentication failed for '{username}': user is inactive.")
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        self.logger.info(f"User '{username}' authenticated successfully.")
        return user


    async def get_current_user(self, token: str) -> User:
        """Retrieves the current authenticated user from a JWT token."""
        self._check_secret_key()
        token_data = self.decode_access_token(token)
        if token_data is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials", headers={"WWW-Authenticate": "Bearer"})
        
        user = self.db.get_user_by_username(token_data.username)
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found", headers={"WWW-Authenticate": "Bearer"})
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user", headers={"WWW-Authenticate": "Bearer"})
        
        # Ensure the role and organization_id from the token match the user from DB
        # This adds an extra layer of security if user roles can change dynamically
        if user.role != token_data.role or user.organization_id != token_data.organization_id:
            self.logger.warning(f"User {user.username} token data mismatch with DB. Token role: {token_data.role}, DB role: {user.role}. Re-issuing token might be needed.")
            # Optionally, raise HTTPException or force re-login
            # For now, we'll proceed but log a warning.
            
        return user


# Create a singleton instance for use across the application
auth_service_instance = AuthService(db)
