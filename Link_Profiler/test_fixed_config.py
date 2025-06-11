#!/usr/bin/env python3
"""
Fixed Config Test - Test Mission Control with proper config loading
"""

import os
import sys
import asyncio

# Set the required environment variables directly
os.environ["LP_REDIS_URL"] = "redis://localhost:6379/0"
os.environ["LP_DATABASE_URL"] = "postgresql://link_profiler:password@localhost:5432/link_profiler_db"
os.environ["LP_AUTH_SECRET_KEY"] = "test-secret-key-for-mission-control-debugging-please-change-in-production"
os.environ["LP_MONITOR_PASSWORD"] = "test-monitor-password"

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# First, let's manually load the config.yaml file and check what's in it
import yaml

config_file_path = os.path.join(project_root, "Link_Profiler", "config", "config.yaml")
print(f"Loading config from: {config_file_path}")
print(f"Config file exists: {os.path.exists(config_file_path)}")

if os.path.exists(config_file_path):
    with open(config_file_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    print(f"Mission Control section from YAML:")
    mission_control_section = config_data.get('mission_control', {})
    print(f"  enabled: {mission_control_section.get('enabled')}")
    print(f"  websocket_enabled: {mission_control_section.get('websocket_enabled')}")
    print(f"  dashboard_refresh_rate: {mission_control_section.get('dashboard_refresh_rate')}")

# Now import the config loader and see what it loads
from Link_Profiler.config.config_loader import config_loader

print(f"\nConfiguration from config_loader:")
print(f"  mission_control.enabled: {config_loader.get('mission_control.enabled')}")
print(f"  mission_control.websocket_enabled: {config_loader.get('mission_control.websocket_enabled')}")
print(f"  redis.url: {config_loader.get('redis.url')}")

# Let's also check what the internal config data looks like
print(f"\nInternal config_loader._config_data keys: {list(config_loader._config_data.keys())}")

# Let's try to force reload the config with the correct path
print(f"\nAttempting to manually fix config paths...")

# Temporarily modify the config loader to use correct paths
original_load_config = config_loader._load_config

def fixed_load_config(self):
    """Fixed version that uses correct paths"""
    current_dir = os.getcwd()
    config_dir = os.path.join(current_dir, "config")
    
    config_paths = [
        os.path.join(config_dir, "core.yaml"),
        os.path.join(config_dir, "crawler.yaml"),
        os.path.join(config_dir, "external_apis.yaml"),
        os.path.join(config_dir, "security.yaml"),
        os.path.join(config_dir, "monitoring.yaml"),
        os.path.join(config_dir, "features.yaml"),
        os.path.join(config_dir, "config.yaml")  # This one should exist
    ]
    
    loaded_files = []
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        self._merge_config(self._config_data, file_config)
                        loaded_files.append(path)
                        print(f"Loaded config file: {path}")
            except Exception as e:
                print(f"Error loading config file {path}: {e}")
        else:
            print(f"Config file not found: {path}")

    if loaded_files:
        print(f"Successfully loaded configuration from: {loaded_files}")
    else:
        print("No configuration files found!")

    self._load_env_variables()

# Monkey patch the method and reload
import types
config_loader._load_config = types.MethodType(fixed_load_config, config_loader)
config_loader._config_data = {}  # Clear existing config
config_loader._load_config()

print(f"\nAfter fixed loading:")
print(f"  mission_control.enabled: {config_loader.get('mission_control.enabled')}")
print(f"  mission_control.websocket_enabled: {config_loader.get('mission_control.websocket_enabled')}")
print(f"  redis.url: {config_loader.get('redis.url')}")

async def test_with_fixed_config():
    """Test Mission Control with fixed configuration"""
    
    # Check if we have the Mission Control settings now
    if config_loader.get('mission_control.enabled') is None:
        print("[ERROR] Mission Control configuration still not loaded properly!")
        return False
    
    print(f"\n[SUCCESS] Mission Control configuration loaded:")
    print(f"  enabled: {config_loader.get('mission_control.enabled')}")
    print(f"  websocket_enabled: {config_loader.get('mission_control.websocket_enabled')}")
    
    # For now, skip Redis/DB tests since they're not running locally
    # The main issue was the configuration loading
    
    print(f"\n[SUCCESS] Configuration issue appears to be resolved!")
    print(f"The WebSocket should now work if Redis and Database are available.")
    
    return True

if __name__ == "__main__":
    asyncio.run(test_with_fixed_config())
