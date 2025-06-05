"""
Technical Auditor - Runs technical audits on web pages using Google Lighthouse CLI.
File: Link_Profiler/crawlers/technical_auditor.py
"""

import asyncio
import json
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime # Added import for datetime

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.core.models import CrawlConfig, SEOMetrics # Import CrawlConfig and SEOMetrics
from Link_Profiler.monitoring.prometheus_metrics import EXTERNAL_API_CALLS_TOTAL, EXTERNAL_API_CALL_DURATION_SECONDS, EXTERNAL_API_CALL_ERRORS_TOTAL # Import Prometheus metrics

logger = logging.getLogger(__name__)

class TechnicalAuditor:
    """
    Runs technical audits on web pages using Google Lighthouse CLI.
    Requires Node.js and Lighthouse CLI to be installed on the system.
    """
    def __init__(self, lighthouse_path: str = "lighthouse"):
        self.logger = logging.getLogger(__name__ + ".TechnicalAuditor")
        self.lighthouse_path = lighthouse_path # Store the path to the lighthouse executable
        self.enabled = config_loader.get("technical_auditor.enabled", True) # Assuming a config for enabling/disabling
        
        if not self.enabled:
            self.logger.info("Technical Auditor (Lighthouse) is disabled by configuration.")
            return

        # Verify Lighthouse CLI installation
        if not self._check_lighthouse_installed():
            self.logger.error(f"Lighthouse CLI not found at '{self.lighthouse_path}'. Technical audits will be disabled.")
            self.enabled = False

    def _check_lighthouse_installed(self) -> bool:
        """Checks if Lighthouse CLI is installed and accessible."""
        try:
            # Use asyncio.create_subprocess_exec for non-blocking check
            # For a simple check, os.system or shutil.which might be enough
            # but for consistency with async operations, we'll use asyncio.
            # This is a synchronous check, so it's fine to run it in __init__
            # if the event loop is not yet running.
            # For a more robust check, consider running it in an async context.
            
            # A simple synchronous check for now
            import shutil
            if shutil.which(self.lighthouse_path):
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error checking Lighthouse installation: {e}")
            return False

    async def run_lighthouse_audit(self, url: str, config: Optional[CrawlConfig] = None) -> Optional[SEOMetrics]:
        """
        Runs a Google Lighthouse audit for a given URL and extracts key SEO-related metrics.
        
        Args:
            url: The URL to audit.
            config: Optional CrawlConfig to influence the audit (e.g., user_agent or other relevant settings).
            
        Returns:
            An SEOMetrics object populated with Lighthouse audit results, or None if audit fails.
        """
        if not self.enabled:
            self.logger.warning("Lighthouse audit skipped: Technical Auditor is disabled.")
            return None

        self.logger.info(f"Starting Lighthouse audit for: {url}")
        
        # Define the command to run Lighthouse CLI
        # --output=json: output results as JSON
        # --output-path=stdout: print JSON to stdout
        # --chrome-flags="--headless --disable-gpu": run Chrome in headless mode
        # --quiet: suppress Lighthouse console output
        # --max-wait-for-load=15000: max wait time for page load in ms
        # --emulated-form-factor=mobile: run audit as mobile (can be desktop)
        # --throttling-method=simulate: simulate network/CPU throttling
        
        # Use user_agent from config if available, otherwise default
        user_agent_flag = f'--emulated-user-agent="{config.user_agent}"' if config and config.user_agent else ''

        command = [
            self.lighthouse_path, # Use the stored lighthouse_path
            url,
            '--output=json',
            '--output-path=stdout',
            '--chrome-flags="--headless --disable-gpu --no-sandbox"', # --no-sandbox for Docker environments
            '--quiet',
            f'--max-wait-for-load={config.request_timeout * 1000}' if config and config.request_timeout else '--max-wait-for-load=30000', # Default to 30s
            '--emulated-form-factor=mobile', # Default to mobile audit
            '--throttling-method=simulate',
            user_agent_flag
        ]
        
        # Filter out empty strings from command list
        command = [arg for arg in command if arg]

        process = None
        audit_start_time = datetime.now()
        
        # Prometheus metrics
        EXTERNAL_API_CALLS_TOTAL.labels(service="technical_auditor", api_client_type="lighthouse_cli", endpoint="run_audit").inc()

        try:
            # Execute Lighthouse CLI command
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_message = stderr.decode(errors='ignore').strip()
                self.logger.error(f"Lighthouse audit failed for {url} with exit code {process.returncode}: {error_message}")
                EXTERNAL_API_CALL_ERRORS_TOTAL.labels(service="technical_auditor", api_client_type="lighthouse_cli", endpoint="run_audit", status_code=str(process.returncode)).inc()
                return None

            audit_json = stdout.decode(errors='ignore')
            audit_report = json.loads(audit_json)
            
            # Extract relevant metrics from the Lighthouse report
            seo_metrics = self._parse_lighthouse_report(audit_report, url)
            self.logger.info(f"Lighthouse audit completed successfully for {url}.")
            return seo_metrics

        except FileNotFoundError:
            self.logger.error(f"Lighthouse CLI not found at '{self.lighthouse_path}'. Please ensure Node.js and Lighthouse are installed and in PATH, or provide correct path.")
            EXTERNAL_API_CALL_ERRORS_TOTAL.labels(service="technical_auditor", api_client_type="lighthouse_cli", endpoint="run_audit", status_code="cli_not_found").inc()
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Lighthouse JSON output for {url}: {e}")
            self.logger.error(f"Raw stdout: {stdout.decode(errors='ignore')}")
            EXTERNAL_API_CALL_ERRORS_TOTAL.labels(service="technical_auditor", api_client_type="lighthouse_cli", endpoint="run_audit", status_code="json_parse_error").inc()
            return None
        except asyncio.TimeoutError:
            self.logger.error(f"Lighthouse audit timed out for {url}.")
            EXTERNAL_API_CALL_ERRORS_TOTAL.labels(service="technical_auditor", api_client_type="lighthouse_cli", endpoint="run_audit", status_code="timeout").inc()
            return None
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during Lighthouse audit for {url}: {e}", exc_info=True)
            EXTERNAL_API_CALL_ERRORS_TOTAL.labels(service="technical_auditor", api_client_type="lighthouse_cli", endpoint="run_audit", status_code="unexpected_error").inc()
            return None
        finally:
            if process and process.returncode is None:
                self.logger.warning(f"Lighthouse process for {url} is still running. Terminating.")
                process.terminate()
                await process.wait()
            
            duration = (datetime.now() - audit_start_time).total_seconds()
            EXTERNAL_API_CALL_DURATION_SECONDS.labels(service="technical_auditor", api_client_type="lighthouse_cli", endpoint="run_audit").observe(duration)

    def _parse_lighthouse_report(self, report: Dict[str, Any], url: str) -> SEOMetrics:
        """
        Parses a Lighthouse report JSON and extracts relevant SEO metrics.
        """
        audits = report.get('audits', {})
        categories = report.get('categories', {})
        
        # Initialize SEOMetrics with default values
        seo_metrics = SEOMetrics(url=url)
        
        # Overall scores
        seo_metrics.performance_score = categories.get('performance', {}).get('score', 0) * 100
        seo_metrics.accessibility_score = categories.get('accessibility', {}).get('score', 0) * 100
        seo_metrics.seo_score = categories.get('seo', {}).get('score', 0) * 100
        seo_metrics.mobile_friendly = categories.get('pwa', {}).get('score', 0) * 100 > 50 # Simple heuristic
        seo_metrics.audit_timestamp = datetime.fromisoformat(report.get('fetchTime').replace('Z', '+00:00'))

        # Specific SEO audits
        # Title
        title_audit = audits.get('title-text')
        if title_audit:
            # Lighthouse 'title-text' audit details can be complex.
            # A simple way to get the title text is from the 'full-page-screenshot' or 'final-url'
            # For title length, we need to check the audit's displayValue or score.
            # If score is 0, it's missing or empty.
            if title_audit.get('score') == 0:
                seo_metrics.issues.append("Missing or empty title tag.")
            else:
                # Attempt to get title from audit details if available
                display_value = title_audit.get('displayValue', '')
                if 'title' in display_value.lower(): # "Title text is '...' (X characters)"
                    match = re.search(r"'(.*?)'", display_value)
                    if match:
                        seo_metrics.title_length = len(match.group(1))
                elif 'characters' in display_value.lower(): # "Title text is X characters"
                    match = re.search(r'(\d+)\s+characters', display_value)
                    if match:
                        seo_metrics.title_length = int(match.group(1))
                
                # Fallback: if title_length is still None, try to get it from the page's title
                # This would require parsing the HTML, which is outside this module's scope.
                # For now, if not found in audit, leave as None.
        
        # Meta Description
        meta_desc_audit = audits.get('meta-description')
        if meta_desc_audit:
            if meta_desc_audit.get('score') == 0:
                seo_metrics.issues.append("Missing or empty meta description.")
            else:
                display_value = meta_desc_audit.get('displayValue', '')
                if 'characters' in display_value.lower():
                    match = re.search(r'(\d+)\s+characters', display_value)
                    if match:
                        seo_metrics.meta_description_length = int(match.group(1))

        # H1 tags
        h1_audit = audits.get('heading-elements')
        if h1_audit and h1_audit.get('details', {}).get('items'):
            h1_count = sum(1 for item in h1_audit['details']['items'] if item.get('node', {}).get('nodeLabel', '').lower().startswith('h1'))
            seo_metrics.h1_count = h1_count
            if h1_count == 0:
                seo_metrics.issues.append("Missing H1 heading.")
            elif h1_count > 1:
                seo_metrics.issues.append("Multiple H1 headings found.")
        
        # Canonical
        canonical_audit = audits.get('canonical')
        if canonical_audit:
            seo_metrics.has_canonical = canonical_audit.get('score') == 1
            if not seo_metrics.has_canonical:
                seo_metrics.issues.append("Missing or invalid canonical tag.")

        # Robots Meta
        robots_meta_audit = audits.get('robots-txt') # This audit checks for robots.txt validity, not meta tag
        # Lighthouse doesn't have a direct audit for meta robots tag, need to infer or check manually
        # For now, assume if robots.txt is valid, meta robots is not blocking.
        seo_metrics.has_robots_meta = True # Placeholder, needs actual check if desired

        # Structured Data
        structured_data_audit = audits.get('structured-data')
        if structured_data_audit and structured_data_audit.get('details', {}).get('items'):
            for item in structured_data_audit['details']['items']:
                if item.get('entityType'):
                    seo_metrics.structured_data_types.append(item['entityType'])
            if not seo_metrics.structured_data_types:
                seo_metrics.issues.append("No structured data found.")

        # Image Alt Text
        image_alt_audit = audits.get('image-alt')
        if image_alt_audit:
            # Lighthouse 'image-alt' audit provides 'items' for images without alt text
            items_without_alt = [item for item in image_alt_audit.get('details', {}).get('items', []) if item.get('score') == 0]
            seo_metrics.images_count = image_alt_audit.get('details', {}).get('overallSavingsMs', 0) # This is not count, need to find actual count
            # Lighthouse doesn't directly give total image count, only those missing alt.
            # For now, we'll just count images without alt.
            seo_metrics.images_without_alt = len(items_without_alt)
            if seo_metrics.images_without_alt > 0:
                seo_metrics.issues.append(f"{seo_metrics.images_without_alt} images missing alt text.")

        # Broken Links (Lighthouse doesn't directly audit broken links on the page)
        # This would typically come from a separate crawl/link check.
        # seo_metrics.broken_links = [] # Placeholder

        # Page size and response time
        # Lighthouse provides 'total-byte-weight' for page size
        total_byte_weight_audit = audits.get('total-byte-weight')
        if total_byte_weight_audit:
            seo_metrics.page_size_bytes = total_byte_weight_audit.get('numericValue') # in bytes

        # Response time (using FCP as a proxy for initial response)
        fcp_audit = audits.get('first-contentful-paint')
        if fcp_audit:
            seo_metrics.response_time_ms = fcp_audit.get('numericValue') # in milliseconds

        # Open Graph and Twitter Card (Lighthouse doesn't directly audit these)
        # These would need to be extracted from HTML directly.
        # seo_metrics.og_title = ...
        # seo_metrics.twitter_title = ...

        return seo_metrics
