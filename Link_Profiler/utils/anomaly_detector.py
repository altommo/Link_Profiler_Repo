"""
Anomaly Detector - Detects unusual patterns in crawling and data extraction.
File: Link_Profiler/utils/anomaly_detector.py
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import deque

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.core.models import CrawlResult # Assuming CrawlResult is available

logger = logging.getLogger(__name__)

class AnomalyDetector:
    """
    Detects anomalies in crawl behaviour and content quality based on predefined rules
    and historical data.
    """
    def __init__(self):
        self.logger = logging.getLogger(__name__ + ".AnomalyDetector")
        self.config = config_loader.get("anomaly_detection", {})
        self.enabled = self.config.get("enabled", False)

        # Thresholds (configurable via config.json)
        self.error_rate_threshold = self.config.get("error_rate_threshold", 0.20) # 20% errors
        self.empty_content_threshold = self.config.get("empty_content_threshold", 100) # Bytes
        self.low_link_count_threshold = self.config.get("low_link_count_threshold", 2) # Links
        self.captcha_spike_threshold = self.config.get("captcha_spike_threshold", 3) # Number of CAPTCHAs in a short period
        self.crawl_rate_drop_threshold = self.config.get("crawl_rate_drop_threshold", 0.5) # 50% drop
        self.unexpected_status_codes = self.config.get("unexpected_status_codes", [403, 407, 429, 500, 502, 503, 504])

        # History for real-time detection (per domain or global)
        # For simplicity, using a global deque for recent crawl results to detect spikes
        self.recent_crawl_results: deque[CrawlResult] = deque(maxlen=self.config.get("history_window_size", 100))
        self.recent_captcha_detections: deque[datetime] = deque(maxlen=self.config.get("captcha_window_size", 10)) # Store timestamps of CAPTCHA events

        self.logger.info(f"Anomaly Detector initialized. Enabled: {self.enabled}")

    def detect_anomalies_for_crawl_result(self, result: CrawlResult) -> List[str]:
        """
        Detects anomalies for a single crawl result.
        """
        if not self.enabled:
            return []

        anomalies: List[str] = []

        # 1. High HTTP Error Rate / Unexpected Status Code
        if result.status_code in self.unexpected_status_codes:
            anomalies.append(f"Unexpected HTTP Status Code: {result.status_code}")
        
        # 2. Empty or Very Short Content
        if result.content_type == "text/html" and len(result.content) < self.empty_content_threshold:
            anomalies.append(f"Unusually short content ({len(result.content)} bytes)")

        # 3. Low Link Count (for pages expected to have many links)
        if result.content_type == "text/html" and len(result.links_found) < self.low_link_count_threshold:
            anomalies.append(f"Low number of links found ({len(result.links_found)})")

        # 4. Validation Issues (from ContentValidator)
        if result.validation_issues:
            anomalies.extend([f"Content Validation Issue: {issue}" for issue in result.validation_issues])
            
            # Specific check for CAPTCHA detection
            if any("CAPTCHA detected" in issue for issue in result.validation_issues):
                self.recent_captcha_detections.append(datetime.now())
                anomalies.append("CAPTCHA Detected")

        # Add current result to history for rate-based anomaly detection
        self.recent_crawl_results.append(result)

        # Check for CAPTCHA spike (global over recent history)
        if self.detect_captcha_spike():
            anomalies.append("CAPTCHA Spike Detected")

        # Check for sudden drop in successful crawl rate (global)
        if self.detect_crawl_rate_drop():
            anomalies.append("Crawl Rate Drop Detected")

        if anomalies:
            self.logger.warning(f"Anomalies detected for {result.url}: {anomalies}")
        return anomalies

    def detect_captcha_spike(self) -> bool:
        """
        Detects if there's a sudden spike in CAPTCHA detections within a short window.
        """
        if len(self.recent_captcha_detections) < self.captcha_spike_threshold:
            return False # Not enough data points for a spike

        # Check if all recent CAPTCHA detections happened within a very short time frame
        time_window_seconds = self.config.get("captcha_time_window_seconds", 60) # e.g., 60 seconds
        
        if self.recent_captcha_detections:
            oldest_detection = self.recent_captcha_detections[0]
            newest_detection = self.recent_captcha_detections[-1]
            
            if (newest_detection - oldest_detection).total_seconds() < time_window_seconds:
                self.logger.warning(f"Potential CAPTCHA spike: {len(self.recent_captcha_detections)} CAPTCHAs in {time_window_seconds}s.")
                return True
        return False

    def detect_crawl_rate_drop(self) -> bool:
        """
        Detects a significant drop in successful crawl rate over the recent history.
        This is a simplified heuristic. A real ML model would use time-series analysis.
        """
        if len(self.recent_crawl_results) < self.history_size * 0.5: # Need sufficient history
            return False

        successful_crawls = [r for r in self.recent_crawl_results if 200 <= r.status_code < 400]
        
        # Compare current success rate to an expected baseline or a moving average
        # For simplicity, let's compare the success rate of the last half of the history
        # against the first half.
        
        first_half_success = [r for r in list(self.recent_crawl_results)[:self.history_size // 2] if 200 <= r.status_code < 400]
        second_half_success = [r for r in list(self.recent_crawl_results)[self.history_size // 2:] if 200 <= r.status_code < 400]

        if len(first_half_success) == 0: # Avoid division by zero
            return False # Cannot determine drop if no initial success

        current_success_rate = len(second_half_success) / (self.history_size // 2)
        baseline_success_rate = len(first_half_success) / (self.history_size // 2)

        if baseline_success_rate > 0 and (baseline_success_rate - current_success_rate) / baseline_success_rate > self.crawl_rate_drop_threshold:
            self.logger.warning(f"Crawl rate drop detected: Baseline {baseline_success_rate:.1%} vs Current {current_success_rate:.1%}")
            return True
        
        return False

    def reset_history(self):
        """Resets the internal history of crawl results and captcha detections."""
        self.recent_crawl_results.clear()
        self.recent_captcha_detections.clear()
        self.logger.info("Anomaly Detector history reset.")

# Create a singleton instance
anomaly_detector = AnomalyDetector()
