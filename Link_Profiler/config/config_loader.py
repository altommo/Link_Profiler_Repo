import os
import json
import logging
from typing import Dict, Any, Optional
import yaml # Import yaml

logger = logging.getLogger(__name__)

class ConfigLoader:
    """
    Loads configuration from JSON/YAML files and environment variables.
    Environment variables take precedence over file settings.
    """
    _instance = None
    _config: Dict[str, Any] = {}
    _is_loaded: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
        return cls._instance

    def load_config(self, config_dir: str = "Link_Profiler/config", env_var_prefix: str = ""):
        """
        Loads configuration from default.yaml (or default.json if yaml not found)
        and environment variables.
        Environment variables with the given prefix (e.g., "LP_") will override
        settings in the config file.
        """
        if self._is_loaded:
            logger.debug("Config already loaded. Skipping re-load.")
            return

        config_file_path_yaml = os.path.join(config_dir, "config.yaml")
        config_file_path_json = os.path.join(config_dir, "default.json") # Fallback to default.json

        loaded_from_file = {}
        if os.path.exists(config_file_path_yaml):
            try:
                with open(config_file_path_yaml, 'r') as f:
                    loaded_from_file = yaml.safe_load(f)
                logger.info(f"Configuration loaded from {config_file_path_yaml}")
            except yaml.YAMLError as e:
                logger.error(f"Error loading YAML config from {config_file_path_yaml}: {e}")
                loaded_from_file = {} # Fallback to empty if YAML fails
        elif os.path.exists(config_file_path_json):
            try:
                with open(config_file_path_json, 'r') as f:
                    loaded_from_file = json.load(f)
                logger.info(f"Configuration loaded from {config_file_path_json}")
            except json.JSONDecodeError as e:
                logger.error(f"Error loading JSON config from {config_file_path_json}: {e}")
                loaded_from_file = {} # Fallback to empty if JSON fails
        else:
            logger.warning(f"No config file found at {config_file_path_yaml} or {config_file_path_json}. Using environment variables and defaults only. Attempted from directory: {config_dir}") # Added debug info

        self._config = loaded_from_file if loaded_from_file is not None else {}

        # Override with environment variables
        for key, value in os.environ.items():
            if key.startswith(env_var_prefix):
                # Convert environment variable name (e.g., LP_DATABASE_URL) to config path (database.url)
                config_path = key[len(env_var_prefix):].lower().replace('_', '.')
                
                # Attempt to convert value to appropriate type (int, float, bool, list, dict)
                converted_value = self._convert_env_value(value)
                
                logger.info(f"Processing env var: {key} -> {config_path} = {converted_value}") # Added logging
                self._set_nested_value(self._config, config_path, converted_value)
                logger.debug(f"Overrode config setting '{config_path}' with environment variable '{key}'")

        self._is_loaded = True

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Retrieves a configuration value using a dot-separated key path (e.g., "database.url").
        """
        keys = key_path.split('.')
        current_value = self._config
        for key in keys:
            if isinstance(current_value, dict) and key in current_value:
                current_value = current_value[key]
            else:
                return default
        return current_value

    def _set_nested_value(self, d: Dict, key_path: str, value: Any):
        """Sets a value in a nested dictionary using a dot-separated key path."""
        keys = key_path.split('.')
        for i, key in enumerate(keys):
            if i == len(keys) - 1:
                d[key] = value
            else:
                if not isinstance(d.get(key), dict):
                    d[key] = {}
                d = d[key]

    def _convert_env_value(self, value: str) -> Any:
        """Attempts to convert environment variable string value to appropriate Python type."""
        if value.lower() == 'true':
            return True
        if value.lower() == 'false':
            return False
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                if value.startswith('[') and value.endswith(']'):
                    try:
                        return json.loads(value) # For list/array like "[item1, item2]"
                    except json.JSONDecodeError:
                        pass
                if value.startswith('{') and value.endswith('}'):
                    try:
                        return json.loads(value) # For dict like "{"key": "value"}"
                    except json.JSONDecodeError:
                        pass
                return value # Return as string if no other conversion works

    def _deep_update(self, main_dict: Dict, update_dict: Dict):
        """
        Recursively updates a dictionary with values from another dictionary.
        Existing keys in main_dict that are also in update_dict will be overwritten.
        """
        for key, value in update_dict.items():
            if isinstance(value, dict) and key in main_dict and isinstance(main_dict[key], dict):
                main_dict[key] = self._deep_update(main_dict[key], value)
            else:
                main_dict[key] = value
        return main_dict

# Global instance for easy access
config_loader = ConfigLoader()
