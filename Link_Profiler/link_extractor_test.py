#!/usr/bin/env python3
"""
Link Extractor Test Suite (Using Real LinkExtractor)
Tests the LinkExtractor component against known HTML samples with updated expectations.
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional

# Ensure current directory is in path to import link_extractor
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from link_extractor import LinkExtractor, Backlink, LinkType
from urllib.parse import urlparse

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
            "total_links": 6,  # 5 <a> + 1 canonical
            "sponsored_links": 1,  # only pure sponsored
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
            "total_links": 8,  # 7 <a> + 1 canonical
            "external_links": 2,
            "internal_links": 6,
            "sponsored_links": 0,  # no pure sponsored
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
            "total_links": 4,  # Only valid HTTP/HTTPS links
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


class LinkExtractorTester:
    """Test suite for the real LinkExtractor"""
    def __init__(self):
        self.test_results: List[Dict[str, Any]] = []
        self.extractor = LinkExtractor()

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
            # Extract links using real LinkExtractor
            links: List[Backlink] = await self.extractor.extract_links(
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
                test_result['errors'] = [k for k, v in validations.items() if not v]

        except Exception as e:
            error_msg = f"Exception during extraction: {str(e)}"
            test_result['errors'] = [error_msg]
            print(f"❌ {error_msg}")

        # Print validation results
        print(f"\n📋 Validation:")
        for check, passed in test_result['validations'].items():
            status = "✅" if passed else "❌"
            print(f"   {status} {check}")

        overall_status = "✅ PASSED" if test_result['passed'] else "❌ FAILED"
        print(f"\n{overall_status}")

        return test_result

    def _analyze_links(self, links: List[Backlink], base_url: str) -> Dict[str, Any]:
        """Analyze extracted links"""
        base_domain = urlparse(base_url).netloc
        analysis: Dict[str, Any] = {
            'total_links': len(links),
            'external_links': 0,
            'internal_links': 0,
            'link_types': {},
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
            lt = link.link_type
            analysis['link_types'][lt] = analysis['link_types'].get(lt, 0) + 1

        return analysis

    def _validate_results(self, actual: Dict[str, Any], expected: Dict[str, Any]) -> Dict[str, bool]:
        """Validate actual vs expected results"""
        validations: Dict[str, bool] = {}

        # total_links
        if 'total_links' in expected:
            validations['total_links'] = actual['total_links'] == expected['total_links']

        # external_links
        if 'external_links' in expected:
            validations['external_links'] = actual['external_links'] == expected['external_links']

        # internal_links
        if 'internal_links' in expected:
            validations['internal_links'] = actual['internal_links'] == expected['internal_links']

        # link type counts
        type_checks = {
            'follow_links': LinkType.FOLLOW,
            'nofollow_links': LinkType.NOFOLLOW,
            'sponsored_links': LinkType.SPONSORED,
            'ugc_links': LinkType.UGC,
            'canonical_links': LinkType.CANONICAL
        }
        for check, lt in type_checks.items():
            if check in expected:
                count = actual['link_types'].get(lt, 0)
                validations[check] = count == expected[check]

        # expected_urls
        if 'expected_urls' in expected:
            validations['expected_urls'] = set(expected['expected_urls']).issubset(set(actual['urls']))

        # valid_schemes_only
        if expected.get('valid_schemes_only'):
            invalid = False
            for url in actual['urls']:
                scheme = urlparse(url).scheme
                if scheme not in ['http', 'https']:
                    invalid = True
                    break
            validations['valid_schemes_only'] = not invalid

        return validations

    async def run_test_suite(self) -> List[Dict[str, Any]]:
        """Run the complete test suite"""
        print("🚀 Link Extractor Test Suite")
        print("=" * 70)

        all_results: List[Dict[str, Any]] = []
        passed_count = 0

        for test_name, test_data in TEST_HTML_SAMPLES.items():
            try:
                result = await self.test_html_sample(test_name, test_data)
                all_results.append(result)
                if result.get('passed'):
                    passed_count += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"❌ Failed to test {test_name}: {e}")
                all_results.append({'test_name': test_name, 'passed': False, 'error': str(e)})

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
            status = "✅" if result.get('passed') else "❌"
            name = result.get('test_name', 'Unknown')
            print(f"   {status} {name}: Links={result.get('actual', {}).get('total_links', 'N/A')}, Types={len(result.get('actual', {}).get('link_types', {}))}")
            if result.get('errors'):
                for err in result['errors']:
                    print(f"       Failed: {err}")

        try:
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            fname = f"link_extractor_test_results_{ts}.json"
            with open(fname, 'w') as f:
                json.dump(all_results, f, indent=2, default=str)
            print(f"\n💾 Results saved to: {fname}")
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