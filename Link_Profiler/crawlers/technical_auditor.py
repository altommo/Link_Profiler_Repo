"""
Technical Auditor - Runs Lighthouse audits on URLs.
File: Link_Profiler/crawlers/technical_auditor.py
"""

import asyncio
import logging
import json
from typing import List, Dict, Any, Optional
import os

from Link_Profiler.core.models import SEOMetrics, CrawlConfig # Absolute import

logger = logging.getLogger(__name__)

class TechnicalAuditor:
    """
    Runs technical audits on web pages using Google Lighthouse CLI.
    Requires Node.js and Lighthouse CLI to be installed on the system.
    """
    def __init__(self, lighthouse_path: str = "lighthouse"):
        self.logger = logging.getLogger(__name__)
        self.lighthouse_path = lighthouse_path # Store the path to the lighthouse executable

    async def __aenter__(self):
        """No specific async setup needed for this class."""
        self.logger.info("Entering TechnicalAuditor context.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """No specific async cleanup needed for this class."""
        self.logger.info("Exiting TechnicalAuditor context.")
        pass

    async def run_lighthouse_audit(self, url: str, config: CrawlConfig) -> Optional[SEOMetrics]:
        """
        Runs a Lighthouse audit for a given URL and extracts key SEO-related metrics.
        
        Args:
            url: The URL to audit.
            config: The CrawlConfig, potentially containing user_agent or other relevant settings.
            
        Returns:
            An SEOMetrics object populated with Lighthouse audit results, or None if audit fails.
        """
        self.logger.info(f"Running Lighthouse audit for: {url}")
        
        # Define the command to run Lighthouse CLI
        # --output=json: output results as JSON
        # --output-path=stdout: print JSON to stdout
        # --chrome-flags="--headless --disable-gpu": run Chrome in headless mode
        # --quiet: suppress Lighthouse console output
        # --max-wait-for-load=15000: max wait time for page load in ms
        # --emulated-form-factor=mobile: run audit as mobile (can be desktop)
        # --throttling-method=simulate: simulate network/CPU throttling
        
        # Use user_agent from config if available, otherwise default
        user_agent_flag = f'--emulated-user-agent="{config.user_agent}"' if config.user_agent else ''

        command = [
            self.lighthouse_path, # Use the stored lighthouse_path
            url,
            '--output=json',
            '--output-path=stdout',
            '--chrome-flags="--headless --disable-gpu --no-sandbox"', # --no-sandbox for Docker environments
            '--quiet',
            f'--max-wait-for-load={config.timeout_seconds * 1000}',
            '--emulated-form-factor=mobile', # Default to mobile audit
            '--throttling-method=simulate',
            user_agent_flag
        ]
        
        # Filter out empty strings from command list
        command = [arg for arg in command if arg]

        process = None
        try:
            # Run the command
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                self.logger.error(f"Lighthouse audit failed for {url} with exit code {process.returncode}.")
                self.logger.error(f"Lighthouse stderr: {stderr.decode(errors='ignore')}")
                return None

            # Parse the JSON output
            audit_result = json.loads(stdout.decode(errors='ignore'))
            
            # Extract relevant metrics
            metrics = SEOMetrics(url=url, audit_timestamp=datetime.now())
            
            # Performance Score
            metrics.performance_score = audit_result['categories']['performance']['score'] * 100 if 'performance' in audit_result['categories'] else None
            
            # Accessibility Score
            metrics.accessibility_score = audit_result['categories']['accessibility']['score'] * 100 if 'accessibility' in audit_result['categories'] else None
            
            # Mobile Friendly (Lighthouse doesn't give a direct boolean, but performance/accessibility on mobile form factor implies it)
            # We can infer mobile-friendliness if the audit was run on mobile and scores are good.
            # For simplicity, we'll set it to True if performance/accessibility scores are above a threshold.
            metrics.mobile_friendly = (metrics.performance_score is not None and metrics.performance_score >= 70) or \
                                      (metrics.accessibility_score is not None and metrics.accessibility_score >= 70)
            
            # Basic SEO checks (Lighthouse has an SEO category, but it's more about best practices than on-page content)
            # These would typically be populated by ContentParser.
            # However, if Lighthouse is the primary source, we can try to map some.
            # For now, we'll rely on ContentParser for these, and Lighthouse for performance/accessibility.
            
            # Example of extracting an issue:
            if 'audits' in audit_result:
                # Example: Check for 'uses-http2' audit
                http2_audit = audit_result['audits'].get('uses-http2')
                if http2_audit and not http2_audit.get('score', 0) > 0:
                    metrics.issues.append("Page does not use HTTP/2 for all resources.")
                
                # Example: Check for 'viewport' audit
                viewport_audit = audit_result['audits'].get('viewport')
                if viewport_audit and not viewport_audit.get('score', 0) > 0:
                    metrics.issues.append("Page does not have a <meta name='viewport'> tag with width or initial-scale.")

            metrics.calculate_seo_score() # Recalculate overall SEO score including Lighthouse data
            
            self.logger.info(f"Lighthouse audit for {url} completed. Performance: {metrics.performance_score:.1f}, Accessibility: {metrics.accessibility_score:.1f}")
            return metrics

        except FileNotFoundError:
            self.logger.error(f"Lighthouse CLI not found at '{self.lighthouse_path}'. Please ensure Node.js and Lighthouse are installed and in PATH, or provide correct path.")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Lighthouse JSON output for {url}: {e}")
            self.logger.error(f"Raw stdout: {stdout.decode(errors='ignore')}")
            return None
        except asyncio.TimeoutError:
            self.logger.error(f"Lighthouse audit timed out for {url} after {config.timeout_seconds} seconds.")
            return None
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during Lighthouse audit for {url}: {e}", exc_info=True)
            return None
        finally:
            if process and process.returncode is None:
                self.logger.warning(f"Lighthouse process for {url} is still running. Terminating.")
                process.terminate()
                await process.wait()

# Example usage (for testing)
async def main():
    logging.basicConfig(level=logging.INFO)
    
    # Ensure Lighthouse is installed: npm install -g lighthouse
    # And Node.js is in your PATH
    
    test_url = "https://www.google.com"
    test_config = CrawlConfig(timeout_seconds=60, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    
    async with TechnicalAuditor() as auditor: # Default lighthouse_path is "lighthouse"
        metrics = await auditor.run_lighthouse_audit(test_url, test_config)
        if metrics:
            print(f"\n--- Lighthouse Audit Results for {test_url} ---")
            print(f"Performance Score: {metrics.performance_score:.1f}")
            print(f"Accessibility Score: {metrics.accessibility_score:.1f}")
            print(f"Mobile Friendly: {metrics.mobile_friendly}")
            print(f"Overall SEO Score (incl. Lighthouse): {metrics.seo_score:.1f}")
            if metrics.issues:
                print("Issues:")
                for issue in metrics.issues:
                    print(f"- {issue}")
        else:
            print(f"Lighthouse audit failed for {test_url}.")

if __name__ == "__main__":
    asyncio.run(main())
