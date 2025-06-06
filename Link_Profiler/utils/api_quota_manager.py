import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class APIQuotaManager:
    """Simple manager to track external API quotas."""

    def __init__(self, config: Dict[str, Any]):
        self.quotas: Dict[str, Dict[str, Any]] = {}
        self._load_config(config)

    def _load_config(self, config: Dict[str, Any]):
        apis = config.get("external_apis", {})
        for name, settings in apis.items():
            if settings.get("api_key"):
                self.quotas[name] = {
                    "limit": settings.get("monthly_limit", -1),
                    "used": 0,
                    "reset_day_of_month": settings.get("reset_day_of_month", 1),
                    "last_reset_date": self._calc_last_reset(settings.get("reset_day_of_month", 1)),
                }

    def _calc_last_reset(self, day: int) -> datetime:
        now = datetime.now()
        if now.day >= day:
            return now.replace(day=day, hour=0, minute=0, second=0, microsecond=0)
        last_month = (now.replace(day=1) - timedelta(days=1)).replace(day=day, hour=0, minute=0, second=0, microsecond=0)
        return last_month

    def record_usage(self, api_name: str, amount: int = 1) -> None:
        quota = self.quotas.get(api_name)
        if not quota:
            logger.warning("Unknown API %s", api_name)
            return
        if datetime.now() - quota["last_reset_date"] > timedelta(days=30):
            quota["used"] = 0
            quota["last_reset_date"] = self._calc_last_reset(quota["reset_day_of_month"])
        quota["used"] += amount

    def get_remaining(self, api_name: str) -> Optional[int]:
        quota = self.quotas.get(api_name)
        if not quota:
            return None
        limit = quota["limit"]
        return None if limit < 0 else max(0, limit - quota["used"])

    def get_api_status(self) -> Dict[str, Any]:
        status = {}
        for name, q in self.quotas.items():
            status[name] = {
                "limit": q["limit"],
                "used": q["used"],
                "remaining": self.get_remaining(name),
                "reset_day_of_month": q["reset_day_of_month"],
                "last_reset_date": q["last_reset_date"].isoformat(),
            }
        return status
