#!/usr/bin/env python3
"""
Simplified test server that doesn't require full database setup
"""

import os
import sys
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
import jwt
from typing import Dict, List, Any, Optional

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

app = FastAPI(title="Link Profiler API (Test Mode)")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, be more specific
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# Simple in-memory auth
SECRET_KEY = "test-secret-key-for-development-only"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Simple user database
USERS_DB = {
    "monitor_user": {
        "username": "monitor_user",
        "email": "admin@linkprofiler.com",
        "hashed_password": "fakehashed",  # In real app, this would be properly hashed
        "is_admin": True,
        "is_active": True,
        "id": "test-admin-id"
    }
}

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except jwt.PyJWTError:
        return None

async def get_current_user(token: str = Depends(oauth2_scheme)):
    username = verify_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = USERS_DB.get(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_admin_user(current_user: dict = Depends(get_current_user)):
    if not current_user.get("is_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation forbidden: Admin access required"
        )
    return current_user

@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = USERS_DB.get(form_data.username)
    if not user or form_data.password != "monitor_password":  # Simple password check
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "email": current_user["email"],
        "is_active": current_user["is_active"],
        "is_admin": current_user["is_admin"],
        "created_at": "2025-01-01T00:00:00Z"
    }

@app.get("/admin/config")
async def get_system_config(current_user: dict = Depends(get_current_admin_user)):
    return {
        "logging_level": "INFO",
        "api_cache_enabled": True,
        "api_cache_ttl": 3600,
        "crawler_max_depth": 3,
        "crawler_render_javascript": True
    }

@app.put("/admin/config")
async def update_system_config(config_update: dict, current_user: dict = Depends(get_current_admin_user)):
    # Just return the updated config (in a real app, you'd save it)
    return {
        "logging_level": config_update.get("logging_level", "INFO"),
        "api_cache_enabled": config_update.get("api_cache_enabled", True),
        "api_cache_ttl": config_update.get("api_cache_ttl", 3600),
        "crawler_max_depth": config_update.get("crawler_max_depth", 3),
        "crawler_render_javascript": config_update.get("crawler_render_javascript", True)
    }

@app.get("/admin/api_keys")
async def get_api_keys(current_user: dict = Depends(get_current_admin_user)):
    # Return mock API keys data
    return [
        {
            "api_name": "google_pagespeed",
            "enabled": False,
            "api_key_masked": "AIza****xyz123",
            "monthly_limit": 1000,
            "cost_per_unit": 0.01
        },
        {
            "api_name": "serpapi",
            "enabled": False,
            "api_key_masked": "****",
            "monthly_limit": 100,
            "cost_per_unit": 0.05
        }
    ]

@app.post("/admin/api_keys/{api_name}/update")
async def update_api_key(api_name: str, update_data: dict, current_user: dict = Depends(get_current_admin_user)):
    return {"message": f"API key for {api_name} updated successfully (mock)"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "mode": "test", "database_connected": False}

if __name__ == "__main__":
    import uvicorn
    print("Starting Link Profiler API in TEST MODE")
    print("Default admin credentials:")
    print("  Username: monitor_user")
    print("  Password: monitor_password")
    print("Server will be available at: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
