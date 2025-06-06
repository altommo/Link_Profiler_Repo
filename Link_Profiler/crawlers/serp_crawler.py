import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
import random

from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.core.models import SERPResult, SEOMetrics # Import SEOMetrics
from Link_Profiler.utils.user_agent_manager import user_agent_manager
from Link_Profiler.utils.api_rate_limiter import api_rate_limited
from Link_Profiler.utils.session_manager import SessionManager
from Link_Profiler.utils.distributed_circuit_breaker import DistributedResilienceManager

logger = logging.getLogger(__name__)

class SERPCrawler:
    """
    Crawls Search Engine Results Pages (SERPs) using Playwright.
    Designed to bypass basic bot detection and extract structured results.
    """
    def __init__(self, headless: bool = True, browser_type: str = "chromium", session_manager: Optional[SessionManager] = None, resilience_manager: Optional[DistributedResilienceManager] = None):
        self.logger = logging.getLogger(__name__ + ".SERPCrawler")
        self.headless = headless
        self.browser_type = browser_type
        self.browser: Optional[Browser] = None
        self.enabled = config_loader.get("serp_crawler.playwright.enabled", False)
        self.session_manager = session_manager
        if self.session_manager is None:
            from Link_Profiler.utils.session_manager import session_manager as global_session_manager
            self.session_manager = global_session_manager
            self.logger.warning("No SessionManager provided to SERPCrawler. Falling back to global SessionManager.")
        
        self.resilience_manager = resilience_manager
        if self.enabled and self.resilience_manager is None:
            raise ValueError(f"{self.__class__.__name__} is enabled but no DistributedResilienceManager was provided.")

        if not self.enabled:
            self.logger.info("SERP Crawler (Playwright) is disabled by configuration.")

    async def __aenter__(self):
        """Launches the Playwright browser."""
        if not self.enabled:
            return self

        self.logger.info(f"Entering SERPCrawler context. Launching Playwright browser ({self.browser_type}, headless={self.headless})...")
        try:
            self.playwright_instance = await async_playwright().start()
            if self.browser_type == "chromium":
                self.browser = await self.playwright_instance.chromium.launch(headless=self.headless)
            elif self.browser_type == "firefox":
                self.browser = await self.playwright_instance.firefox.launch(headless=self.headless)
            elif self.browser_type == "webkit":
                self.browser = await self.playwright_instance.webkit.launch(headless=self.headless)
            else:
                raise ValueError(f"Unsupported browser type: {self.browser_type}")
            self.logger.info("Playwright browser launched.")
        except Exception as e:
            self.logger.error(f"Failed to launch Playwright browser: {e}. SERP crawling will be disabled.", exc_info=True)
            self.enabled = False
            self.browser = None
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes the Playwright browser."""
        if self.browser:
            self.logger.info("Exiting SERPCrawler context. Closing Playwright browser.")
            await self.browser.close()
            await self.playwright_instance.stop()
            self.browser = None

    @api_rate_limited(service="serp_crawler", api_client_type="playwright", endpoint="get_serp_data")
    async def get_serp_data(self, keyword: str, num_results: int = 10, search_engine: str = "google") -> List[SERPResult]:
        """
        Fetches SERP data for a given keyword using Playwright.
        """
        if not self.enabled or not self.browser:
            self.logger.warning(f"SERP Crawler not enabled or browser not launched. Skipping SERP data for '{keyword}'.")
            return []

        self.logger.info(f"Crawling SERP for keyword: '{keyword}' on {search_engine} (Limit: {num_results})...")
        page: Optional[Page] = None
        results: List[SERPResult] = []
        try:
            page = await self.browser.new_page()
            
            # Set random user agent and other headers for stealth
            headers = user_agent_manager.get_random_headers()
            await page.set_extra_http_headers(headers)

            # Simulate human-like delay
            if config_loader.get("anti_detection.human_like_delays", False):
                delay_range = config_loader.get("anti_detection.random_delay_range", [1.0, 3.0])
                await asyncio.sleep(random.uniform(delay_range[0], delay_range[1]))

            search_url = self._build_search_url(keyword, search_engine)
            self.logger.debug(f"Navigating to: {search_url}")

            # Use resilience manager for page navigation
            await self.resilience_manager.execute_with_resilience(
                lambda: page.goto(search_url, wait_until="domcontentloaded", timeout=config_loader.get("crawler.timeout_seconds", 30) * 1000),
                url=search_url # Use search_url for circuit breaker naming
            )

            # Check for CAPTCHA or block page
            if await self._is_captcha_page(page):
                self.logger.warning(f"CAPTCHA detected for {search_url}. Cannot proceed with SERP crawl.")
                return []

            # Extract results based on search engine (simplified selectors)
            if search_engine == "google":
                results = await self._extract_google_results(page, keyword, num_results)
            elif search_engine == "bing":
                results = await self._extract_bing_results(page, keyword, num_results)
            else:
                self.logger.warning(f"Unsupported search engine for crawling: {search_engine}.")

            self.logger.info(f"Found {len(results)} SERP results for '{keyword}' on {search_engine}.")
            return results

        except PlaywrightTimeoutError:
            self.logger.error(f"Playwright timeout while crawling SERP for '{keyword}'.")
            return []
        except Exception as e:
            self.logger.error(f"Error crawling SERP for '{keyword}': {e}", exc_info=True)
            return []
        finally:
            if page:
                await page.close()

    def _build_search_url(self, keyword: str, search_engine: str) -> str:
        """Constructs the search engine URL."""
        encoded_keyword = keyword.replace(' ', '+')
        if search_engine == "google":
            return f"https://www.google.com/search?q={encoded_keyword}"
        elif search_engine == "bing":
            return f"https://www.bing.com/search?q={encoded_keyword}"
        else:
            raise ValueError(f"Unsupported search engine: {search_engine}")

    async def _is_captcha_page(self, page: Page) -> bool:
        """Checks if the current page is a CAPTCHA or block page."""
        # Simple check: look for common CAPTCHA elements or text
        content = await page.content()
        if "captcha" in content.lower() or "verify you are human" in content.lower() or "unusual traffic" in content.lower():
            return True
        # Add more sophisticated checks if needed (e.g., specific element selectors)
        return False

    async def _extract_google_results(self, page: Page, keyword: str, num_results: int) -> List[SERPResult]:
        """Extracts results from a Google SERP."""
        extracted_results = []
        # Google's selectors can change frequently, these are examples
        # Look for organic results (usually in div with class 'g' or 'rc')
        # This is a simplified example, real-world would need more robust selectors
        elements = await page.query_selector_all('div.g, div.rc') # Common selectors for results

        now = datetime.utcnow() # Capture current time once
        for i, element in enumerate(elements):
            if len(extracted_results) >= num_results:
                break
            try:
                title_element = await element.query_selector('h3')
                url_element = await element.query_selector('a')
                snippet_element = await element.query_selector('.VwiC3b, .lEBKkf') # Common snippet classes

                title = await title_element.inner_text() if title_element else ""
                url = await url_element.get_attribute('href') if url_element else ""
                snippet = await snippet_element.inner_text() if snippet_element else ""

                if url and title:
                    extracted_results.append(
                        SERPResult(
                            keyword=keyword,
                            rank=i + 1,
                            url=url,
                            title=title,
                            snippet=snippet,
                            domain=urlparse(url).netloc,
                            position_type="organic",
                            timestamp=now, # Use the captured time
                            last_fetched_at=now # Set last_fetched_at
                        )
                    )
            except Exception as e:
                self.logger.debug(f"Error extracting Google result: {e}")
                continue
        return extracted_results

    async def _extract_bing_results(self, page: Page, keyword: str, num_results: int) -> List[SERPResult]:
        """Extracts results from a Bing SERP."""
        extracted_results = []
        # Bing's selectors can change frequently, these are examples
        elements = await page.query_selector_all('li.b_algo') # Common selector for results

        now = datetime.utcnow() # Capture current time once
        for i, element in enumerate(elements):
            if len(extracted_results) >= num_results:
                break
            try:
                title_element = await element.query_selector('h2 a')
                url_element = await element.query_selector('h2 a')
                snippet_element = await element.query_selector('.b_snippet, .b_lineclamp4')

                title = await title_element.inner_text() if title_element else ""
                url = await url_element.get_attribute('href') if url_element else ""
                snippet = await snippet_element.inner_text() if snippet_element else ""

                if url and title:
                    extracted_results.append(
                        SERPResult(
                            keyword=keyword,
                            rank=i + 1,
                            url=url,
                            title=title,
                            snippet=snippet,
                            domain=urlparse(url).netloc,
                            position_type="organic",
                            timestamp=now, # Use the captured time
                            last_fetched_at=now # Set last_fetched_at
                        )
                    )
            except Exception as e:
                self.logger.debug(f"Error extracting Bing result: {e}")
                continue
        return extracted_results
