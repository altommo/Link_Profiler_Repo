import asyncio
import logging
from Link_Profiler.clients.wayback_machine_client import WaybackClient
from Link_Profiler.services.ai_service import AIService
from Link_Profiler.utils.content_validator import ContentValidator
from Link_Profiler.utils.proxy_manager import proxy_manager
# Assuming session_manager is available globally or passed via dependency injection
from Link_Profiler.utils.session_manager import session_manager 
from Link_Profiler.config.env_config import EnvironmentConfig

async def comprehensive_website_analysis(url: str):
    """
    Complete example of website analysis using real implementations.
    """
    print(f"🔍 Starting comprehensive analysis of: {url}")
    
    # Initialize components
    validator = ContentValidator()
    results = {}
    
    # Test proxy system
    print("📡 Testing proxy system...")
    proxy_stats = proxy_manager.get_proxy_stats()
    print(f"Proxy stats: {proxy_stats}")
    
    # Historical analysis with Wayback Machine
    print("🕐 Fetching historical snapshots...")
    async with WaybackClient(session_manager=session_manager) as wayback: # Pass session_manager
        snapshots = await wayback.get_snapshots(url, limit=5)
        results['historical_snapshots'] = len(snapshots)
        
        if snapshots:
            print(f"Found {len(snapshots)} historical snapshots")
            latest = snapshots[-1]
            print(f"Latest snapshot: {latest.timestamp_iso}")
        else:
            print("No historical snapshots found")
    
    # Content analysis
    print("📄 Analyzing current content...")
    async with session_manager:
        try:
            async with session_manager.get(url, timeout=30) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Validate content quality
                    quality_analysis = validator.validate_content_quality(content, url)
                    results['content_quality'] = quality_analysis
                    
                    print(f"Content quality score: {quality_analysis['quality_score']}/100")
                    print(f"Word count: {quality_analysis['word_count']}")
                    print(f"Readability score: {quality_analysis['readability_score']}/100")
                    
                    if quality_analysis['issues']:
                        print(f"Issues found: {', '.join(quality_analysis['issues'])}")
                else:
                    print(f"Failed to fetch content: HTTP {response.status}")
                    
        except Exception as e:
            print(f"Error fetching content: {e}")
    
    # AI-powered analysis (if enabled)
    print("🤖 Running AI analysis...")
    async with AIService(session_manager=session_manager) as ai_service: # Pass session_manager
        if ai_service.enabled:
            try:
                # Content scoring
                ai_analysis = await ai_service.score_content(content[:4000], "website analysis")
                results['ai_analysis'] = ai_analysis
                
                print(f"AI SEO score: {ai_analysis.get('seo_score', 'N/A')}/100")
                print(f"AI readability: {ai_analysis.get('readability_score', 'N/A')}/100")
                
                # Content classification
                classification = await ai_service.classify_content(content[:2000], "general")
                if classification:
                    print(f"Content classification: {classification}")
                    
            except Exception as e:
                print(f"AI analysis error: {e}")
        else:
            print("AI service disabled - skipping AI analysis")
    
    # Summary report
    print("\n📊 ANALYSIS SUMMARY")
    print("=" * 50)
    print(f"URL: {url}")
    print(f"Historical snapshots: {results.get('historical_snapshots', 0)}")
    
    if 'content_quality' in results:
        cq = results['content_quality']
        print(f"Content quality: {cq['quality_score']}/100")
        print(f"Content length: {cq['word_count']} words")
        print(f"Spam score: {cq['spam_score']}/100")
    
    if 'ai_analysis' in results:
        ai = results['ai_analysis']
        print(f"AI SEO score: {ai.get('seo_score', 'N/A')}/100")
        print(f"Semantic keywords: {len(ai.get('semantic_keywords', []))}")
    
    return results

async def run_system_validation():
    """
    Run comprehensive system validation to ensure all implementations work.
    """
    print("🧪 Running system validation...")
    
    # Test environment configuration
    print("1. Testing environment configuration...")
    try:
        missing_vars = EnvironmentConfig.validate_required_vars()
        if missing_vars:
            print(f"❌ Missing required environment variables: {missing_vars}")
        else:
            print("✅ All required environment variables are set")
    except Exception as e:
        print(f"❌ Environment validation error: {e}")
    
    # Test proxy system
    print("2. Testing proxy system...")
    try:
        if proxy_manager.use_proxies:
            stats = proxy_manager.get_proxy_stats()
            print(f"✅ Proxy system: {stats['active']}/{stats['total']} proxies active")
        else:
            print("✅ Proxy system disabled (as configured)")
    except Exception as e:
        print(f"❌ Proxy system error: {e}")
    
    # Test content validator
    print("3. Testing content validator...")
    try:
        validator = ContentValidator()
        test_content = "This is a test article about web development and SEO optimization."
        result = validator.validate_content_quality(test_content, "http://test.com")
        print(f"✅ Content validator: Score {result['quality_score']}/100")
    except Exception as e:
        print(f"❌ Content validator error: {e}")
    
    # Test Wayback client
    print("4. Testing Wayback Machine client...")
    try:
        async with WaybackClient(session_manager=session_manager) as wayback: # Pass session_manager
            if wayback.enabled:
                # Test with a known URL
                snapshots = await wayback.get_snapshots("http://example.com", limit=1)
                print(f"✅ Wayback client: Found {len(snapshots)} snapshots")
            else:
                print("✅ Wayback client disabled (as configured)")
    except Exception as e:
        print(f"❌ Wayback client error: {e}")
    
    # Test AI service
    print("5. Testing AI service...")
    try:
        async with AIService(session_manager=session_manager) as ai_service: # Pass session_manager
            if ai_service.enabled:
                # Test basic functionality
                keywords = await ai_service.suggest_semantic_keywords("technology")
                print(f"✅ AI service: Generated {len(keywords)} semantic keywords")
            else:
                print("✅ AI service disabled (as configured)")
    except Exception as e:
        print(f"❌ AI service error: {e}")
    
    print("\n🎉 System validation completed!")

# Example usage
async def main():
    """Main example function."""
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Run system validation
    await run_system_validation()
    
    print("\n" + "="*60)
    
    # Run comprehensive analysis
    test_url = "https://example.com"
    results = await comprehensive_website_analysis(test_url)
    
    print(f"\n✅ Analysis completed! Results: {len(results)} sections analyzed")

if __name__ == "__main__":
    asyncio.run(main())
