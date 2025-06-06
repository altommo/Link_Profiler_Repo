"""
Config Loader - Loads configuration from JSON/YAML files and environment variables.
Environment variables take precedence over file settings.
File: Link_Profiler/config/config_loader.py
"""

import os
import yaml
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class ConfigLoader:
    """
    Loads configuration from JSON/YAML files and environment variables.
    Environment variables take precedence over file settings.
    Implemented as a singleton to ensure a single, globally accessible configuration.
    """
    _instance = None
    _config_data: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".ConfigLoader")
        self._load_config()

    def _load_config(self):
        """
        Loads configuration from default YAML files and environment variables.
        Environment variables override file settings.
        """
        config_paths = [
            "Link_Profiler/config/core.yaml",
            "Link_Profiler/config/crawler.yaml",
            "Link_Profiler/config/external_apis.yaml",
            "Link_Profiler/config/security.yaml",
            "Link_Profiler/config/monitoring.yaml",
            "Link_Profiler/config/features.yaml",
            "Link_Profiler/config/config.yaml" # Legacy/fallback
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
                except Exception as e:
                    self.logger.error(f"Error loading config file {path}: {e}")
            else:
                self.logger.debug(f"Config file not found: {path}")

        if not loaded_files:
            self.logger.warning("No configuration files found. Using default settings and environment variables only.")
        else:
            self.logger.info(f"Loaded configuration from: {', '.join(loaded_files)}")

        self._load_env_variables()
        self.logger.info("Configuration loaded successfully.")

    def _merge_config(self, target: Dict, source: Dict):
        """
        Recursively merges source dictionary into target dictionary.
        Existing keys in target are overwritten by source.
        """
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._merge_config(target[key], value)
            else:
                target[key] = value

    def _load_env_variables(self):
        """
        Loads environment variables and applies them to the configuration,
        overriding any values loaded from files.
        Supports nested keys using '__' as a separator (e.g., 'DATABASE__URL').
        """
        for key, value in os.environ.items():
            # Only consider environment variables prefixed with 'LP_'
            if not key.startswith('LP_'):
                continue

            # Convert LP_DATABASE_URL to database.url
            # LP_AI_OPENROUTER_API_KEY to ai.openrouter_api_key
            # LP_MONITOR_PASSWORD to monitoring.monitor_auth.password
            config_key_path = key[3:].lower().replace('__', '.') # Remove prefix, lowercase, replace __ with .

            # Handle special cases for password/secret keys that might be directly referenced
            if config_key_path == 'auth.secret_key':
                self._set_nested_value(self._config_data, 'auth.secret_key', value)
                self.logger.debug(f"Applied environment variable LP_AUTH_SECRET_KEY to auth.secret_key")
            elif config_key_path == 'monitor_password': # LP_MONITOR_PASSWORD
                self._set_nested_value(self._config_data, 'monitoring.monitor_auth.password', value)
                self.logger.debug(f"Applied environment variable LP_MONITOR_PASSWORD to monitoring.monitor_auth.password")
            elif config_key_path == 'redis_url': # LP_REDIS_URL
                self._set_nested_value(self._config_data, 'redis.url', value)
                self.logger.debug(f"Applied environment variable LP_REDIS_URL to redis.url")
            elif config_key_path == 'database_url': # LP_DATABASE_URL
                self._set_nested_value(self._config_data, 'database.url', value)
                self.logger.debug(f"Applied environment variable LP_DATABASE_URL to database.url")
            elif config_key_path == 'ai_openrouter_api_key': # LP_AI_OPENROUTER_API_KEY
                self._set_nested_value(self._config_data, 'ai.openrouter_api_key', value)
                self.logger.debug(f"Applied environment variable LP_AI_OPENROUTER_API_KEY to ai.openrouter_api_key")
            elif config_key_path == 'mission_control_enabled':
                self._set_nested_value(self._config_data, 'mission_control.enabled', value.lower() == 'true')
                self.logger.debug("Applied environment variable LP_MISSION_CONTROL_ENABLED to mission_control.enabled")
            elif config_key_path == 'websocket_enabled':
                self._set_nested_value(self._config_data, 'websocket.enabled', value.lower() == 'true')
                self.logger.debug("Applied environment variable LP_WEBSOCKET_ENABLED to websocket.enabled")
            elif config_key_path == 'dashboard_refresh_rate':
                self._set_nested_value(self._config_data, 'mission_control.dashboard_refresh_rate', int(value))
                self.logger.debug("Applied environment variable LP_DASHBOARD_REFRESH_RATE to mission_control.dashboard_refresh_rate")
            else:
                # Generic handling for other LP_ variables
                self._set_nested_value(self._config_data, config_key_path, value)
                self.logger.debug(f"Applied environment variable {key} to {config_key_path}")


    def _set_nested_value(self, data: Dict, key_path: str, value: Any):
        """Sets a value in a nested dictionary using a dot-separated key path."""
        parts = key_path.split('.')
        current = data
        for i, part in enumerate(parts):
            if i == len(parts) - 1:
                current[part] = value
            else:
                if part not in current or not isinstance(current[part], dict):
                    current[part] = {}
                current = current[part]

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Retrieves a configuration value using a dot-separated key path.
        
        Args:
            key_path: The dot-separated path to the configuration value (e.g., "database.url").
            default: The default value to return if the key path is not found.
            
        Returns:
            The configuration value or the default value if not found.
        """
        parts = key_path.split('.')
        current = self._config_data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def reload(self):
        """Reloads the configuration from files and environment variables."""
        self._config_data = {} # Clear existing config
        self._load_config()
        self.logger.info("Configuration reloaded.")

# Create a singleton instance for global access
config_loader = ConfigLoader()
