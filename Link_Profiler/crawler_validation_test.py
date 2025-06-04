#!/usr/bin/env python3
"""
Web Crawler Validation Test
Tests your actual WebCrawler against known expected results from the simple test
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add the project root to Python path
sys.path.insert(0, r"C:\Users\hp\Documents\Projects\Domain_Research\Link_Profiler_Repo\Link_Profiler")

# Expected results from your simple crawler test
KNOWN_RESULTS = {
    "http://example.com/": {
        "status_code": 200,
        "content_length_range": [1200, 1300],  # 1,256 characters ± tolerance
        "links_count": 1,
        "expected_links": ["https://www.iana.org/domains/example"],
        "crawl_time_max": 2000,  # Should be under 2 seconds
        "content_type": "text/html"
    },
    "http://quotes.toscrape.com/": {
        "status_code": 200,
        "content_length_range": [10000, 12000],  # 11,021 characters ± tolerance
        "links_count_range": [45, 55],  # 49 links ± tolerance
        "crawl_time_max": 2000,
        "content_type": "text/html",
        "expected_link_patterns": [
            "quotes.toscrape.com/login",
            "quotes.toscrape.com/author/",
            "quotes.toscrape.com/tag/"
        ]
    },
    "http://books.toscrape.com/": {
        "status_code": 200,
        "content_length_range": [50000, 55000],  # 51,274 characters ± tolerance
        "links_count_range": [70, 80],  # 73 links ± tolerance
        "crawl_time_max": 2000,
        "content_type": "text/html",
        "expected_link_patterns": [
            "books.toscrape.com/catalogue/",
            "books.toscrape.com/index.html"
        ]
    },
    "https://httpbin.org/html": {
        "status_code": 200,
        "content_length_range": [3500, 4000],  # 3,739 characters ± tolerance
        "links_count": 0,  # No links found in simple test
        "crawl_time_max": 2000,
        "content_type": "text/html"
    },
    "https://httpbin.org/status/404": {
        "status_code": 404,
        "links_count": 0,
        "crawl_time_max": 2000,
        "content_type": "text/html"
    }
}


class WebCrawlerValidator:
    """Validates WebCrawler against known expected results"""
    
    def __init__(self):
        self.test_results = []
        
    def create_minimal_crawler_setup(self):
        """Create minimal setup needed for WebCrawler testing"""
        try:
            from core.models import CrawlConfig
            from database.database import Database
            from crawlers.web_crawler import WebCrawler
            
            # Create basic config
            config = {
                "max_pages": 1,  # Only test single page crawls
                "max_depth": 1,
                "delay_seconds": 0.1,
                "timeout_seconds": 10,
                "follow_redirects": True,
                "respect_robots_txt": False,
                "user_agent": "TestCrawler/1.0 (Validation)",
                "allowed_domains": [],  # Allow all domains
                "render_javascript": False,
                "custom_headers": {},
                "extract_image_text": False,
                "extract_video_content": False,
                "extract_pdfs": False,
                "captcha_solving_enabled": False,
                "proxy_list": [],
                "proxy_region": None
            }
            
            # Minimal service configurations
            anti_detection_config = {
                "user_agent_rotation": False,
                "consistent_ua_per_domain": False,
                "request_header_randomization": False,
                "human_like_delays": False,
                "stealth_mode": False,
                "browser_fingerprint_randomization": False,
                "ml_rate_optimization": False,
                "anomaly_detection_enabled": False
            }
            
            proxy_config = {"use_proxies": False}
            quality_assurance_config = {"content_validation": False}
            
            # Mock all services as None for basic testing
            services = {
                'database': None,
                'redis_client': None,
                'clickhouse_loader': None,
                'config': config,
                'anti_detection_config': anti_detection_config,
                'proxy_config': proxy_config,
                'quality_assurance_config': quality_assurance_config,
                'domain_analyzer_service': None,
                'ai_service': MockAIService(),  # Create a mock AI service
                'link_health_service': None,
                'serp_service': None,
                'keyword_service': None,
                'social_media_service': None,
                'web3_service': None,
                'link_building_service': None,
                'report_service': None,
                'playwright_browser': None
            }
            
            return WebCrawler, services
            
        except ImportError as e:
            print(f"❌ Failed to import required modules: {e}")
            return None, None
    
    async def test_single_url(self, url: str, expected: Dict[str, Any]) -> Dict[str, Any]:
        """Test crawling a single URL against expected results"""
        print(f"\n{'='*60}")
        print(f"🔍 Testing WebCrawler on: {url}")
        print(f"{'='*60}")
        
        WebCrawler, crawler_setup = self.create_minimal_crawler_setup()
        if not WebCrawler:
            return {
                'url': url,
                'success': False,
                'error': 'Failed to setup crawler',
                'timestamp': datetime.now().isoformat()
            }
        
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
            async with WebCrawler(**crawler_setup) as crawler:
                # Crawl the URL
                result = await crawler.crawl_url(url)
                
                # Extract actual results
                actual = {
                    'status_code': result.status_code,
                    'content_length': len(result.content) if result.content else 0,
                    'links_count': len(result.links_found) if result.links_found else 0,
                    'content_type': result.content_type or 'unknown',
                    'crawl_time_ms': result.crawl_time_ms,
                    'error_message': result.error_message,
                    'has_seo_metrics': result.seo_metrics is not None,
                    'links_sample': [link.target_url for link in (result.links_found or [])[:5]]
                }
                
                test_result['actual'] = actual
                
                # Print actual results
                print(f"📊 Actual Results:")
                print(f"   Status Code: {actual['status_code']}")
                print(f"   Content Length: {actual['content_length']:,} chars")
                print(f"   Links Found: {actual['links_count']}")
                print(f"   Content Type: {actual['content_type']}")
                print(f"   Crawl Time: {actual['crawl_time_ms']:.1f}ms")
                print(f"   Has SEO Metrics: {actual['has_seo_metrics']}")
                
                if actual['error_message']:
                    print(f"   Error: {actual['error_message']}")
                
                if actual['links_sample']:
                    print(f"   Sample Links:")
                    for i, link in enumerate(actual['links_sample'], 1):
                        print(f"      {i}. {link}")
                
                # Validate results
                validations = self.validate_against_expected(actual, expected)
                test_result['validations'] = validations
                test_result['passed'] = all(validations.values())
                
                if not test_result['passed']:
                    failed_validations = [k for k, v in validations.items() if not v]
                    test_result['errors'] = [f"Failed validation: {k}" for k in failed_validations]
                
        except Exception as e:
            test_result['errors'] = [f"Exception during crawl: {str(e)}"]
            print(f"❌ Error during crawl: {e}")
        
        # Print validation results
        print(f"\n📋 Validation Results:")
        if test_result.get('validations'):
            for validation, passed in test_result['validations'].items():
                status = "✅" if passed else "❌"
                print(f"   {status} {validation}")
        
        if test_result['passed']:
            print(f"\n🎉 TEST PASSED")
        else:
            print(f"\n❌ TEST FAILED")
            for error in test_result['errors']:
                print(f"      {error}")
        
        return test_result
    
    def validate_against_expected(self, actual: Dict, expected: Dict) -> Dict[str, bool]:
        """Validate actual results against expected results"""
        validations = {}
        
        # Status code validation
        if 'status_code' in expected:
            validations['status_code'] = actual['status_code'] == expected['status_code']
        
        # Content length validation
        if 'content_length_range' in expected:
            min_len, max_len = expected['content_length_range']
            validations['content_length'] = min_len <= actual['content_length'] <= max_len
        
        # Links count validation
        if 'links_count' in expected:
            validations['links_count'] = actual['links_count'] == expected['links_count']
        elif 'links_count_range' in expected:
            min_count, max_count = expected['links_count_range']
            validations['links_count'] = min_count <= actual['links_count'] <= max_count
        
        # Content type validation
        if 'content_type' in expected:
            validations['content_type'] = expected['content_type'] in actual['content_type'].lower()
        
        # Performance validation
        if 'crawl_time_max' in expected:
            validations['performance'] = actual['crawl_time_ms'] <= expected['crawl_time_max']
        
        # No errors validation
        validations['no_errors'] = not actual['error_message']
        
        # Link pattern validation
        if 'expected_link_patterns' in expected and actual['links_sample']:
            links_text = ' '.join(actual['links_sample'])
            pattern_matches = [pattern in links_text for pattern in expected['expected_link_patterns']]
            validations['link_patterns'] = any(pattern_matches)
        
        # Specific links validation
        if 'expected_links' in expected and actual['links_sample']:
            expected_found = [link in actual['links_sample'] for link in expected['expected_links']]
            validations['specific_links'] = any(expected_found)
        
        return validations
    
    async def run_validation_suite(self):
        """Run the complete validation suite"""
        print("🚀 Web Crawler Validation Suite")
        print("Testing your WebCrawler against known expected results")
        print("=" * 80)
        
        all_results = []
        passed_count = 0
        
        for url, expected in KNOWN_RESULTS.items():
            result = await self.test_single_url(url, expected)
            all_results.append(result)
            if result['passed']:
                passed_count += 1
            
            # Small delay between tests
            await asyncio.sleep(1)
        
        # Print final summary
        total_tests = len(KNOWN_RESULTS)
        print(f"\n{'='*80}")
        print(f"🎯 FINAL VALIDATION SUMMARY")
        print(f"{'='*80}")
        print(f"Total URLs Tested: {total_tests}")
        print(f"Tests Passed: {passed_count}")
        print(f"Tests Failed: {total_tests - passed_count}")
        print(f"Success Rate: {(passed_count / total_tests) * 100:.1f}%")
        
        print(f"\n📊 Test Breakdown:")
        for result in all_results:
            status = "✅" if result['passed'] else "❌"
            print(f"   {status} {result['url']}")
            if result.get('errors'):
                for error in result['errors']:
                    print(f"        {error}")
        
        # Save detailed results
        results_file = f"crawler_validation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(results_file, 'w') as f:
                json.dump(all_results, f, indent=2, default=str)
            print(f"\n💾 Detailed results saved to: {results_file}")
        except Exception as e:
            print(f"⚠️  Could not save results file: {e}")
        
        return all_results


class MockAIService:
    """Mock AI service for testing"""
    @property
    def enabled(self):
        return False
    
    def is_nlp_analysis_enabled(self):
        return False
    
    def is_video_analysis_enabled(self):
        return False
    
    def is_content_classification_enabled(self):
        return False


async def main():
    """Main validation runner"""
    validator = WebCrawlerValidator()
    await validator.run_validation_suite()


if __name__ == "__main__":
    # Handle event loop for Windows
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())
