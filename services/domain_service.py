"""
Domain Service - Provides functionalities related to domain information.
File: services/domain_service.py
"""

import asyncio
import logging
from typing import Optional, Dict
from urllib.parse import urlparse
import random

from ..core.models import Domain

class DomainService:
    """
    Service for querying domain-related information, such as availability and WHOIS data.
    Currently uses placeholder logic.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def check_domain_availability(self, domain_name: str) -> bool:
        """
        Simulates checking if a domain name is available for registration.
        In a real application, this would query a WHOIS API or a domain registrar API.
        """
        self.logger.info(f"Simulating domain availability check for: {domain_name}")
        await asyncio.sleep(0.5) # Simulate network delay

        # Placeholder logic: some domains are available, some are not
        if domain_name.lower() in ["example.com", "testdomain.org", "available.net"]:
            return True
        elif domain_name.lower() in ["google.com", "microsoft.com", "apple.com"]:
            return False
        else:
            return random.choice([True, False]) # Randomly available or not

    async def get_whois_info(self, domain_name: str) -> Optional[Dict]:
        """
        Simulates fetching WHOIS information for a domain.
        In a real application, this would query a WHOIS API.
        """
        self.logger.info(f"Simulating WHOIS info retrieval for: {domain_name}")
        await asyncio.sleep(1.0) # Simulate network delay

        # Placeholder WHOIS data
        if domain_name.lower() == "example.com":
            return {
                "domain_name": "EXAMPLE.COM",
                "registrar": "IANA",
                "creation_date": "1995-08-14",
                "expiration_date": "2025-08-13",
                "name_servers": ["A.IANA-SERVERS.NET", "B.IANA-SERVERS.NET"],
                "status": "clientDeleteProhibited https://icann.org/epp#clientDeleteProhibited",
                "emails": ["abuse@iana.org"],
                "updated_date": "2023-08-14"
            }
        elif domain_name.lower() == "google.com":
            return {
                "domain_name": "GOOGLE.COM",
                "registrar": "MarkMonitor Inc.",
                "creation_date": "1997-09-15",
                "expiration_date": "2028-09-14",
                "name_servers": ["NS1.GOOGLE.COM", "NS2.GOOGLE.COM"],
                "status": "clientDeleteProhibited https://icann.org/epp#clientDeleteProhibited",
                "emails": ["abuse-contact@markmonitor.com"],
                "updated_date": "2023-09-15"
            }
        else:
            # Generic placeholder for other domains
            return {
                "domain_name": domain_name.upper(),
                "registrar": "Simulated Registrar",
                "creation_date": "2020-01-01",
                "expiration_date": "2025-01-01",
                "name_servers": ["NS1.SIMULATED.COM", "NS2.SIMULATED.COM"],
                "status": "ok",
                "emails": [f"admin@{domain_name}"],
                "updated_date": "2023-01-01"
            }

    async def get_domain_info(self, domain_name: str) -> Optional[Domain]:
        """
        Combines WHOIS info and availability check into a Domain model.
        """
        whois_data = await self.get_whois_info(domain_name)
        if not whois_data:
            return None

        is_available = await self.check_domain_availability(domain_name)

        # Parse dates from WHOIS data
        creation_date_str = whois_data.get("creation_date")
        expiration_date_str = whois_data.get("expiration_date")
        
        creation_date = None
        expiration_date = None

        try:
            if creation_date_str:
                creation_date = datetime.strptime(creation_date_str, "%Y-%m-%d")
            if expiration_date_str:
                expiration_date = datetime.strptime(expiration_date_str, "%Y-%m-%d")
        except ValueError:
            self.logger.warning(f"Could not parse date from WHOIS data for {domain_name}")

        # Calculate age if creation date is available
        age_days = None
        if creation_date:
            age_days = (datetime.now() - creation_date).days

        # Create a Domain object (authority_score, trust_score, spam_score are placeholders for now)
        domain_obj = Domain(
            name=domain_name,
            authority_score=random.uniform(0, 100), # Placeholder
            trust_score=random.uniform(0, 100),     # Placeholder
            spam_score=random.uniform(0, 100),      # Placeholder
            age_days=age_days,
            whois_data=whois_data,
            first_seen=creation_date,
            # For simplicity, last_crawled is not set here, but could be from a separate crawl
        )
        return domain_obj

