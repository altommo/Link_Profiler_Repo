#!/usr/bin/env python3
"""
Working WebCrawler Test with Import Fixes
This test script fixes the import issues and provides a fallback link extractor
"""

import asyncio
import sys
import os
import json
import time
import aiohttp
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

# Fix Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Known results from your simple crawler test
KNOWN_RESULTS = {
    "http://example.com/": {
        "status_code": 200,
        "content_length_range": [1200, 1300],
        "links_count": 1,
        "crawl_time_max": 3000,
        "content_type_contains": "text/html"
    },
    "http://quotes.toscrape.com/": {
        "status_code": 200,
        "content_length_range": [10000, 12000],
        "links_count_range": [45, 55],
        "crawl_time_max": 3000,
        "content_type_contains": "text/html"
    },
    "http://books.toscrape.com/": {
        "status_code": 200,
        "content_length_range": [50000, 55000],
        "links_count_range": [70, 80],
        "crawl_time_max": 3000,
        "content_type_contains": "text/html"
    },
    "https://httpbin.org/html": {
        "status_code": 200,
        "content_length_range": [3500, 4000],
        "links_count": 0,
        "crawl_time_max": 3000,
        "content_type_contains": "text/html"
    },
    "https://httpbin.org/status/404": {
        "status_code": 404,
        "links_count": 0,
        "crawl_time_max": 3000,
        "content_type_contains": "text/html"
    }
}


class MockBacklink:
    """Mock Backlink class for testing"""
    def __init__(self, target_url: str, source_url: str, anchor_text: str = "", link_type: str = "internal"):
        self.target_url = target_url
        self.source_url = source_url
        self.anchor_text = anchor_text
        self.link_type = link_type
        self.http_status = None
        self.crawl_timestamp = None


class MockCrawlResult:
    """Mock CrawlResult class for testing"""
    def __init__(self, url: str, status_code: int = 200, content: Union[str, bytes] = "", 
                 content_type: str = "text/html", crawl_time_ms: int = 0, 
                 error_message: str = None, links_found: List = None):
        self.url = url
        self.status_code = status_code
        self.content = content
        self.content_type = content_type
        self.crawl_time_ms = crawl_time_ms
        self.error_message = error_message
        self.links_found = links_found or []
        self.headers = {}
        self.redirect_url = None
        self.seo_metrics = None
        self.crawl_timestamp = datetime.now()
        self.validation_issues = []
        self.anomaly_flags = []


class MockCrawlConfig:
    """Mock CrawlConfig for testing"""
    def __init__(self, **kwargs):
        self.max_pages = kwargs.get('max_pages', 1)
        self.max_depth = kwargs.get('max_depth', 1)
        self.delay_seconds = kwargs.get('delay_seconds', 0.1)
        self.timeout_seconds = kwargs.get('timeout_seconds', 15)
        self.follow_redirects = kwargs.get('follow_redirects', True)
        self.respect_robots_txt = kwargs.get('respect_robots_txt', False)
        self.user_agent = kwargs.get('user_agent', "TestCrawler/1.0")
        self.allowed_domains = kwargs.get('allowed_domains', [])
        self.render_javascript = kwargs.get('render_javascript', False)
        self.custom_headers = kwargs.get('custom_headers', {})
        self.extract_image_text = kwargs.get('extract_image_text', False)
        self.extract_video_content = kwargs.get('extract_video_content', False)
        self.extract_pdfs = kwargs.get('extract_pdfs', False)
        self.captcha_solving_enabled = kwargs.get('captcha_solving_enabled', False)
        self.proxy_list = kwargs.get('proxy_list', [])
        self.proxy_region = kwargs.get('proxy_region', None)
    
    def is_domain_allowed(self, domain: str) -> bool:
        """Check if domain is allowed"""
        if not self.allowed_domains:
            return True
        return domain in self.allowed_domains


