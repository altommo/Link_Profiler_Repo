import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import random # For simulation
import math # For ceiling

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.monitoring.prometheus_metrics import (
    API_QUOTA_LIMIT_GAUGE, API_QUOTA_USED_GAUGE, API_QUOTA_REMAINING_GAUGE, API_QUOTA_PERCENTAGE_USED_GAUGE
)

logger = logging.getLogger(__name__)

class APIQuotaManagerService:
    """
    Manages and optimizes external API usage, tracking quotas and predicting exhaustion.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(APIQuotaManagerService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".APIQuotaManagerService")
        self.enabled = config_loader.get("api_quota_manager.enabled", False)
        self.quotas_config = config_loader.get("api_quota_manager.quotas", {})
        
        # Internal state to track current usage (for simulation/mocking purposes)
        # In a real system, this would be persisted (e.g., in Redis or DB)
        # and updated by the API clients themselves.
        self._current_usage: Dict[str, Dict[str, Any]] = {}
        self._initialize_quotas()

        if not self.enabled:
            self.logger.info("API Quota Manager Service is disabled by configuration.")

    def _initialize_quotas(self):
        """Initializes the internal quota tracking from config."""
        for api_name, config in self.quotas_config.items():
            self._current_usage[api_name] = {
                "limit": config.get("limit", 0),
                "used": 0, # This would be loaded from persistence in a real system
                "reset_day_of_month": config.get("reset_day_of_month", 1),
                "last_reset_date": self._get_last_reset_date(api_name, config.get("reset_day_of_month", 1))
            }
            # Set initial Prometheus gauges
            API_QUOTA_LIMIT_GAUGE.labels(api_name=api_name).set(config.get("limit", 0))

    def _get_last_reset_date(self, api_name: str, reset_day: int) -> datetime:
        """Calculates the last reset date for a given API."""
        now = datetime.now()
        if now.day >= reset_day:
            # Reset happened this month
            return now.replace(day=reset_day, hour=0, minute=0, second=0, microsecond=0)
        else:
            # Reset happened last month
            # Handle January correctly
            if now.month == 1:
                return now.replace(year=now.year - 1, month=12, day=reset_day, hour=0, minute=0, second=0, microsecond=0)
            else:
                return now.replace(month=now.month - 1, day=reset_day, hour=0, minute=0, second=0, microsecond=0)

    def _days_into_current_period(self, api_name: str) -> int:
        """Calculates how many days into the current billing period."""
        now = datetime.now()
        last_reset = self._current_usage[api_name]["last_reset_date"]
        return (now - last_reset).days + 1 # +1 to include current day

    def _days_remaining_in_current_period(self, api_name: str) -> int:
        """Calculates how many days remaining in the current billing period."""
        now = datetime.now()
        reset_day = self._current_usage[api_name]["reset_day_of_month"]
        
        # Calculate next reset date
        if now.day < reset_day:
            next_reset = now.replace(day=reset_day, hour=0, minute=0, second=0, microsecond=0)
        else:
            # Next month's reset day
            if now.month == 12:
                next_reset = now.replace(year=now.year + 1, month=1, day=reset_day, hour=0, minute=0, second=0, microsecond=0)
            else:
                next_reset = now.replace(month=now.month + 1, day=reset_day, hour=0, minute=0, second=0, microsecond=0)
        
        return (next_reset - now).days # Days remaining

    def increment_usage(self, api_name: str, amount: int = 1):
        """Increments the usage for a given API."""
        if not self.enabled or api_name not in self._current_usage:
            return

        # In a real system, this would be an atomic operation on a persistent store (e.g., Redis INCR)
        self._current_usage[api_name]["used"] += amount
        self.logger.debug(f"Incremented usage for {api_name} by {amount}. New usage: {self._current_usage[api_name]['used']}")

    async def get_all_api_quota_statuses(self) -> List[Dict[str, Any]]:
        """Returns the current status for all managed APIs."""
        statuses: List[Dict[str, Any]] = []
        for api_name, data in self._current_usage.items():
            limit = data["limit"]
            used = data["used"]
            remaining = limit - used
            percentage_used = (used / limit * 100) if limit > 0 else 0
            
            status_str = "OK"
            if percentage_used >= 90:
                status_str = "Critical"
            elif percentage_used >= 75:
                status_str = "Warning"
            elif percentage_used >= 50:
                status_str = "High Usage"

            predicted_exhaustion_date = None
            recommended_action = None

            if used > 0: # Only predict if there's some usage
                days_into_period = self._days_into_current_period(api_name)
                daily_usage_rate = used / days_into_period
                
                if daily_usage_rate > 0:
                    remaining_quota_days = remaining / daily_usage_rate
                    predicted_exhaustion_date = datetime.now() + timedelta(days=remaining_quota_days)
                    
                    if predicted_exhaustion_date < datetime.now() + timedelta(days=self._days_remaining_in_current_period(api_name)):
                        recommended_action = "Reduce usage or consider upgrading plan."
                    elif percentage_used >= 75:
                        recommended_action = "Monitor closely, consider alternative APIs."

            statuses.append({
                "api_name": api_name,
                "limit": limit,
                "used": used,
                "remaining": remaining,
                "reset_date": data["last_reset_date"] + timedelta(days=self._days_remaining_in_current_period(api_name) + 1), # Next reset date
                "percentage_used": round(percentage_used, 2),
                "status": status_str,
                "predicted_exhaustion_date": predicted_exhaustion_date,
                "recommended_action": recommended_action
            })

            # Update Prometheus gauges
            API_QUOTA_USED_GAUGE.labels(api_name=api_name).set(used)
            API_QUOTA_REMAINING_GAUGE.labels(api_name=api_name).set(remaining)
            API_QUOTA_PERCENTAGE_USED_GAUGE.labels(api_name=api_name).set(percentage_used)

        return statuses

    async def optimize_api_call(self, query_type: str, priority: str) -> Optional[str]:
        """
        Routes API calls to maximize free tier usage across providers.
        This is a placeholder for a more complex routing logic.
        """
        if not self.enabled:
            self.logger.warning("API Quota Manager is disabled. No API optimization will occur.")
            return None # Or return a default API name

        # This logic would be highly specific to your API clients and their capabilities.
        # For demonstration, we'll pick a random API that's not exhausted.
        available_apis = [
            api_name for api_name, data in self._current_usage.items()
            if data["used"] < data["limit"]
        ]

        if not available_apis:
            self.logger.error("All configured APIs are exhausted.")
            return None

        # Simple optimization: prioritize based on remaining quota
        # High priority: pick the one with most remaining quota
        # Low priority: pick the one with least remaining quota (to burn through free tiers)
        if priority == 'high':
            best_api = max(available_apis, key=lambda api: self._current_usage[api]["limit"] - self._current_usage[api]["used"])
        else: # 'low' or default
            best_api = min(available_apis, key=lambda api: self._current_usage[api]["limit"] - self._current_usage[api]["used"])
        
        self.logger.info(f"Optimized API call for query_type '{query_type}' with priority '{priority}'. Selected: {best_api}")
        return best_api

# Singleton instance
api_quota_manager_service = APIQuotaManagerService()
