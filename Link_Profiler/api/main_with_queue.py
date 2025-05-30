"""
Extended API with Queue System
This extends the main API with queue distribution capabilities
"""
# Import the existing app and add queue endpoints
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import main app
from Link_Profiler.api.main import app

# Import and add queue endpoints
try:
    from Link_Profiler.api.queue_endpoints import add_queue_endpoints
    add_queue_endpoints(app)
    print("✅ Queue endpoints added successfully")
except ImportError as e:
    print(f"⚠️ Queue endpoints not available: {e}")

# Export the enhanced app
__all__ = ['app']

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
