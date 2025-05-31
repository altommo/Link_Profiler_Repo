"""
Configuration Loader - Centralized management for application settings.
File: Link_Profiler/config/config_loader.py
"""

import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConfigLoader:
    """
    Loads configuration from JSON files and environment variables.
    Environment variables take precedence over JSON file settings.
    """
    _instance = None
    _config: Dict[str, Any] = {}
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance

    def load_config(self, config_dir: str = "Link_Profiler/config", env_var_prefix: str = ""):
        """
        Loads configuration.
        Order of precedence (lowest to highest):
        1. default.json
        2. {ENVIRONMENT}.json (e.g., development.json, production.json)
        3. Environment variables (prefixed with env_var_prefix, e.g., APP_REDIS_URL)
        """
        if self._loaded:
            return self._config

        self._config = {}

        # 1. Load default.json
        default_config_path = os.path.join(config_dir, "default.json")
        if os.path.exists(default_config_path):
            with open(default_config_path, 'r') as f:
                self._config.update(json.load(f))
            logger.info(f"Loaded default configuration from {default_config_path}")
        else:
            logger.warning(f"Default config file not found at {default_config_path}. Proceeding with empty config.")

        # 2. Load environment-specific config
        environment = os.getenv("ENVIRONMENT", "development").lower()
        env_config_path = os.path.join(config_dir, f"{environment}.json")
        if os.path.exists(env_config_path):
            with open(env_config_path, 'r') as f:
                env_config = json.load(f)
                self._deep_update(self._config, env_config)
            logger.info(f"Loaded {environment} configuration from {env_config_path}")
        else:
            logger.info(f"No specific config file found for ENVIRONMENT='{environment}' at {env_config_path}.")

        # 3. Override with environment variables
        for key, value in os.environ.items():
            if key.startswith(env_var_prefix):
                # Convert env var name (e.g., APP_REDIS_URL) to config path (e.g., ["redis", "url"])
                # Example: APP_CRAWLER_MAX_DEPTH -> ["crawler", "max_depth"]
                # Example: APP_DATABASE_URL -> ["database", "url"]
                config_path = [p.lower() for p in key[len(env_var_prefix):].split('_')]
                
                current_level = self._config
                for i, part in enumerate(config_path):
                    if i == len(config_path) - 1: # Last part is the actual setting
                        try:
                            # Attempt to convert to int, float, or bool if possible
                            if value.lower() == 'true':
                                current_level[part] = True
                            elif value.lower() == 'false':
                                current_level[part] = False
                            elif value.isdigit():
                                current_level[part] = int(value)
                            elif value.replace('.', '', 1).isdigit():
                                current_level[part] = float(value)
                            else:
                                current_level[part] = value
                        except Exception:
                            current_level[part] = value # Fallback to string
                        logger.debug(f"Overrode config: {'.'.join(config_path)} = {current_level[part]} from env var {key}")
                    else:
                        if part not in current_level or not isinstance(current_level[part], dict):
                            current_level[part] = {}
                        current_level = current_level[part]
        
        self._loaded = True
        return self._config

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Retrieves a configuration value using a dot-separated path (e.g., "crawler.max_depth").
        """
        parts = key_path.split('.')
        current_value = self._config
        for part in parts:
            if isinstance(current_value, dict) and part in current_value:
                current_value = current_value[part]
            else:
                return default
        return current_value

    def _deep_update(self, main_dict: Dict, update_dict: Dict):
        """Recursively updates a dictionary."""
        for key, value in update_dict.items():
            if key in main_dict and isinstance(main_dict[key], dict) and isinstance(value, dict):
                self._deep_update(main_dict[key], value)
            else:
                main_dict[key] = value

# Initialize and load config once
config_loader = ConfigLoader()
config_loader.load_config(env_var_prefix="LP_") # Using LP_ as prefix for Link Profiler environment variables
