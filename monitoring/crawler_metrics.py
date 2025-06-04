"""
Comprehensive Monitoring and Metrics for Crawler System
Real-time performance tracking and health monitoring
"""
import time
import asyncio
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

@dataclass
class MetricPoint:
    """Single metric data point"""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)

class Counter:
    """Prometheus-style counter metric"""
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.values: Dict[str, float] = defaultdict(float)

    def inc(self, amount: float = 1.0, labels: Dict[str, str] = None):
        """Increment counter"""
        key = self._labels_to_key(labels or {})
        self.values[key] += amount

    def get(self, labels: Dict[str, str] = None) -> float:
        """Get counter value"""
        key = self._labels_to_key(labels or {})
        return self.values[key]

    def _labels_to_key(self, labels: Dict[str, str]) -> str:
        """Convert labels dict to string key"""
        return json.dumps(sorted(labels.items()))

class Histogram:
    """Histogram metric for tracking distributions"""
    def __init__(self, name: str, description: str = "", buckets: List[float] = None):
        self.name = name
        self.description = description
        self.buckets = buckets or [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, 100.0]
        self.observations: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000)) # Keep recent observations
        self.bucket_counts: Dict[str, Dict[float, int]] = defaultdict(lambda: defaultdict(int))
        self.sum_values: Dict[str, float] = defaultdict(float)
        self.count_values: Dict[str, int] = defaultdict(int)

    def observe(self, value: float, labels: Dict[str, str] = None):
        """Record observation"""
        key = self._labels_to_key(labels or {})
        
        self.observations[key].append(value)
        
        # Update buckets
        for bucket in self.buckets:
            if value <= bucket:
                self.bucket_counts[key][bucket] += 1
        
        # Update sum and count
        self.sum_values[key] += value
        self.count_values[key] += 1

    def get_percentile(self, percentile: float, labels: Dict[str, str] = None) -> float:
        """Get percentile value"""
        key = self._labels_to_key(labels or {})
        if key not in self.observations or not self.observations[key]:
            return 0.0
        
        observations_list = sorted(list(self.observations[key])) # Convert deque to list and sort
        index = int(percentile / 100.0 * len(observations_list))
        return observations_list[min(index, len(observations_list) - 1)]

    def get_average(self, labels: Dict[str, str] = None) -> float:
        """Get average value"""
        key = self._labels_to_key(labels or {})
        if self.count_values[key] == 0:
            return 0.0
        return self.sum_values[key] / self.count_values[key]

    def _labels_to_key(self, labels: Dict[str, str]) -> str:
        return json.dumps(sorted(labels.items()))

class Gauge:
    """Gauge metric for values that can go up and down"""
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.values: Dict[str, float] = defaultdict(float)

    def set(self, value: float, labels: Dict[str, str] = None):
        """Set gauge value"""
        key = self._labels_to_key(labels or {})
        self.values[key] = value

    def inc(self, amount: float = 1.0, labels: Dict[str, str] = None):
        """Increment gauge"""
        key = self._labels_to_key(labels or {})
        self.values[key] += amount

    def dec(self, amount: float = 1.0, labels: Dict[str, str] = None):
        """Decrement gauge"""
        key = self._labels_to_key(labels or {})
        self.values[key] -= amount

    def get(self, labels: Dict[str, str] = None) -> float:
        """Get gauge value"""
        key = self._labels_to_key(labels or {})
        return self.values[key]

    def _labels_to_key(self, labels: Dict[str, str]) -> str:
        return json.dumps(sorted(labels.items()))

