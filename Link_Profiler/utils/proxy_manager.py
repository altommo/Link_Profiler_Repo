import random
import time # Added for time.time()
import asyncio # Added for asyncio.sleep
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, field
import logging
import aiohttp # Added for aiohttp.ClientSession and ClientTimeout
from enum import Enum # Added missing import

# Removed direct import of config_loader, will use global instance

logger = logging.getLogger(__name__)

class ProxyStatus(Enum): # Defined outside dataclass for clarity
    ACTIVE = "active"
    FAILED = "failed"
    BANNED = "banned"
    TESTING = "testing"

@dataclass
class ProxyDetails:
    url: str
    region: str = "unknown"
    status: ProxyStatus = ProxyStatus.TESTING # Default status
    last_used: float = 0 # Changed to float for time.time()
    failure_count: int = 0
    success_count: int = 0
    avg_response_time: float = 0
    last_failure_reason: str = ""

class ProxyManager:
    """Real proxy management with health checking and rotation."""
    
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProxyManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.logger = logging.getLogger(__name__ + ".ProxyManager")
        
        # Import config_loader here to avoid circular dependency at module level
        from Link_Profiler.config.config_loader import config_loader 

        # Configuration from config_loader
        self.use_proxies = config_loader.get("proxy.use_proxies", False)
        self.retry_delay = config_loader.get("proxy.proxy_retry_delay_seconds", 300)
        self.max_failures = config_loader.get("proxy.max_failures_before_ban", 5) # Default added

        self.proxies: List[ProxyDetails] = []
        # Load proxies from config
        proxy_list = config_loader.get("proxy.proxy_list", [])
        for proxy_config in proxy_list:
            if isinstance(proxy_config, dict):
                proxy = ProxyDetails(
                    url=proxy_config.get("url", ""),
                    region=proxy_config.get("region", "unknown")
                )
                self.proxies.append(proxy)
        
        self.logger.info(f"Initialized ProxyManager with {len(self.proxies)} proxies")
    
    def get_next_proxy(self) -> Optional[ProxyDetails]:
        """Get the next available proxy using round-robin with health checking."""
        if not self.use_proxies or not self.proxies:
            return None
        
        # Filter active proxies
        active_proxies = [
            p for p in self.proxies 
            if p.status == ProxyStatus.ACTIVE or 
            (p.status == ProxyStatus.FAILED and time.time() - p.last_used > self.retry_delay)
        ]
        
        if not active_proxies:
            # If no active proxies, try testing failed ones
            failed_proxies = [p for p in self.proxies if p.status == ProxyStatus.FAILED]
            if failed_proxies:
                # Reset the proxy with least recent failure
                proxy = min(failed_proxies, key=lambda p: p.last_used)
                proxy.status = ProxyStatus.TESTING
                return proxy
            return None
        
        # Sort by success rate and response time
        active_proxies.sort(key=lambda p: (
            p.success_count / max(1, p.success_count + p.failure_count),  # Success rate
            -p.avg_response_time  # Faster is better (negative for reverse sort)
        ), reverse=True)
        
        # Use weighted random selection favoring better proxies
        if len(active_proxies) > 1:
            # 70% chance for best proxy, 30% for others
            if random.random() < 0.7:
                return active_proxies[0]
            else:
                return random.choice(active_proxies[1:])
        
        return active_proxies[0]
    
    def mark_proxy_good(self, proxy_url: str, response_time: float = 0):
        """Mark a proxy as working."""
        proxy = self._find_proxy(proxy_url)
        if proxy:
            proxy.status = ProxyStatus.ACTIVE
            proxy.success_count += 1
            proxy.last_used = time.time()
            
            # Update average response time
            if response_time > 0:
                if proxy.avg_response_time == 0:
                    proxy.avg_response_time = response_time
                else:
                    # Moving average
                    proxy.avg_response_time = (proxy.avg_response_time * 0.8) + (response_time * 0.2)
            
            self.logger.debug(f"Proxy {proxy_url} marked as good (success: {proxy.success_count})")
    
    def mark_proxy_bad(self, proxy_url: str, reason: str = ""):
        """Mark a proxy as failed."""
        proxy = self._find_proxy(proxy_url)
        if proxy:
            proxy.failure_count += 1
            proxy.last_used = time.time()
            proxy.last_failure_reason = reason
            
            if proxy.failure_count >= self.max_failures:
                proxy.status = ProxyStatus.BANNED
                self.logger.warning(f"Proxy {proxy_url} banned after {proxy.failure_count} failures")
            else:
                proxy.status = ProxyStatus.FAILED
                self.logger.debug(f"Proxy {proxy_url} marked as failed: {reason}")
    
    def _find_proxy(self, proxy_url: str) -> Optional[ProxyDetails]:
        """Find proxy by URL."""
        return next((p for p in self.proxies if p.url == proxy_url), None)
    
    async def test_proxy(self, proxy: ProxyDetails, test_url: str = "http://httpbin.org/ip") -> bool:
        """Test if a proxy is working."""
        try:
            start_time = time.time()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    test_url,
                    proxy=proxy.url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    response_time = time.time() - start_time
                    
                    if response.status == 200:
                        self.mark_proxy_good(proxy.url, response_time)
                        return True
                    else:
                        self.mark_proxy_bad(proxy.url, f"HTTP {response.status}")
                        return False
        
        except Exception as e:
            self.mark_proxy_bad(proxy.url, str(e))
            return False
    
    async def test_all_proxies(self) -> Dict[str, bool]:
        """Test all proxies and return results."""
        if not self.proxies:
            return {}
        
        self.logger.info(f"Testing {len(self.proxies)} proxies...")
        
        tasks = []
        for proxy in self.proxies:
            task = asyncio.create_task(self.test_proxy(proxy))
            tasks.append((proxy.url, task))
        
        results = {}
        for proxy_url, task in tasks:
            try:
                result = await task
                results[proxy_url] = result
            except Exception as e:
                self.logger.error(f"Error testing proxy {proxy_url}: {e}")
                results[proxy_url] = False
        
        active_count = sum(1 for r in results.values() if r)
        self.logger.info(f"Proxy testing complete: {active_count}/{len(self.proxies)} active")
        
        return results
    
    def get_proxy_stats(self) -> Dict[str, Any]:
        """Get statistics about proxy performance."""
        if not self.proxies:
            return {"total": 0, "active": 0, "failed": 0, "banned": 0}
        
        stats = {
            "total": len(self.proxies),
            "active": sum(1 for p in self.proxies if p.status == ProxyStatus.ACTIVE),
            "failed": sum(1 for p in self.proxies if p.status == ProxyStatus.FAILED),
            "banned": sum(1 for p in self.proxies if p.status == ProxyStatus.BANNED),
            "testing": sum(1 for p in self.proxies if p.status == ProxyStatus.TESTING)
        }
        
        # Average success rate
        total_attempts = sum(p.success_count + p.failure_count for p in self.proxies)
        total_successes = sum(p.success_count for p in self.proxies)
        
        stats["success_rate"] = (total_successes / total_attempts) if total_attempts > 0 else 0
        
        # Calculate average response time only for proxies with recorded response times
        response_times = [p.avg_response_time for p in self.proxies if p.avg_response_time > 0]
        stats["avg_response_time"] = sum(response_times) / max(1, len(response_times))
        
        return stats

# Create singleton instance
proxy_manager = ProxyManager()
