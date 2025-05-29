"""
Database Module - Placeholder for data persistence operations
File: Link_Profiler/database/database.py
"""

from typing import List, Dict, Optional, Any
from Link_Profiler.core.models import Backlink, LinkProfile, CrawlJob, Domain, URL, SEOMetrics, serialize_model, CrawlStatus
import json
import os
from urllib.parse import urlparse

# --- SQLAlchemy Imports ---
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import IntegrityError
from Link_Profiler.database.models import (
    Base, DomainORM, URLORM, BacklinkORM, LinkProfileORM, CrawlJobORM, SEOMetricsORM,
    LinkTypeEnum, ContentTypeEnum, CrawlStatusEnum, SpamLevelEnum
)
import logging

logger = logging.getLogger(__name__)

class Database:
    """
    A class for database operations using SQLAlchemy with PostgreSQL.
    """
    def __init__(self, db_url: str = "postgresql://postgres:postgres@localhost:5432/link_profiler_db"):
        self.engine = create_engine(db_url)
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        self._create_tables()

    def _create_tables(self):
        """Creates database tables based on SQLAlchemy models."""
        Base.metadata.create_all(self.engine)
        logger.info("Database tables checked/created.")

    def _get_session(self):
        """Returns a new session from the session factory."""
        return self.Session()

    # --- Helper to convert ORM objects to dataclass objects ---
    def _to_dataclass(self, orm_obj: Any):
        if isinstance(orm_obj, DomainORM):
            return Domain(
                name=orm_obj.name,
                authority_score=orm_obj.authority_score,
                trust_score=orm_obj.trust_score,
                spam_score=orm_obj.spam_score,
                age_days=orm_obj.age_days,
                country=orm_obj.country,
                ip_address=orm_obj.ip_address,
                whois_data=orm_obj.whois_data,
                total_pages=orm_obj.total_pages,
                total_backlinks=orm_obj.total_backlinks,
                referring_domains=orm_obj.referring_domains,
                first_seen=orm_obj.first_seen,
                last_crawled=orm_obj.last_crawled
            )
        elif isinstance(orm_obj, URLORM):
            # Note: domain and path are init=False in dataclass, so pass others
            return URL(
                url=orm_obj.url,
                title=orm_obj.title,
                description=orm_obj.description,
                content_type=ContentTypeEnum(orm_obj.content_type),
                content_length=orm_obj.content_length,
                status_code=orm_obj.status_code,
                redirect_url=orm_obj.redirect_url,
                canonical_url=orm_obj.canonical_url,
                last_modified=orm_obj.last_modified,
                crawl_status=CrawlStatusEnum(orm_obj.crawl_status),
                crawl_date=orm_obj.crawl_date,
                error_message=orm_obj.error_message
            )
        elif isinstance(orm_obj, BacklinkORM):
            return Backlink(
                id=orm_obj.id,
                source_url=orm_obj.source_url,
                target_url=orm_obj.target_url,
                anchor_text=orm_obj.anchor_text,
                link_type=LinkTypeEnum(orm_obj.link_type),
                context_text=orm_obj.context_text,
                position_on_page=orm_obj.position_on_page,
                is_image_link=orm_obj.is_image_link,
                alt_text=orm_obj.alt_text,
                discovered_date=orm_obj.discovered_date,
                last_seen_date=orm_obj.last_seen_date,
                authority_passed=orm_obj.authority_passed,
                is_active=orm_obj.is_active,
                spam_level=SpamLevelEnum(orm_obj.spam_level)
            )
        elif isinstance(orm_obj, LinkProfileORM):
            return LinkProfile(
                target_url=orm_obj.target_url,
                total_backlinks=orm_obj.total_backlinks,
                unique_domains=orm_obj.unique_domains,
                dofollow_links=orm_obj.dofollow_links,
                nofollow_links=orm_obj.nofollow_links,
                authority_score=orm_obj.authority_score,
                trust_score=orm_obj.trust_score,
                spam_score=orm_obj.spam_score,
                anchor_text_distribution=orm_obj.anchor_text_distribution,
                referring_domains=set(orm_obj.referring_domains), # Convert list back to set
                analysis_date=orm_obj.analysis_date,
                backlinks=[] # Backlinks are loaded separately or via relationship if needed
            )
        elif isinstance(orm_obj, CrawlJobORM):
            return CrawlJob(
                id=orm_obj.id,
                target_url=orm_obj.target_url,
                job_type=orm_obj.job_type,
                status=CrawlStatusEnum(orm_obj.status),
                priority=orm_obj.priority,
                created_date=orm_obj.created_date,
                started_date=orm_obj.started_date,
                completed_date=orm_obj.completed_date,
                progress_percentage=orm_obj.progress_percentage,
                urls_discovered=orm_obj.urls_discovered,
                urls_crawled=orm_obj.urls_crawled,
                links_found=orm_obj.links_found,
                errors_count=orm_obj.errors_count,
                config=orm_obj.config,
                results=orm_obj.results,
                error_log=orm_obj.error_log
            )
        elif isinstance(orm_obj, SEOMetricsORM):
            return SEOMetrics(
                url=orm_obj.url,
                title_length=orm_obj.title_length,
                description_length=orm_obj.description_length,
                h1_count=orm_obj.h1_count,
                h2_count=orm_obj.h2_count,
                internal_links=orm_obj.internal_links,
                external_links=orm_obj.external_links,
                images_count=orm_obj.images_count,
                images_without_alt=orm_obj.images_without_alt,
                page_size_kb=orm_obj.page_size_kb,
                load_time_ms=orm_obj.load_time_ms,
                has_canonical=orm_obj.has_canonical,
                has_robots_meta=orm_obj.has_robots_meta,
                has_schema_markup=orm_obj.has_schema_markup,
                mobile_friendly=orm_obj.mobile_friendly,
                ssl_enabled=orm_obj.ssl_enabled,
                seo_score=orm_obj.seo_score,
                issues=orm_obj.issues
            )
        return None

    # --- Helper to convert dataclass objects to ORM objects ---
    def _to_orm(self, dc_obj: Any):
        if isinstance(dc_obj, Domain):
            return DomainORM(
                name=dc_obj.name,
                authority_score=dc_obj.authority_score,
                trust_score=dc_obj.trust_score,
                spam_score=dc_obj.spam_score,
                age_days=dc_obj.age_days,
                country=dc_obj.country,
                ip_address=dc_obj.ip_address,
                whois_data=dc_obj.whois_data,
                total_pages=dc_obj.total_pages,
                total_backlinks=dc_obj.total_backlinks,
                referring_domains=dc_obj.referring_domains,
                first_seen=dc_obj.first_seen,
                last_crawled=dc_obj.last_crawled
            )
        elif isinstance(dc_obj, URL):
            return URLORM(
                url=dc_obj.url,
                domain_name=dc_obj.domain, # Use the calculated domain
                path=dc_obj.path, # Use the calculated path
                title=dc_obj.title,
                description=dc_obj.description,
                content_type=dc_obj.content_type.value,
                content_length=dc_obj.content_length,
                status_code=dc_obj.status_code,
                redirect_url=dc_obj.redirect_url,
                canonical_url=dc_obj.canonical_url,
                last_modified=dc_obj.last_modified,
                crawl_status=dc_obj.crawl_status.value,
                crawl_date=dc_obj.crawl_date,
                error_message=dc_obj.error_message
            )
        elif isinstance(dc_obj, Backlink):
            return BacklinkORM(
                id=dc_obj.id,
                source_url=dc_obj.source_url,
                target_url=dc_obj.target_url,
                source_domain_name=dc_obj.source_domain, # Use calculated domain
                target_domain_name=dc_obj.target_domain, # Use calculated domain
                anchor_text=dc_obj.anchor_text,
                link_type=dc_obj.link_type.value,
                context_text=dc_obj.context_text,
                position_on_page=dc_obj.position_on_page,
                is_image_link=dc_obj.is_image_link,
                alt_text=dc_obj.alt_text,
                discovered_date=dc_obj.discovered_date,
                last_seen_date=dc_obj.last_seen_date,
                authority_passed=dc_obj.authority_passed,
                is_active=dc_obj.is_active,
                spam_level=dc_obj.spam_level.value
            )
        elif isinstance(dc_obj, LinkProfile):
            return LinkProfileORM(
                target_url=dc_obj.target_url,
                target_domain_name=dc_obj.target_domain, # Use calculated domain
                total_backlinks=dc_obj.total_backlinks,
                unique_domains=dc_obj.unique_domains,
                dofollow_links=dc_obj.dofollow_links,
                nofollow_links=dc_obj.nofollow_links,
                authority_score=dc_obj.authority_score,
                trust_score=dc_obj.trust_score,
                spam_score=dc_obj.spam_score,
                anchor_text_distribution=dc_obj.anchor_text_distribution,
                referring_domains=list(dc_obj.referring_domains), # Convert set to list for ARRAY
                analysis_date=dc_obj.analysis_date
            )
        elif isinstance(dc_obj, CrawlJob):
            return CrawlJobORM(
                id=dc_obj.id,
                target_url=dc_obj.target_url,
                job_type=dc_obj.job_type,
                status=dc_obj.status.value,
                priority=dc_obj.priority,
                created_date=dc_obj.created_date,
                started_date=dc_obj.started_date,
                completed_date=dc_obj.completed_date,
                progress_percentage=dc_obj.progress_percentage,
                urls_discovered=dc_obj.urls_discovered,
                urls_crawled=dc_obj.urls_crawled,
                links_found=dc_obj.links_found,
                errors_count=dc_obj.errors_count,
                config=dc_obj.config,
                results=dc_obj.results,
                error_log=dc_obj.error_log
            )
        elif isinstance(dc_obj, SEOMetrics):
            return SEOMetricsORM(
                url=dc_obj.url,
                title_length=dc_obj.title_length,
                description_length=dc_obj.description_length,
                h1_count=dc_obj.h1_count,
                h2_count=dc_obj.h2_count,
                internal_links=dc_obj.internal_links,
                external_links=dc_obj.external_links,
                images_count=dc_obj.images_count,
                images_without_alt=dc_obj.images_without_alt,
                page_size_kb=dc_obj.page_size_kb,
                load_time_ms=dc_obj.load_time_ms,
                has_canonical=dc_obj.has_canonical,
                has_robots_meta=dc_obj.has_robots_meta,
                has_schema_markup=dc_obj.has_schema_markup,
                mobile_friendly=dc_obj.mobile_friendly,
                ssl_enabled=dc_obj.ssl_enabled,
                seo_score=dc_obj.seo_score,
                issues=dc_obj.issues
            )
        return None

    # --- Backlink Operations ---
    def add_backlink(self, backlink: Backlink) -> None:
        session = self._get_session()
        try:
            # Ensure source and target domains exist
            source_domain_name = urlparse(backlink.source_url).netloc.lower()
            target_domain_name = urlparse(backlink.target_url).netloc.lower()

            session.merge(DomainORM(name=source_domain_name))
            session.merge(DomainORM(name=target_domain_name))

            # Check if backlink already exists based on source_url and target_url
            existing_orm_backlink = session.query(BacklinkORM).filter_by(
                source_url=backlink.source_url,
                target_url=backlink.target_url
            ).first()

            if existing_orm_backlink:
                # Update existing backlink's last_seen_date and other relevant fields
                logger.debug(f"Updating existing backlink: from {backlink.source_url} to {backlink.target_url}")
                existing_orm_backlink.last_seen_date = backlink.last_seen_date
                existing_orm_backlink.anchor_text = backlink.anchor_text
                existing_orm_backlink.link_type = backlink.link_type.value
                existing_orm_backlink.context_text = backlink.context_text
                existing_orm_backlink.is_image_link = backlink.is_image_link
                existing_orm_backlink.alt_text = backlink.alt_text
                existing_orm_backlink.authority_passed = backlink.authority_passed
                existing_orm_backlink.is_active = backlink.is_active
                existing_orm_backlink.spam_level = backlink.spam_level.value
            else:
                # Add new backlink
                logger.debug(f"Adding new backlink: from {backlink.source_url} to {backlink.target_url}")
                orm_backlink = self._to_orm(backlink)
                if orm_backlink is None:
                    logger.error(f"Failed to convert backlink dataclass to ORM for {backlink.source_url} -> {backlink.target_url}")
                    return # Exit if conversion failed
                session.add(orm_backlink)
            
            session.commit()
            logger.info(f"Successfully added/updated backlink from {backlink.source_url} to {backlink.target_url}.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding/updating backlink: {type(e).__name__}: {e}", exc_info=True)
            raise # Re-raise to indicate failure
        finally:
            session.close()

    def add_backlinks(self, backlinks: List[Backlink]) -> None:
        session = self._get_session()
        try:
            logger.info(f"Attempting to add/update {len(backlinks)} backlinks to the database.")
            
            for i, backlink in enumerate(backlinks):
                # Ensure source and target domains exist
                source_domain_name = urlparse(backlink.source_url).netloc.lower()
                target_domain_name = urlparse(backlink.target_url).netloc.lower()
                
                # Add domains if they don't exist (merge handles upsert for domains)
                session.merge(DomainORM(name=source_domain_name))
                session.merge(DomainORM(name=target_domain_name))

                # Check if backlink already exists based on source_url and target_url
                existing_orm_backlink = session.query(BacklinkORM).filter_by(
                    source_url=backlink.source_url,
                    target_url=backlink.target_url
                ).first()

                if existing_orm_backlink:
                    # Update existing backlink's last_seen_date and other relevant fields
                    logger.debug(f"Updating existing backlink: from {backlink.source_url} to {backlink.target_url}")
                    existing_orm_backlink.last_seen_date = backlink.last_seen_date
                    existing_orm_backlink.anchor_text = backlink.anchor_text
                    existing_orm_backlink.link_type = backlink.link_type.value
                    existing_orm_backlink.context_text = backlink.context_text
                    existing_orm_backlink.is_image_link = backlink.is_image_link
                    existing_orm_backlink.alt_text = backlink.alt_text
                    existing_orm_backlink.authority_passed = backlink.authority_passed
                    existing_orm_backlink.is_active = backlink.is_active
                    existing_orm_backlink.spam_level = backlink.spam_level.value
                    # No need to add to session, it's already managed
                else:
                    # Add new backlink
                    logger.debug(f"Adding new backlink: from {backlink.source_url} to {backlink.target_url}")
                    orm_backlink = self._to_orm(backlink)
                    if orm_backlink is None:
                        logger.error(f"Failed to convert backlink dataclass to ORM for backlink {i+1}/{len(backlinks)}")
                        continue # Skip this backlink if conversion failed
                    session.add(orm_backlink)
            
            logger.debug("Attempting session.commit() for all backlinks.")
            session.commit()
            logger.info(f"Successfully added/updated {len(backlinks)} backlinks.")

        except Exception as e: # Catching general Exception for now, can refine later
            session.rollback()
            logger.error(f"Error adding/updating backlinks: {type(e).__name__}: {e}", exc_info=True)
            raise # Re-raise the exception after logging and rollback
        finally:
            session.close()

    def get_backlinks_for_target(self, target_url: str) -> List[Backlink]:
        session = self._get_session()
        try:
            parsed_target = urlparse(target_url)
            target_domain = parsed_target.netloc.lower() # Lowercase for consistent comparison
            target_path = parsed_target.path

            logger.info(f"Querying backlinks for target_url: {target_url}, domain: {target_domain}, path: {target_path}")

            if not target_domain:
                logger.warning(f"Invalid target_url for backlink query: {target_url}")
                return []

            # Build the filter condition
            filter_condition = BacklinkORM.target_url.startswith(target_url)

            # If the target_url is the root URL without a trailing slash,
            # also include backlinks pointing to the root URL *with* a trailing slash.
            if target_path in ["", "/"] and not target_url.endswith('/'):
                 target_url_with_slash = target_url + '/'
                 logger.debug(f"Adding filter for target_url with trailing slash: {target_url_with_slash}")
                 filter_condition = or_(
                     filter_condition,
                     BacklinkORM.target_url.startswith(target_url_with_slash)
                 )


            orm_backlinks = session.query(BacklinkORM).filter(
                filter_condition
            ).all()
            
            logger.info(f"Found {len(orm_backlinks)} ORM backlinks matching the filter.")

            # Add debug logging for retrieved backlinks' target URLs
            for i, bl in enumerate(orm_backlinks):
                 logger.debug(f"Retrieved backlink {i+1}: Target URL: {bl.target_url}")


            dataclass_backlinks = [self._to_dataclass(bl) for bl in orm_backlinks]
            logger.info(f"Returning {len(dataclass_backlinks)} dataclass backlinks for target {target_url}")
            return dataclass_backlinks

        except Exception as e:
            logger.error(f"Error getting backlinks for target {target_url}: {e}")
            return []
        finally:
            session.close()

    def get_all_backlinks(self) -> List[Backlink]:
        session = self._get_session()
        try:
            logger.info("Attempting to retrieve all backlinks from the database.")
            orm_backlinks = session.query(BacklinkORM).all()
            logger.info(f"Retrieved {len(orm_backlinks)} ORM backlinks.")
            
            # Add debug logging to show domain names of retrieved backlinks
            for i, bl in enumerate(orm_backlinks):
                 logger.debug(f"Retrieved backlink {i+1}: Source Domain: {bl.source_domain_name}, Target Domain: {bl.target_domain_name}")

            return [self._to_dataclass(bl) for bl in orm_backlinks]
        except Exception as e:
            logger.error(f"Error getting all backlinks: {e}")
            return []
        finally:
            session.close()

    # --- LinkProfile Operations ---
    def save_link_profile(self, profile: LinkProfile) -> None:
        session = self._get_session()
        try:
            # Ensure target domain exists
            target_domain_name = urlparse(profile.target_url).netloc.lower()
            session.merge(DomainORM(name=target_domain_name))

            orm_profile = self._to_orm(profile)
            session.merge(orm_profile) # Use merge for upsert
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving link profile for {profile.target_url}: {e}")
        finally:
            session.close()

    def get_link_profile(self, target_url: str) -> Optional[LinkProfile]:
        session = self._get_session()
        try:
            orm_profile = session.query(LinkProfileORM).get(target_url)
            if orm_profile:
                return self._to_dataclass(orm_profile)
            return None
        except Exception as e:
            logger.error(f"Error getting link profile for {target_url}: {e}")
            return None
        finally:
            session.close()

    # --- CrawlJob Operations ---
    def add_crawl_job(self, job: CrawlJob) -> None:
        session = self._get_session()
        try:
            orm_job = self._to_orm(job)
            session.add(orm_job)
            session.commit()
        except IntegrityError:
            session.rollback()
            logger.warning(f"CrawlJob with ID {job.id} already exists. Skipping.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding crawl job {job.id}: {e}")
        finally:
            session.close()

    def get_crawl_job(self, job_id: str) -> Optional[CrawlJob]:
        session = self._get_session()
        try:
            orm_job = session.query(CrawlJobORM).get(job_id)
            if orm_job:
                return self._to_dataclass(orm_job)
            return None
        except Exception as e:
            logger.error(f"Error getting crawl job {job_id}: {e}")
            return None
        finally:
            session.close()

    def update_crawl_job(self, job: CrawlJob) -> None:
        session = self._get_session()
        try:
            orm_job = session.query(CrawlJobORM).get(job.id)
            if orm_job:
                # Update fields manually or use merge if primary key is set
                orm_job.target_url = job.target_url
                orm_job.job_type = job.job_type
                orm_job.status = job.status.value
                orm_job.priority = job.priority
                orm_job.created_date = job.created_date
                orm_job.started_date = job.started_date
                orm_job.completed_date = job.completed_date
                orm_job.progress_percentage = job.progress_percentage
                orm_job.urls_discovered = job.urls_discovered
                orm_job.urls_crawled = job.urls_crawled
                orm_job.links_found = job.links_found
                orm_job.errors_count = job.errors_count
                orm_job.config = job.config
                orm_job.results = job.results
                error_log = job.error_log # Get the list from the dataclass
                # Ensure error_log is a list of strings before assigning to ORM
                orm_job.error_log = [str(err) for err in error_log] if isinstance(error_log, list) else []
                session.commit()
            else:
                raise ValueError(f"CrawlJob with ID {job.id} not found for update.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating crawl job {job.id}: {e}")
            raise # Re-raise to indicate failure
        finally:
            session.close()

    def get_pending_crawl_jobs(self) -> List[CrawlJob]:
        session = self._get_session()
        try:
            orm_jobs = session.query(CrawlJobORM).filter(
                CrawlJobORM.status == CrawlStatusEnum.PENDING.value
            ).all()
            return [self._to_dataclass(job) for job in orm_jobs]
        except Exception as e:
            logger.error(f"Error getting pending crawl jobs: {e}")
            return []
        finally:
            session.close()

    # --- Domain Operations ---
    def save_domain(self, domain: Domain) -> None:
        session = self._get_session()
        try:
            orm_domain = self._to_orm(domain)
            session.merge(orm_domain) # Use merge for upsert
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving domain {domain.name}: {e}")
        finally:
            session.close()

    def get_domain(self, name: str) -> Optional[Domain]:
        session = self._get_session()
        try:
            orm_domain = session.query(DomainORM).get(name)
            if orm_domain:
                return self._to_dataclass(orm_domain)
            return None
        except Exception as e:
            logger.error(f"Error getting domain {name}: {e}")
            return None
        finally:
            session.close()

    # --- URL Operations ---
    def save_url(self, url_obj: URL) -> None:
        session = self._get_session()
        try:
            # Ensure domain exists for the URL
            domain_name = urlparse(url_obj.url).netloc.lower()
            session.merge(DomainORM(name=domain_name))

            orm_url = self._to_orm(url_obj)
            session.merge(orm_url) # Use merge for upsert
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving URL {url_obj.url}: {e}")
        finally:
            session.close()

    def get_url(self, url_str: str) -> Optional[URL]:
        session = self._get_session()
        try:
            orm_url = session.query(URLORM).get(url_str)
            if orm_url:
                return self._to_dataclass(orm_url)
            return None
        except Exception as e:
            logger.error(f"Error getting URL {url_str}: {e}")
            return None
        finally:
            session.close()

    # --- SEOMetrics Operations ---
    def save_seo_metrics(self, seo_metrics: SEOMetrics) -> None:
        session = self._get_session()
        try:
            # Ensure URL exists for SEO metrics
            url_obj = URL(url=seo_metrics.url) # Create a dummy URL object to get domain/path
            session.merge(URLORM(url=url_obj.url, domain_name=url_obj.domain, path=url_obj.path))

            orm_seo_metrics = self._to_orm(seo_metrics)
            session.merge(orm_seo_metrics) # Use merge for upsert
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving SEO metrics for {seo_metrics.url}: {e}")
        finally:
            session.close()

    def get_seo_metrics(self, url_str: str) -> Optional[SEOMetrics]:
        session = self._get_session()
        try:
            orm_seo_metrics = session.query(SEOMetricsORM).get(url_str)
            if orm_seo_metrics:
                return self._to_dataclass(orm_seo_metrics)
            return None
        except Exception as e:
            logger.error(f"Error getting SEO metrics for {url_str}: {e}")
            return []
        finally:
            session.close()
