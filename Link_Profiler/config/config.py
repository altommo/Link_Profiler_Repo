import yaml
from dataclasses import dataclass
from typing import Optional
import os

@dataclass
class DatabaseConfig:
    url: str

@dataclass
class APIConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    external_url: str = ""
    internal_url: str = ""

@dataclass
class RedisConfig:
    url: str
    cache_ttl: int = 3600

@dataclass
class AuthConfig:
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

@dataclass
class Config:
    database: DatabaseConfig
    api: APIConfig
    redis: RedisConfig
    auth: AuthConfig

def load_config(config_path: Optional[str] = None) -> Config:
    """Load configuration from YAML file"""
    if config_path is None:
        config_path = os.getenv('CONFIG_FILE', '/opt/Link_Profiler_Repo/config.yaml')
    
    with open(config_path, 'r') as f:
        data = yaml.safe_load(f)
    
    return Config(
        database=DatabaseConfig(**data.get('database', {})),
        api=APIConfig(**data.get('api', {})),
        redis=RedisConfig(**data.get('redis', {})),
        auth=AuthConfig(**data.get('auth', {}))
    )
