"""
Main entry point for the Link Profiler API application.
File: main.py
"""

# This file is primarily for documentation purposes on how to run the application.
# The actual FastAPI application is located in api/main.py.

# To run the application, use uvicorn directly from your project root:
# uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# The --reload flag is useful for development as it restarts the server on code changes.
# For production, you would typically omit --reload and use a process manager like Gunicorn.

# Example of how to run it programmatically (less common for production setup):
# import uvicorn
# from api.main import app
#
# if __name__ == "__main__":
#     uvicorn.run(app, host="0.0.0.0", port=8000)

# The previous sys.path.insert and direct import were causing issues with relative imports
# when this file was run directly. By instructing to run via `uvicorn api.main:app`,
# Python correctly interprets `api` as a package.
