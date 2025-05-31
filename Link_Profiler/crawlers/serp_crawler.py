"""
SERP Crawler - Drives a headless browser (Playwright) to extract SERP data.
File: Link_Profiler/crawlers/serp_crawler.py
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse, urlencode

from playwright.async_api import async_playwright, Page, BrowserContext, Browser
from playwright_stealth import stealth_async

from Link_Profiler.core.models import SERPResult # Absolute import

logger = logging.getLogger(__name__)

class SERPCrawler:
    """
    Crawls Search Engine Results Pages (SERPs) using Playwright to extract data.
    Supports Google and Bing.
    """
    def __init__(self, headless: bool = True, browser_type: str = "chromium"):
        self.headless = headless
        self.browser_type = browser_type # 'chromium', 'firefox', 'webkit'
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        """Launches the browser and creates a new context."""
        self.logger.info(f"Launching Playwright browser ({self.browser_type}, headless={self.headless})...")
        self.playwright_instance = await async_playwright().start()
        
        if self.browser_type == "chromium":
            self.browser = await self.playwright_instance.chromium.launch(headless=self.headless)
        elif self.browser_type == "firefox":
            self.browser = await self.playwright_instance.firefox.launch(headless=self.headless)
        elif self.browser_type == "webkit":
            self.browser = await self.playwright_instance.webkit.launch(headless=self.headless)
        else:
            raise ValueError(f"Unsupported browser type: {self.browser_type}")
        
        self.context = await self.browser.new_context()
        self.logger.info("Playwright browser launched and context created.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes the browser."""
        if self.browser:
            self.logger.info("Closing Playwright browser...")
            await self.browser.close()
            self.browser = None
            self.context = None
        if self.playwright_instance:
            await self.playwright_instance.stop()
            self.playwright_instance = None
        self.logger.info("Playwright browser closed.")

    async def _navigate_to_search(self, page: Page, keyword: str, search_engine: str = "google"):
        """Navigates to the search engine and performs a search."""
        if search_engine.lower() == "google":
            search_url = f"https://www.google.com/search?q={urlencode({'q': keyword})}"
            await page.goto(search_url, wait_until="domcontentloaded")
            # Apply stealth to avoid bot detection
            await stealth_async(page)
            # Wait for results to load, adjust selector as needed
            await page.wait_for_selector("#search #rso > div", timeout=10000) # Main results container
        elif search_engine.lower() == "bing":
            search_url = f"https://www.bing.com/search?q={urlencode({'q': keyword})}"
            await page.goto(search_url, wait_until="domcontentloaded")
            await stealth_async(page)
            await page.wait_for_selector("#b_results > li.b_algo", timeout=10000) # Main results container
        else:
            raise ValueError(f"Unsupported search engine: {search_engine}")

    async def _extract_google_serp_results(self, page: Page, keyword: str, num_results: int) -> List[SERPResult]:
        """Extracts SERP results from a Google search results page."""
        results: List[SERPResult] = []
        
        # Extract organic results
        organic_results = await page.query_selector_all("#search #rso > div")
        
        for i, result_div in enumerate(organic_results):
            if len(results) >= num_results:
                break

            # Skip non-organic results like "People also ask", "Top stories", etc.
            # These often have specific classes or structures.
            # Example: check if it's a standard organic result div
            class_attr = await result_div.get_attribute("class")
            if class_attr and ("g" not in class_attr.split() and "xpd" not in class_attr.split()):
                continue # Skip non-standard result blocks

            link_element = await result_div.query_selector("a[jsaction='click:h5fJlb']") # Common selector for organic links
            if not link_element:
                link_element = await result_div.query_selector("a[href^='http']") # Fallback for any link
            
            if link_element:
                result_url = await link_element.get_attribute("href")
                title_element = await result_div.query_selector("h3")
                title_text = await title_element.text_content() if title_element else ""
                
                snippet_element = await result_div.query_selector(".VwiC3b") # Common snippet class
                snippet_text = await snippet_element.text_content() if snippet_element else ""

                # Basic rich features detection (can be expanded)
                rich_features = []
                if await result_div.query_selector(".yp1CPe"): # Featured snippet class
                    rich_features.append("Featured Snippet")
                if await result_div.query_selector(".kno-kp"): # Knowledge panel
                    rich_features.append("Knowledge Panel")
                if await result_div.query_selector(".g-img"): # Image result
                    rich_features.append("Image Result")
                # TODO: Add more rich feature detection (e.g., local pack, video carousel)

                if result_url and title_text:
                    results.append(
                        SERPResult(
                            keyword=keyword,
                            position=len(results) + 1, # Position based on extraction order
                            result_url=result_url,
                            title_text=title_text.strip(),
                            snippet_text=snippet_text.strip(),
                            rich_features=rich_features,
                            crawl_timestamp=datetime.now()
                        )
                    )
        return results

    async def _extract_bing_serp_results(self, page: Page, keyword: str, num_results: int) -> List[SERPResult]:
        """Extracts SERP results from a Bing search results page."""
        results: List[SERPResult] = []
        
        organic_results = await page.query_selector_all("#b_results > li.b_algo")
        
        for i, result_li in enumerate(organic_results):
            if len(results) >= num_results:
                break

            link_element = await result_li.query_selector("h2 > a")
            if link_element:
                result_url = await link_element.get_attribute("href")
                title_text = await link_element.text_content()
                
                snippet_element = await result_li.query_selector(".b_vlist2 > p, .b_lineclamp2") # Common snippet classes
                snippet_text = await snippet_element.text_content() if snippet_element else ""

                rich_features = []
                # TODO: Add Bing-specific rich feature detection

                if result_url and title_text:
                    results.append(
                        SERPResult(
                            keyword=keyword,
                            position=len(results) + 1,
                            result_url=result_url,
                            title_text=title_text.strip(),
                            snippet_text=snippet_text.strip(),
                            rich_features=rich_features,
                            crawl_timestamp=datetime.now()
                        )
                    )
        return results

    async def get_serp_data(self, keyword: str, num_results: int = 10, search_engine: str = "google") -> List[SERPResult]:
        """
        Performs a search and extracts SERP data.
        """
        if not self.browser or not self.context:
            raise RuntimeError("Browser not launched. Use SERPCrawler within an async context.")

        page: Page = await self.context.new_page()
        page_load_time: Optional[float] = None
        
        try:
            start_time = datetime.now()
            await self._navigate_to_search(page, keyword, search_engine)
            end_time = datetime.now()
            page_load_time = (end_time - start_time).total_seconds()

            if search_engine.lower() == "google":
                serp_results = await self._extract_google_serp_results(page, keyword, num_results)
            elif search_engine.lower() == "bing":
                serp_results = await self._extract_bing_serp_results(page, keyword, num_results)
            else:
                raise ValueError(f"Unsupported search engine: {search_engine}")
            
            # Populate page_load_time for each result
            for result in serp_results:
                result.page_load_time = page_load_time

            self.logger.info(f"Extracted {len(serp_results)} SERP results for '{keyword}' from {search_engine}.")
            return serp_results

        except Exception as e:
            self.logger.error(f"Error extracting SERP data for '{keyword}' from {search_engine}: {e}", exc_info=True)
            return []
        finally:
            await page.close()

# Example usage (for testing)
async def main():
    logging.basicConfig(level=logging.INFO)
    keyword = "best python web frameworks"
    
    async with SERPCrawler(headless=True) as crawler:
        results = await crawler.get_serp_data(keyword, num_results=5, search_engine="google")
        for r in results:
            print(f"Pos: {r.position}, Title: {r.title_text}, URL: {r.result_url}, Snippet: {r.snippet_text[:50]}...")
            print(f"  Rich Features: {r.rich_features}, Load Time: {r.page_load_time:.2f}s")

        print("\n--- Bing Search ---")
        results_bing = await crawler.get_serp_data(keyword, num_results=5, search_engine="bing")
        for r in results_bing:
            print(f"Pos: {r.position}, Title: {r.title_text}, URL: {r.result_url}, Snippet: {r.snippet_text[:50]}...")
            print(f"  Rich Features: {r.rich_features}, Load Time: {r.page_load_time:.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
