#!/usr/bin/env python3
"""
Debug script to test authentication and settings endpoints
"""

import os
import sys
import requests
import json

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Configuration
API_BASE_URL = "http://localhost:8000"  # Adjust if different
DEFAULT_ADMIN_USERNAME = "monitor_user"
DEFAULT_ADMIN_PASSWORD = "monitor_password"

def test_login():
    """Test the login endpoint"""
    print("=== Testing Login ===")
    login_url = f"{API_BASE_URL}/token"
    
    login_data = {
        "username": DEFAULT_ADMIN_USERNAME,
        "password": DEFAULT_ADMIN_PASSWORD
    }
    
    try:
        response = requests.post(login_url, data=login_data, headers={
            "Content-Type": "application/x-www-form-urlencoded"
        })
        
        print(f"Login Status Code: {response.status_code}")
        print(f"Login Response: {response.text}")
        
        if response.status_code == 200:
            token_data = response.json()
            return token_data.get("access_token")
        else:
            print("Login failed!")
            return None
            
    except Exception as e:
        print(f"Error during login: {e}")
        return None

def test_user_me(token):
    """Test the /users/me endpoint"""
    print("\n=== Testing /users/me ===")
    if not token:
        print("No token available, skipping...")
        return None
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(f"{API_BASE_URL}/users/me", headers=headers)
        print(f"Users/me Status Code: {response.status_code}")
        print(f"Users/me Response: {response.text}")
        
        if response.status_code == 200:
            return response.json()
        else:
            print("User verification failed!")
            return None
            
    except Exception as e:
        print(f"Error during user verification: {e}")
        return None

def test_admin_config(token):
    """Test the /admin/config endpoint"""
    print("\n=== Testing /admin/config ===")
    if not token:
        print("No token available, skipping...")
        return
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(f"{API_BASE_URL}/admin/config", headers=headers)
        print(f"Admin/config Status Code: {response.status_code}")
        print(f"Admin/config Response: {response.text}")
        
    except Exception as e:
        print(f"Error during admin config request: {e}")

def test_admin_api_keys(token):
    """Test the /admin/api_keys endpoint"""
    print("\n=== Testing /admin/api_keys ===")
    if not token:
        print("No token available, skipping...")
        return
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(f"{API_BASE_URL}/admin/api_keys", headers=headers)
        print(f"Admin/api_keys Status Code: {response.status_code}")
        print(f"Admin/api_keys Response: {response.text}")
        
    except Exception as e:
        print(f"Error during admin api_keys request: {e}")

def main():
    print(f"Testing authentication with API at {API_BASE_URL}")
    print(f"Using admin credentials: {DEFAULT_ADMIN_USERNAME} / {DEFAULT_ADMIN_PASSWORD}")
    
    # Step 1: Login
    token = test_login()
    
    # Step 2: Verify user
    user_data = test_user_me(token)
    
    # Step 3: Test admin endpoints
    test_admin_config(token)
    test_admin_api_keys(token)
    
    if user_data:
        print(f"\n=== Summary ===")
        print(f"User: {user_data.get('username')}")
        print(f"Is Admin: {user_data.get('is_admin')}")
        print(f"Email: {user_data.get('email')}")

if __name__ == "__main__":
    main()
