"""
Distributed Circuit Breaker Implementation for Crawler Resilience
Uses Redis to store and synchronize circuit breaker state across multiple instances.
"""

import asyncio
import time
import random
from enum import Enum
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import aiohttp
import redis.asyncio as redis
import json

from Link_Profiler.config.config_loader import config_loader

logger = logging.getLogger(__name__)

class CircuitBreakerState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered

@dataclass
class DistributedCircuitBreakerConfig:
    failure_threshold: int = 5           # Failures before opening
    recovery_timeout: int = 60           # Seconds before trying half-open
    success_threshold: int = 3           # Successes needed to close from half-open
    timeout_duration: int = 30           # Request timeout in seconds
    redis_key_prefix: str = "cb_state:" # Redis key prefix for circuit breaker states
    enabled: bool = False                # Whether distributed circuit breaker is enabled

class DistributedCircuitBreaker:
    def __init__(self, name: str, redis_client: redis.Redis, config: DistributedCircuitBreakerConfig):
        self.name = name
        self.redis = redis_client
        self.config = config
        self.key = f"{self.config.redis_key_prefix}{self.name}"
        self.logger = logging.getLogger(f"{__name__}.{name}")
        
        # Local cache to reduce Redis calls, but state is authoritative in Redis
        self._local_state: Dict[str, Any] = {}
        self._last_sync_time: float = 0.0
        self._sync_interval: float = 1.0 # How often to sync local cache with Redis

    async def _load_state(self) -> Dict[str, Any]:
        """Loads the circuit breaker state from Redis."""
        if time.time() - self._last_sync_time < self._sync_interval and self._local_state:
            return self._local_state

        state_json = await self.redis.get(self.key)
        if state_json:
            state = json.loads(state_json)
            self._local_state = state
            self._last_sync_time = time.time()
            return state
        return {
            "state": CircuitBreakerState.CLOSED.value,
            "failure_count": 0,
            "success_count": 0,
            "last_failure_time": 0.0,
            "next_attempt_time": 0.0
        }

    async def _save_state(self, state: Dict[str, Any]):
        """Saves the circuit breaker state to Redis."""
        self._local_state = state
        self._last_sync_time = time.time()
        await self.redis.set(self.key, json.dumps(state))

    async def can_execute(self) -> bool:
        """Checks if a request can be executed based on the distributed state."""
        if not self.config.enabled:
            return True # If distributed CB is disabled, always allow

        state_data = await self._load_state()
        current_state = CircuitBreakerState(state_data["state"])
        now = time.time()

        if current_state == CircuitBreakerState.CLOSED:
            return True
        elif current_state == CircuitBreakerState.OPEN:
            if state_data["next_attempt_time"] and now >= state_data["next_attempt_time"]:
                # Transition to HALF_OPEN
                state_data["state"] = CircuitBreakerState.HALF_OPEN.value
                state_data["success_count"] = 0 # Reset success count for half-open
                await self._save_state(state_data)
                self.logger.info(f"Circuit breaker {self.name} switching to HALF_OPEN")
                return True
            return False
        elif current_state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    async def record_success(self):
        """Records a successful execution."""
        if not self.config.enabled: return

        state_data = await self._load_state()
        current_state = CircuitBreakerState(state_data["state"])

        if current_state == CircuitBreakerState.HALF_OPEN:
            state_data["success_count"] += 1
            if state_data["success_count"] >= self.config.success_threshold:
                state_data["state"] = CircuitBreakerState.CLOSED.value
                state_data["failure_count"] = 0
                state_data["success_count"] = 0
                state_data["next_attempt_time"] = 0.0
                await self._save_state(state_data)
                self.logger.info(f"Circuit breaker {self.name} CLOSED - service recovered")
        elif current_state == CircuitBreakerState.CLOSED:
            # Gradually reduce failure count in CLOSED state
            state_data["failure_count"] = max(0, state_data["failure_count"] - 1)
            await self._save_state(state_data)
    
    async def record_failure(self):
        """Records a failed execution."""
        if not self.config.enabled: return

        state_data = await self._load_state()
        current_state = CircuitBreakerState(state_data["state"])
        now = time.time()

        state_data["failure_count"] += 1
        state_data["last_failure_time"] = now
        
        if current_state == CircuitBreakerState.CLOSED:
            if state_data["failure_count"] >= self.config.failure_threshold:
                state_data["state"] = CircuitBreakerState.OPEN.value
                state_data["next_attempt_time"] = now + self.config.recovery_timeout
                await self._save_state(state_data)
                self.logger.warning(f"Circuit breaker {self.name} OPENED after {state_data['failure_count']} failures")
        elif current_state == CircuitBreakerState.HALF_OPEN:
            state_data["state"] = CircuitBreakerState.OPEN.value
            state_data["next_attempt_time"] = now + self.config.recovery_timeout
            await self._save_state(state_data)
            self.logger.warning(f"Circuit breaker {self.name} OPENED from HALF_OPEN due to failure")

    async def get_status(self) -> Dict[str, Any]:
        """Returns the current status of the circuit breaker."""
        state_data = await self._load_state()
        return {
            "state": state_data["state"],
            "failure_count": state_data["failure_count"],
            "success_count": state_data["success_count"],
            "last_failure_time": state_data["last_failure_time"],
            "next_attempt_time": state_data["next_attempt_time"]
        }

