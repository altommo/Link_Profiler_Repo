"""
Setup Script for Link Profiler Authentication
This script helps configure the environment variables needed for authentication.
"""

import os
import secrets
import string
from pathlib import Path

def generate_secret_key(length=64):
    """Generate a secure random secret key."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_env_file():
    """Create .env file with required configurations."""
    project_root = Path(__file__).parent
    env_file = project_root / ".env"
    env_example = project_root / ".env.example"
    
    if env_file.exists():
        print(f"⚠️  .env file already exists at {env_file}")
        response = input("Do you want to overwrite it? (y/N): ")
        if response.lower() != 'y':
            return False
    
    # Read the example file
    if not env_example.exists():
        print(f"❌ .env.example file not found at {env_example}")
        return False
    
    with open(env_example, 'r') as f:
        template = f.read()
    
    # Generate secure secret key
    secret_key = generate_secret_key()
    
    # Replace placeholders with actual values
    env_content = template.replace(
        "your-secure-jwt-secret-key-here-minimum-32-characters-long",
        secret_key
    )
    
    # Prompt for database configuration
    print("\n🔧 Database Configuration")
    print("Please provide your PostgreSQL database details:")
    
    db_host