import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class APIQuotaManager:
    """
    Manages and optimizes external API usage, especially for free tiers.
    Tracks usage, predicts exhaustion, and can suggest optimal routing.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(APIQuotaManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Dict[str, Any]):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".APIQuotaManager")
        self.quotas: Dict[str, Dict[str, Any]] = {}
        self._load_api_configs(config)
        self.logger.info("APIQuotaManager initialized.")

    def _load_api_configs(self, config: Dict[str, Any]):
        """Loads API configurations from the main config."""
        external_apis_config = config.get("external_apis", {})
        for api_name, api_settings in external_apis_config.items():
            # Only load if enabled and API key is present
            if api_settings.get("enabled", False) and api_settings.get("api_key"):
                self.quotas[api_name] = {
                    'limit': api_settings.get("monthly_limit", -1), # -1 for unlimited
                    'used': 0, # This would ideally be loaded from persistence (e.g., Redis/DB)
                    'reset_day_of_month': api_settings.get("reset_day_of_month", 1),
                    'last_reset_date': self._get_last_reset_date(api_settings.get("reset_day_of_month", 1)),
                    'cost_per_unit': api_settings.get("cost_per_unit", 0.0),
                    'quality_score': api_settings.get("quality_score", 3), # 1-5, 5 being best, default to 3
                    'supported_query_types': api_settings.get("supported_query_types", [])
                }
                self.logger.info(f"Loaded API quota for {api_name}: Limit={self.quotas[api_name]['limit']}, Reset Day={self.quotas[api_name]['reset_day_of_month']}, Quality={self.quotas[api_name]['quality_score']}")

    def _get_last_reset_date(self, reset_day_of_month: int) -> datetime:
        """Calculates the last reset date for a given reset day of the month."""
        now = datetime.now()
        if now.day >= reset_day_of_month:
            return now.replace(day=reset_day_of_month, hour=0, minute=0, second=0, microsecond=0)
        else:
            # If current day is before reset day, reset was last month
            last_month = now.replace(day=1) - timedelta(days=1)
            # Handle cases where reset_day_of_month might be greater than days in last_month
            try:
                return last_month.replace(day=reset_day_of_month, hour=0, minute=0, second=0, microsecond=0)
            except ValueError:
                # e.g., Feb 30th, set to last day of Feb
                return last_month.replace(day=self._last_day_of_month(last_month.year, last_month.month), hour=0, minute=0, second=0, microsecond=0)

    def _last_day_of_month(self, year: int, month: int) -> int:
        """Returns the last day of the given month and year."""
        if month == 12:
            return 31
        return (datetime(year, month + 1, 1) - timedelta(days=1)).day

    async def __aenter__(self):
        """Context manager entry point."""
        self.logger.info("APIQuotaManager entered context.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point."""
        self.logger.info("APIQuotaManager exited context.")

    def record_usage(self, api_name: str, amount: int = 1):
        """Records usage for a specific API."""
        if api_name in self.quotas:
            # Check if reset is needed
            # A simple check: if current date is past the reset day and last reset was in a previous month
            now = datetime.now()
            if now.day >= self.quotas[api_name]['reset_day_of_month'] and \
               now.month != self.quotas[api_name]['last_reset_date'].month:
                self.reset_quota(api_name)
            
            self.quotas[api_name]['used'] += amount
            self.logger.debug(f"API {api_name} usage: {self.quotas[api_name]['used']}/{self.quotas[api_name]['limit']}")
        else:
            self.logger.warning(f"Attempted to record usage for unknown API: {api_name}")

    def get_remaining_quota(self, api_name: str) -> Optional[int]:
        """Returns remaining quota for an API. Returns None for unlimited."""
        if api_name not in self.quotas:
            return 0 # Or raise error, depending on desired strictness
        limit = self.quotas[api_name]['limit']
        if limit == -1: # Unlimited
            return None
        return max(0, limit - self.quotas[api_name]['used'])

    def reset_quota(self, api_name: str):
        """Resets the quota for a specific API."""
        if api_name in self.quotas:
            self.quotas[api_name]['used'] = 0
            self.quotas[api_name]['last_reset_date'] = self._get_last_reset_date(self.quotas[api_name]['reset_day_of_month'])
            self.logger.info(f"Quota for {api_name} reset. New usage: {self.quotas[api_name]['used']}/{self.quotas[api_name]['limit']}")

    def get_available_apis(self, query_type: Optional[str] = None) -> List[str]:
        """
        Returns a list of APIs that are enabled, have an API key, and have remaining quota.
        Optionally filters by supported query type.
        """
        available = []
        for api_name, data in self.quotas.items():
            remaining = self.get_remaining_quota(api_name)
            if remaining is None or remaining > 0: # Unlimited or has quota left
                if query_type is None or query_type in data.get('supported_query_types', []):
                    available.append(api_name)
        return available

    def get_best_quality_api(self, query_type: Optional[str] = None) -> Optional[str]:
        """
        Returns the highest quality API with available quota for a given query type.
        Prioritizes quality, then remaining quota if quality is equal.
        """
        available_apis = self.get_available_apis(query_type)
        if not available_apis:
            return None
        
        # Sort by quality_score (descending), then by remaining quota (descending)
        # Remaining quota: None (unlimited) should be treated as highest
        def sort_key(api_name):
            data = self.quotas[api_name]
            remaining = self.get_remaining_quota(api_name)
            # Treat None (unlimited) as a very large number for sorting
            remaining_val = float('inf') if remaining is None else remaining
            return (data.get('quality_score', 0), remaining_val)

        sorted_apis = sorted(available_apis, key=sort_key, reverse=True)
        return sorted_apis[0] if sorted_apis else None

    def get_quota_optimized_api(self, query_type: Optional[str] = None) -> Optional[str]:
        """
        Returns an API that optimizes for remaining free tier quota,
        prioritizing those with more remaining quota or lower cost.
        """
        available_apis = self.get_available_apis(query_type)
        if not available_apis:
            return None

        # Sort by remaining quota (descending), then by cost_per_unit (ascending)
        # Remaining quota: None (unlimited) should be treated as highest
        def sort_key(api_name):
            data = self.quotas[api_name]
            remaining = self.get_remaining_quota(api_name)
            remaining_val = float('inf') if remaining is None else remaining
            return (remaining_val, data.get('cost_per_unit', 0.0))

        sorted_apis = sorted(available_apis, key=sort_key, reverse=True)
        return sorted_apis[0] if sorted_apis else None

    def get_api_status(self) -> Dict[str, Any]:
        """Returns a summary of all API statuses."""
        status = {}
        for api_name, data in self.quotas.items():
            limit = data['limit']
            used = data['used']
            remaining = self.get_remaining_quota(api_name)
            percentage_used = (used / limit * 100) if limit > 0 else 0

            status[api_name] = {
                'limit': limit,
                'used': used,
                'remaining': remaining,
                'reset_day_of_month': data['reset_day_of_month'],
                'last_reset_date': data['last_reset_date'].isoformat(),
                'quality_score': data['quality_score'],
                'supported_query_types': data['supported_query_types'],
                'cost_per_unit': data['cost_per_unit'],
                'percentage_used': percentage_used # Include percentage used for dashboard
            }
        return status
