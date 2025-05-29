"""
Link Extractor - Extracts links from HTML content.
File: Link_Profiler/crawlers/link_extractor.py
"""

from typing import List
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging

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
            rel = a_tag.get('rel', [])
            link_type = self._determine_link_type(rel)

            links.append(
                Backlink(
                    source_url=base_url,
                    target_url=full_url,
                    anchor_text=anchor_text,
                    link_type=link_type,
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
                        source_url=base_url,
                        target_url=canonical_url,
                        anchor_text="canonical",
                        link_type=LinkType.CANONICAL,
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
        """Determines the link type based on 'rel' attributes."""
        if 'nofollow' in rel_attributes:
            return LinkType.NOFOLLOW
        if 'sponsored' in rel_attributes:
            return LinkType.SPONSORED
        if 'ugc' in rel_attributes:
            return LinkType.UGC
        return LinkType.FOLLOW

    def _get_context_text(self, tag, max_length: int = 100) -> str:
        """Extracts surrounding text for context."""
        # This is a simplified approach. A more robust solution might involve
        # traversing the DOM or using regex on the raw HTML.
        context = ""
        if tag.previous_sibling and hasattr(tag.previous_sibling, 'get_text'):
            context += tag.previous_sibling.get_text(strip=True) + " "
        context += tag.get_text(strip=True) # The anchor text itself
        if tag.next_sibling and hasattr(tag.next_sibling, 'get_text'):
            context += " " + tag.next_sibling.get_text(strip=True)
        
        return context.strip()[:max_length]
