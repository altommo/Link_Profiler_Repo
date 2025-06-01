"""
Security Audit Service - Provides functionalities for security-related data.
File: Link_Profiler/services/security_audit_service.py
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
import json
import redis.asyncio as redis

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.clients.security_trails_client import SecurityTrailsClient
from Link_Profiler.clients.ssl_labs_client import SSLLabsClient

logger = logging.getLogger(__name__)

class SecurityAuditService:
    """
    Service for performing security-related audits and data collection.
    """
    def __init__(self, security_trails_client: SecurityTrailsClient, ssl_labs_client: SSLLabsClient, redis_client: Optional[redis.Redis] = None, cache_ttl: int = 3600):
        self.logger = logging.getLogger(__name__)
        self.security_trails_client = security_trails_client
        self.ssl_labs_client = ssl_labs_client
        self.redis_client = redis_client
        self.cache_ttl = cache_ttl
        self.enabled = config_loader.get("technical_auditor.security_trails_api.enabled", False) or \
                       config_loader.get("technical_auditor.ssl_labs_api.enabled", False)

        if not self.enabled:
            self.logger.info("Security Audit Service is disabled by configuration (SecurityTrails and SSL Labs APIs are disabled).")

    async def __aenter__(self):
        """Async context manager entry for SecurityAuditService."""
        self.logger.debug("Entering SecurityAuditService context.")
        await self.security_trails_client.__aenter__()
        await self.ssl_labs_client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit for SecurityAuditService."""
        self.logger.debug("Exiting SecurityAuditService context.")
        await self.security_trails_client.__aexit__(exc_type, exc_val, exc_tb)
        await self.ssl_labs_client.__aexit__(exc_type, exc_val, exc_tb)
        if self.redis_client:
            await self.redis_client.close()

    async def _get_cached_response(self, cache_key: str) -> Optional[Any]:
        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    self.logger.debug(f"Cache hit for {cache_key}")
                    return json.loads(cached_data)
            except Exception as e:
                self.logger.error(f"Error retrieving from cache for {cache_key}: {e}", exc_info=True)
        return None

    async def _set_cached_response(self, cache_key: str, data: Any):
        if self.redis_client:
            try:
                await self.redis_client.setex(cache_key, self.cache_ttl, json.dumps(data))
                self.logger.debug(f"Cached {cache_key} with TTL {self.cache_ttl}")
            except Exception as e:
                self.logger.error(f"Error setting cache for {cache_key}: {e}", exc_info=True)

    async def get_subdomain_data(self, domain: str) -> List[str]:
        """
        Fetches subdomains for a given domain using SecurityTrails.
        """
        if not self.security_trails_client.enabled:
            self.logger.warning("SecurityTrails client is disabled. Cannot fetch subdomain data.")
            return []
        
        cache_key = f"securitytrails_subdomains:{domain}"
        cached_result = await self._get_cached_response(cache_key)
        if cached_result:
            return cached_result

        subdomains = await self.security_trails_client.get_subdomains(domain)
        if subdomains:
            await self._set_cached_response(cache_key, subdomains)
        return subdomains

    async def get_dns_history_data(self, domain: str, record_type: str = 'a') -> Optional[Dict[str, Any]]:
        """
        Fetches DNS history for a given domain and record type using SecurityTrails.
        """
        if not self.security_trails_client.enabled:
            self.logger.warning("SecurityTrails client is disabled. Cannot fetch DNS history.")
            return None

        cache_key = f"securitytrails_dns_history:{domain}:{record_type}"
        cached_result = await self._get_cached_response(cache_key)
        if cached_result:
            return cached_result

        dns_history = await self.security_trails_client.get_dns_history(domain, record_type)
        if dns_history:
            await self._set_cached_response(cache_key, dns_history)
        return dns_history

    async def get_ssl_analysis_data(self, host: str) -> Optional[Dict[str, Any]]:
        """
        Performs SSL/TLS analysis for a given host using SSL Labs.
        """
        if not self.ssl_labs_client.enabled:
            self.logger.warning("SSL Labs client is disabled. Cannot perform SSL analysis.")
            return None

        cache_key = f"ssllabs_analysis:{host}"
        cached_result = await self._get_cached_response(cache_key)
        if cached_result:
            return cached_result

        ssl_analysis = await self.ssl_labs_client.analyze_ssl(host)
        if ssl_analysis:
            await self._set_cached_response(cache_key, ssl_analysis)
        return ssl_analysis

    async def perform_comprehensive_security_audit(self, domain: str) -> Dict[str, Any]:
        """
        Performs a comprehensive security audit for a domain, aggregating data from multiple sources.
        """
        self.logger.info(f"Starting comprehensive security audit for domain: {domain}.")
        
        audit_results = {}
        
        # Subdomain discovery
        subdomains = await self.get_subdomain_data(domain)
        audit_results['subdomains'] = subdomains
        
        # DNS history (A records)
        dns_history_a = await self.get_dns_history_data(domain, 'a')
        audit_results['dns_history_a'] = dns_history_a

        # SSL analysis for main domain
        ssl_analysis = await self.get_ssl_analysis_data(domain)
        audit_results['ssl_analysis'] = ssl_analysis

        # You could extend this to check SSL for subdomains, MX records, etc.
        
        self.logger.info(f"Comprehensive security audit for {domain} completed.")
        return audit_results
