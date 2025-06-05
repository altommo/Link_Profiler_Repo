"""
Advanced Session Manager with Optimized Connection Pooling
Provides intelligent session management with adaptive sizing and health monitoring
"""

import asyncio
import aiohttp
import time
import random
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from urllib.parse import urlparse
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)

@dataclass
class ConnectionStats:
    """Statistics for connection monitoring"""
    total_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    last_used: float = field(default_factory=time.time)
    success_rate: float = 1.0
    
    def update(self, success: bool, response_time: float):
        """Update connection statistics"""
        self.total_requests += 1
        if not success:
            self.failed_requests += 1
        
        # Update average response time (rolling average)
        if self.total_requests == 1:
            self.avg_response_time = response_time
        else:
            self.avg_response_time = (self.avg_response_time * 0.9) + (response_time * 0.1)
        
        self.success_rate = 1.0 - (self.failed_requests / self.total_requests)
        self.last_used = time.time()

class AdaptiveConnectionPool:
    """Adaptive connection pool that adjusts based on performance"""
    
    def __init__(self, domain: str, initial_size: int = 5, max_size: int = 20):
        self.domain = domain
        self.initial_size = initial_size
        self.max_size = max_size
        self.current_size = initial_size
        self.stats = ConnectionStats()
        self.last_adaptation = time.time()
        self.adaptation_interval = 60  # seconds
        
    def should_expand(self) -> bool:
        """Check if pool should be expanded"""
        now = time.time()
        if now - self.last_adaptation < self.adaptation_interval:
            return False
        
        # Expand if success rate is high and response time is low
        return (self.stats.success_rate > 0.95 and 
                self.stats.avg_response_time < 2.0 and
                self.current_size < self.max_size)
    
    def should_contract(self) -> bool:
        """Check if pool should be contracted"""
        now = time.time()
        if now - self.last_adaptation < self.adaptation_interval:
            return False
        
        # Contract if success rate is low or response time is high
        return (self.stats.success_rate < 0.8 or 
                self.stats.avg_response_time > 5.0) and self.current_size > 2
    
    def adapt_size(self):
        """Adapt pool size based on performance"""
        if self.should_expand():
            self.current_size = min(self.current_size + 2, self.max_size)
            logger.info(f"Expanded connection pool for {self.domain} to {self.current_size}")
            self.last_adaptation = time.time()
        elif self.should_contract():
            self.current_size = max(self.current_size - 1, 2)
            logger.info(f"Contracted connection pool for {self.domain} to {self.current_size}")
            self.last_adaptation = time.time()

