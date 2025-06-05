import os
from typing import Any, Optional, Dict, List
import secrets
import logging

logger = logging.getLogger(__name__)

class EnvironmentConfig:
    """Real environment variable configuration with validation and defaults."""
    
    @staticmethod
    def get_env_var(key: str, default: Any = None, required: bool = False, var_type: type = str) -> Any:
        """
        Get environment variable with type conversion and validation.
        
        Args:
            key: Environment variable name
            default: Default value if not set
            required: Whether variable is required
            var_type: Type to convert to (str, int, bool, list)
            
        Returns:
            Converted value or default
        """
        value = os.getenv(key)
        
        if value is None:
            if required:
                raise ValueError(f"Required environment variable {key} is not set")
            return default
        
        # Type conversion
        try:
            if var_type == bool:
                return value.lower() in ('true', '1', 'yes', 'on')
            elif var_type == int:
                return int(value)
            elif var_type == float:
                return float(value)
            elif var_type == list:
                return [item.strip() for item in value.split(',') if item.strip()]
            else:
                return value
        except ValueError as e:
            raise ValueError(f"Environment variable {key}='{value}' cannot be converted to {var_type.__name__}: {e}")
    
    @staticmethod
    def generate_secret_key(length: int = 32) -> str:
        """Generate a secure random secret key."""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def validate_required_vars() -> List[str]:
        """Validate all required environment variables are set."""
        required_vars = {
            'LP_DATABASE_URL': str,
            'LP_REDIS_URL': str,
            'LP_AUTH_SECRET_KEY': str
        }
        
        missing = []
        for var_name, var_type in required_vars.items():
            try:
                EnvironmentConfig.get_env_var(var_name, required=True, var_type=var_type)
            except ValueError:
                missing.append(var_name)
        
        return missing
    
    @staticmethod
    def get_database_url() -> str:
        """Get database URL with validation."""
        db_url = EnvironmentConfig.get_env_var('LP_DATABASE_URL', required=True)
        if not db_url.startswith(('postgresql://', 'mysql://', 'sqlite:///')):
            raise ValueError(f"Invalid database URL format: {db_url}")
        return db_url
    
    @staticmethod
    def get_redis_url() -> str:
        """Get Redis URL with validation."""
        redis_url = EnvironmentConfig.get_env_var('LP_REDIS_URL', default='redis://localhost:6379/0')
        if not redis_url.startswith('redis://'):
            raise ValueError(f"Invalid Redis URL format: {redis_url}")
        return redis_url
    
    @staticmethod
    def get_api_key(service: str, required: bool = False) -> Optional[str]:
        """Get API key for a service."""
        key_name = f"LP_{service.upper()}_API_KEY"
        return EnvironmentConfig.get_env_var(key_name, required=required)
