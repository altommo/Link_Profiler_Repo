"""
Content Validator - Provides utilities for validating crawled content quality.
File: Link_Profiler/utils/content_validator.py
"""

import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import re

# Assuming CrawlResult and CrawlConfig are available from core.models
# We'll import them directly if needed, or pass necessary data.
# For now, we'll define a simple structure for validation results.

logger = logging.getLogger(__name__)

class ContentValidator:
    """
    Performs various checks on crawled content to assess its quality and detect anomalies.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".ContentValidator")
        # Common bot detection phrases (can be expanded)
        self.bot_detection_phrases = [
            "access denied", "you have been blocked", "captcha", "robot check",
            "rate limit exceeded", "please verify you are human", "403 forbidden",
            "too many requests", "cloudflare" # Cloudflare often indicates bot protection
        ]
        # Minimum content length for a "meaningful" page (can be configured)
        self.min_meaningful_content_length = 500 # characters

    def validate_crawl_result(self, url: str, html_content: str, status_code: int) -> List[str]:
        """
        Performs a comprehensive validation of a crawled page's content.
        
        Args:
            url: The URL of the crawled page.
            html_content: The HTML content of the page.
            status_code: The HTTP status code of the response.
            
        Returns:
            A list of strings, where each string is an identified validation issue.
            Returns an empty list if no issues are found.
        """
        issues: List[str] = []

        # 1. Check HTTP Status Code for errors
        if status_code >= 400:
            issues.append(f"HTTP Error: Status code {status_code} indicates a problem.")

        # 2. Detect bot detection indicators in content
        bot_indicators = self.detect_bot_indicators(html_content)
        if bot_indicators:
            issues.extend([f"Bot detection indicator found: '{indicator}'" for indicator in bot_indicators])

        # 3. Check content completeness/quality
        content_completeness_issues = self.check_content_completeness(html_content)
        if content_completeness_issues:
            issues.extend(content_completeness_issues)
        
        # 4. Check for common scraping artifacts (e.g., incomplete HTML, placeholder text)
        scraping_artifacts = self.detect_scraping_artifacts(html_content)
        if scraping_artifacts:
            issues.extend([f"Scraping artifact detected: '{artifact}'" for artifact in scraping_artifacts])

        if issues:
            self.logger.warning(f"Validation issues found for {url}: {'; '.join(issues)}")
        else:
            self.logger.debug(f"No validation issues found for {url}.")
            
        return issues

    def detect_bot_indicators(self, html_content: str) -> List[str]:
        """
        Detects common phrases or patterns indicating bot detection.
        """
        found_indicators = []
        content_lower = html_content.lower()
        
        for phrase in self.bot_detection_phrases:
            if phrase in content_lower:
                found_indicators.append(phrase)
        
        # Check for specific HTML elements often used in CAPTCHAs or blocks
        if re.search(r'<div[^>]*id=["\']g-recaptcha["\']', html_content):
            found_indicators.append("reCAPTCHA element")
        if re.search(r'<title>attention required! | cloudflare</title>', content_lower):
            found_indicators.append("Cloudflare 'Attention Required' page")

        return found_indicators

    def check_content_completeness(self, html_content: str) -> List[str]:
        """
        Checks if the content appears to be complete and meaningful.
        This is a heuristic and might need tuning.
        """
        issues = []
        
        # Remove HTML tags to get plain text for length check
        soup = BeautifulSoup(html_content, 'lxml')
        text_content = soup.get_text(separator=' ', strip=True)
        
        if len(text_content) < self.min_meaningful_content_length:
            issues.append(f"Content is unusually short ({len(text_content)} characters), possibly incomplete or an error page.")
            
        # Check for common "empty page" or "loading" indicators
        if re.search(r'loading\.\.\.', text_content.lower()) and len(text_content) < 200:
            issues.append("Page contains 'loading...' text and is very short, possibly indicating incomplete load.")
        
        return issues

    def detect_scraping_artifacts(self, html_content: str) -> List[str]:
        """
        Identifies patterns that suggest the page was not fully loaded or rendered correctly,
        or contains anti-scraping placeholders.
        """
        issues = []
        content_lower = html_content.lower()

        # Common placeholder texts
        if "javascript is required" in content_lower:
            issues.append("Page requires JavaScript, content might be incomplete without rendering.")
        if "enable cookies" in content_lower:
            issues.append("Page requires cookies, content might be incomplete.")
        
        # Check for truncated HTML (very basic, might need more advanced parsing)
        if not html_content.strip().endswith(('</html>', '</body>')):
            # This is a very weak check, as content might be streamed or malformed.
            # More robust check would involve parsing and checking for unclosed tags.
            pass 
            
        return issues

# Example usage (for testing)
async def main():
    validator = ContentValidator()

    # Test Case 1: Normal content
    normal_html = """
    <html>
    <head><title>Normal Page</title></head>
    <body>
        <h1>Welcome</h1>
        <p>This is a normal page with sufficient content for testing purposes. It should pass all validation checks.</p>
        <p>More content here to ensure it meets the minimum length requirements.</p>
    </body>
    </html>
    """
    issues1 = validator.validate_crawl_result("http://example.com/normal", normal_html, 200)
    print(f"Normal page issues: {issues1}") # Expected: []

    # Test Case 2: Bot detection
    bot_html = """
    <html>
    <head><title>Access Denied</title></head>
    <body>
        <h1>Access Denied</h1>
        <p>You have been blocked due to suspicious activity. Please verify you are human.</p>
        <div id="g-recaptcha"></div>
    </body>
    </html>
    """
    issues2 = validator.validate_crawl_result("http://example.com/blocked", bot_html, 403)
    print(f"Blocked page issues: {issues2}") # Expected: ['HTTP Error: Status code 403 indicates a problem.', 'Bot detection indicator found: 'access denied'', 'Bot detection indicator found: 'you have been blocked'', 'Bot detection indicator found: 'please verify you are human'', 'Bot detection indicator found: 'reCAPTCHA element'']

    # Test Case 3: Short content
    short_html = """<html><body><h1>Error</h1><p>Page not found.</p></body></html>"""
    issues3 = validator.validate_crawl_result("http://example.com/short", short_html, 404)
    print(f"Short page issues: {issues3}") # Expected: ['HTTP Error: Status code 404 indicates a problem.', 'Content is unusually short...']

    # Test Case 4: Cloudflare block
    cloudflare_html = """
    <html>
    <head><title>Attention Required! | Cloudflare</title></head>
    <body>
        <p>Please wait while your request is being verified.</p>
    </body>
    </html>
    """
    issues4 = validator.validate_crawl_result("http://example.com/cloudflare", cloudflare_html, 403)
    print(f"Cloudflare page issues: {issues4}") # Expected: ['HTTP Error: Status code 403 indicates a problem.', 'Bot detection indicator found: 'cloudflare'', 'Bot detection indicator found: 'Cloudflare 'Attention Required' page'', 'Content is unusually short...']

    # Test Case 5: JavaScript required
    js_html = """
    <html>
    <body>
        <noscript>Please enable JavaScript to view this page.</noscript>
        <div id="app-root"></div>
    </body>
    </html>
    """
    issues5 = validator.validate_crawl_result("http://example.com/js-required", js_html, 200)
    print(f"JS required page issues: {issues5}") # Expected: ['Content is unusually short...', 'Scraping artifact detected: 'Page requires JavaScript, content might be incomplete without rendering.'']

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