class EnhancedSessionManager:
    """Production-grade session manager with intelligent pooling"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.sessions: Dict[str, aiohttp.ClientSession] = {}
        self.connection_pools: Dict[str, AdaptiveConnectionPool] = {}
        self.domain_stats: Dict[str, ConnectionStats] = defaultdict(ConnectionStats)
        self.global_connector_limit = self.config.get('global_connection_limit', 500)
        self.active_connections = 0
        self.connection_history = deque(maxlen=1000)
        
    async def get_session(self, url: str) -> aiohttp.ClientSession:
        """Get optimized session for domain"""
        domain = urlparse(url).netloc
        
        if domain not in self.sessions:
            await self._create_session_for_domain(domain)
        
        # Adapt connection pool if needed
        if domain in self.connection_pools:
            self.connection_pools[domain].adapt_size()
        
        return self.sessions[domain]
    
    async def _create_session_for_domain(self, domain: str):
        """Create optimized session for specific domain"""
        # Create adaptive connection pool config
        if domain not in self.connection_pools:
            initial_size = self.config.get('initial_pool_size', 5)
            max_size = self.config.get('max_pool_size_per_domain', 20)
            self.connection_pools[domain] = AdaptiveConnectionPool(domain, initial_size, max_size)
        
        pool = self.connection_pools[domain]
        
        # Create optimized connector
        connector = aiohttp.TCPConnector(
            limit=pool.current_size,
            limit_per_host=pool.current_size,
            ttl_dns_cache=self.config.get('dns_cache_ttl', 300),
            use_dns_cache=True,
            keepalive_timeout=self.config.get('keepalive_timeout', 30),
            enable_cleanup_closed=True,
            ssl=False if self.config.get('disable_ssl_verification') else None,
            family=0,  # Both IPv4 and IPv6
            happy_eyeballs_delay=0.25,  # Faster connection establishment
            sock_connect=None,
            sock_read=None
        )
        
        # Create timeout configuration
        timeout = aiohttp.ClientTimeout(
            total=self.config.get('total_timeout', 30),
            connect=self.config.get('connect_timeout', 10),
            sock_read=self.config.get('read_timeout', 20),
            sock_connect=self.config.get('sock_connect_timeout', 5)
        )
        
        # Create session with optimized settings
        session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers=self._get_optimized_headers(domain),
            auto_decompress=True,
            trust_env=True,
            requote_redirect_url=False
        )
        
        self.sessions[domain] = session
        logger.info(f"Created optimized session for {domain} with pool size {pool.current_size}")
    
    def _get_optimized_headers(self, domain: str) -> Dict[str, str]:
        """Get optimized headers for domain"""
        base_headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        
        # Add domain-specific optimizations
        if 'cdn' in domain.lower() or 'cloudflare' in domain.lower():
            base_headers['CF-Connecting-IP'] = '1.1.1.1'  # Cloudflare optimization
        
        return base_headers
    
    async def make_request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make optimized HTTP request with retry logic"""
        domain = urlparse(url).netloc
        session = await self.get_session(url)
        
        start_time = time.time()
        max_retries = self.config.get('max_retries', 3)
        
        for attempt in range(max_retries + 1):
            try:
                # Add request tracking
                self.active_connections += 1
                
                async with session.request(method, url, **kwargs) as response:
                    response_time = time.time() - start_time
                    
                    # Update statistics
                    success = 200 <= response.status < 400
                    self.domain_stats[domain].update(success, response_time)
                    if domain in self.connection_pools:
                        self.connection_pools[domain].stats.update(success, response_time)
                    
                    # Track connection performance
                    self.connection_history.append({
                        'domain': domain,
                        'response_time': response_time,
                        'status': response.status,
                        'success': success,
                        'timestamp': time.time()
                    })
                    
                    self.active_connections -= 1
                    return response
                    
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                self.active_connections -= 1
                response_time = time.time() - start_time
                
                # Update failure statistics
                self.domain_stats[domain].update(False, response_time)
                if domain in self.connection_pools:
                    self.connection_pools[domain].stats.update(False, response_time)
                
                if attempt == max_retries:
                    logger.error(f"Final retry failed for {url}: {e}")
                    raise
                
                # Exponential backoff with jitter
                delay = min(2 ** attempt + random.uniform(0, 1), 10)
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries + 1}) for {url}: {e}. Retrying in {delay:.2f}s")
                await asyncio.sleep(delay)
                
                # Recreate session if too many failures
                if self.domain_stats[domain].success_rate < 0.5:
                    await self._recreate_session(domain)
    
    async def _recreate_session(self, domain: str):
        """Recreate session for domain if it's performing poorly"""
        if domain in self.sessions:
            try:
                await self.sessions[domain].close()
            except Exception as e:
                logger.error(f"Error closing session for {domain}: {e}")
            del self.sessions[domain]
        
        # Reset stats
        self.domain_stats[domain] = ConnectionStats()
        if domain in self.connection_pools:
            self.connection_pools[domain].stats = ConnectionStats()
        
        logger.info(f"Recreated session for {domain} due to poor performance")
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status"""
        domain_health = {}
        for domain, stats in self.domain_stats.items():
            pool_info = {}
            if domain in self.connection_pools:
                pool = self.connection_pools[domain]
                pool_info = {
                    'current_size': pool.current_size,
                    'max_size': pool.max_size,
                    'last_adaptation': pool.last_adaptation
                }
            
            domain_health[domain] = {
                'total_requests': stats.total_requests,
                'success_rate': stats.success_rate,
                'avg_response_time': stats.avg_response_time,
                'last_used': stats.last_used,
                'pool_info': pool_info
            }
        
        # Recent performance metrics
        recent_requests = [req for req in self.connection_history 
                          if time.time() - req['timestamp'] < 300]  # Last 5 minutes
        
        return {
            'active_connections': self.active_connections,
            'total_domains': len(self.sessions),
            'recent_requests_5min': len(recent_requests),
            'recent_success_rate': sum(1 for req in recent_requests if req['success']) / len(recent_requests) if recent_requests else 1.0,
            'domain_health': domain_health
        }
    
    async def optimize_performance(self):
        """Perform performance optimizations"""
        now = time.time()
        
        # Clean up old sessions
        domains_to_cleanup = []
        for domain, stats in self.domain_stats.items():
            if now - stats.last_used > 3600:  # 1 hour
                domains_to_cleanup.append(domain)
        
        for domain in domains_to_cleanup:
            if domain in self.sessions:
                await self.sessions[domain].close()
                del self.sessions[domain]
            if domain in self.connection_pools:
                del self.connection_pools[domain]
            del self.domain_stats[domain]
            logger.info(f"Cleaned up unused session for {domain}")
        
        # Adapt all connection pools
        for pool in self.connection_pools.values():
            pool.adapt_size()
    
    async def close_all(self):
        """Close all sessions"""
        for session in self.sessions.values():
            try:
                await session.close()
            except Exception as e:
                logger.error(f"Error closing session: {e}")
        
        self.sessions.clear()
        self.connection_pools.clear()
        self.domain_stats.clear()
        logger.info("All sessions closed")
    
    async def __aenter__(self):
        """Context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.close_all()

# Global session manager instance
session_manager = None

def get_session_manager(config: Dict[str, Any] = None) -> EnhancedSessionManager:
    """Get global session manager instance"""
    global session_manager
    if session_manager is None:
        session_manager = EnhancedSessionManager(config)
    return session_manager
