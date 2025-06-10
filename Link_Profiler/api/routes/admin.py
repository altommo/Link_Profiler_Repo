from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from Link_Profiler.api.schemas import ApiKeyInfo
from Link_Profiler.config.config_loader import config_loader # Import the config_loader singleton

# Assuming you have a dependency for authentication/authorization
# from Link_Profiler.auth.dependencies import get_current_admin_user

router = APIRouter()

def _load_api_key_configs() -> Dict[str, Dict[str, Any]]:
    """
    Loads API key configurations from the ConfigLoader.
    """
    # The 'external_apis' section in your config_loader is expected to hold API key details.
    # Example structure in external_apis.yaml or environment variables:
    # external_apis:
    #   google_maps:
    #     key: "sk-google-maps-..."
    #     enabled: true
    #     monthly_limit: 100000
    #     cost_per_unit: 0.005
    #   openai:
    #     key: "sk-openai-..."
    #     enabled: false
    #     monthly_limit: -1
    #     cost_per_unit: 0.02
    
    all_api_configs = config_loader.get("external_apis", {})
    
    # Filter and format the API keys for the frontend display
    formatted_keys = {}
    for api_name, api_data in all_api_configs.items():
        if isinstance(api_data, dict): # Ensure it's a dictionary
            formatted_keys[api_name] = {
                "key": api_data.get("key", ""),
                "enabled": api_data.get("enabled", False),
                "monthly_limit": api_data.get("monthly_limit", 0),
                "cost_per_unit": api_data.get("cost_per_unit", 0.0)
            }
    return formatted_keys

@router.get("/admin/api_keys", response_model=List[ApiKeyInfo])
async def get_api_keys(
    # Add dependency for admin authentication if needed, e.g.:
    # current_user: Any = Depends(get_current_admin_user)
):
    """
    Retrieves a list of configured API keys with masked values.
    Requires administrator privileges.
    """
    api_key_configs = _load_api_key_configs()
    api_keys_info: List[ApiKeyInfo] = []

    for api_name, config in api_key_configs.items():
        # Mask the API key for security
        full_key = config.get("key", "")
        masked_key = f"{full_key[:6]}...{full_key[-4:]}" if len(full_key) > 10 else "********"

        api_keys_info.append(
            ApiKeyInfo(
                api_name=api_name,
                enabled=config.get("enabled", False),
                api_key_masked=masked_key,
                monthly_limit=config.get("monthly_limit", 0),
                cost_per_unit=config.get("cost_per_unit", 0.0)
            )
        )
    return api_keys_info

@router.post("/admin/api_keys/{api_name}/update")
async def update_api_key(
    api_name: str,
    # Add dependency for admin authentication if needed, e.g.:
    # current_user: Any = Depends(get_current_admin_user),
    new_key_data: Dict[str, str] # Expects {"new_key": "..."}
):
    """
    Updates a specific API key.
    Requires administrator privileges.
    """
    # In a real application, you would update the actual configuration source here.
    # For demonstration, we'll just acknowledge the update.
    # You should also validate the new_key and handle persistence.
    
    # Check if the API name exists in the current configuration
    if not config_loader.get(f"external_apis.{api_name}"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"API key '{api_name}' not found in configuration.")

    new_key_value = new_key_data.get("new_key")
    if not new_key_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="'new_key' field is required.")

    # Here you would call a service or config manager to securely update the key
    # For a persistent change, you would need to write this back to the configuration file
    # or a secrets management system. ConfigLoader currently only reads.
    # Example: config_loader.set(f"external_apis.{api_name}.key", new_key_value)
    # This would update the in-memory config, but not persist it.
    
    print(f"Simulating update for API key '{api_name}' with new key: {new_key_value}")
    
    return {"message": f"API key for {api_name} updated successfully (simulated)."}

