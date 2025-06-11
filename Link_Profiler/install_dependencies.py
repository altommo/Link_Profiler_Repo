#!/usr/bin/env python3
"""
Install missing dependencies for Link Profiler
"""

import subprocess
import sys

# List of required packages
packages = [
    "praw",
    "psycopg2",
    "redis",
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "alembic",
    "passlib",
    "python-jose[cryptography]",
    "python-multipart",
    "aiohttp",
    "requests",
    "beautifulsoup4",
    "lxml",
    "playwright",
    "pandas",
    "numpy"
]

def install_packages():
    """Install required packages"""
    for package in packages:
        print(f"Installing {package}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✅ {package} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {package}: {e}")
        except Exception as e:
            print(f"❌ Error installing {package}: {e}")

if __name__ == "__main__":
    print("Installing missing dependencies for Link Profiler...")
    install_packages()
    print("Installation complete!")