class SimpleLinkExtractor:
    """Simple link extractor that works without complex dependencies"""
    
    def extract_links(self, source_url: str, html_content: str) -> List[MockBacklink]:
        """Extract links from HTML content"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            links = []
            
            # Find all anchor tags with href
            for tag in soup.find_all('a', href=True):
                href = tag['href'].strip()
                if href:
                    # Convert relative URLs to absolute
                    absolute_url = urljoin(source_url, href)
                    anchor_text = tag.get_text(strip=True)
                    
                    # Determine link type
                    source_domain = urlparse(source_url).netloc
                    target_domain = urlparse(absolute_url).netloc
                    link_type = "internal" if source_domain == target_domain else "external"
                    
                    link = MockBacklink(
                        target_url=absolute_url,
                        source_url=source_url,
                        anchor_text=anchor_text,
                        link_type=link_type
                    )
                    links.append(link)
            
            return links
            
        except Exception as e:
            print(f"⚠️  Error extracting links: {e}")
            return []


class MinimalWebCrawler:
    """Minimal WebCrawler implementation for testing"""
    
    def __init__(self, config: Dict, **kwargs):
        self.config = MockCrawlConfig(**config)
        self.session = None
        self.link_extractor = SimpleLinkExtractor()
        
    async def __aenter__(self):
        """Async context manager entry"""
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
        headers = {
            'User-Agent': self.config.user_agent
        }
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            headers=headers
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def crawl_url(self, url: str, last_crawl_result: Optional = None) -> MockCrawlResult:
        """Crawl a single URL"""
        start_time = time.time()
        
        try:
            async with self.session.get(url, allow_redirects=self.config.follow_redirects) as response:
                status_code = response.status
                content = await response.text()
                content_type = response.headers.get('content-type', '').lower()
                
                crawl_time_ms = int((time.time() - start_time) * 1000)
                
                # Extract links if it's HTML
                links = []
                if 'text/html' in content_type:
                    links = self.link_extractor.extract_links(url, content)
                
                return MockCrawlResult(
                    url=url,
                    status_code=status_code,
                    content=content,
                    content_type=content_type,
                    crawl_time_ms=crawl_time_ms,
                    links_found=links
                )
                
        except Exception as e:
            return MockCrawlResult(
                url=url,
                status_code=500,
                error_message=f"Crawl error: {str(e)}",
                crawl_time_ms=int((time.time() - start_time) * 1000)
            )


class WorkingCrawlerTest:
    """Working crawler test that uses the minimal implementation"""
    
    def __init__(self):
        self.test_results = []
    
    def create_test_config(self) -> Dict:
        """Create test configuration"""
        return {
            "max_pages": 1,
            "max_depth": 1,
            "delay_seconds": 0.1,
            "timeout_seconds": 15,
            "follow_redirects": True,
            "respect_robots_txt": False,
            "user_agent": "WorkingTestCrawler/1.0",
            "allowed_domains": [],
            "render_javascript": False
        }
    
    async def test_url_with_minimal_crawler(self, url: str, expected: Dict[str, Any]) -> Dict[str, Any]:
        """Test URL with minimal crawler implementation"""
        print(f"\n{'='*60}")
        print(f"🔍 Testing with Minimal Crawler: {url}")
        print(f"{'='*60}")
        
        test_result = {
            'url': url,
            'timestamp': datetime.now().isoformat(),
            'expected': expected,
            'actual': {},
            'validations': {},
            'passed': False,
            'errors': []
        }
        
        try:
            config = self.create_test_config()
            
            async with MinimalWebCrawler(config=config) as crawler:
                print("✅ Minimal WebCrawler initialized")
                
                result = await crawler.crawl_url(url)
                
                # Extract actual results
                actual = {
                    'status_code': result.status_code,
                    'content_length': len(result.content) if result.content else 0,
                    'links_count': len(result.links_found),
                    'content_type': result.content_type,
                    'crawl_time_ms': result.crawl_time_ms,
                    'error_message': result.error_message
                }
                
                test_result['actual'] = actual
                
                # Print results
                print(f"📊 Results:")
                print(f"   Status Code: {actual['status_code']}")
                print(f"   Content Length: {actual['content_length']:,} chars")
                print(f"   Links Found: {actual['links_count']}")
                print(f"   Content Type: {actual['content_type']}")
                print(f"   Crawl Time: {actual['crawl_time_ms']:.1f}ms")
                
                if actual['error_message']:
                    print(f"   ⚠️  Error: {actual['error_message']}")
                
                # Show sample links
                if result.links_found:
                    print(f"   🔗 Sample Links:")
                    for i, link in enumerate(result.links_found[:3]):
                        print(f"      {i+1}. {link.target_url}")
                    if len(result.links_found) > 3:
                        print(f"      ... and {len(result.links_found) - 3} more")
                
                # Validate results
                validations = self.validate_results(actual, expected)
                test_result['validations'] = validations
                test_result['passed'] = all(validations.values())
                
                if not test_result['passed']:
                    failed = [k for k, v in validations.items() if not v]
                    test_result['errors'] = failed
                
        except Exception as e:
            error_msg = f"Exception during test: {str(e)}"
            test_result['errors'] = [error_msg]
            print(f"❌ {error_msg}")
        
        # Print validation results
        print(f"\n📋 Validation:")
        if test_result.get('validations'):
            for check, passed in test_result['validations'].items():
                status = "✅" if passed else "❌"
                print(f"   {status} {check}")
        
        overall_status = "✅ PASSED" if test_result['passed'] else "❌ FAILED"
        print(f"\n{overall_status}")
        
        return test_result
    
    def validate_results(self, actual: Dict, expected: Dict) -> Dict[str, bool]:
        """Validate actual vs expected results"""
        validations = {}
        
        # Status code
        if 'status_code' in expected:
            validations['status_code'] = actual['status_code'] == expected['status_code']
        
        # Content length range
        if 'content_length_range' in expected:
            min_len, max_len = expected['content_length_range']
            validations['content_length'] = min_len <= actual['content_length'] <= max_len
        
        # Links count
        if 'links_count' in expected:
            validations['links_count'] = actual['links_count'] == expected['links_count']
        elif 'links_count_range' in expected:
            min_count, max_count = expected['links_count_range']
            validations['links_count'] = min_count <= actual['links_count'] <= max_count
        
        # Content type
        if 'content_type_contains' in expected:
            validations['content_type'] = expected['content_type_contains'] in actual['content_type'].lower()
        
        # Performance
        if 'crawl_time_max' in expected:
            validations['performance'] = actual['crawl_time_ms'] <= expected['crawl_time_max']
        
        # No critical errors
        validations['no_critical_errors'] = not actual['error_message'] or actual['status_code'] in [404, 403]
        
        return validations
    
    async def run_working_test_suite(self):
        """Run the working test suite"""
        print("🚀 Working WebCrawler Test Suite")
        print("=" * 70)
        print("This test uses a minimal crawler implementation to bypass import issues")
        
        all_results = []
        passed_count = 0
        
        for url, expected in KNOWN_RESULTS.items():
            try:
                result = await self.test_url_with_minimal_crawler(url, expected)
                all_results.append(result)
                
                if result.get('passed', False):
                    passed_count += 1
                
                # Small delay between tests
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Failed to test {url}: {e}")
                all_results.append({
                    'url': url,
                    'success': False,
                    'error': str(e),
                    'passed': False
                })
        
        # Final summary
        total_tests = len(KNOWN_RESULTS)
        print(f"\n{'='*70}")
        print(f"🎯 WORKING TEST SUITE SUMMARY")
        print(f"{'='*70}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_count}")
        print(f"Failed: {total_tests - passed_count}")
        print(f"Success Rate: {(passed_count / total_tests) * 100:.1f}%")
        
        print(f"\n📊 Comparison with Simple Crawler:")
        print("URL                          | Simple | Working | Match")
        print("-" * 65)
        
        simple_results = {
            "http://example.com/": {"links": 1, "chars": 1256},
            "http://quotes.toscrape.com/": {"links": 49, "chars": 11021},
            "http://books.toscrape.com/": {"links": 73, "chars": 51274},
            "https://httpbin.org/html": {"links": 0, "chars": 3739},
            "https://httpbin.org/status/404": {"links": 0, "chars": 0}
        }
        
        for result in all_results:
            if result.get('actual'):
                url = result['url']
                actual = result['actual']
                simple = simple_results.get(url, {"links": "?", "chars": "?"})
                
                links_match = "✅" if abs(actual['links_count'] - simple['links']) <= 5 else "❌"
                
                print(f"{url:<28} | {simple['links']:>6} | {actual['links_count']:>7} | {links_match}")
        
        # Save results
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            results_file = f"working_crawler_test_results_{timestamp}.json"
            with open(results_file, 'w') as f:
                json.dump(all_results, f, indent=2, default=str)
            print(f"\n💾 Results saved to: {results_file}")
        except Exception as e:
            print(f"⚠️  Could not save results: {e}")
        
        return all_results


async def main():
    """Main test runner"""
    print("🔧 Working WebCrawler Test")
    print("This test bypasses import issues and provides a baseline comparison")
    print("=" * 80)
    
    tester = WorkingCrawlerTest()
    await tester.run_working_test_suite()
    
    print(f"\n🎯 Next Steps:")
    print("1. ✅ This working test shows what your crawler should achieve")
    print("2. 🔧 Fix the import issues in your actual WebCrawler")
    print("3. 🧪 Compare your WebCrawler results with these baseline results")
    print("4. 🚀 Use these URLs as your standard test cases")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
