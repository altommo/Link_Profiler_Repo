"""
Local Circuit Breaker Implementation for Crawler Resilience
Prevents cascading failures and implements smart retry logic
"""

import asyncio
import time
import random
from enum import Enum
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import aiohttp # Import aiohttp

logger = logging.getLogger(__name__)

class CircuitBreakerState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered

@dataclass
class LocalCircuitBreakerConfig:
    failure_threshold: int = 5           # Failures before opening
    recovery_timeout: int = 60           # Seconds before trying half-open
    success_threshold: int = 3           # Successes needed to close from half-open
    timeout_duration: int = 30           # Request timeout in seconds

class LocalCircuitBreaker:
    def __init__(self, name: str, config: LocalCircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.next_attempt_time = None
        
    def can_execute(self) -> bool:
        """Check if request can be executed"""
        now = time.time()
        
        if self.state == CircuitBreakerState.CLOSED:
            return True
        elif self.state == CircuitBreakerState.OPEN:
            if self.next_attempt_time and now >= self.next_attempt_time:
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info(f"Local circuit breaker {self.name} switching to HALF_OPEN")
                return True
            return False
        elif self.state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self):
        """Record successful execution"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._close_circuit()
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)  # Gradually recover
    
    def record_failure(self):
        """Record failed execution"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self._open_circuit()
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self._open_circuit()
    
    def _open_circuit(self):
        """Open the circuit breaker"""
        self.state = CircuitBreakerState.OPEN
        self.next_attempt_time = time.time() + self.config.recovery_timeout
        logger.warning(f"Local circuit breaker {self.name} OPENED after {self.failure_count} failures")
    
    def _close_circuit(self):
        """Close the circuit breaker"""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.next_attempt_time = None
        logger.info(f"Local circuit breaker {self.name} CLOSED - service recovered")

class ExponentialBackoff:
    """Implements exponential backoff with jitter"""
    
    def __init__(self, initial_delay: float = 1.0, max_delay: float = 60.0, 
                 exponential_base: float = 2.0, jitter: bool = True):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number"""
        delay = min(self.initial_delay * (self.exponential_base ** attempt), self.max_delay)
        
        if self.jitter:
            # Add random jitter to prevent thundering herd
            jitter_range = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)

class LocalResilienceManager:
    """Manages local circuit breakers and retry logic for all domains"""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, LocalCircuitBreaker] = {}
        self.backoff = ExponentialBackoff()
        
    def get_circuit_breaker(self, domain: str) -> LocalCircuitBreaker:
        """Get or create circuit breaker for domain"""
        if domain not in self.circuit_breakers:
            config = LocalCircuitBreakerConfig()
            self.circuit_breakers[domain] = LocalCircuitBreaker(domain, config)
        return self.circuit_breakers[domain]
    
    async def execute_with_resilience(self, func: Callable, url: str, *args, **kwargs) -> Any:
        """Execute function with circuit breaker and retry logic"""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        circuit_breaker = self.get_circuit_breaker(domain)
        
        if not circuit_breaker.can_execute():
            raise CircuitBreakerOpenError(f"Circuit breaker open for {domain}")
        
        # Attempt with retries
        max_retries = 5
        for attempt in range(max_retries):
            try:
                result = await asyncio.wait_for(
                    func(url, *args, **kwargs),
                    timeout=circuit_breaker.config.timeout_duration
                )
                circuit_breaker.record_success()
                return result
                
            except (asyncio.TimeoutError, aiohttp.ClientError, ConnectionError) as e:
                circuit_breaker.record_failure()
                
                if attempt == max_retries - 1:
                    logger.error(f"Final retry failed for {url}: {e}")
                    raise
                
                delay = self.backoff.calculate_delay(attempt)
                logger.warning(f"Attempt {attempt + 1} failed for {url}, retrying in {delay:.2f}s: {e}")
                await asyncio.sleep(delay)
        
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all circuit breakers"""
        status = {}
        for domain, cb in self.circuit_breakers.items():
            status[domain] = {
                'state': cb.state.value,
                'failure_count': cb.failure_count,
                'last_failure_time': cb.last_failure_time
            }
        return status

class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open"""
    pass
