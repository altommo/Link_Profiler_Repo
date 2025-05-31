"""
Technical Auditor - Performs technical SEO audits using various tools
File: Link_Profiler/crawlers/technical_auditor.py
"""

import asyncio
import logging
import subprocess
import json
import tempfile
import os
from typing import Optional, Dict, Any
from datetime import datetime

from Link_Profiler.core.models import SEOMetrics, CrawlConfig

logger = logging.getLogger(__name__)

class TechnicalAuditor:
    """
    Performs technical SEO audits using Lighthouse and other tools
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    async def run_lighthouse_audit(self, url: str, config: CrawlConfig) -> Optional[SEOMetrics]:
        """
        Run Lighthouse audit on a URL and return SEO metrics
        """
        try:
            # Create a temporary file for Lighthouse output
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Lighthouse command
            lighthouse_cmd = [
                'lighthouse',
                url,
                '--output=json',
                f'--output-path={temp_path}',
                '--only-categories=performance,accessibility,best-practices,seo',
                '--headless',
                '--no-enable-error-reporting'
            ]
            
            # Run Lighthouse
            process = await asyncio.create_subprocess_exec(
                *lighthouse_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                # Read the JSON output
                with open(temp_path, 'r', encoding='utf-8') as f:
                    lighthouse_data = json.load(f)
                
                # Extract metrics
                categories = lighthouse_data.get('categories', {})
                
                # Create SEO metrics from Lighthouse data
                seo_metrics = SEOMetrics(
                    url=url,
                    performance_score=int(categories.get('performance', {}).get('score', 0) * 100),
                    accessibility_score=int(categories.get('accessibility', {}).get('score', 0) * 100),
                    best_practices_score=int(categories.get('best-practices', {}).get('score', 0) * 100),
                    seo_score=int(categories.get('seo', {}).get('score', 0) * 100),
                    audit_timestamp=datetime.now()
                )
                
                # Extract additional technical metrics if available
                audits = lighthouse_data.get('audits', {})
                
                # Page load time
                if 'first-contentful-paint' in audits:
                    fcp = audits['first-contentful-paint'].get('numericValue', 0)
                    seo_metrics.load_time_ms = fcp
                
                # Page size (approximate)
                if 'total-byte-weight' in audits:
                    total_bytes = audits['total-byte-weight'].get('numericValue', 0)
                    seo_metrics.page_size_kb = total_bytes / 1024
                
                # Mobile friendly check
                if 'viewport' in audits:
                    seo_metrics.mobile_friendly = audits['viewport'].get('score', 0) == 1
                
                # HTTPS check
                if 'is-on-https' in audits:
                    seo_metrics.ssl_enabled = audits['is-on-https'].get('score', 0) == 1
                
                # Meta description
                if 'meta-description' in audits:
                    meta_desc = audits['meta-description'].get('details', {}).get('items', [])
                    if meta_desc and len(meta_desc) > 0:
                        desc_length = len(meta_desc[0].get('description', ''))
                        seo_metrics.description_length = desc_length
                
                # Title tag
                if 'document-title' in audits:
                    title_audit = audits['document-title']
                    if title_audit.get('score') == 1:
                        # Approximate title length (Lighthouse doesn't give exact length)
                        seo_metrics.title_length = 50  # Default assumption
                
                # Images without alt text
                if 'image-alt' in audits:
                    img_alt_audit = audits['image-alt']
                    failing_images = img_alt_audit.get('details', {}).get('items', [])
                    seo_metrics.images_without_alt = len(failing_images)
                
                # Calculate overall SEO score
                seo_metrics.calculate_seo_score()
                
                self.logger.info(f"Lighthouse audit completed for {url}")
                return seo_metrics
                
            else:
                error_msg = stderr.decode('utf-8') if stderr else "Unknown error"
                self.logger.error(f"Lighthouse audit failed for {url}: {error_msg}")
                return None
                
        except FileNotFoundError:
            self.logger.error("Lighthouse is not installed. Please install it with: npm install -g lighthouse")
            return None
        except Exception as e:
            self.logger.error(f"Error running Lighthouse audit for {url}: {e}")
            return None
        finally:
            # Clean up temporary file
            try:
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except:
                pass
    
    async def run_basic_technical_audit(self, url: str, html_content: str) -> SEOMetrics:
        """
        Run a basic technical audit without external tools
        """
        from Link_Profiler.crawlers.content_parser import ContentParser
        
        parser = ContentParser()
        seo_metrics = await parser.parse_seo_metrics(url, html_content)
        
        # Add timestamp
        seo_metrics.audit_timestamp = datetime.now()
        
        return seo_metrics
    
    def check_lighthouse_availability(self) -> bool:
        """
        Check if Lighthouse is available on the system
        """
        try:
            result = subprocess.run(['lighthouse', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
