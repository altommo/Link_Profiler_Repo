"""
Link Extractor - Extracts various types of links from HTML content.
File: Link_Profiler/crawlers/link_extractor.py
"""

import asyncio
import logging
from typing import List, Optional # Added Optional import
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Tag # Import Tag
import uuid # Import uuid

from Link_Profiler.core.models import Backlink, LinkType # Absolute import

logger = logging.getLogger(__name__)

class LinkExtractor:
    """
    Extracts various types of links (href, src, etc.) from HTML content.
    """
    async def extract_links(self, base_url: str, html_content: str) -> List[Backlink]:
        """
        Extracts all relevant links from the given HTML content.
        """
        links: List[Backlink] = []
        soup = BeautifulSoup(html_content, 'lxml') # Using lxml for potentially faster parsing

        # Extract <a> tags
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            full_url = self._resolve_url(base_url, href)
            if not full_url:
                continue

            anchor_text = a_tag.get_text(strip=True)
            
            # Get all 'rel' attributes, split by space, and filter out empty strings
            rel_attr_str = a_tag.get('rel')
            rel_attributes = [r.strip() for r in rel_attr_str.split(' ')] if isinstance(rel_attr_str, str) else []
            rel_attributes = [r for r in rel_attributes if r] # Remove empty strings
            
            link_type = self._determine_link_type(rel_attributes)

            links.append(
                Backlink(
                    id=str(uuid.uuid4()), # Generate a unique ID for each backlink
                    source_url=base_url,
                    target_url=full_url,
                    anchor_text=anchor_text,
                    link_type=link_type,
                    rel_attributes=rel_attributes, # Pass all rel attributes
                    context_text=self._get_context_text(a_tag)
                )
            )
        
        # Extract canonical links
        canonical_tag = soup.find('link', rel='canonical', href=True)
        if canonical_tag:
            canonical_url = self._resolve_url(base_url, canonical_tag['href'].strip())
            if canonical_url:
                links.append(
                    Backlink(
                        id=str(uuid.uuid4()), # Generate a unique ID for the canonical link
                        source_url=base_url,
                        target_url=canonical_url,
                        anchor_text="canonical",
                        link_type=LinkType.CANONICAL,
                        rel_attributes=['canonical'], # Canonical links typically have rel="canonical"
                        context_text=""
                    )
                )

        # You can add more extraction logic here for other tags like:
        # <img src="...">, <link href="...">, <script src="..."> etc.
        # For now, focusing on primary SEO-relevant links.

        return links

    def _resolve_url(self, base_url: str, relative_url: str) -> Optional[str]:
        """Resolves a relative URL against a base URL."""
        try:
            # Handle mailto, tel, javascript, and other non-http/https schemes
            parsed_url = urlparse(relative_url)
            if parsed_url.scheme and parsed_url.scheme not in ['http', 'https']:
                return None # Skip non-web links

            return urljoin(base_url, relative_url)
        except Exception as e:
            logger.warning(f"Could not resolve URL '{relative_url}' from base '{base_url}': {e}")
            return None

    def _determine_link_type(self, rel_attributes: List[str]) -> LinkType:
        """Determines the primary link type based on 'rel' attributes."""
        # Prioritize sponsored over nofollow if both are present
        # The order of checks here is crucial for prioritization
        if 'sponsored' in rel_attributes:
            return LinkType.SPONSORED
        if 'ugc' in rel_attributes: # UGC should be checked before nofollow if it's a distinct type
            return LinkType.UGC
        if 'nofollow' in rel_attributes:
            return LinkType.NOFOLLOW
        if 'canonical' in rel_attributes: # Link tags can have rel="canonical"
            return LinkType.CANONICAL
        if 'redirect' in rel_attributes: # Not a standard rel, but for internal tracking
            return LinkType.REDIRECT
        
        return LinkType.FOLLOW # Default to follow if no specific rel attribute is found

    def _get_context_text(self, tag: Tag, max_length: int = 100) -> str:
        """Extracts surrounding text for context."""
        # This is a simplified approach. A more robust solution might involve
        # traversing the DOM or using regex on the raw HTML.
        context = ""
        # Check if previous_sibling exists and is a NavigableString (text) or Tag
        if tag.previous_sibling:
            if isinstance(tag.previous_sibling, str):
                context += tag.previous_sibling.strip() + " "
            elif isinstance(tag.previous_sibling, Tag):
                context += tag.previous_sibling.get_text(strip=True) + " "
        
        context += tag.get_text(strip=True) # The anchor text itself
        
        # Check if next_sibling exists and is a NavigableString (text) or Tag
        if tag.next_sibling:
            if isinstance(tag.next_sibling, str):
                context += " " + tag.next_sibling.strip()
            elif isinstance(tag.next_sibling, Tag):
                context += " " + tag.next_sibling.get_text(strip=True)
        
        return context.strip()[:max_length]
