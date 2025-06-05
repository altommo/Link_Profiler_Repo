import yaml
import os
from pathlib import Path

def split_config_file():
    """Split the large config.yaml into focused configuration files."""
    
    # Read the main config file
    config_path = Path("Link_Profiler/config/config.yaml")
    if not config_path.exists():
        print(f"Config file not found: {config_path}")
        return
    
    with open(config_path, 'r') as f:
        full_config = yaml.safe_load(f)
    
    # Define configuration splits
    config_splits = {
        'core.yaml': {
            'database': full_config.get('database', {}),
            'redis': full_config.get('redis', {}),
            'queue': full_config.get('queue', {}),
            'queue_system': full_config.get('queue_system', {})
        },
        'crawler.yaml': {
            'crawler': full_config.get('crawler', {}),
            'anti_detection': full_config.get('anti_detection', {}),
            'quality_assurance': full_config.get('quality_assurance', {}),
            'proxy': full_config.get('proxy', {}),
            'browser_crawler': full_config.get('browser_crawler', {}),
            'connection_optimization': full_config.get('connection_optimization', {}),
            'rate_limiting': full_config.get('rate_limiting', {}),
            'circuit_breaker': full_config.get('circuit_breaker', {}),
            'advanced_session_manager': full_config.get('advanced_session_manager', {})
        },
        'external_apis.yaml': {
            'api_cache': full_config.get('api_cache', {}),
            'domain_api': full_config.get('domain_api', {}),
            'backlink_api': full_config.get('backlink_api', {}),
            'serp_api': full_config.get('serp_api', {}),
            'serp_crawler': full_config.get('serp_crawler', {}),
            'keyword_api': full_config.get('keyword_api', {}),
            'ai': full_config.get('ai', {}),
            'technical_auditor': full_config.get('technical_auditor', {}),
            'social_media_crawler': full_config.get('social_media_crawler', {}),
            'web3_crawler': full_config.get('web3_crawler', {}),
            'historical_data': full_config.get('historical_data', {}),
            'local_seo': full_config.get('local_seo', {})
        },
        'security.yaml': {
            'auth': full_config.get('auth', {}),
            'system': full_config.get('system', {})
        },
        'monitoring.yaml': {
            'monitoring': full_config.get('monitoring', {}),
            'notifications': full_config.get('notifications', {}),
            'logging': full_config.get('logging', {})
        },
        'features.yaml': {
            'api': full_config.get('api', {}),
            'satellite': full_config.get('satellite', {})
        }
    }
    
    # Create config directory if it doesn't exist
    config_dir = Path("Link_Profiler/config")
    config_dir.mkdir(exist_ok=True)
    
    # Write split configuration files
    for filename, config_section in config_splits.items():
        file_path = config_dir / filename
        
        # Skip empty configurations
        if not any(config_section.values()):
            continue
        
        with open(file_path, 'w') as f:
            yaml.dump(config_section, f, default_flow_style=False, indent=2)
        
        print(f"Created: {file_path}")
    
    # Create backup of original config
    backup_path = config_dir / "config_original_backup.yaml"
    os.rename(config_path, backup_path)
    print(f"Original config backed up to: {backup_path}")
    
    print("Configuration split completed successfully!")

if __name__ == "__main__":
    split_config_file()
