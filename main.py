"""
Main entry point for the Link Profiler API application.
File: main.py
"""

import uvicorn
import os
import sys

# Add the project root to the Python path to allow absolute imports
# This assumes 'main.py' is in the project root and 'api' is a subdirectory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from api.main import app

if __name__ == "__main__":
    # You can configure uvicorn here.
    # For production, consider using a process manager like Gunicorn.
    uvicorn.run(app, host="0.0.0.0", port=8000)