class ExponentialBackoff:
    """Implements exponential backoff with jitter."""
    
    def __init__(self, initial_delay: float = 1.0, max_delay: float = 60.0, 
                 exponential_base: float = 2.0, jitter: bool = True):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number."""
        delay = min(self.initial_delay * (self.exponential_base ** attempt), self.max_delay)
        
        if self.jitter:
            jitter_range = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)

class DistributedResilienceManager:
    """Manages distributed circuit breakers and retry logic."""
    _instance: Optional['DistributedResilienceManager'] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DistributedResilienceManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, redis_client: redis.Redis):
        if self._initialized:
            return
        self._initialized = True
        self.redis = redis_client
        self.backoff = ExponentialBackoff()
        self.circuit_breaker_configs: Dict[str, DistributedCircuitBreakerConfig] = {}
        self.circuit_breakers: Dict[str, DistributedCircuitBreaker] = {}
        self.logger = logging.getLogger(__name__)

        # Load configuration for distributed circuit breaker
        cb_config_data = config_loader.get("circuit_breaker", {})
        self.global_cb_config = DistributedCircuitBreakerConfig(
            failure_threshold=cb_config_data.get("failure_threshold", 5),
            recovery_timeout=cb_config_data.get("recovery_timeout", 60),
            success_threshold=cb_config_data.get("success_threshold", 3),
            timeout_duration=cb_config_data.get("timeout_duration", 30),
            enabled=cb_config_data.get("enabled", False) # Check if distributed CB is enabled
        )
        if self.global_cb_config.enabled:
            self.logger.info("Distributed Circuit Breaker is ENABLED.")
        else:
            self.logger.info("Distributed Circuit Breaker is DISABLED. Using local resilience.")

    async def __aenter__(self):
        """Ensures Redis connection is active."""
        try:
            await self.redis.ping()
            self.logger.info("DistributedResilienceManager connected to Redis.")
        except Exception as e:
            self.logger.error(f"DistributedResilienceManager failed to connect to Redis: {e}", exc_info=True)
            # If Redis is critical for distributed CB, you might want to disable it or raise error
            self.global_cb_config.enabled = False
            self.logger.warning("Distributed Circuit Breaker disabled due to Redis connection failure.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific cleanup needed for Redis client, managed externally."""
        pass
        
    def get_circuit_breaker(self, name: str) -> DistributedCircuitBreaker:
        """Get or create a distributed circuit breaker for a given name (e.g., domain)."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = DistributedCircuitBreaker(name, self.redis, self.global_cb_config)
        return self.circuit_breakers[name]
    
    async def execute_with_resilience(self, func: Callable, url: str, *args, **kwargs) -> Any:
        """Execute function with distributed circuit breaker and retry logic."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        
        # Use the domain as the name for the circuit breaker
        circuit_breaker = self.get_circuit_breaker(domain)
        
        if self.global_cb_config.enabled:
            can_exec = await circuit_breaker.can_execute()
            if not can_exec:
                raise CircuitBreakerOpenError(f"Circuit breaker open for {domain}")
        
        # Attempt with retries
        max_retries = 5 # Configurable
        for attempt in range(max_retries):
            try:
                result = await asyncio.wait_for(
                    func(*args, **kwargs), # Pass args and kwargs directly to func
                    timeout=self.global_cb_config.timeout_duration
                )
                if self.global_cb_config.enabled:
                    await circuit_breaker.record_success()
                return result
                
            except (asyncio.TimeoutError, aiohttp.ClientError, ConnectionError) as e:
                if self.global_cb_config.enabled:
                    await circuit_breaker.record_failure()
                
                if attempt == max_retries - 1:
                    self.logger.error(f"Final retry failed for {url}: {e}")
                    raise
                
                delay = self.backoff.calculate_delay(attempt)
                self.logger.warning(f"Attempt {attempt + 1} failed for {url}, retrying in {delay:.2f}s: {e}")
                await asyncio.sleep(delay)
            except Exception as e:
                # Catch all other exceptions, record as failure, and re-raise
                if self.global_cb_config.enabled:
                    await circuit_breaker.record_failure()
                self.logger.error(f"Unexpected error during execution for {url}: {e}", exc_info=True)
                raise
        
    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all managed circuit breakers."""
        status = {}
        for domain, cb in self.circuit_breakers.items():
            status[domain] = await cb.get_status()
        return status

class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""
    pass

# The global singleton instance will now be managed by the class itself
# and explicitly instantiated in main.py.
# distributed_resilience_manager: Optional[DistributedResilienceManager] = None
