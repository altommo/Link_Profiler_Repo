import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
import time # Import time for monotonic clock
import asyncio # Import asyncio
import random # For simulating ML model output
from collections import deque # For tracking recent performance

from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager, CircuitBreakerState # Import CircuitBreakerState

logger = logging.getLogger(__name__)

class SimpleMLPredictor:
    """
    A placeholder for a simple Machine Learning model that predicts API call value/cost.
    In a real scenario, this would be a trained model (e.g., scikit-learn, TensorFlow).
    For now, it provides a simulated prediction based on input features.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".SimpleMLPredictor")
        self.logger.info("SimpleMLPredictor initialized (placeholder for actual ML model).")

    def predict_value(self, features: Dict[str, Any]) -> float:
        """
        Simulates a prediction of the value/cost-effectiveness of an API call.
        Features might include: quality_score, success_rate, avg_response_time,
        remaining_quota, cost_per_unit, predicted_exhaustion_date.
        
        Returns a score where higher is better (more cost-effective/valuable).
        """
        # This is a very simplistic, rule-based "prediction" for demonstration.
        # A real ML model would learn these relationships from data.
        
        score = 0.0
        
        # Prioritize quality and success
        score += features.get('quality_score', 0) * 0.5
        score += features.get('success_rate', 0.0) * 10
        
        # Penalize high response time
        if features.get('avg_response_time', 0) > 500:
            score -= (features['avg_response_time'] / 500) * 0.1
            
        # Reward remaining quota, penalize cost
        if features.get('remaining_quota') is not None:
            score += min(features['remaining_quota'] / 100, 10) # Cap reward
        score -= features.get('cost_per_unit', 0) * 5
        
        # Add some randomness to simulate model variability
        score += random.uniform(-0.5, 0.5)
        
        self.logger.debug(f"ML Predictor input: {features}, Predicted Score: {score:.2f}")
        return score

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

        self.ml_predictor = SimpleMLPredictor() # Initialize the ML predictor
        self.ml_enabled_for_routing = config.get("api_routing.ml_enabled", False) # New config flag
        self.recent_calls_window_size = config.get("api_routing.recent_calls_window_size", 50) # Number of recent calls to track for dynamic weighting

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
                    'usage_history': [], # To store (timestamp, usage_delta) for burn rate calculation
                    'recent_calls': deque(maxlen=self.recent_calls_window_size) # Store (success, response_time_ms)
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

    def record_api_performance(self, api_name: str, success: bool, response_time_ms: float, query_type: Optional[str] = None, strategy_used: Optional[str] = None):
        """
        Records performance metrics for an API call.
        Also collects data for ML model training.
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
        
        # Store recent call for dynamic weighting
        perf['recent_calls'].append((success, response_time_ms))

        self.logger.debug(f"API {api_name} performance: Success Rate={perf['success_rate']:.2f}, Avg Response Time={perf['average_response_time_ms']:.2f}ms")

        # Collect data point for ML model training
        # In a real system, this would be persisted to a database or data lake
        data_point = {
            "timestamp": datetime.utcnow().isoformat(),
            "api_name": api_name,
            "query_type": query_type,
            "strategy_used": strategy_used,
            "success": success,
            "response_time_ms": response_time_ms,
            "quality_score": self.quotas[api_name]['quality_score'],
            "cost_per_unit": self.quotas[api_name]['cost_per_unit'],
            "remaining_quota": self.get_remaining_quota(api_name),
            "predicted_exhaustion_date": self.predict_exhaustion_date(api_name).isoformat() if self.predict_exhaustion_date(api_name) else None,
            "circuit_breaker_state": (asyncio.run(self.resilience_manager.get_circuit_breaker(api_name).get_status()))['state'].value # Sync call for logging
        }
        self.logger.debug(f"ML Data Point: {data_point}")
        # Here you would typically save data_point to a persistent store (e.g., ClickHouse, S3, PostgreSQL)
        # For this exercise, we'll just log it.


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
                    'usage_history': [],
                    'recent_calls': deque(maxlen=self.recent_calls_window_size)
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

    async def _calculate_api_score(self, api_name: str, strategy: str = 'best_quality', ml_enabled: bool = False) -> float:
        """
        Calculates a composite score for an API based on the chosen strategy and current metrics.
        This acts as the "decision tree" or "ML-like algorithm".
        """
        quota_data = self.quotas[api_name]
        perf_data = self._api_performance.get(api_name, {})

        quality = quota_data.get('quality_score', 0)
        cost_per_unit = quota_data.get('cost_per_unit', float('inf'))
        
        success_rate = perf_data.get('success_rate', 0.0)
        avg_response_time = perf_data.get('average_response_time_ms', float('inf'))
        
        remaining = self.get_remaining_quota(api_name)
        remaining_val = float('inf') if remaining is None else remaining

        predicted_exhaustion = self.predict_exhaustion_date(api_name)

        # Circuit Breaker Penalty
        cb = self.resilience_manager.get_circuit_breaker(api_name)
        cb_status = await cb.get_status()
        cb_penalty = 0
        if cb_status['state'] == CircuitBreakerState.HALF_OPEN:
            cb_penalty = self.weights['half_open_penalty']
        elif cb_status['state'] == CircuitBreakerState.OPEN:
            cb_penalty = -float('inf') # Should be filtered out by get_available_apis, but defensive

        # Dynamic Performance Adjustment (Advanced Decision Tree / Real-time Performance Monitoring)
        recent_calls = perf_data.get('recent_calls', deque())
        dynamic_performance_adjustment = 0
        if len(recent_calls) >= 5: # Need at least 5 recent calls to make a judgment
            recent_successes = sum(1 for s, _ in recent_calls if s)
            recent_failures = len(recent_calls) - recent_successes
            recent_avg_response_time = sum(rt for _, rt in recent_calls) / len(recent_calls)

            # If recent success rate is significantly lower than overall, penalize
            if recent_successes / len(recent_calls) < success_rate * 0.9: # 10% drop
                dynamic_performance_adjustment += (recent_successes / len(recent_calls) - success_rate) * self.weights['success_rate'] * 0.5 # Half the normal weight

            # If recent response time is significantly higher than overall, penalize
            if recent_avg_response_time > avg_response_time * 1.1: # 10% increase
                dynamic_performance_adjustment += (recent_avg_response_time / self.performance_thresholds['high_response_time_ms']) * self.weights['response_time'] * 0.5 # Half the normal weight
        
        # Performance Penalty (based on overall performance)
        performance_penalty = 0
        if success_rate < self.performance_thresholds['low_success_rate']:
            performance_penalty += (success_rate - self.performance_thresholds['low_success_rate']) * self.weights['success_rate'] # Negative penalty
        if avg_response_time > self.performance_thresholds['high_response_time_ms']:
            performance_penalty += (avg_response_time / self.performance_thresholds['high_response_time_ms']) * self.weights['response_time'] # Negative penalty

        # Exhaustion Penalty
        exhaustion_penalty = 0
        if predicted_exhaustion:
            time_to_exhaustion = (predicted_exhaustion - datetime.now()).total_seconds()
            if time_to_exhaustion < 0: # Already exhausted
                exhaustion_penalty = -float('inf')
            elif time_to_exhaustion < timedelta(days=1).total_seconds(): # Less than 1 day
                exhaustion_penalty = self.weights['exhaustion_penalty_factor'] * 100 # Very high penalty
            elif time_to_exhaustion < timedelta(days=self.exhaustion_warning_days).total_seconds(): # Within warning days
                exhaustion_penalty = self.weights['exhaustion_penalty_factor'] * (1 - (time_to_exhaustion / timedelta(days=self.exhaustion_warning_days).total_seconds())) # Scale penalty

        # ML Model Integration
        ml_score = 0.0
        if ml_enabled:
            features = {
                'quality_score': quality,
                'success_rate': success_rate,
                'avg_response_time': avg_response_time,
                'remaining_quota': remaining_val,
                'cost_per_unit': cost_per_unit,
                'time_to_exhaustion_seconds': time_to_exhaustion if predicted_exhaustion else float('inf'),
                'circuit_breaker_state': cb_status['state'].value
            }
            ml_score = self.ml_predictor.predict_value(features)
            self.logger.debug(f"API {api_name} ML Score: {ml_score:.2f}")

        # Combine factors based on strategy
        score = 0.0
        if strategy == 'best_quality':
            score = (quality * self.weights['quality'] + 
                     success_rate * self.weights['success_rate'] + 
                     remaining_val * self.weights['remaining_quota'] + 
                     avg_response_time * self.weights['response_time'] + 
                     performance_penalty + cb_penalty + dynamic_performance_adjustment)
        elif strategy == 'quota_optimized':
            if ml_enabled:
                # When ML is enabled for quota optimization, its prediction heavily influences the score
                score = ml_score * 1000000 # Scale ML score to be dominant
            else:
                score = (remaining_val * self.weights['remaining_quota'] + 
                         cost_per_unit * self.weights['cost_per_unit'] + 
                         success_rate * self.weights['success_rate'] + 
                         avg_response_time * self.weights['response_time'] + 
                         exhaustion_penalty + performance_penalty + cb_penalty + dynamic_performance_adjustment)
        else: # Default or custom strategy
            score = (quality * self.weights['quality'] + 
                     remaining_val * self.weights['remaining_quota'] - 
                     cost_per_unit * self.weights['cost_per_unit'] + 
                     success_rate * self.weights['success_rate'] + 
                     avg_response_time * self.weights['response_time'] + 
                     exhaustion_penalty + performance_penalty + cb_penalty + dynamic_performance_adjustment)
        
        return score

    async def get_best_quality_api(self, query_type: Optional[str] = None, ml_enabled: bool = False) -> Optional[str]:
        """
        Returns the highest quality API with available quota for a given query type.
        Prioritizes quality, then success rate, then remaining quota, then response time.
        Considers circuit breaker state.
        """
        available_apis = await self.get_available_apis(query_type) # Await this call
        if not available_apis:
            return None
        
        # Sort asynchronously using the _calculate_api_score with 'best_quality' strategy
        scored_apis = await asyncio.gather(*[self._calculate_api_score(api_name, 'best_quality', ml_enabled) for api_name in available_apis])
        sorted_apis_with_scores = sorted(zip(available_apis, scored_apis), key=lambda x: x[1], reverse=True)

        return sorted_apis_with_scores[0][0] if sorted_apis_with_scores else None

    async def get_quota_optimized_api(self, query_type: Optional[str] = None, ml_enabled: bool = False) -> Optional[str]:
        """
        Returns an API that optimizes for remaining free tier quota,
        prioritizing those with more remaining quota or lower cost, also considering performance and predicted exhaustion.
        Considers circuit breaker state.
        """
        available_apis = await self.get_available_apis(query_type) # Await this call
        if not available_apis:
            return None

        # Sort asynchronously using the _calculate_api_score with 'quota_optimized' strategy
        scored_apis = await asyncio.gather(*[self._calculate_api_score(api_name, 'quota_optimized', ml_enabled) for api_name in available_apis])
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
