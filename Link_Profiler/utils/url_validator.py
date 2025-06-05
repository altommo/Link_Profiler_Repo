import re
import socket
import asyncio
from urllib.parse import urlparse
import dns.resolver
from typing import Tuple, Optional, Dict, Any
import logging

# Assuming session_manager is available globally or passed via dependency injection
from Link_Profiler.utils.session_manager import session_manager 

logger = logging.getLogger(__name__)

class URLValidator:
    """Real URL validation and domain checking utilities."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".URLValidator")
    
    def is_valid_url(self, url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL."""
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return None
    
    async def check_domain_exists(self, domain: str) -> Tuple[bool, Optional[str]]:
        """
        Check if domain exists via DNS lookup.
        
        Returns:
            Tuple of (exists, ip_address)
        """
        try:
            # Remove protocol if present
            domain = domain.replace('http://', '').replace('https://', '').split('/')[0]
            
            # DNS lookup
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5
            resolver.lifetime = 5
            
            answers = resolver.resolve(domain, 'A')
            ip_address = str(answers[0])
            
            self.logger.debug(f"Domain {domain} resolves to {ip_address}")
            return True, ip_address
            
        except dns.resolver.NXDOMAIN:
            self.logger.debug(f"Domain {domain} does not exist")
            return False, None
        except Exception as e:
            self.logger.warning(f"Error checking domain {domain}: {e}")
            return False, None
    
    async def check_url_accessible(self, url: str, timeout: int = 10) -> Tuple[bool, Optional[int]]:
        """
        Check if URL is accessible via HTTP.
        
        Returns:
            Tuple of (accessible, status_code)
        """
        try:
            # Assuming session_manager is imported and available
            
            async with session_manager:
                async with session_manager.get(url, timeout=timeout) as response:
                    return True, response.status
                    
        except Exception as e:
            self.logger.debug(f"URL {url} not accessible: {e}")
            return False, None
    
    def validate_email(self, email: str) -> bool:
        """Validate email address format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def is_internal_url(self, url: str, base_domain: str) -> bool:
        """Check if URL is internal to base domain."""
        try:
            url_domain = self.extract_domain(url)
            return url_domain and (url_domain == base_domain or url_domain.endswith(f'.{base_domain}'))
        except Exception:
            return False
