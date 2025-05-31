"""
Auth Service - Handles user authentication, registration, and JWT token management.
File: Link_Profiler/services/auth_service.py
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
import uuid

from passlib.context import CryptContext # For password hashing
from jose import JWTError, jwt # For JWT token handling

from Link_Profiler.database.database import Database
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
        self.secret_key = config_loader.get("auth.secret_key")
        self.algorithm = config_loader.get("auth.algorithm", "HS256")
        self.access_token_expire_minutes = config_loader.get("auth.access_token_expire_minutes", 30)
        self.logger = logging.getLogger(__name__)

        if not self.secret_key:
            self.logger.error("AUTH_SECRET_KEY is not configured. Authentication will not work.")
            raise ValueError("AUTH_SECRET_KEY must be set in configuration.")

    async def __aenter__(self):
        """No specific async setup needed for this class."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific async cleanup needed for this class."""
        pass

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verifies a plain password against a hashed password."""
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hashes a plain password."""
        return pwd_context.hash(password)

    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Creates a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def decode_access_token(self, token: str) -> Optional[TokenData]:
        """Decodes and validates a JWT access token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            username: str = payload.get("sub")
            if username is None:
                return None
            token_data = TokenData(username=username)
        except JWTError:
            return None
        return token_data

    async def register_user(self, username: str, email: str, password: str) -> User:
        """Registers a new user."""
        hashed_password = self.get_password_hash(password)
        user_id = str(uuid.uuid4())
        new_user = User(
            id=user_id,
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_active=True,
            is_admin=False # Default to non-admin
        )
        try:
            created_user = self.db.create_user(new_user)
            self.logger.info(f"User '{username}' registered successfully.")
            return created_user
        except ValueError as e:
            self.logger.warning(f"User registration failed for '{username}': {e}")
            raise

    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticates a user by username and password."""
        user = self.db.get_user_by_username(username)
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        self.logger.info(f"User '{username}' authenticated successfully.")
        return user

    async def get_current_user(self, token: str) -> User:
        """Retrieves the current authenticated user from a JWT token."""
        token_data = self.decode_access_token(token)
        if token_data is None:
            raise ValueError("Invalid authentication credentials")
        
        user = self.db.get_user_by_username(token_data.username)
        if user is None:
            raise ValueError("User not found")
        if not user.is_active:
            raise ValueError("Inactive user")
        return user
