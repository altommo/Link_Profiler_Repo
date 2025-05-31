"""
Content Parser - Extracts SEO-related metrics and information from page content.
File: Link_Profiler/crawlers/content_parser.py
"""

from typing import Optional, Dict, Any, List
from bs4 import BeautifulSoup
import logging
from urllib.parse import urlparse, urljoin
from datetime import datetime
import json # Import the json module

from Link_Profiler.core.models import SEOMetrics # Absolute import

logger = logging.getLogger(__name__)

class ContentParser:
    """
    Parses HTML content to extract various SEO-related metrics and other useful information.
    """
    async def parse_seo_metrics(self, url: str, html_content: str) -> SEOMetrics:
        """
        Parses the HTML content to extract various SEO metrics.
        """
        metrics = SEOMetrics(url=url)
        
        try:
            soup = BeautifulSoup(html_content, 'lxml')

            # Title
            title_tag = soup.find('title')
            if title_tag and title_tag.string:
                metrics.title_length = len(title_tag.string.strip())

            # Meta Description
            meta_description = soup.find('meta', attrs={'name': 'description'})
            if meta_description and meta_description.get('content'):
                metrics.meta_description_length = len(meta_description['content'].strip()) # Corrected field name

            # Headings (H1, H2)
            metrics.h1_count = len(soup.find_all('h1'))
            metrics.h2_count = len(soup.find_all('h2'))

            # Internal and External Links (basic count, detailed analysis is in LinkExtractor)
            internal_links_count = 0
            external_links_count = 0
            parsed_base_domain = urlparse(url).netloc

            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].strip()
                full_url = urljoin(url, href)
                parsed_link_domain = urlparse(full_url).netloc
                
                if parsed_link_domain == parsed_base_domain:
                    internal_links_count += 1
                elif parsed_link_domain: # Ensure it's a valid domain, not just relative path
                    external_links_count += 1
            metrics.internal_links = internal_links_count
            metrics.external_links = external_links_count

            # Images and Alt Text
            metrics.images_count = 0
            metrics.images_without_alt = 0
            for img_tag in soup.find_all('img'):
                metrics.images_count += 1
                if not img_tag.get('alt'):
                    metrics.images_without_alt += 1

            # Canonical Tag
            canonical_tag = soup.find('link', rel='canonical', href=True)
            metrics.has_canonical = bool(canonical_tag)

            # Robots Meta Tag
            robots_meta = soup.find('meta', attrs={'name': 'robots'})
            metrics.has_robots_meta = bool(robots_meta)

            # Schema Markup (basic check for script tags with type="application/ld+json")
            schema_script = soup.find('script', type='application/ld+json')
            metrics.has_schema_markup = bool(schema_script)
            
            # Extract structured data types
            structured_data_types = set()
            for script_tag in soup.find_all('script', type='application/ld+json'):
                try:
                    json_ld = json.loads(script_tag.string)
                    if isinstance(json_ld, dict) and '@type' in json_ld:
                        sd_type = json_ld['@type']
                        if isinstance(sd_type, list):
                            structured_data_types.update(sd_type)
                        else:
                            structured_data_types.add(sd_type)
                    elif isinstance(json_ld, list): # Handle array of structured data
                        for item in json_ld:
                            if isinstance(item, dict) and '@type' in item:
                                sd_type = item['@type']
                                if isinstance(sd_type, list):
                                    structured_data_types.update(sd_type)
                                else:
                                    structured_data_types.add(sd_type)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON-LD found on {url}")
            metrics.structured_data_types = sorted(list(structured_data_types))

            # Open Graph Meta Tags
            metrics.og_title = self._get_meta_content(soup, 'property', 'og:title')
            metrics.og_description = self._get_meta_content(soup, 'property', 'og:description')

            # Twitter Card Meta Tags
            metrics.twitter_title = self._get_meta_content(soup, 'name', 'twitter:title')
            metrics.twitter_description = self._get_meta_content(soup, 'name', 'twitter:description')

            # Mobile Friendly (very basic check, real check requires Lighthouse/similar)
            # Look for viewport meta tag
            viewport_meta = soup.find('meta', attrs={'name': 'viewport'})
            metrics.mobile_friendly = bool(viewport_meta and 'width=device-width' in viewport_meta.get('content', ''))

            # Performance & Best Practices scores (performance_score, accessibility_score)
            # These cannot be determined from HTML content alone and would require external tools (e.g., Lighthouse).
            # They will remain None unless populated by an external process.

            metrics.audit_timestamp = datetime.now() # Set audit timestamp

            metrics.calculate_seo_score() # Calculate the score based on extracted data

        except Exception as e:
            logger.error(f"Error parsing SEO metrics for {url}: {e}")
            metrics.issues.append(f"Error during parsing: {e}")
        
        return metrics

    def _get_meta_content(self, soup: BeautifulSoup, attr_name: str, attr_value: str) -> Optional[str]:
        """Helper to extract content from meta tags."""
        tag = soup.find('meta', attrs={attr_name: attr_value})
        return tag.get('content').strip() if tag and tag.get('content') else None
