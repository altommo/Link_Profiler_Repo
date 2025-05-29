"""
Database Module - Placeholder for data persistence operations
File: Link_Profiler/database/database.py
"""

from typing import List, Dict, Optional
from Link_Profiler.core.models import Backlink, LinkProfile, CrawlJob, Domain, URL, SEOMetrics, serialize_model, CrawlStatus # Changed to absolute import and added CrawlStatus
import json
import os

# For demonstration, we'll use a simple in-memory storage or JSON file.
# In a real application, this would be replaced with a proper database (e.g., PostgreSQL, MongoDB).

class Database:
    """
    A placeholder class for database operations.
    Currently uses in-memory lists and can optionally persist to JSON files.
    """
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self._backlinks: List[Backlink] = []
        self._link_profiles: List[LinkProfile] = []
        self._crawl_jobs: List[CrawlJob] = []
        self._domains: List[Domain] = []
        self._urls: List[URL] = []
        self._seo_metrics: List[SEOMetrics] = []
        self._load_data()

    def _get_file_path(self, filename: str) -> str:
        return os.path.join(self.data_dir, filename)

    def _load_data(self):
        """Load data from JSON files if they exist."""
        try:
            with open(self._get_file_path("backlinks.json"), 'r') as f:
                self._backlinks = [Backlink.from_dict(item) for item in json.load(f)]
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error loading backlinks: {e}")

        try:
            with open(self._get_file_path("link_profiles.json"), 'r') as f:
                self._link_profiles = [LinkProfile.from_dict(item) for item in json.load(f)]
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error loading link profiles: {e}")
        
        try:
            with open(self._get_file_path("crawl_jobs.json"), 'r') as f:
                self._crawl_jobs = [CrawlJob.from_dict(item) for item in json.load(f)]
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error loading crawl jobs: {e}")

        try: # Load domains
            with open(self._get_file_path("domains.json"), 'r') as f:
                self._domains = [Domain.from_dict(item) for item in json.load(f)]
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error loading domains: {e}")

        try: # Load URLs
            with open(self._get_file_path("urls.json"), 'r') as f:
                self._urls = [URL.from_dict(item) for item in json.load(f)]
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error loading URLs: {e}")

        try: # Load SEO Metrics
            with open(self._get_file_path("seo_metrics.json"), 'r') as f:
                self._seo_metrics = [SEOMetrics.from_dict(item) for item in json.load(f)]
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error loading SEO metrics: {e}")


    def _save_data(self):
        """Save current in-memory data to JSON files."""
        with open(self._get_file_path("backlinks.json"), 'w') as f:
            json.dump([serialize_model(bl) for bl in self._backlinks], f, indent=4)
        with open(self._get_file_path("link_profiles.json"), 'w') as f:
            json.dump([serialize_model(lp) for lp in self._link_profiles], f, indent=4)
        with open(self._get_file_path("crawl_jobs.json"), 'w') as f:
            json.dump([serialize_model(cj) for cj in self._crawl_jobs], f, indent=4)
        with open(self._get_file_path("domains.json"), 'w') as f:
            json.dump([serialize_model(d) for d in self._domains], f, indent=4)
        with open(self._get_file_path("urls.json"), 'w') as f:
            json.dump([serialize_model(u) for u in self._urls], f, indent=4)
        with open(self._get_file_path("seo_metrics.json"), 'w') as f:
            json.dump([serialize_model(sm) for sm in self._seo_metrics], f, indent=4)


    # --- Backlink Operations ---
    def add_backlink(self, backlink: Backlink) -> None:
        """Adds a single backlink to storage."""
        self._backlinks.append(backlink)
        self._save_data()

    def add_backlinks(self, backlinks: List[Backlink]) -> None:
        """Adds multiple backlinks to storage."""
        self._backlinks.extend(backlinks)
        self._save_data()

    def get_backlinks_for_target(self, target_url: str) -> List[Backlink]:
        """Retrieves all backlinks for a given target URL."""
        return [bl for bl in self._backlinks if bl.target_url == target_url]

    def get_all_backlinks(self) -> List[Backlink]:
        """Retrieves all stored backlinks."""
        return list(self._backlinks)

    # --- LinkProfile Operations ---
    def save_link_profile(self, profile: LinkProfile) -> None:
        """Saves or updates a link profile."""
        # For simplicity, if a profile for the target_url exists, replace it.
        # In a real DB, you'd have unique IDs or proper update logic.
        existing_profile_index = next((i for i, p in enumerate(self._link_profiles) 
                                       if p.target_url == profile.target_url), -1)
        if existing_profile_index != -1:
            self._link_profiles[existing_profile_index] = profile
        else:
            self._link_profiles.append(profile)
        self._save_data()

    def get_link_profile(self, target_url: str) -> Optional[LinkProfile]:
        """Retrieves a link profile for a given target URL."""
        return next((p for p in self._link_profiles if p.target_url == target_url), None)

    # --- CrawlJob Operations ---
    def add_crawl_job(self, job: CrawlJob) -> None:
        """Adds a new crawl job."""
        self._crawl_jobs.append(job)
        self._save_data()

    def get_crawl_job(self, job_id: str) -> Optional[CrawlJob]:
        """Retrieves a crawl job by its ID."""
        return next((job for job in self._crawl_jobs if job.id == job_id), None)

    def update_crawl_job(self, job: CrawlJob) -> None:
        """Updates an existing crawl job."""
        existing_job_index = next((i for i, j in enumerate(self._crawl_jobs) 
                                   if j.id == job.id), -1)
        if existing_job_index != -1:
            self._crawl_jobs[existing_job_index] = job
            self._save_data()
        else:
            raise ValueError(f"CrawlJob with ID {job.id} not found.")

    def get_pending_crawl_jobs(self) -> List[CrawlJob]:
        """Retrieves all pending crawl jobs."""
        return [job for job in self._crawl_jobs if job.status == CrawlStatus.PENDING]

    # --- Domain Operations ---
    def save_domain(self, domain: Domain) -> None:
        """Saves or updates domain information."""
        existing_domain_index = next((i for i, d in enumerate(self._domains) 
                                      if d.name == domain.name), -1)
        if existing_domain_index != -1:
            self._domains[existing_domain_index] = domain
        else:
            self._domains.append(domain)
        self._save_data() # Ensure persistence

    def get_domain(self, name: str) -> Optional[Domain]:
        """Retrieves domain information by name."""
        return next((d for d in self._domains if d.name == name), None)

    # --- URL Operations ---
    def save_url(self, url_obj: URL) -> None:
        """Saves or updates URL information."""
        existing_url_index = next((i for i, u in enumerate(self._urls) 
                                   if u.url == url_obj.url), -1)
        if existing_url_index != -1:
            self._urls[existing_url_index] = url_obj
        else:
            self._urls.append(url_obj)
        self._save_data() # Ensure persistence

    def get_url(self, url_str: str) -> Optional[URL]:
        """Retrieves URL information by URL string."""
        return next((u for u in self._urls if u.url == url_str), None)

    # --- SEOMetrics Operations ---
    def save_seo_metrics(self, seo_metrics: SEOMetrics) -> None:
        """Saves or updates SEO metrics for a URL."""
        existing_metrics_index = next((i for i, sm in enumerate(self._seo_metrics) 
                                       if sm.url == seo_metrics.url), -1)
        if existing_metrics_index != -1:
            self._seo_metrics[existing_metrics_index] = seo_metrics
        else:
            self._seo_metrics.append(seo_metrics)
        self._save_data() # Ensure persistence

    def get_seo_metrics(self, url_str: str) -> Optional[SEOMetrics]:
        """Retrieves SEO metrics for a URL."""
        return next((sm for sm in self._seo_metrics if sm.url == url_str), None)
