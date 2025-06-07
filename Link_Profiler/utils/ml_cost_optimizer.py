import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class MLCostOptimizer:
    """
    A more sophisticated, rule-based "Machine Learning" model for predicting
    the value/cost-effectiveness of an API call. This is a deterministic
    model based on weighted features, serving as a placeholder for a
    true trained ML model.
    """
    def __init__(self, weights: Dict[str, float] = None):
        self.logger = logging.getLogger(__name__ + ".MLCostOptimizer")
        # Default weights, can be overridden by config
        self.weights = {
            'quality_score': 0.3,
            'success_rate': 0.4,
            'avg_response_time_ms': -0.001, # Negative weight: lower is better
            'remaining_quota_ratio': 0.2,
            'cost_per_unit': -0.1,       # Negative weight: lower is better
            'time_to_exhaustion_hours': 0.005, # Positive weight: longer is better
            'circuit_breaker_penalty': -100.0, # High penalty for open/half-open
            'dynamic_performance_adjustment': 0.1 # For real-time fluctuations
        }
        if weights:
            self.weights.update(weights)
        self.logger.info(f"MLCostOptimizer initialized with weights: {self.weights}")

    def predict_value(self, features: Dict[str, Any]) -> float:
        """
        Predicts a score representing the value/cost-effectiveness of an API call.
        Higher score indicates a more desirable API.

        Features expected:
        - 'quality_score': int (1-5)
        - 'success_rate': float (0.0-1.0)
        - 'avg_response_time_ms': float (milliseconds)
        - 'remaining_quota': Optional[int]
        - 'limit': Optional[int] (for calculating remaining_quota_ratio)
        - 'cost_per_unit': float
        - 'time_to_exhaustion_seconds': Optional[float]
        - 'circuit_breaker_state': str (e.g., "CLOSED", "HALF_OPEN", "OPEN")
        - 'dynamic_performance_adjustment': float (from APIQuotaManager's real-time analysis)
        """
        score = 0.0

        # Normalize and apply weights
        quality = features.get('quality_score', 0)
        score += quality * self.weights['quality_score']

        success_rate = features.get('success_rate', 0.0)
        score += success_rate * self.weights['success_rate']

        avg_response_time_ms = features.get('avg_response_time_ms', 0.0)
        score += avg_response_time_ms * self.weights['avg_response_time_ms']

        remaining_quota = features.get('remaining_quota')
        limit = features.get('limit')
        if remaining_quota is not None and limit is not None and limit > 0:
            remaining_quota_ratio = remaining_quota / limit
            score += remaining_quota_ratio * self.weights['remaining_quota_ratio']
        elif remaining_quota is None: # Unlimited quota
            score += 1.0 * self.weights['remaining_quota_ratio'] # Treat as full quota

        cost_per_unit = features.get('cost_per_unit', 0.0)
        score += cost_per_unit * self.weights['cost_per_unit']

        time_to_exhaustion_seconds = features.get('time_to_exhaustion_seconds')
        if time_to_exhaustion_seconds is not None and time_to_exhaustion_seconds > 0:
            time_to_exhaustion_hours = time_to_exhaustion_seconds / 3600
            score += time_to_exhaustion_hours * self.weights['time_to_exhaustion_hours']
        elif time_to_exhaustion_seconds is not None and time_to_exhaustion_seconds <= 0:
            score += -1000.0 # Heavy penalty if already exhausted

        circuit_breaker_state = features.get('circuit_breaker_state')
        if circuit_breaker_state == "OPEN" or circuit_breaker_state == "HALF_OPEN":
            score += self.weights['circuit_breaker_penalty']

        dynamic_performance_adjustment = features.get('dynamic_performance_adjustment', 0.0)
        score += dynamic_performance_adjustment * self.weights['dynamic_performance_adjustment']

        self.logger.debug(f"ML Predictor input: {features}, Predicted Score: {score:.2f}")
        return score
