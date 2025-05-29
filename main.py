"""
Main entry point for the Link Profiler API application.
File: main.py
"""

import uvicorn
import os
import sys

# Removed sys.path.insert here. Relying on uvicorn's app_dir.

# The application is now imported as a module from the Link_Profiler package.
# This requires the 'Link_Profiler' directory to be on the PYTHONPATH,
# which is typically handled by 'pip install -e .' or by setting PYTHONPATH.
# When running with uvicorn, --app-dir . ensures the current directory
# (which should be the project root) is added to sys.path.
# The import below is commented out as it's not needed for uvicorn.run()
# from Link_Profiler.api.main import app 

if __name__ == "__main__":
    # Run uvicorn, specifying the app module and the application directory.
    # --app-dir . tells uvicorn to add the current directory (project root)
    # to sys.path, allowing absolute imports like Link_Profiler.api.main to resolve.
    uvicorn.run(
        "Link_Profiler.api.main:app", # Specify the app as a module within the package
        host="0.0.0.0",
        port=8000,
        reload=True,
        app_dir="." # Crucial for resolving absolute imports from the project root
    )
