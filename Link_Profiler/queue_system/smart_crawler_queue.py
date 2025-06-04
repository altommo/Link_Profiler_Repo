"""
ML-Enhanced Adaptive Rate Limiter
Learns optimal crawling patterns for each domain
"""

import asyncio
import time
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
import logging

logger = logging.getLogger(__name__)

@dataclass
class DomainProfile:
    """ML-based profile for a domain's crawling characteristics"""
    domain: str
    request_history: deque = field(default_factory=lambda: deque(maxlen=100))
    response_times: deque = field(default_factory=lambda: deque(maxlen=50))
    success_rate: float = 1.0
    optimal_delay: float = 1.0
    last_updated: float = field(default_factory=time.time)
    
    # ML features
    avg_response_time: float = 0.0
    p95_response_time: float = 0.0
    error_rate: float = 0.0
    server_load_indicator: float = 0.0

class ResponseAnalyzer:
    """Analyzes server responses to detect load and adjust timing"""
    
    def extract_signals(self, crawl_result) -> Dict[str, float]:
        """Extract ML features from crawl result"""
        signals = {
            'response_time': crawl_result.crawl_time_ms / 1000.0,
            'content_length': len(crawl_result.content) if crawl_result.content else 0,
            'status_code': crawl_result.status_code,
            'is_success': 1.0 if 200 <= crawl_result.status_code < 400 else 0.0,
            'server_time': self._extract_server_time(crawl_result),
            'content_encoding': self._analyze_content_encoding(crawl_result)
        }
        return signals
    
    def _extract_server_time(self, result) -> float:
        """Extract server processing time from headers"""
        if hasattr(result, 'headers') and result.headers:
            # Look for common server timing headers
            timing_headers = ['X-Response-Time', 'X-Runtime', 'Server-Timing']
            for header in timing_headers:
                if header in result.headers:
                    try:
                        return float(result.headers[header].split()[0])
                    except (ValueError, IndexError):
                        continue
        return 0.0
    
    def _analyze_content_encoding(self, result) -> float:
        """Analyze content encoding efficiency"""
        if hasattr(result, 'headers') and result.headers:
            encoding = result.headers.get('Content-Encoding', '')
            if 'gzip' in encoding or 'br' in encoding:
                return 1.0  # Compressed content indicates efficient server
        return 0.5

class MLRateLimiter:
    """Machine Learning enhanced rate limiter"""
    
    def __init__(self):
        self.domain_profiles: Dict[str, DomainProfile] = {}
        self.response_analyzer = ResponseAnalyzer()
        self.global_config = {
            'min_delay': 0.1,
            'max_delay': 30.0,
            'learning_rate': 0.1,
            'aggression_factor': 0.8  # How aggressive to be with optimization
        }
    
    def get_domain_profile(self, domain: str) -> DomainProfile:
        """Get or create domain profile"""
        if domain not in self.domain_profiles:
            self.domain_profiles[domain] = DomainProfile(domain=domain)
        return self.domain_profiles[domain]
    
    async def adaptive_wait(self, domain: str, last_response=None):
        """ML-enhanced adaptive waiting"""
        profile = self.get_domain_profile(domain)
        
        if last_response:
            # Update profile with new data
            self._update_profile(profile, last_response)
        
        # Calculate optimal delay using ML model
        optimal_delay = self._predict_optimal_delay(profile)
        
        # Apply server stress detection
        if last_response and self._detect_server_stress(last_response):
            optimal_delay *= 1.5
            logger.info(f"Server stress detected for {domain}, increasing delay to {optimal_delay:.2f}s")
        
        # Ensure delay is within bounds
        optimal_delay = max(self.global_config['min_delay'], 
                          min(optimal_delay, self.global_config['max_delay']))
        
        await asyncio.sleep(optimal_delay)
        profile.last_updated = time.time()
    
    def _update_profile(self, profile: DomainProfile, response):
        """Update domain profile with new response data"""
        signals = self.response_analyzer.extract_signals(response)
        
        # Add to history
        profile.request_history.append({
            'timestamp': time.time(),
            'response_time': signals['response_time'],
            'success': signals['is_success'],
            'status_code': signals['status_code']
        })
        
        profile.response_times.append(signals['response_time'])
        
        # Update statistics
        if profile.response_times:
            profile.avg_response_time = np.mean(profile.response_times)
            profile.p95_response_time = np.percentile(profile.response_times, 95)
        
        # Update success rate
        recent_requests = list(profile.request_history)[-20:]  # Last 20 requests
        if recent_requests:
            profile.success_rate = sum(r['success'] for r in recent_requests) / len(recent_requests)
            profile.error_rate = 1.0 - profile.success_rate
    
    def _predict_optimal_delay(self, profile: DomainProfile) -> float:
        """Use lightweight ML model to predict optimal delay"""
        # Simple linear regression model based on key features
        base_delay = 1.0
        
        # Factor in response time (slower server = longer delay)
        if profile.avg_response_time > 0:
            response_factor = min(profile.avg_response_time / 2.0, 3.0)
            base_delay *= (1.0 + response_factor * 0.3)
        
        # Factor in success rate (lower success = longer delay)
        if profile.success_rate < 0.9:
            error_factor = (1.0 - profile.success_rate) * 5.0
            base_delay *= (1.0 + error_factor)
        
        # Factor in server load
        if profile.p95_response_time > profile.avg_response_time * 2:
            load_factor = 1.5
            base_delay *= load_factor
        
        # Apply learning - gradually optimize based on success
        if profile.success_rate > 0.95 and profile.avg_response_time < 2.0:
            # Server is happy, we can be more aggressive
            base_delay *= self.global_config['aggression_factor']
        
        return base_delay
    
    def _detect_server_stress(self, response) -> bool:
        """Detect if server is under stress"""
        if not response:
            return False
        
        stress_indicators = [
            response.status_code in [429, 503, 504],  # Rate limit or server error
            response.crawl_time_ms > 10000,  # Very slow response
            hasattr(response, 'headers') and 'Retry-After' in response.headers
        ]
        
        return any(stress_indicators)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics for all domains"""
        stats = {}
        for domain, profile in self.domain_profiles.items():
            stats[domain] = {
                'success_rate': profile.success_rate,
                'avg_response_time': profile.avg_response_time,
                'optimal_delay': profile.optimal_delay,
                'requests_count': len(profile.request_history),
                'last_updated': profile.last_updated
            }
        return stats