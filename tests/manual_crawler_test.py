#!/usr/bin/env python3
"""
Manual WebCrawler Test
Test your WebCrawler by calling it directly through your API or main.py
"""

import asyncio
import aiohttp
import time
import json
from typing import Dict, List, Any

# Your known expected results from the simple test
EXPECTED_RESULTS = {
    "http://example.com/": {
        "status_code": 200,
        "content_length": 1256,
        "links_count": 1,
        "description": "Simple example domain with 1 IANA link"
    },
    "http://quotes.toscrape.com/": {
        "status_code": 200,
        "content_length": 11021,
        "links_count": 49,
        "description": "Quotes site with pagination and author links"
    },
    "http://books.toscrape.com/": {
        "status_code": 200,
        "content_length": 51274,
        "links_count": 73,
        "description": "Books catalog with category and product links"
    },
    "https://httpbin.org/html": {
        "status_code": 200,
        "content_length": 3739,
        "links_count": 0,
        "description": "Simple test HTML page"
    },
    "https://httpbin.org/status/404": {
        "status_code": 404,
        "content_length": 0,
        "links_count": 0,
        "description": "404 error test"
    }
}


class ManualCrawlerTester:
    """Test WebCrawler through your API endpoints"""
    
    def __init__(self, api_base_url="http://127.0.0.1:8000"):
        self.api_base_url = api_base_url
        
    async def test_via_api(self, target_url: str, expected: Dict[str, Any]):
        """Test crawling via your API endpoint"""
        print(f"\n{'='*60}")
        print(f"🔍 Testing via API: {target_url}")
        print(f"📝 Expected: {expected['description']}")
        print(f"{'='*60}")
        
        # Prepare crawl job payload
        payload = {
            "target_url": target_url,
            "initial_seed_urls": [target_url],
            "config": {
                "max_pages": 1,
                "max_depth": 1,
                "delay_seconds": 0.1,
                "timeout_seconds": 15,
                "respect_robots_txt": False
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                # Submit crawl job
                print("📤 Submitting crawl job...")
                async with session.post(
                    f"{self.api_base_url}/crawl/start_backlink_discovery",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    if response.status == 202:
                        job_data = await response.json()
                        job_id = job_data.get('job_id')
                        print(f"✅ Job submitted: {job_id}")
                        
                        # Poll for completion
                        result = await self.poll_job_status(session, job_id, target_url, expected)
                        return result
                    else:
                        error_text = await response.text()
                        print(f"❌ Failed to submit job: {response.status} - {error_text}")
                        return {
                            'url': target_url,
                            'success': False,
                            'error': f"API submission failed: {response.status}"
                        }
                        
        except Exception as e:
            print(f"❌ Error testing via API: {e}")
            return {
                'url': target_url,
                'success': False,
                'error': f"Exception: {str(e)}"
            }
    
    async def poll_job_status(self, session: aiohttp.ClientSession, job_id: str, target_url: str, expected: Dict[str, Any]):
        """Poll job status until completion"""
        print(f"⏳ Polling job status for {job_id}...")
        
        for attempt in range(30):  # Poll for up to 60 seconds
            try:
                async with session.get(
                    f"{self.api_base_url}/crawl/status/{job_id}",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    
                    if response.status == 200:
                        status_data = await response.json()
                        status = status_data.get('status')
                        progress = status_data.get('progress_percentage', 0)
                        
                        print(f"   Status: {status}, Progress: {progress:.1f}%")
                        
                        if status == "completed":
                            return self.analyze_job_results(status_data, target_url, expected)
                        elif status == "failed":
                            error_msg = status_data.get('error_message', 'Unknown error')
                            print(f"❌ Job failed: {error_msg}")
                            return {
                                'url': target_url,
                                'success': False,
                                'error': f"Job failed: {error_msg}"
                            }
                        elif status in ["queued", "in_progress"]:
                            await asyncio.sleep(2)
                            continue
                        else:
                            print(f"⚠️  Unknown status: {status}")
                            await asyncio.sleep(2)
                            
                    else:
                        print(f"❌ Status check failed: {response.status}")
                        await asyncio.sleep(2)
                        
            except Exception as e:
                print(f"⚠️  Error checking status: {e}")
                await asyncio.sleep(2)
        
        print("⏰ Job polling timed out")
        return {
            'url': target_url,
            'success': False,
            'error': "Job polling timed out"
        }
    
    def analyze_job_results(self, job_data: Dict, target_url: str, expected: Dict[str, Any]):
        """Analyze completed job results"""
        print(f"\n📊 Job completed! Analyzing results...")
        
        # Extract relevant data from job results
        results = job_data.get('results', {})
        pages_crawled = results.get('pages_crawled', 0)
        total_links_found = results.get('total_links_found', 0)
        crawl_duration = results.get('crawl_duration_seconds', 0)
        errors = results.get('errors', [])
        
        print(f"   Pages Crawled: {pages_crawled}")
        print(f"   Total Links Found: {total_links_found}")
        print(f"   Crawl Duration: {crawl_duration:.2f}s")
        print(f"   Errors: {len(errors)}")
        
        # Compare with expected results
        actual = {
            'pages_crawled': pages_crawled,
            'total_links_found': total_links_found,
            'crawl_duration': crawl_duration,
            'error_count': len(errors)
        }
        
        # Validation
        validations = {}
        
        # Should crawl at least 1 page
        validations['pages_crawled'] = pages_crawled >= 1
        
        # Links count validation (with tolerance)
        expected_links = expected.get('links_count', 0)
        tolerance = max(5, expected_links * 0.2)  # 20% tolerance or 5 links
        validations['links_count'] = abs(total_links_found - expected_links) <= tolerance
        
        # Performance validation (should complete in reasonable time)
        validations['performance'] = crawl_duration <= 30.0  # 30 seconds max
        
        # Error validation (minimal errors expected)
        validations['minimal_errors'] = len(errors) <= 2
        
        all_passed = all(validations.values())
        
        print(f"\n📋 Validation Results:")
        for check, passed in validations.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {check}")
        
        print(f"\n🎯 Overall: {'✅ PASSED' if all_passed else '❌ FAILED'}")
        
        return {
            'url': target_url,
            'success': True,
            'job_completed': True,
            'actual': actual,
            'expected': expected,
            'validations': validations,
            'passed': all_passed,
            'job_data': job_data
        }
    
    async def test_api_health(self):
        """Test if the API is running and accessible"""
        print("🏥 Testing API health...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Try a simple health check or root endpoint
                async with session.get(
                    f"{self.api_base_url}/",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    
                    if response.status == 200:
                        print("✅ API is accessible")
                        return True
                    else:
                        print(f"⚠️  API returned status {response.status}")
                        return False
                        
        except Exception as e:
            print(f"❌ API not accessible: {e}")
            print(f"💡 Make sure your API is running on {self.api_base_url}")
            print("   You can start it with: python main.py")
            return False
    
    async def run_full_test_suite(self):
        """Run complete test suite"""
        print("🚀 Manual WebCrawler Test Suite")
        print("=" * 70)
        
        # First check if API is accessible
        api_healthy = await self.test_api_health()
        if not api_healthy:
            print("\n❌ Cannot proceed - API is not accessible")
            print("📝 To start your API:")
            print("   1. cd /opt/Link_Profiler_Repo/Link_Profiler")
            print("   2. python main.py")
            print("   3. Wait for 'Application startup complete'")
            print("   4. Then run this test again")
            return []
        
        print(f"\n🎯 Testing {len(EXPECTED_RESULTS)} URLs...")
        
        all_results = []
        passed_count = 0
        
        for url, expected in EXPECTED_RESULTS.items():
            try:
                result = await self.test_via_api(url, expected)
                all_results.append(result)
                
                if result.get('passed', False):
                    passed_count += 1
                
                # Small delay between tests
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"❌ Failed to test {url}: {e}")
                all_results.append({
                    'url': url,
                    'success': False,
                    'error': str(e),
                    'passed': False
                })
        
        # Final summary
        total_tests = len(EXPECTED_RESULTS)
        success_rate = (passed_count / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"\n{'='*70}")
        print(f"🏆 FINAL TEST RESULTS")
        print(f"{'='*70}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_count}")
        print(f"Failed: {total_tests - passed_count}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        print(f"\n📊 Detailed Results:")
        for result in all_results:
            status = "✅" if result.get('passed', False) else "❌"
            url = result['url']
            
            if result.get('job_completed'):
                actual = result.get('actual', {})
                print(f"{status} {url}")
                print(f"    Links: {actual.get('total_links_found', 'N/A')}, "
                      f"Duration: {actual.get('crawl_duration', 0):.1f}s")
            else:
                error = result.get('error', 'Unknown error')
                print(f"{status} {url} - {error}")
        
        # Performance insights
        successful_results = [r for r in all_results if r.get('job_completed')]
        if successful_results:
            avg_duration = sum(r['actual']['crawl_duration'] for r in successful_results) / len(successful_results)
            total_links = sum(r['actual']['total_links_found'] for r in successful_results)
            
            print(f"\n📈 Performance Summary:")
            print(f"   Average crawl time: {avg_duration:.2f}s")
            print(f"   Total links discovered: {total_links}")
            print(f"   Links per second: {total_links/sum(r['actual']['crawl_duration'] for r in successful_results):.1f}")
        
        # Save results
        try:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            results_file = f"manual_crawler_test_results_{timestamp}.json"
            with open(results_file, 'w') as f:
                json.dump(all_results, f, indent=2, default=str)
            print(f"\n💾 Results saved to: {results_file}")
        except Exception as e:
            print(f"⚠️  Could not save results: {e}")
        
        return all_results


class DirectFileTest:
    """Alternative: Test by running WebCrawler script directly"""
    
    async def test_direct_execution(self):
        """Test by executing your crawler directly"""
        print("\n🔧 Alternative: Direct File Execution Test")
        print("=" * 50)
        
        test_commands = [
            "python -c \"from crawlers.web_crawler import WebCrawler; print('✅ WebCrawler import successful')\"",
            "python -c \"from core.models import CrawlConfig; print('✅ CrawlConfig import successful')\"",
            "python -c \"from database.database import Database; print('✅ Database import successful')\"",
            "python tests/test_api.py",  # Your existing test file
        ]
        
        print("🧪 Testing import commands:")
        for cmd in test_commands[:3]:  # Just the import tests
            print(f"\n💻 Running: {cmd}")
            try:
                import subprocess
                result = subprocess.run(
                    cmd, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    timeout=10
                )
                
                if result.returncode == 0:
                    print(f"✅ Success: {result.stdout.strip()}")
                else:
                    print(f"❌ Failed: {result.stderr.strip()}")
                    
            except subprocess.TimeoutExpired:
                print("⏰ Command timed out")
            except Exception as e:
                print(f"❌ Error running command: {e}")
        
        print(f"\n💡 You can also run your existing test with:")
        print(f"   python tests/test_api.py")


async def main():
    """Main test runner with multiple approaches"""
    print("🎯 WebCrawler Validation - Multiple Approaches")
    print("=" * 80)
    
    # Approach 1: API-based testing (recommended)
    print("\n1️⃣ APPROACH 1: API-Based Testing (Recommended)")
    api_tester = ManualCrawlerTester()
    api_results = await api_tester.run_full_test_suite()
    
    # Approach 2: Direct file testing
    print("\n2️⃣ APPROACH 2: Direct Import Testing")
    direct_tester = DirectFileTest()
    await direct_tester.test_direct_execution()
    
    # Summary and recommendations
    print(f"\n{'='*80}")
    print("🎯 TESTING RECOMMENDATIONS")
    print(f"{'='*80}")
    
    if any(r.get('passed', False) for r in api_results):
        print("✅ API-based testing worked! Your WebCrawler is functioning correctly.")
        print("🎉 You can use these URLs as reliable test cases for your crawler.")
    else:
        print("⚠️  API-based testing had issues. Try these alternatives:")
        print("   1. Make sure your API is running: python main.py")
        print("   2. Check the API logs for errors")
        print("   3. Try running your existing tests/test_api.py script")
        print("   4. Use the simple crawler test as a baseline comparison")
    
    print(f"\n📋 Known Good Test URLs (from your simple test):")
    for url, expected in EXPECTED_RESULTS.items():
        print(f"   🔗 {url}")
        print(f"      Expected: {expected['links_count']} links, {expected['content_length']:,} chars")
    
    print(f"\n🚀 Next Steps:")
    print("   1. Compare your WebCrawler results with the simple crawler results")
    print("   2. If results differ significantly, debug link extraction logic")
    print("   3. Use these URLs in your automated testing pipeline")
    print("   4. Add more test cases as needed for edge cases")


if __name__ == "__main__":
    print("🔧 Manual WebCrawler Test Script")
    print("This script tests your WebCrawler through multiple approaches")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()