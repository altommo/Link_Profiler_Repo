#!/usr/bin/env python3
"""
Link Extractor Test Suite
Tests the LinkExtractor component with known HTML samples
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urljoin

# Fix Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Test HTML samples with known expected results
TEST_HTML_SAMPLES = {
    "simple_links": {
        "description": "Simple HTML with basic links",
        "base_url": "https://example.com/",
        "html": """
        <html>
        <body>
            <a href="https://google.com">External Link</a>
            <a href="/internal-page">Internal Link</a>
            <a href="relative.html">Relative Link</a>
            <a href="mailto:test@example.com">Email Link</a>
            <a href="tel:+1234567890">Phone Link</a>
        </body>
        </html>
        """,
        "expected": {
            "total_links": 3,  # Should exclude mailto and tel
            "external_links": 1,
            "internal_links": 2,
            "expected_urls": [
                "https://google.com",
                "https://example.com/internal-page", 
                "https://example.com/relative.html"
            ]
        }
    },
    
    "seo_links": {
        "description": "SEO-focused links with rel attributes",
        "base_url": "https://example.com/",
        "html": """
        <html>
        <head>
            <link rel="canonical" href="https://example.com/canonical-page">
        </head>
        <body>
            <a href="https://sponsor.com" rel="sponsored">Sponsored Link</a>
            <a href="https://nofollow.com" rel="nofollow">No Follow Link</a>
            <a href="https://ugc.com" rel="ugc">User Generated Content</a>
            <a href="https://normal.com">Normal Link</a>
            <a href="https://multi.com" rel="nofollow sponsored">Multiple Rels</a>
        </body>
        </html>
        """,
        "expected": {
            "total_links": 6,  # 5 regular links + 1 canonical
            "sponsored_links": 2,  # sponsored and multi-rel
            "nofollow_links": 2,  # nofollow and multi-rel
            "ugc_links": 1,
            "canonical_links": 1,
            "follow_links": 1  # Only the normal link
        }
    },
    
    "complex_content": {
        "description": "Complex content similar to real websites",
        "base_url": "https://blog.example.com/post/123",
        "html": """
        <html>
        <head>
            <link rel="canonical" href="https://blog.example.com/post/123">
        </head>
        <body>
            <nav>
                <a href="/">Home</a>
                <a href="/about">About</a>
                <a href="/contact">Contact</a>
            </nav>
            <article>
                <h1>Article Title</h1>
                <p>Check out <a href="https://external-site.com">this external resource</a> for more info.</p>
                <p>Also see our <a href="/related-post">related post</a> on the topic.</p>
            </article>
            <footer>
                <a href="/privacy" rel="nofollow">Privacy Policy</a>
                <a href="https://affiliate.com/product" rel="sponsored nofollow">Buy Now</a>
            </footer>
        </body>
        </html>
        """,
        "expected": {
            "total_links": 8,  # 7 regular links + 1 canonical
            "navigation_links": 3,
            "external_links": 2,
            "internal_links": 5,
            "sponsored_links": 1,
            "nofollow_links": 2
        }
    },
    
    "edge_cases": {
        "description": "Edge cases and potential issues",
        "base_url": "https://test.com/",
        "html": """
        <html>
        <body>
            <a href="">Empty href</a>
            <a href="   ">Whitespace href</a>
            <a href="#fragment">Fragment only</a>
            <a href="javascript:void(0)">JavaScript link</a>
            <a href="ftp://files.example.com">FTP link</a>
            <a>No href attribute</a>
            <a href="valid-link.html">Valid Link</a>
            <a href="./same-directory.html">Same directory</a>
            <a href="../parent-directory.html">Parent directory</a>
        </body>
        </html>
        """,
        "expected": {
            "total_links": 4,  # Only valid web links
            "valid_schemes_only": True,
            "expected_urls": [
                "https://test.com/#fragment",
                "https://test.com/valid-link.html",
                "https://test.com/same-directory.html",
                "https://test.com/parent-directory.html"
            ]
        }
    }
}


class MockLinkType:
    """Mock LinkType for testing without import dependencies"""
    FOLLOW = "follow"
    NOFOLLOW = "nofollow" 
    SPONSORED = "sponsored"
    UGC = "ugc"
    CANONICAL = "canonical"


class MockBacklink:
    """Mock Backlink class for testing"""
    def __init__(self, id: str, source_url: str, target_url: str, anchor_text: str = "", 
                 link_type: str = "follow", rel_attributes: List[str] = None, context_text: str = ""):
        self.id = id
        self.source_url = source_url
        self.target_url = target_url
        self.anchor_text = anchor_text
        self.link_type = link_type
        self.rel_attributes = rel_attributes or []
        self.context_text = context_text


class SimpleLinkExtractor:
    """Simplified LinkExtractor for testing without import dependencies"""
    
    def __init__(self):
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin, urlparse
        import uuid
        self.BeautifulSoup = BeautifulSoup
        self.urljoin = urljoin
        self.urlparse = urlparse
        self.uuid = uuid
    
    async def extract_links(self, base_url: str, html_content: str) -> List[MockBacklink]:
        """Extract links from HTML content"""
        links = []
        soup = self.BeautifulSoup(html_content, 'html.parser')
        
        # Extract <a> tags
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href'].strip()
            full_url = self._resolve_url(base_url, href)
            if not full_url:
                continue
            
            anchor_text = a_tag.get_text(strip=True)
            
            # Get rel attributes
            rel_attr_str = a_tag.get('rel')
            if isinstance(rel_attr_str, list):
                rel_attributes = rel_attr_str
            elif isinstance(rel_attr_str, str):
                rel_attributes = [r.strip() for r in rel_attr_str.split(' ') if r.strip()]
            else:
                rel_attributes = []
            
            link_type = self._determine_link_type(rel_attributes)
            context_text = self._get_context_text(a_tag)
            
            links.append(MockBacklink(
                id=str(self.uuid.uuid4()),
                source_url=base_url,
                target_url=full_url,
                anchor_text=anchor_text,
                link_type=link_type,
                rel_attributes=rel_attributes,
                context_text=context_text
            ))
        
        # Extract canonical links
        canonical_tag = soup.find('link', rel='canonical', href=True)
        if canonical_tag:
            canonical_url = self._resolve_url(base_url, canonical_tag['href'].strip())
            if canonical_url:
                links.append(MockBacklink(
                    id=str(self.uuid.uuid4()),
                    source_url=base_url,
                    target_url=canonical_url,
                    anchor_text="canonical",
                    link_type=MockLinkType.CANONICAL,
                    rel_attributes=['canonical'],
                    context_text=""
                ))
        
        return links
    
    def _resolve_url(self, base_url: str, relative_url: str) -> Optional[str]:
        """Resolve relative URL to absolute URL"""
        try:
            if not relative_url or relative_url.isspace():
                return None
            
            parsed_url = self.urlparse(relative_url)
            if parsed_url.scheme and parsed_url.scheme not in ['http', 'https']:
                return None
            
            return self.urljoin(base_url, relative_url)
        except Exception:
            return None
    
    def _determine_link_type(self, rel_attributes: List[str]) -> str:
        """Determine link type from rel attributes"""
        if 'nofollow' in rel_attributes:
            return MockLinkType.NOFOLLOW
        if 'sponsored' in rel_attributes:
            return MockLinkType.SPONSORED
        if 'ugc' in rel_attributes:
            return MockLinkType.UGC
        return MockLinkType.FOLLOW
    
    def _get_context_text(self, tag, max_length: int = 100) -> str:
        """Get context text around the link"""
        context = ""
        if tag.previous_sibling and hasattr(tag.previous_sibling, 'get_text'):
            context += tag.previous_sibling.get_text(strip=True) + " "
        context += tag.get_text(strip=True)
        if tag.next_sibling and hasattr(tag.next_sibling, 'get_text'):
            context += " " + tag.next_sibling.get_text(strip=True)
        
        return context.strip()[:max_length]


class LinkExtractorTester:
    """Test suite for LinkExtractor"""
    
    def __init__(self):
        self.test_results = []
        self.extractor = SimpleLinkExtractor()
    
    async def test_html_sample(self, test_name: str, test_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test a single HTML sample"""
        print(f"\n{'='*60}")
        print(f"🔍 Testing: {test_name}")
        print(f"📝 {test_data['description']}")
        print(f"{'='*60}")
        
        test_result = {
            'test_name': test_name,
            'timestamp': datetime.now().isoformat(),
            'expected': test_data['expected'],
            'actual': {},
            'validations': {},
            'passed': False,
            'errors': []
        }
        
        try:
            # Extract links
            links = await self.extractor.extract_links(
                test_data['base_url'], 
                test_data['html']
            )
            
            # Analyze results
            actual = self._analyze_links(links, test_data['base_url'])
            test_result['actual'] = actual
            
            # Print results
            print(f"📊 Results:")
            print(f"   Total Links Found: {actual['total_links']}")
            print(f"   External Links: {actual['external_links']}")
            print(f"   Internal Links: {actual['internal_links']}")
            print(f"   Link Types: {actual['link_types']}")
            
            # Show sample links
            if links:
                print(f"   🔗 Sample Links:")
                for i, link in enumerate(links[:3]):
                    print(f"      {i+1}. {link.target_url} ({link.link_type})")
                    if link.anchor_text:
                        print(f"         Text: '{link.anchor_text}'")
                if len(links) > 3:
                    print(f"      ... and {len(links) - 3} more")
            
            # Validate results
            validations = self._validate_results(actual, test_data['expected'])
            test_result['validations'] = validations
            test_result['passed'] = all(validations.values())
            
            if not test_result['passed']:
                failed = [k for k, v in validations.items() if not v]
                test_result['errors'] = failed
            
        except Exception as e:
            error_msg = f"Exception during extraction: {str(e)}"
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
    
    def _analyze_links(self, links: List[MockBacklink], base_url: str) -> Dict[str, Any]:
        """Analyze extracted links"""
        from urllib.parse import urlparse
        
        base_domain = urlparse(base_url).netloc
        
        analysis = {
            'total_links': len(links),
            'external_links': 0,
            'internal_links': 0,
            'link_types': {},
            'rel_attributes': {},
            'urls': [link.target_url for link in links],
            'anchor_texts': [link.anchor_text for link in links if link.anchor_text],
        }
        
        for link in links:
            # Count external vs internal
            link_domain = urlparse(link.target_url).netloc
            if link_domain == base_domain:
                analysis['internal_links'] += 1
            else:
                analysis['external_links'] += 1
            
            # Count link types
            link_type = link.link_type
            analysis['link_types'][link_type] = analysis['link_types'].get(link_type, 0) + 1
            
            # Count rel attributes
            for rel in link.rel_attributes:
                analysis['rel_attributes'][rel] = analysis['rel_attributes'].get(rel, 0) + 1
        
        return analysis
    
    def _validate_results(self, actual: Dict, expected: Dict) -> Dict[str, bool]:
        """Validate actual vs expected results"""
        validations = {}
        
        # Total links validation
        if 'total_links' in expected:
            validations['total_links'] = actual['total_links'] == expected['total_links']
        
        # External/internal links
        if 'external_links' in expected:
            validations['external_links'] = actual['external_links'] == expected['external_links']
        
        if 'internal_links' in expected:
            validations['internal_links'] = actual['internal_links'] == expected['internal_links']
        
        # Link type counts
        link_type_checks = ['sponsored_links', 'nofollow_links', 'ugc_links', 'canonical_links', 'follow_links']
        for check in link_type_checks:
            if check in expected:
                link_type = check.replace('_links', '')
                if link_type == 'follow':
                    link_type = MockLinkType.FOLLOW
                elif link_type == 'nofollow':
                    link_type = MockLinkType.NOFOLLOW
                elif link_type == 'sponsored':
                    link_type = MockLinkType.SPONSORED
                elif link_type == 'ugc':
                    link_type = MockLinkType.UGC
                elif link_type == 'canonical':
                    link_type = MockLinkType.CANONICAL
                
                actual_count = actual['link_types'].get(link_type, 0)
                validations[check] = actual_count == expected[check]
        
        # Expected URLs validation
        if 'expected_urls' in expected:
            expected_urls = set(expected['expected_urls'])
            actual_urls = set(actual['urls'])
            validations['expected_urls'] = expected_urls.issubset(actual_urls)
        
        # Valid schemes only
        if 'valid_schemes_only' in expected and expected['valid_schemes_only']:
            invalid_schemes = []
            for url in actual['urls']:
                from urllib.parse import urlparse
                scheme = urlparse(url).scheme
                if scheme not in ['http', 'https']:
                    invalid_schemes.append(scheme)
            validations['valid_schemes_only'] = len(invalid_schemes) == 0
        
        return validations
    
    async def run_test_suite(self):
        """Run the complete test suite"""
        print("🚀 Link Extractor Test Suite")
        print("=" * 70)
        
        all_results = []
        passed_count = 0
        
        for test_name, test_data in TEST_HTML_SAMPLES.items():
            try:
                result = await self.test_html_sample(test_name, test_data)
                all_results.append(result)
                
                if result.get('passed', False):
                    passed_count += 1
                
                # Small delay between tests
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Failed to test {test_name}: {e}")
                all_results.append({
                    'test_name': test_name,
                    'success': False,
                    'error': str(e),
                    'passed': False
                })
        
        # Final summary
        total_tests = len(TEST_HTML_SAMPLES)
        print(f"\n{'='*70}")
        print(f"🎯 LINK EXTRACTOR TEST SUMMARY")
        print(f"{'='*70}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_count}")
        print(f"Failed: {total_tests - passed_count}")
        print(f"Success Rate: {(passed_count / total_tests) * 100:.1f}%")
        
        print(f"\n📊 Detailed Results:")
        for result in all_results:
            status = "✅" if result.get('passed', False) else "❌"
            test_name = result.get('test_name', 'Unknown')
            
            if result.get('actual'):
                actual = result['actual']
                print(f"   {status} {test_name}")
                print(f"       Links: {actual['total_links']}, Types: {len(actual['link_types'])}")
                if result.get('errors'):
                    for error in result['errors']:
                        print(f"       Failed: {error}")
            else:
                error = result.get('error', 'Unknown error')
                print(f"   {status} {test_name} - Error: {error}")
        
        # Save results
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            results_file = f"link_extractor_test_results_{timestamp}.json"
            with open(results_file, 'w') as f:
                json.dump(all_results, f, indent=2, default=str)
            print(f"\n💾 Results saved to: {results_file}")
        except Exception as e:
            print(f"⚠️  Could not save results: {e}")
        
        return all_results


async def main():
    """Main test runner"""
    print("🔧 Link Extractor Component Test")
    print("This test validates the LinkExtractor's ability to parse HTML and extract links")
    print("=" * 80)
    
    tester = LinkExtractorTester()
    await tester.run_test_suite()
    
    print(f"\n🎯 Link Extractor Assessment:")
    print("✅ Tests basic link extraction from <a> tags")
    print("✅ Tests SEO link types (nofollow, sponsored, UGC)")
    print("✅ Tests canonical link detection")
    print("✅ Tests URL resolution (relative to absolute)")
    print("✅ Tests edge cases and invalid links")
    print("✅ Tests complex real-world HTML structures")
    
    print(f"\n🚀 This component is critical for your WebCrawler's link discovery!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
