"""
Environment Loader Utility - Ensures .env file is loaded before other modules initialize
File: Link_Profiler/config/env_loader.py
"""

import os
from pathlib import Path

def load_env_file(env_path=None):
    """
    Load environment variables from .env file.
    This should be called early in the application startup.
    """
    if env_path is None:
        # Look for .env file in the project root
        current_dir = Path(__file__).parent
        env_path = current_dir.parent.parent / '.env'
    else:
        env_path = Path(env_path)
    
    if not env_path.exists():
        print(f"Warning: .env file not found at {env_path}")
        return False
    
    print(f"Loading environment variables from: {env_path}")
    
    with open(env_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                try:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    
                    # Set environment variable
                    os.environ[key] = value
                    
                except ValueError:
                    print(f"Warning: Invalid format in .env file line {line_num}: {line}")
                    
    return True

# Auto-load environment variables when this module is imported
# This ensures they're available before other modules initialize
load_env_file()
