import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import time # Import time for monotonic clock
import asyncio # Import asyncio

from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager, CircuitBreakerState # Import CircuitBreakerState

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

    def __init__(self, config: Dict[str, Any], resilience_manager: DistributedResilienceManager):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".APIQuotaManager")
        self.quotas: Dict[str, Dict[str, Any]] = {}
        self._api_performance: Dict[str, Dict[str, Any]] = {} # Stores performance metrics
        self.resilience_manager = resilience_manager # Store the resilience manager
        self._load_api_configs(config)

        # Configurable weights and thresholds for API selection logic
        self.weights = {
            'quality': 1000000,          # High weight for inherent quality
            'success_rate': 100000,      # Significant weight for recent success
            'response_time': -1,         # Negative weight as lower is better
            'remaining_quota': 1,        # Linear weight for remaining quota
            'cost_per_unit': -1000,      # Negative weight as lower cost is better
            'exhaustion_penalty_factor': -10000, # Base penalty for predicted exhaustion
            'half_open_penalty': -50000  # Penalty for half-open state
        }
        self.performance_thresholds = {
            'low_success_rate': 0.9,     # Threshold below which success rate is penalized
            'high_response_time_ms': 1000 # Threshold above which response time is penalized
        }
        self.exhaustion_warning_days = 7 # Days until exhaustion to start applying heavy penalty

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
                # Initialize performance metrics for each API
                self._api_performance[api_name] = {
                    'total_calls': 0,
                    'successful_calls': 0,
                    'total_response_time_ms': 0.0,
                    'average_response_time_ms': 0.0,
                    'success_rate': 1.0, # Start with 100% success
                    'usage_history': [] # To store (timestamp, usage_delta) for burn rate calculation
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
            # Record usage for burn rate calculation
            if api_name in self._api_performance:
                self._api_performance[api_name]['usage_history'].append((now, amount))
                # Keep history manageable, e.g., last 24 hours or 1000 entries
                self._api_performance[api_name]['usage_history'] = [
                    (ts, amt) for ts, amt in self._api_performance[api_name]['usage_history']
                    if now - ts < timedelta(hours=24)
                ]
            self.logger.debug(f"API {api_name} usage: {self.quotas[api_name]['used']}/{self.quotas[api_name]['limit']}")
        else:
            self.logger.warning(f"Attempted to record usage for unknown API: {api_name}")

    def record_api_performance(self, api_name: str, success: bool, response_time_ms: float):
        """
        Records performance metrics for an API call.
        """
        if api_name not in self._api_performance:
            self.logger.warning(f"Attempted to record performance for unknown API: {api_name}")
            return

        perf = self._api_performance[api_name]
        perf['total_calls'] += 1
        perf['total_response_time_ms'] += response_time_ms
        if success:
            perf['successful_calls'] += 1

        perf['average_response_time_ms'] = perf['total_response_time_ms'] / perf['total_calls'] if perf['total_calls'] > 0 else 0.0
        perf['success_rate'] = perf['successful_calls'] / perf['total_calls'] if perf['total_calls'] > 0 else 0.0
        self.logger.debug(f"API {api_name} performance: Success Rate={perf['success_rate']:.2f}, Avg Response Time={perf['average_response_time_ms']:.2f}ms")


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
            # Optionally reset performance metrics on quota reset
            if api_name in self._api_performance:
                self._api_performance[api_name] = {
                    'total_calls': 0,
                    'successful_calls': 0,
                    'total_response_time_ms': 0.0,
                    'average_response_time_ms': 0.0,
                    'success_rate': 1.0,
                    'usage_history': []
                }

    def _calculate_burn_rate(self, api_name: str) -> float:
        """
        Calculates the average burn rate (units per hour) for an API
        based on its recent usage history.
        """
        if api_name not in self._api_performance or not self._api_performance[api_name]['usage_history']:
            return 0.0 # No history, no burn rate

        history = self._api_performance[api_name]['usage_history']
        
        # Get the total usage and time span from the history
        total_usage = sum(amount for _, amount in history)
        
        # Calculate time span from oldest to newest entry
        oldest_timestamp = history[0][0]
        newest_timestamp = history[-1][0]
        
        time_span_hours = (newest_timestamp - oldest_timestamp).total_seconds() / 3600
        
        if time_span_hours > 0:
            return total_usage / time_span_hours
        return 0.0

    def predict_exhaustion_date(self, api_name: str) -> Optional[datetime]:
        """
        Predicts the date when an API's quota will be exhausted.
        Returns None if unlimited, no usage, or burn rate is zero.
        """
        remaining_quota = self.get_remaining_quota(api_name)
        if remaining_quota is None or remaining_quota <= 0:
            return None # Unlimited or already exhausted

        burn_rate_per_hour = self._calculate_burn_rate(api_name)
        if burn_rate_per_hour <= 0:
            return None # No usage or no burn rate

        hours_to_exhaustion = remaining_quota / burn_rate_per_hour
        return datetime.now() + timedelta(hours=hours_to_exhaustion)


    async def get_available_apis(self, query_type: Optional[str] = None) -> List[str]:
        """
        Returns a list of APIs that are enabled, have an API key, and have remaining quota.
        Optionally filters by supported query type and excludes APIs with open circuit breakers.
        """
        available = []
        for api_name, data in self.quotas.items():
            remaining = self.get_remaining_quota(api_name)
            
            # Check circuit breaker state
            cb = self.resilience_manager.get_circuit_breaker(api_name)
            cb_status = await cb.get_status()
            
            if cb_status['state'] == CircuitBreakerState.OPEN:
                self.logger.debug(f"API {api_name} circuit breaker is OPEN. Excluding from available APIs.")
                continue # Exclude APIs with open circuit breakers

            if remaining is None or remaining > 0: # Unlimited or has quota left
                if query_type is None or query_type in data.get('supported_query_types', []):
                    available.append(api_name)
        return available

    async def get_best_quality_api(self, query_type: Optional[str] = None) -> Optional[str]:
        """
        Returns the highest quality API with available quota for a given query type.
        Prioritizes quality, then success rate, then remaining quota, then response time.
        Considers circuit breaker state.
        """
        available_apis = await self.get_available_apis(query_type) # Await this call
        if not available_apis:
            return None
        
        async def sort_key_async(api_name):
            quota_data = self.quotas[api_name]
            perf_data = self._api_performance.get(api_name, {})
            
            quality = quota_data.get('quality_score', 0)
            success_rate = perf_data.get('success_rate', 0.0)
            avg_response_time = perf_data.get('average_response_time_ms', float('inf')) # Lower is better
            remaining = self.get_remaining_quota(api_name)
            remaining_val = float('inf') if remaining is None else remaining # Higher is better

            # Get circuit breaker state
            cb = self.resilience_manager.get_circuit_breaker(api_name)
            cb_status = await cb.get_status()
            
            # Penalize APIs based on circuit breaker state
            cb_penalty = 0
            if cb_status['state'] == CircuitBreakerState.HALF_OPEN:
                cb_penalty = self.weights['half_open_penalty'] # Significant penalty for half-open (being tested)
            elif cb_status['state'] == CircuitBreakerState.OPEN:
                cb_penalty = -float('inf') # Should already be filtered by get_available_apis, but double-check

            # Penalize low success rate and high response time
            performance_penalty = 0
            if success_rate < self.performance_thresholds['low_success_rate']:
                performance_penalty += (success_rate - self.performance_thresholds['low_success_rate']) * self.weights['success_rate'] # Negative penalty
            if avg_response_time > self.performance_thresholds['high_response_time_ms']:
                performance_penalty += (avg_response_time / self.performance_thresholds['high_response_time_ms']) * self.weights['response_time'] # Negative penalty

            # Combine all factors into a single score
            score = (quality * self.weights['quality'] + 
                     success_rate * self.weights['success_rate'] + 
                     remaining_val * self.weights['remaining_quota'] + 
                     avg_response_time * self.weights['response_time'] + 
                     performance_penalty + cb_penalty)
            return score

        # Sort asynchronously
        scored_apis = await asyncio.gather(*[sort_key_async(api_name) for api_name in available_apis])
        sorted_apis_with_scores = sorted(zip(available_apis, scored_apis), key=lambda x: x[1], reverse=True)

        return sorted_apis_with_scores[0][0] if sorted_apis_with_scores else None

    async def get_quota_optimized_api(self, query_type: Optional[str] = None) -> Optional[str]:
        """
        Returns an API that optimizes for remaining free tier quota,
        prioritizing those with more remaining quota or lower cost, also considering performance and predicted exhaustion.
        Considers circuit breaker state.
        """
        available_apis = await self.get_available_apis(query_type) # Await this call
        if not available_apis:
            return None

        async def sort_key_async(api_name):
            quota_data = self.quotas[api_name]
            perf_data = self._api_performance.get(api_name, {})

            remaining = self.get_remaining_quota(api_name)
            remaining_val = float('inf') if remaining is None else remaining # Higher is better
            cost_per_unit = quota_data.get('cost_per_unit', float('inf')) # Lower is better
            success_rate = perf_data.get('success_rate', 0.0) # Higher is better
            avg_response_time = perf_data.get('average_response_time_ms', float('inf')) # Lower is better
            
            # Get circuit breaker state
            cb = self.resilience_manager.get_circuit_breaker(api_name)
            cb_status = await cb.get_status()

            # Penalize APIs based on circuit breaker state
            cb_penalty = 0
            if cb_status['state'] == CircuitBreakerState.HALF_OPEN:
                cb_penalty = self.weights['half_open_penalty'] # Significant penalty for half-open (being tested)
            elif cb_status['state'] == CircuitBreakerState.OPEN:
                cb_penalty = -float('inf') # Should already be filtered by get_available_apis, but double-check
            
            # Predictive exhaustion: prioritize APIs that are NOT predicted to run out soon
            predicted_exhaustion = self.predict_exhaustion_date(api_name)
            
            # Dynamic exhaustion penalty: more severe as exhaustion date gets closer
            exhaustion_penalty = 0
            if predicted_exhaustion:
                time_to_exhaustion = (predicted_exhaustion - datetime.now()).total_seconds()
                if time_to_exhaustion < 0: # Already exhausted
                    exhaustion_penalty = -float('inf')
                elif time_to_exhaustion < timedelta(days=1).total_seconds(): # Less than 1 day
                    exhaustion_penalty = self.weights['exhaustion_penalty_factor'] * 100 # Very high penalty
                elif time_to_exhaustion < timedelta(days=self.exhaustion_warning_days).total_seconds(): # Within warning days
                    exhaustion_penalty = self.weights['exhaustion_penalty_factor'] * (1 - (time_to_exhaustion / timedelta(days=self.exhaustion_warning_days).total_seconds())) # Scale penalty

            # Penalize low success rate and high response time
            performance_penalty = 0
            if success_rate < self.performance_thresholds['low_success_rate']:
                performance_penalty += (success_rate - self.performance_thresholds['low_success_rate']) * self.weights['success_rate'] # Negative penalty
            if avg_response_time > self.performance_thresholds['high_response_time_ms']:
                performance_penalty += (avg_response_time / self.performance_thresholds['high_response_time_ms']) * self.weights['response_time'] # Negative penalty

            # Combine all factors into a single score
            score = (remaining_val * self.weights['remaining_quota'] + 
                     cost_per_unit * self.weights['cost_per_unit'] + 
                     success_rate * self.weights['success_rate'] + 
                     avg_response_time * self.weights['response_time'] + 
                     exhaustion_penalty + performance_penalty + cb_penalty)
            return score

        # Sort asynchronously
        scored_apis = await asyncio.gather(*[sort_key_async(api_name) for api_name in available_apis])
        sorted_apis_with_scores = sorted(zip(available_apis, scored_apis), key=lambda x: x[1], reverse=True)

        return sorted_apis_with_scores[0][0] if sorted_apis_with_scores else None

    async def get_any_available_api(self, query_type: Optional[str] = None) -> Optional[str]:
        """
        Returns the first available API for a given query type, ignoring quality/cost.
        Useful as a last-resort fallback.
        """
        available_apis = await self.get_available_apis(query_type)
        if available_apis:
            return available_apis[0]
        return None

    async def get_api_status(self) -> Dict[str, Any]:
        """Returns a summary of all API statuses including performance metrics and predicted exhaustion."""
        status = {}
        for api_name, data in self.quotas.items():
            limit = data['limit']
            used = data['used']
            remaining = self.get_remaining_quota(api_name)
            percentage_used = (used / limit * 100) if limit > 0 else 0

            perf_data = self._api_performance.get(api_name, {})
            predicted_exhaustion = self.predict_exhaustion_date(api_name)

            # Get circuit breaker state
            cb = self.resilience_manager.get_circuit_breaker(api_name)
            cb_status = await cb.get_status()

            status[api_name] = {
                'limit': limit,
                'used': used,
                'remaining': remaining,
                'reset_day_of_month': data['reset_day_of_month'],
                'last_reset_date': data['last_reset_date'].isoformat(),
                'quality_score': data['quality_score'],
                'supported_query_types': data['supported_query_types'],
                'cost_per_unit': data['cost_per_unit'],
                'percentage_used': percentage_used,
                'performance': {
                    'total_calls': perf_data.get('total_calls', 0),
                    'successful_calls': perf_data.get('successful_calls', 0),
                    'average_response_time_ms': perf_data.get('average_response_time_ms', 0.0),
                    'success_rate': perf_data.get('success_rate', 0.0),
                    'circuit_breaker_state': cb_status['state'].value # Add CB state here
                },
                'predicted_exhaustion_date': predicted_exhaustion.isoformat() if predicted_exhaustion else None
            }
        return status