class CrawlerMetrics:
    """Comprehensive metrics collection for crawler system"""
    def __init__(self):
        # Request metrics
        self.requests_total = Counter("crawler_requests_total", "Total crawler requests")
        self.requests_failed = Counter("crawler_requests_failed", "Failed crawler requests")
        self.response_time = Histogram("crawler_response_time_seconds", "Response time distribution")
        self.content_size = Histogram("crawler_content_size_bytes", "Content size distribution")
        
        # Queue metrics
        self.queue_size = Gauge("crawler_queue_size", "Current queue size")
        self.queue_wait_time = Histogram("crawler_queue_wait_time_seconds", "Queue wait time")
        
        # Domain metrics
        self.active_domains = Gauge("crawler_active_domains", "Number of active domains")
        self.domain_success_rate = Gauge("crawler_domain_success_rate", "Success rate per domain")
        
        # Resource metrics
        self.active_connections = Gauge("crawler_active_connections", "Active HTTP connections")
        self.memory_usage = Gauge("crawler_memory_usage_bytes", "Memory usage")
        self.cpu_usage = Gauge("crawler_cpu_usage_percent", "CPU usage percentage")
        
        # Business metrics
        self.links_discovered = Counter("crawler_links_discovered_total", "Total links discovered")
        self.pages_crawled = Counter("crawler_pages_crawled_total", "Total pages crawled")
        self.data_extracted = Counter("crawler_data_extracted_total", "Total data points extracted")
        
        # Error tracking
        self.error_types = Counter("crawler_errors_by_type", "Errors by type")
        self.circuit_breaker_state = Gauge("crawler_circuit_breaker_state", "Circuit breaker states")
        
        # Performance tracking
        self.throughput_rps = Gauge("crawler_throughput_rps", "Requests per second")
        self.efficiency_score = Gauge("crawler_efficiency_score", "Overall efficiency score")
        
        # Internal tracking
        self.domains_crawled: Set[str] = set()
        self.start_time = time.time()
        self.last_metrics_update = time.time()
        self.request_times = deque(maxlen=1000)  # For throughput calculation

    async def track_request_start(self, url: str, metadata: Dict[str, Any] = None):
        """Track start of request"""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        
        labels = {'domain': domain}
        if metadata:
            labels.update({k: str(v) for k, v in metadata.items() if k in ['job_id', 'priority']})
        
        self.requests_total.inc(labels=labels)
        self.domains_crawled.add(domain)
        self.active_domains.set(len(self.domains_crawled))
        
        return {
            'start_time': time.time(),
            'domain': domain,
            'labels': labels
        }

    async def track_request_complete(self, url: str, response: Any, request_context: Dict):
        """Track completion of request"""
        end_time = time.time()
        duration = end_time - request_context['start_time']
        domain = request_context['domain']
        labels = request_context['labels']
        
        # Track response time
        self.response_time.observe(duration, labels=labels)
        
        # Track content size
        if hasattr(response, 'content') and response.content:
            content_size = len(response.content) if isinstance(response.content, bytes) else len(response.content.encode('utf-8'))
            self.content_size.observe(content_size, labels=labels)
        
        # Track success/failure
        if response.error_message:
            self.requests_failed.inc(labels={**labels, 'error_type': 'request_error'})
            self.error_types.inc(labels={'type': 'request_error', 'domain': domain})
        elif response.status_code >= 400:
            error_type = f"http_{response.status_code}"
            self.requests_failed.inc(labels={**labels, 'error_type': error_type})
            self.error_types.inc(labels={'type': error_type, 'domain': domain})
        
        # Track links discovered
        if hasattr(response, 'links_found') and response.links_found:
            self.links_discovered.inc(len(response.links_found), labels=labels)
        
        # Track pages crawled
        if not response.error_message and 200 <= response.status_code < 400:
            self.pages_crawled.inc(labels=labels)
        
        # Update throughput tracking
        self.request_times.append(end_time)
        self._update_throughput()

    async def track_queue_metrics(self, queue_stats: Dict[str, Any]):
        """Track queue-related metrics"""
        self.queue_size.set(queue_stats.get('queue_size', 0))
        
        # Track per-domain queue metrics
        if 'domains' in queue_stats:
            for domain, domain_stats in queue_stats['domains'].items():
                domain_labels = {'domain': domain}
                self.queue_size.set(domain_stats.get('queue_size', 0), labels=domain_labels)

    async def track_circuit_breaker_state(self, domain: str, state: str):
        """Track circuit breaker state changes"""
        state_value = {'closed': 0, 'half_open': 1, 'open': 2}.get(state.lower(), 3)
        self.circuit_breaker_state.set(state_value, labels={'domain': domain})

    async def track_resource_usage(self):
        """Track system resource usage"""
        try:
            import psutil
            process = psutil.Process()
            
            # Memory usage
            memory_info = process.memory_info()
            self.memory_usage.set(memory_info.rss)
            
            # CPU usage
            cpu_percent = process.cpu_percent(interval=None) # Non-blocking call
            self.cpu_usage.set(cpu_percent)
            
        except ImportError:
            logger.warning("psutil not available for resource monitoring")
        except Exception as e:
            logger.error(f"Error tracking resource usage: {e}")

    def calculate_efficiency_score(self) -> float:
        """Calculate overall crawler efficiency score (0-100)"""
        try:
            # Get overall success rate
            total_requests = self.requests_total.get()
            total_failures = self.requests_failed.get()
            
            if total_requests == 0:
                return 100.0
            
            success_rate = max(0, (total_requests - total_failures) / total_requests)
            
            # Get average response time
            avg_response_time = self.response_time.get_average()
            response_score = max(0, min(1, (5.0 - avg_response_time) / 5.0))  # 5s = 0%, 0s = 100%
            
            # Get throughput score
            current_rps = self.throughput_rps.get()
            throughput_score = min(1, current_rps / 10.0)  # 10 RPS = 100%
            
            # Combined efficiency score
            efficiency = (success_rate * 0.5 + response_score * 0.3 + throughput_score * 0.2) * 100
            
            self.efficiency_score.set(efficiency)
            return efficiency
            
        except Exception as e:
            logger.error(f"Error calculating efficiency score: {e}")
            return 0.0

    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report"""
        now = time.time()
        uptime = now - self.start_time
        
        # Calculate success rates by domain
        domain_health = {}
        for domain in self.domains_crawled:
            domain_labels = {'domain': domain}
            total = self.requests_total.get(labels=domain_labels)
            failed = self.requests_failed.get(labels=domain_labels)
            success_rate = (total - failed) / total if total > 0 else 1.0
            
            domain_health[domain] = {
                'success_rate': success_rate,
                'total_requests': total,
                'failed_requests': failed,
                'avg_response_time': self.response_time.get_average(labels=domain_labels),
                'p95_response_time': self.response_time.get_percentile(95, labels=domain_labels)
            }
        
        # Overall health metrics
        total_requests = self.requests_total.get()
        total_failures = self.requests_failed.get()
        overall_success_rate = (total_requests - total_failures) / total_requests if total_requests > 0 else 1.0
        
        efficiency = self.calculate_efficiency_score()
        
        return {
            'timestamp': now,
            'uptime_seconds': uptime,
            'overall_health': {
                'success_rate': overall_success_rate,
                'efficiency_score': efficiency,
                'throughput_rps': self.throughput_rps.get(),
                'total_requests': total_requests,
                'total_failures': total_failures,
                'active_domains': len(self.domains_crawled),
                'queue_size': self.queue_size.get()
            },
            'performance': {
                'avg_response_time': self.response_time.get_average(),
                'p50_response_time': self.response_time.get_percentile(50),
                'p95_response_time': self.response_time.get_percentile(95),
                'p99_response_time': self.response_time.get_percentile(99)
            },
            'resources': {
                'memory_usage_mb': self.memory_usage.get() / (1024 * 1024) if self.memory_usage.get() else 0.0,
                'cpu_usage_percent': self.cpu_usage.get(),
                'active_connections': self.active_connections.get()
            },
            'business_metrics': {
                'pages_crawled': self.pages_crawled.get(),
                'links_discovered': self.links_discovered.get(),
                'data_extracted': self.data_extracted.get()
            },
            'domain_health': domain_health,
            'alerts': self._generate_alerts(overall_success_rate, efficiency)
        }

    def _generate_alerts(self, success_rate: float, efficiency: float) -> List[Dict[str, Any]]:
        """Generate health alerts"""
        alerts = []
        
        if success_rate < 0.8:
            alerts.append({
                'level': 'critical' if success_rate < 0.5 else 'warning',
                'message': f"Low success rate: {success_rate:.1%}",
                'metric': 'success_rate',
                'value': success_rate
            })
        
        if efficiency < 50:
            alerts.append({
                'level': 'warning',
                'message': f"Low efficiency score: {efficiency:.1f}",
                'metric': 'efficiency',
                'value': efficiency
            })
        
        avg_response_time = self.response_time.get_average()
        if avg_response_time > 10:
            alerts.append({
                'level': 'warning',
                'message': f"High response time: {avg_response_time:.2f}s",
                'metric': 'response_time',
                'value': avg_response_time
            })
        
        return alerts

    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        
        # Helper to format metric lines
        def add_metric_lines(metric_name: str, metric_type: str, description: str, values: Dict[str, float], is_histogram: bool = False):
            lines.append(f"# HELP {metric_name} {description}")
            lines.append(f"# TYPE {metric_name} {metric_type}")
            
            for labels_key, value in values.items():
                labels_dict = json.loads(labels_key) if labels_key else {}
                labels_str = ','.join([f'{k}="{v}"' for k, v in labels_dict.items()])
                
                if is_histogram:
                    # Histograms have _bucket, _sum, _count
                    # This simplified export only shows sum and count, not buckets
                    pass # Handled separately below for histograms
                else:
                    if labels_str:
                        lines.append(f"{metric_name}{{{labels_str}}} {value}")
                    else:
                        lines.append(f"{metric_name} {value}")

        # Export counters
        add_metric_lines(self.requests_total.name, "counter", 
                        self.requests_total.description, self.requests_total.values)
        
        add_metric_lines(self.requests_failed.name, "counter",
                        self.requests_failed.description, self.requests_failed.values)
        
        add_metric_lines(self.links_discovered.name, "counter",
                        self.links_discovered.description, self.links_discovered.values)
        
        add_metric_lines(self.pages_crawled.name, "counter",
                        self.pages_crawled.description, self.pages_crawled.values)
        
        add_metric_lines(self.data_extracted.name, "counter",
                        self.data_extracted.description, self.data_extracted.values)
        
        add_metric_lines(self.error_types.name, "counter",
                        self.error_types.description, self.error_types.values)

        # Export gauges
        add_metric_lines(self.queue_size.name, "gauge",
                        self.queue_size.description, self.queue_size.values)
        
        add_metric_lines(self.active_domains.name, "gauge",
                        self.active_domains.description, self.active_domains.values)
        
        add_metric_lines(self.domain_success_rate.name, "gauge",
                        self.domain_success_rate.description, self.domain_success_rate.values)
        
        add_metric_lines(self.active_connections.name, "gauge",
                        self.active_connections.description, self.active_connections.values)
        
        add_metric_lines(self.memory_usage.name, "gauge",
                        self.memory_usage.description, self.memory_usage.values)
        
        add_metric_lines(self.cpu_usage.name, "gauge",
                        self.cpu_usage.description, self.cpu_usage.values)
        
        add_metric_lines(self.throughput_rps.name, "gauge",
                        self.throughput_rps.description, self.throughput_rps.values)
        
        add_metric_lines(self.efficiency_score.name, "gauge",
                        self.efficiency_score.description, self.efficiency_score.values)
        
        add_metric_lines(self.circuit_breaker_state.name, "gauge",
                        self.circuit_breaker_state.description, self.circuit_breaker_state.values)

        # Export histograms (sum and count)
        lines.append(f"# HELP {self.response_time.name} {self.response_time.description}")
        lines.append(f"# TYPE {self.response_time.name} histogram")
        for labels_key in self.response_time.sum_values:
            labels_dict = json.loads(labels_key) if labels_key else {}
            labels_str = ','.join([f'{k}="{v}"' for k, v in labels_dict.items()])
            
            for bucket in self.response_time.buckets:
                count = self.response_time.bucket_counts[labels_key].get(bucket, 0)
                lines.append(f"{self.response_time.name}_bucket{{{labels_str},le=\"{bucket}\"}} {count}")
            lines.append(f"{self.response_time.name}_bucket{{{labels_str},le=\"+Inf\"}} {self.response_time.count_values[labels_key]}")
            lines.append(f"{self.response_time.name}_sum{{{labels_str}}} {self.response_time.sum_values[labels_key]}")
            lines.append(f"{self.response_time.name}_count{{{labels_str}}} {self.response_time.count_values[labels_key]}")

        lines.append(f"# HELP {self.content_size.name} {self.content_size.description}")
        lines.append(f"# TYPE {self.content_size.name} histogram")
        for labels_key in self.content_size.sum_values:
            labels_dict = json.loads(labels_key) if labels_key else {}
            labels_str = ','.join([f'{k}="{v}"' for k, v in labels_dict.items()])
            
            for bucket in self.content_size.buckets:
                count = self.content_size.bucket_counts[labels_key].get(bucket, 0)
                lines.append(f"{self.content_size.name}_bucket{{{labels_str},le=\"{bucket}\"}} {count}")
            lines.append(f"{self.content_size.name}_bucket{{{labels_str},le=\"+Inf\"}} {self.content_size.count_values[labels_key]}")
            lines.append(f"{self.content_size.name}_sum{{{labels_str}}} {self.content_size.sum_values[labels_key]}")
            lines.append(f"{self.content_size.name}_count{{{labels_str}}} {self.content_size.count_values[labels_key]}")

        lines.append(f"# HELP {self.queue_wait_time.name} {self.queue_wait_time.description}")
        lines.append(f"# TYPE {self.queue_wait_time.name} histogram")
        for labels_key in self.queue_wait_time.sum_values:
            labels_dict = json.loads(labels_key) if labels_key else {}
            labels_str = ','.join([f'{k}="{v}"' for k, v in labels_dict.items()])
            
            for bucket in self.queue_wait_time.buckets:
                count = self.queue_wait_time.bucket_counts[labels_key].get(bucket, 0)
                lines.append(f"{self.queue_wait_time.name}_bucket{{{labels_str},le=\"{bucket}\"}} {count}")
            lines.append(f"{self.queue_wait_time.name}_bucket{{{labels_str},le=\"+Inf\"}} {self.queue_wait_time.count_values[labels_key]}")
            lines.append(f"{self.queue_wait_time.name}_sum{{{labels_str}}} {self.queue_wait_time.sum_values[labels_key]}")
            lines.append(f"{self.queue_wait_time.name}_count{{{labels_str}}} {self.queue_wait_time.count_values[labels_key]}")

        return '\n'.join(lines)

# Global metrics instance
crawler_metrics = CrawlerMetrics()
