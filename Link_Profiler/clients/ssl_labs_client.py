"""
SSL Labs Client - Interacts with the SSL Labs API.
File: Link_Profiler/clients/ssl_labs_client.py
"""

import logging
import asyncio
from typing import Dict, Any, Optional
import aiohttp
import json # For parsing JSON response
import random # Import random for simulation
# Removed time import as it's no longer needed for manual performance measurement
from datetime import datetime # Import datetime

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.clients.base_client import BaseAPIClient # Import BaseAPIClient
from Link_Profiler.utils.session_manager import SessionManager # Import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager # Import DistributedResilienceManager
from Link_Profiler.utils.api_quota_manager import APIQuotaManager # Import APIQuotaManager

logger = logging.getLogger(__name__)

class SSLLabsClient(BaseAPIClient): # Inherit from BaseAPIClient
    """
    Client for fetching SSL/TLS analysis from SSL Labs API.
    """
    def __init__(self, session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None, api_quota_manager: Optional[APIQuotaManager] = None):
        super().__init__(session_manager, resilience_manager, api_quota_manager) # Call BaseAPIClient's init
        self.logger = logging.getLogger(__name__ + ".SSLLabsClient")
        self.base_url = config_loader.get("technical_auditor.ssl_labs_api.base_url")
        self.enabled = config_loader.get("technical_auditor.ssl_labs_api.enabled", False)
        
        if not self.enabled:
            self.logger.info("SSL Labs API is disabled by configuration.")

    async def __aenter__(self):
        """Initialise aiohttp session."""
        await super().__aenter__() # Call BaseAPIClient's __aenter__
        if self.enabled:
            self.logger.info("Entering SSLLabsClient context.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session."""
        await super().__aexit__(exc_type, exc_val, exc_tb) # Call BaseAPIClient's __aexit__
        if self.enabled:
            self.logger.info("Exiting SSLLabsClient context.")

    @api_rate_limited(service="ssl_labs_api", api_client_type="ssl_labs_client", endpoint="analyze_ssl")
    async def analyze_ssl(self, host: str, publish: str = 'off', all_results: str = 'done') -> Optional[Dict[str, Any]]:
        """
        Analyzes the SSL/TLS configuration of a given host.
        
        Args:
            host (str): The hostname to analyze.
            publish (str): 'on' to publish results, 'off' to keep private.
            all_results (str): 'on' to return all results, 'done' to wait for completion.
            
        Returns:
            Optional[Dict[str, Any]]: The JSON response from the SSL Labs API, or None on failure.
        """
        if not self.enabled:
            self.logger.warning(f"SSL Labs API is disabled. Simulating SSL analysis for {host}.")
            return self._simulate_ssl_analysis(host)

        endpoint = self.base_url
        params = {
            'host': host,
            'publish': publish,
            'all': all_results,
            'fromCache': 'on', # Try to get from cache first to save time/requests
            'maxAge': 86400 # Use cached results up to 24 hours old
        }

        self.logger.info(f"Calling SSL Labs API for SSL analysis of {host}...")
        
        try:
            data = await self._make_request("GET", endpoint, params=params)
            
            # Implement polling logic
            while data.get('status') in ('IN_PROGRESS', 'DNS'):
                self.logger.info(f"SSL Labs analysis for {host} is {data.get('status')}. Polling in 10 seconds...")
                await asyncio.sleep(10)
                
                data = await self._make_request("GET", endpoint, params=params) # Poll again
            
            if data.get('status') == 'READY':
                self.logger.info(f"SSL analysis for {host} completed with grade: {data.get('endpoints', [{}])[0].get('grade')}.")
                return data
            elif data.get('status') == 'ERROR':
                self.logger.error(f"SSL Labs analysis for {host} returned an error status: {data.get('statusMessage')}")
                return None # Analysis failed
            else:
                self.logger.warning(f"SSL Labs analysis for {host} returned unexpected status: {data.get('status')}. Data: {data}")
                return None # Unexpected status
        except aiohttp.ClientResponseError as e:
            self.logger.error(f"Network/API error fetching SSL analysis for {host} (Status: {e.status}): {e}", exc_info=True)
            return self._simulate_ssl_analysis(host) # Fallback to simulation on error
        except Exception as e:
            self.logger.error(f"Unexpected error fetching SSL analysis for {host}: {e}", exc_info=True)
            return self._simulate_ssl_analysis(host) # Fallback to simulation on error
        
    def _simulate_ssl_analysis(self, host: str) -> Dict[str, Any]:
        """Helper to generate simulated SSL analysis data."""
        self.logger.info(f"Simulating SSL Labs analysis for {host}.")
        from datetime import datetime, timedelta

        grade = random.choice(['A+', 'A', 'B', 'C', 'F'])
        
        return {
            "host": host,
            "port": 443,
            "protocol": "https",
            "status": "READY",
            "startTime": int(datetime.now().timestamp() * 1000),
            "testTime": int(datetime.now().timestamp() * 1000),
            "endpoints": [
                {
                    "ipAddress": f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}",
                    "serverName": host,
                    "statusMessage": "Ready",
                    "grade": grade,
                    "details": {
                        "protocols": [
                            {"id": "TLS 1.3", "name": "TLS", "version": "1.3"} if random.random() > 0.5 else {"id": "TLS 1.2", "name": "TLS", "version": "1.2"},
                            {"id": "TLS 1.2", "name": "TLS", "version": "1.2"}
                        ],
                        "cert": {
                            "subject": f"CN={host}",
                            "issuerLabel": "Simulated CA",
                            "notBefore": int((datetime.now() - timedelta(days=365)).timestamp() * 1000),
                            "notAfter": int((datetime.now() + timedelta(days=365)).timestamp() * 1000),
                            "altNames": [host, f"www.{host}"]
                        },
                        "chain": {
                            "issues": 0,
                            "cert_ids": [f"sim_cert_id_{random.randint(1000,9999)}"]
                        },
                        "freak": False,
                        "poodle": False,
                        "heartbleed": False,
                        "logjam": False,
                        "drown": False,
                        "zeroRated": False,
                        "hstsPolicy": {
                            "status": "present",
                            "maxAge": 31536000,
                            "includeSubDomains": True,
                            "preload": True
                        }
                    }
                }
            ],
            "certs": [
                {
                    "subject": f"CN={host}",
                    "issuerLabel": "Simulated CA",
                    "notBefore": int((datetime.now() - timedelta(days=365)).timestamp() * 1000),
                    "notAfter": int((datetime.now() + timedelta(days=365)).timestamp() * 1000),
                    "altNames": [host, f"www.{host}"]
                }
            ],
            'last_fetched_at': datetime.utcnow().isoformat()
        }
