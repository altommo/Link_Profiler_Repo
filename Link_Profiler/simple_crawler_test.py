#!/usr/bin/env python3
"""
Simple Web Crawler Test
Quick test script to verify basic crawler functionality
"""

import asyncio
import aiohttp
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


class SimpleCrawlerTest:
    """Simplified crawler test for validation"""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            headers={'User-Agent': 'TestCrawler/1.0'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_url(self, url: str):
        """Test crawling a single URL"""
        print(f"\n{'='*50}")
        print(f"Testing: {url}")
        print(f"{'='*50}")
        
        start_time = time.time()
        
        try:
            async with self.session.get(url) as response:
                status_code = response.status
                content = await response.text()
                content_type = response.headers.get('content-type', '')
                
                crawl_time = (time.time() - start_time) * 1000
                
                print(f"✅ Status Code: {status_code}")
                print(f"✅ Content Length: {len(content):,} characters")
                print(f"✅ Content Type: {content_type}")
                print(f"✅ Crawl Time: {crawl_time:.1f}ms")
                
                # Extract links if it's HTML
                if 'text/html' in content_type.lower():
                    links = self.extract_links(url, content)
                    print(f"✅ Links Found: {len(links)}")
                    
                    # Show first 5 links
                    if links:
                        print(f"\n📋 Sample Links:")
                        for i, link in enumerate(links[:5]):
                            print(f"   {i+1}. {link}")
                        if len(links) > 5:
                            print(f"   ... and {len(links) - 5} more")
                    
                    return {
                        'url': url,
                        'status_code': status_code,
                        'content_length': len(content),
                        'links_count': len(links),
                        'crawl_time_ms': crawl_time,
                        'success': True,
                        'links': links[:10]  # Store first 10 links
                    }
                else:
                    return {
                        'url': url,
                        'status_code': status_code,
                        'content_length': len(content),
                        'crawl_time_ms': crawl_time,
                        'success': True,
                        'content_type': content_type
                    }
                    
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            return {
                'url': url,
                'success': False,
                'error': str(e),
                'crawl_time_ms': (time.time() - start_time) * 1000
            }
    
    def extract_links(self, base_url: str, html_content: str):
        """Extract all links from HTML content"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            links = []
            
            # Find all anchor tags with href
            for tag in soup.find_all('a', href=True):
                href = tag['href'].strip()
                if href:
                    # Convert relative URLs to absolute
                    absolute_url = urljoin(base_url, href)
                    links.append(absolute_url)
            
            # Remove duplicates while preserving order
            unique_links = []
            seen = set()
            for link in links:
                if link not in seen:
                    unique_links.append(link)
                    seen.add(link)
            
            return unique_links
            
        except Exception as e:
            print(f"⚠️  Error extracting links: {e}")
            return []
    
    async def run_tests(self):
        """Run tests on known URLs"""
        print("🔍 Simple Web Crawler Test")
        print("=" * 60)
        
        test_urls = [
            # Simple, reliable test sites
            "http://example.com/",
            "http://quotes.toscrape.com/",
            "http://books.toscrape.com/",
            "https://httpbin.org/html",
            
            # Edge cases
            "https://httpbin.org/status/200",  # Should work
            "https://httpbin.org/status/404",  # Should fail gracefully
        ]
        
        results = []
        successful = 0
        
        for url in test_urls:
            result = await self.test_url(url)
            results.append(result)
            if result.get('success', False):
                successful += 1
            
            # Small delay between requests
            await asyncio.sleep(0.5)
        
        # Summary
        print(f"\n{'='*60}")
        print(f"📊 Test Summary")
        print(f"{'='*60}")
        print(f"Total URLs tested: {len(test_urls)}")
        print(f"Successful: {successful}")
        print(f"Failed: {len(test_urls) - successful}")
        print(f"Success rate: {(successful/len(test_urls))*100:.1f}%")
        
        print(f"\n📋 Detailed Results:")
        for result in results:
            status = "✅" if result.get('success') else "❌"
            url = result['url']
            
            if result.get('success'):
                if 'links_count' in result:
                    print(f"{status} {url} - {result['status_code']} - {result['links_count']} links - {result['crawl_time_ms']:.1f}ms")
                else:
                    print(f"{status} {url} - {result['status_code']} - {result['crawl_time_ms']:.1f}ms")
            else:
                print(f"{status} {url} - Error: {result.get('error', 'Unknown')}")
        
        return results


async def main():
    """Main function"""
    async with SimpleCrawlerTest() as tester:
        await tester.run_tests()


if __name__ == "__main__":
    # Run the test
    asyncio.run(main())
