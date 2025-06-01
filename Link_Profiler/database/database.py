"""
Database Operations - Handles all interactions with the PostgreSQL database.
File: Link_Profiler/database/database.py
"""

import logging
from typing import List, Optional, Any, Dict, Set
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.inspection import inspect
from datetime import datetime, timedelta
import enum # Import enum for type checking
from urllib.parse import urlparse # Added import for urlparse

from Link_Profiler.database.models import ( # Changed to absolute import
    Base, DomainORM, URLORM, BacklinkORM, LinkProfileORM, CrawlJobORM,
    SEOMetricsORM, SERPResultORM, KeywordSuggestionORM, AlertRuleORM, UserORM, ContentGapAnalysisResultORM, DomainHistoryORM,
    LinkTypeEnum, ContentTypeEnum, CrawlStatusEnum, SpamLevelEnum,
    AlertSeverityEnum, AlertChannelEnum, DomainIntelligenceORM, SocialMentionORM # New: Import Alerting Enums, DomainIntelligenceORM, SocialMentionORM
)
from Link_Profiler.core.models import ( # Changed to absolute import
    Domain, URL, Backlink, LinkProfile, CrawlJob, SEOMetrics,
    SERPResult, KeywordSuggestion, AlertRule, User, ContentGapAnalysisResult, DomainHistory,
    serialize_model, CrawlError, DomainIntelligence, SocialMention # New: Import DomainIntelligence, SocialMention
)

logger = logging.getLogger(__name__)

class Database:
    """
    A class for database operations using SQLAlchemy with PostgreSQL.
    """
    def __init__(self, db_url: str = "postgresql://postgres:postgres@localhost:5432/link_profiler_db"):
        self.db_url = db_url
        self.engine = create_engine(self.db_url)
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        self._create_tables() # Ensure tables exist on init

    def _create_tables(self):
        """Creates all tables defined in the Base metadata."""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Database tables created or already exist.")
        except OperationalError as e:
            logger.error(f"Could not connect to database or create tables: {e}")
            raise

    def _drop_all_tables(self):
        """Drops all tables defined in the Base metadata. Use with caution."""
        try:
            Base.metadata.drop_all(self.engine)
            logger.warning("All database tables dropped.")
        except OperationalError as e:
            logger.error(f"Could not connect to database or drop tables: {e}")
            raise

    def _get_session(self):
        """Returns a new session."""
        return self.Session()

    def _to_dataclass(self, orm_obj: Any):
        """Converts an ORM object to its corresponding dataclass."""
        if orm_obj is None:
            return None

        # Generic conversion for most fields
        data = {}
        for col in inspect(orm_obj.__class__).columns:
            data[col.key] = getattr(orm_obj, col.key)
        
        # Specific handling for each ORM type
        if isinstance(orm_obj, DomainORM):
            return Domain(**data)
        elif isinstance(orm_obj, URLORM):
            # URL dataclass has init=False for domain and path, so pass others
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
                rel_attributes=orm_obj.rel_attributes, # Added this line
                context_text=orm_obj.context_text,
                position_on_page=orm_obj.position_on_page,
                is_image_link=orm_obj.is_image_link,
                alt_text=orm_obj.alt_text,
                discovered_date=orm_obj.discovered_date,
                last_seen_date=orm_obj.last_seen_date,
                authority_passed=orm_obj.authority_passed,
                is_active=orm_obj.is_active,
                spam_level=SpamLevelEnum(orm_obj.spam_level),
                http_status=orm_obj.http_status,
                crawl_timestamp=orm_obj.crawl_timestamp,
                source_domain_metrics=orm_obj.source_domain_metrics
            )
        elif isinstance(orm_obj, LinkProfileORM):
            # LinkProfile dataclass expects 'referring_domains' as a set
            if 'referring_domains' in data and isinstance(data['referring_domains'], list):
                data['referring_domains'] = set(data['referring_domains'])
            # LinkProfile dataclass expects 'backlinks' field, but ORM doesn't store it directly.
            # It's derived. So, we need to remove it from data if it's not present in ORM.
            data.pop('backlinks', None)
            data.pop('top_pages', None)
            return LinkProfile(**data)
        elif isinstance(orm_obj, CrawlJobORM):
            # Deserialize error_log from JSONB (list of dicts) to List[CrawlError]
            error_log_data = orm_obj.error_log if orm_obj.error_log else []
            data['error_log'] = [CrawlError.from_dict(err_data) for err_data in error_log_data]
            # Convert status enum
            data['status'] = CrawlStatusEnum(orm_obj.status)
            return CrawlJob(**data)
        elif isinstance(orm_obj, SEOMetricsORM):
            return SEOMetrics(**data)
        elif isinstance(orm_obj, SERPResultORM):
            return SERPResult(**data)
        elif isinstance(orm_obj, KeywordSuggestionORM):
            return KeywordSuggestion(**data)
        elif isinstance(orm_obj, AlertRuleORM): # New: Handle AlertRuleORM
            if 'severity' in data and isinstance(data['severity'], str):
                data['severity'] = AlertSeverityEnum(data['severity'])
            if 'notification_channels' in data and isinstance(data['notification_channels'], list):
                data['notification_channels'] = [AlertChannelEnum(c) for c in data['notification_channels']]
            return AlertRule(**data)
        elif isinstance(orm_obj, UserORM): # New: Handle UserORM
            if 'created_at' in data and isinstance(data['created_at'], str):
                data['created_at'] = datetime.fromisoformat(data['created_at'])
            return User(**data)
        elif isinstance(orm_obj, ContentGapAnalysisResultORM): # New: Handle ContentGapAnalysisResultORM
            if 'analysis_date' in data and isinstance(data['analysis_date'], str):
                data['analysis_date'] = datetime.fromisoformat(data['analysis_date'])
            return ContentGapAnalysisResult(**data)
        elif isinstance(orm_obj, DomainHistoryORM): # New: Handle DomainHistoryORM
            if 'snapshot_date' in data and isinstance(data['snapshot_date'], str):
                data['snapshot_date'] = datetime.fromisoformat(data['snapshot_date'])
            return DomainHistory(**data)
        elif isinstance(orm_obj, DomainIntelligenceORM): # New: Handle DomainIntelligenceORM
            if 'last_updated' in data and isinstance(data['last_updated'], str):
                data['last_updated'] = datetime.fromisoformat(data['last_updated'])
            return DomainIntelligence(**data)
        elif isinstance(orm_obj, SocialMentionORM): # New: Handle SocialMentionORM
            if 'published_date' in data and isinstance(data['published_date'], str):
                data['published_date'] = datetime.fromisoformat(data['published_date'])
            return SocialMention(**data)
        return orm_obj

    def _to_orm(self, dc_obj: Any):
        """Converts a dataclass object to its corresponding ORM object."""
        if dc_obj is None:
            return None

        data = serialize_model(dc_obj) # Use the serialize_model utility
        
        # Special handling for enums and sets for ORM
        for key, value in data.items():
            if isinstance(value, enum.Enum):
                data[key] = value.value # Store enum value as string
            if isinstance(value, set):
                data[key] = list(value) # Convert set to list for ARRAY type in ORM

        if isinstance(dc_obj, Domain):
            return DomainORM(**data)
        elif isinstance(dc_obj, URL):
            # URL dataclass has init=False for domain and path, so pass others
            return URLORM(
                url=dc_obj.url,
                domain_name=dc_obj.domain, # Use the calculated domain
                path=dc_obj.path, # Use the calculated path
                **{k: v for k, v in data.items() if k not in ['url', 'domain', 'path']}
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
                rel_attributes=dc_obj.rel_attributes,
                context_text=dc_obj.context_text,
                position_on_page=dc_obj.position_on_page,
                is_image_link=dc_obj.is_image_link,
                alt_text=dc_obj.alt_text,
                discovered_date=dc_obj.discovered_date,
                last_seen_date=dc_obj.last_seen_date,
                authority_passed=dc_obj.authority_passed,
                is_active=dc_obj.is_active,
                spam_level=dc_obj.spam_level.value,
                http_status=dc_obj.http_status,
                crawl_timestamp=dc_obj.crawl_timestamp,
                source_domain_metrics=dc_obj.source_domain_metrics
            )
        elif isinstance(dc_obj, LinkProfile):
            # LinkProfileORM does not have 'backlinks' or 'top_pages' fields
            data.pop('backlinks', None)
            data.pop('top_pages', None)
            return LinkProfileORM(**data)
        elif isinstance(dc_obj, CrawlJob):
            # Handle nested CrawlError dataclasses
            if 'error_log' in data and data['error_log']:
                data['error_log'] = [serialize_model(err) for err in dc_obj.error_log] # Store as list of dicts
            # Convert status enum to value
            data['status'] = dc_obj.status.value
            return CrawlJobORM(**data)
        elif isinstance(dc_obj, SEOMetrics):
            return SEOMetricsORM(**data)
        elif isinstance(dc_obj, SERPResult):
            return SERPResultORM(**data)
        elif isinstance(dc_obj, KeywordSuggestion):
            return KeywordSuggestionORM(**data)
        elif isinstance(dc_obj, AlertRule): # New: Handle AlertRule
            # Convert enums to their string values
            data['severity'] = dc_obj.severity.value
            data['notification_channels'] = [c.value for c in dc_obj.notification_channels]
            return AlertRuleORM(**data)
        elif isinstance(dc_obj, User): # New: Handle User
            return UserORM(**data)
        elif isinstance(dc_obj, ContentGapAnalysisResult): # New: Handle ContentGapAnalysisResult
            return ContentGapAnalysisResultORM(**data)
        elif isinstance(dc_obj, DomainHistory): # New: Handle DomainHistory
            return DomainHistoryORM(**data)
        elif isinstance(dc_obj, DomainIntelligence): # New: Handle DomainIntelligence
            return DomainIntelligenceORM(**data)
        elif isinstance(dc_obj, SocialMention): # New: Handle SocialMention
            return SocialMentionORM(**data)
        return dc_obj

    def add_backlink(self, backlink: Backlink) -> None:
        """Adds a single backlink to the database."""
        session = self._get_session()
        try:
            orm_backlink = self._to_orm(backlink)
            session.add(orm_backlink)
            session.commit()
            logger.debug(f"Added backlink: {backlink.source_url} -> {backlink.target_url}")
        except IntegrityError:
            session.rollback()
            logger.debug(f"Backlink already exists (source: {backlink.source_url}, target: {backlink.target_url}). Skipping.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding backlink {backlink.id}: {e}", exc_info=True)
        finally:
            session.close()

    def add_backlinks(self, backlinks: List[Backlink]) -> None:
        """Adds multiple backlinks to the database in a single transaction."""
        if not backlinks:
            return

        session = self._get_session()
        try:
            orm_backlinks = []
            for backlink in backlinks:
                try:
                    orm_backlinks.append(self._to_orm(backlink))
                except Exception as e:
                    logger.error(f"Error converting backlink {backlink.id} to ORM: {e}", exc_info=True)
            
            session.add_all(orm_backlinks)
            session.commit()
            logger.info(f"Added {len(orm_backlinks)} backlinks to the database.")
        except IntegrityError:
            session.rollback()
            logger.warning(f"Some backlinks already exist. Attempting individual adds for {len(backlinks)} backlinks.")
            # Fallback to individual adds for better error reporting on duplicates
            for backlink in backlinks:
                self.add_backlink(backlink) # This will log duplicates as debug
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding multiple backlinks: {e}", exc_info=True)
        finally:
            session.close()

    def update_backlink(self, backlink: Backlink) -> None:
        """Updates an existing backlink in the database."""
        session = self._get_session()
        try:
            orm_backlink = session.query(BacklinkORM).filter_by(id=backlink.id).first()
            if orm_backlink:
                # Update fields from the dataclass
                updated_data = self._to_orm(backlink) # Convert dataclass to a temporary ORM for data extraction
                for column in inspect(BacklinkORM).columns:
                    # Skip primary key and relationships
                    if column.key == 'id' or column.key.endswith('_rel'):
                        continue
                    if hasattr(updated_data, column.key):
                        setattr(orm_backlink, column.key, getattr(updated_data, column.key))
                session.commit()
                logger.debug(f"Updated backlink: {backlink.id}")
            else:
                logger.warning(f"Backlink with ID {backlink.id} not found for update.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating backlink {backlink.id}: {e}", exc_info=True)
        finally:
            session.close()

    def get_backlinks_for_target(self, target_url: str) -> List[Backlink]:
        """Retrieves all backlinks pointing to a specific target URL."""
        session = self._get_session()
        try:
            orm_backlinks = session.query(BacklinkORM).filter_by(target_url=target_url).all()
            return [self._to_dataclass(bl) for bl in orm_backlinks]
        except Exception as e:
            logger.error(f"Error retrieving backlinks for target {target_url}: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def get_backlinks_from_source(self, source_url: str) -> List[Backlink]:
        """Retrieves all outgoing links (backlinks) from a specific source URL."""
        session = self._get_session()
        try:
            orm_backlinks = session.query(BacklinkORM).filter_by(source_url=source_url).all()
            return [self._to_dataclass(bl) for bl in orm_backlinks]
        except Exception as e:
            logger.error(f"Error retrieving outgoing backlinks from source {source_url}: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def get_all_backlinks(self) -> List[Backlink]:
        """Retrieves all backlinks from the database."""
        session = self._get_session()
        try:
            orm_backlinks = session.query(BacklinkORM).all()
            return [self._to_dataclass(bl) for bl in orm_backlinks]
        except Exception as e:
            logger.error(f"Error retrieving all backlinks: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def save_link_profile(self, profile: LinkProfile) -> None:
        """Saves or updates a link profile."""
        session = self._get_session()
        try:
            orm_profile = session.query(LinkProfileORM).filter_by(target_url=profile.target_url).first()
            if orm_profile:
                # Update existing
                updated_data = self._to_orm(profile)
                for column in inspect(LinkProfileORM).columns:
                    if hasattr(updated_data, column.key):
                        setattr(orm_profile, column.key, getattr(updated_data, column.key))
                logger.debug(f"Updated link profile for {profile.target_url}")
            else:
                # Add new
                orm_profile = self._to_orm(profile)
                session.add(orm_profile)
                logger.debug(f"Added link profile for {profile.target_url}")
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving link profile for {profile.target_url}: {e}", exc_info=True)
        finally:
            session.close()

    def get_link_profile(self, target_url: str) -> Optional[LinkProfile]:
        """Retrieves a link profile by target URL."""
        session = self._get_session()
        try:
            orm_profile = session.query(LinkProfileORM).filter_by(target_url=target_url).first()
            return self._to_dataclass(orm_profile)
        except Exception as e:
            logger.error(f"Error retrieving link profile for {target_url}: {e}", exc_info=True)
            return None
        finally:
            session.close()

    def get_all_link_profiles(self) -> List[LinkProfile]:
        """Retrieves all link profiles from the database."""
        session = self._get_session()
        try:
            orm_profiles = session.query(LinkProfileORM).all()
            return [self._to_dataclass(lp) for lp in orm_profiles]
        except Exception as e:
            logger.error(f"Error retrieving all link profiles: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def add_crawl_job(self, job: CrawlJob) -> None:
        """Adds a new crawl job to the database."""
        session = self._get_session()
        try:
            orm_job = self._to_orm(job)
            session.add(orm_job)
            session.commit()
            logger.info(f"Added crawl job {job.id} to DB.")
        except IntegrityError:
            session.rollback()
            logger.warning(f"Crawl job {job.id} already exists. Skipping.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding crawl job {job.id}: {e}", exc_info=True)
        finally:
            session.close()

    def get_crawl_job(self, job_id: str) -> Optional[CrawlJob]:
        """Retrieves a crawl job by its ID."""
        session = self._get_session()
        try:
            orm_job = session.query(CrawlJobORM).filter_by(id=job_id).first()
            return self._to_dataclass(orm_job)
        except Exception as e:
            logger.error(f"Error retrieving crawl job {job_id}: {e}", exc_info=True)
            return None
        finally:
            session.close()

    def get_all_crawl_jobs(self) -> List[CrawlJob]:
        """Retrieves a list of all crawl jobs from the database."""
        session = self._get_session()
        try:
            orm_jobs = session.query(CrawlJobORM).all()
            return [self._to_dataclass(job) for job in orm_jobs]
        except Exception as e:
            logger.error(f"Error retrieving all crawl jobs: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def update_crawl_job(self, job: CrawlJob) -> None:
        """Updates an existing crawl job's status and progress."""
        session = self._get_session()
        try:
            orm_job = session.query(CrawlJobORM).filter_by(id=job.id).first()
            if orm_job:
                # Update fields from the dataclass
                updated_data = self._to_orm(job)
                for column in inspect(CrawlJobORM).columns:
                    # Skip primary key and relationships
                    if column.key == 'id' or column.key.endswith('_rel'):
                        continue
                    if hasattr(updated_data, column.key):
                        setattr(orm_job, column.key, getattr(updated_data, column.key))
                session.commit()
                logger.debug(f"Updated crawl job {job.id} status to {job.status.value}.")
            else:
                logger.warning(f"Crawl job {job.id} not found for update.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating crawl job {job.id}: {e}", exc_info=True)
        finally:
            session.close()

    def get_pending_crawl_jobs(self) -> List[CrawlJob]:
        """Retrieves all pending crawl jobs."""
        session = self._get_session()
        try:
            orm_jobs = session.query(CrawlJobORM).filter_by(status="pending").all()
            return [self._to_dataclass(job) for job in orm_jobs]
        except Exception as e:
            logger.error(f"Error retrieving pending crawl jobs: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def save_domain(self, domain: Domain) -> None:
        """Saves or updates a domain."""
        session = self._get_session()
        try:
            orm_domain = session.query(DomainORM).filter_by(name=domain.name).first()
            if orm_domain:
                # Update existing
                updated_data = self._to_orm(domain)
                for column in inspect(DomainORM).columns:
                    # Skip primary key and relationships
                    if column.key == 'name' or column.key.endswith('_rel'):
                        continue
                    if hasattr(updated_data, column.key):
                        setattr(orm_domain, column.key, getattr(updated_data, column.key))
                logger.debug(f"Updated domain: {domain.name}")
            else:
                # Add new
                orm_domain = self._to_orm(domain)
                session.add(orm_domain)
                logger.debug(f"Added domain: {domain.name}")
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving domain {domain.name}: {e}", exc_info=True)
        finally:
            session.close()

    def get_domain(self, name: str) -> Optional[Domain]:
        """Retrieves a domain by its name."""
        session = self._get_session()
        try:
            orm_domain = session.query(DomainORM).filter_by(name=name).first()
            return self._to_dataclass(orm_domain)
        except Exception as e:
            logger.error(f"Error retrieving domain {name}: {e}", exc_info=True)
            return None
        finally:
            session.close()

    def get_all_domains(self) -> List[Domain]:
        """Retrieves all domains from the database."""
        session = self._get_session()
        try:
            orm_domains = session.query(DomainORM).all()
            return [self._to_dataclass(d) for d in orm_domains]
        except Exception as e:
            logger.error(f"Error retrieving all domains: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def save_url(self, url_obj: URL) -> None:
        """Saves or updates a URL."""
        session = self._get_session()
        try:
            orm_url = session.query(URLORM).filter_by(url=url_obj.url).first()
            if orm_url:
                # Update existing
                updated_data = self._to_orm(url_obj)
                for column in inspect(URLORM).columns:
                    # Skip primary key and relationships
                    if column.key == 'url' or column.key.endswith('_rel'):
                        continue
                    if hasattr(updated_data, column.key):
                        setattr(orm_url, column.key, getattr(updated_data, column.key))
                session.commit()
                logger.debug(f"Updated URL: {url_obj.url}")
            else:
                # Add new
                orm_url = self._to_orm(url_obj)
                session.add(orm_url)
                logger.debug(f"Added URL: {url_obj.url}")
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving URL {url_obj.url}: {e}", exc_info=True)
        finally:
            session.close()

    def get_url(self, url_str: str) -> Optional[URL]:
        """Retrieves a URL by its string representation."""
        session = self._get_session()
        try:
            orm_url = session.query(URLORM).filter_by(url=url_str).first()
            return self._to_dataclass(orm_url)
        except Exception as e:
            logger.error(f"Error retrieving URL {url_str}: {e}", exc_info=True)
            return None
        finally:
            session.close()

    def save_seo_metrics(self, seo_metrics: SEOMetrics) -> None:
        """Saves or updates SEO metrics for a URL."""
        session = self._get_session()
        try:
            # Ensure the URL exists before saving metrics for it
            url_obj = self.get_url(seo_metrics.url)
            if not url_obj:
                # Create a minimal URL entry if it doesn't exist
                # This might happen if a page is crawled but not explicitly added as a URL first
                logger.warning(f"URL {seo_metrics.url} not found in DB. Creating minimal entry before saving SEO metrics.")
                parsed_url = urlparse(seo_metrics.url)
                domain_name = parsed_url.netloc
                path = parsed_url.path or '/'
                # Ensure domain exists
                if not self.get_domain(domain_name):
                    self.save_domain(Domain(name=domain_name))
                self.save_url(URL(url=seo_metrics.url, domain=domain_name, path=path))
                
            orm_seo_metrics = session.query(SEOMetricsORM).filter_by(url=seo_metrics.url).first()
            if orm_seo_metrics:
                # Update existing
                updated_data = self._to_orm(seo_metrics)
                for column in inspect(SEOMetricsORM).columns:
                    # Skip primary key and relationships
                    if column.key == 'url' or column.key.endswith('_rel'):
                        continue
                    if hasattr(updated_data, column.key):
                        setattr(orm_seo_metrics, column.key, getattr(updated_data, column.key))
                session.commit()
                logger.debug(f"Updated SEO metrics for {seo_metrics.url}")
            else:
                # Add new
                orm_seo_metrics = self._to_orm(seo_metrics)
                session.add(orm_seo_metrics)
                session.commit()
                logger.debug(f"Added SEO metrics for {seo_metrics.url}")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving SEO metrics for {seo_metrics.url}: {e}", exc_info=True)
        finally:
            session.close()

    def get_seo_metrics(self, url_str: str) -> Optional[SEOMetrics]:
        """Retrieves SEO metrics for a URL."""
        session = self._get_session()
        try:
            orm_seo_metrics = session.query(SEOMetricsORM).filter_by(url=url_str).first()
            return self._to_dataclass(orm_seo_metrics)
        except Exception as e:
            logger.error(f"Error retrieving SEO metrics for {url_str}: {e}", exc_info=True)
            return None
        finally:
            session.close()

    def add_serp_results(self, serp_results: List[SERPResult]) -> None:
        """Adds multiple SERP results to the database."""
        if not serp_results:
            return

        session = self._get_session()
        try:
            orm_serp_results = []
            for result in serp_results:
                try:
                    orm_serp_results.append(self._to_orm(result))
                except Exception as e:
                    logger.error(f"Error converting SERP result to ORM: {e}", exc_info=True)
            
            session.add_all(orm_serp_results)
            session.commit()
            logger.info(f"Added {len(orm_serp_results)} SERP results to the database.")
        except IntegrityError:
            session.rollback()
            logger.warning(f"Some SERP results already exist. Attempting individual adds for {len(serp_results)} results.")
            for result in serp_results:
                self.add_serp_result(result) # This will log duplicates as debug
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding multiple SERP results: {e}", exc_info=True)
        finally:
            session.close()

    def add_serp_result(self, serp_result: SERPResult) -> None:
        """Adds a single SERP result to the database."""
        session = self._get_session()
        try:
            orm_serp_result = self._to_orm(serp_result)
            session.add(orm_serp_result)
            session.commit()
            logger.debug(f"Added SERP result for keyword '{serp_result.keyword}' at position {serp_result.position}.")
        except IntegrityError:
            session.rollback()
            logger.debug(f"SERP result for keyword '{serp_result.keyword}' and URL '{serp_result.result_url}' already exists. Skipping.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding SERP result for keyword '{serp_result.keyword}': {e}", exc_info=True)
        finally:
            session.close()

    def get_serp_results_for_keyword(self, keyword: str) -> List[SERPResult]:
        """Retrieves SERP results for a specific keyword."""
        session = self._get_session()
        try:
            orm_results = session.query(SERPResultORM).filter_by(keyword=keyword).order_by(SERPResultORM.position).all()
            return [self._to_dataclass(res) for res in orm_results]
        except Exception as e:
            logger.error(f"Error retrieving SERP results for keyword '{keyword}': {e}", exc_info=True)
            return []
        finally:
            session.close()

    def get_serp_position_history(self, target_url: str, keyword: str, num_snapshots: int = 12) -> List[SERPResult]:
        """
        Retrieves the historical SERP positions for a specific URL and keyword.

        Args:
            target_url: The URL for which to track history.
            keyword: The keyword for which to track history.
            num_snapshots: The maximum number of recent historical snapshots to retrieve.

        Returns:
            A list of SERPResult objects, sorted by crawl_timestamp (most recent first).
        """
        session = self._get_session()
        try:
            orm_history_records = session.query(SERPResultORM).filter(
                SERPResultORM.result_url == target_url,
                SERPResultORM.keyword == keyword
            ).order_by(SERPResultORM.crawl_timestamp.desc()).limit(num_snapshots).all()
            return [self._to_dataclass(rec) for rec in orm_history_records]
        except Exception as e:
            logger.error(f"Error retrieving SERP position history for URL '{target_url}' and keyword '{keyword}': {e}", exc_info=True)
            return []
        finally:
            session.close()

    def add_keyword_suggestions(self, suggestions: List[KeywordSuggestion]) -> None:
        """Adds multiple keyword suggestions to the database."""
        if not suggestions:
            return

        session = self._get_session()
        try:
            orm_suggestions = []
            for suggestion in suggestions:
                try:
                    orm_suggestions.append(self._to_orm(suggestion))
                except Exception as e:
                    logger.error(f"Error converting keyword suggestion to ORM: {e}", exc_info=True)
            
            session.add_all(orm_suggestions)
            session.commit()
            logger.info(f"Added {len(orm_suggestions)} keyword suggestions to the database.")
        except IntegrityError:
            session.rollback()
            logger.warning(f"Some keyword suggestions already exist. Attempting individual adds for {len(suggestions)} suggestions.")
            for suggestion in suggestions:
                self.add_keyword_suggestion(suggestion) # This will log duplicates as debug
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding multiple keyword suggestions: {e}", exc_info=True)
        finally:
            session.close()

    def add_keyword_suggestion(self, suggestion: KeywordSuggestion) -> None:
        """Adds a single keyword suggestion to the database."""
        session = self._get_session()
        try:
            orm_suggestion = self._to_orm(suggestion)
            session.add(orm_suggestion)
            session.commit()
            logger.debug(f"Added keyword suggestion '{suggestion.suggested_keyword}' for seed '{suggestion.seed_keyword}'.")
        except IntegrityError:
            session.rollback()
            logger.debug(f"Keyword suggestion '{suggestion.suggested_keyword}' for seed '{suggestion.seed_keyword}' already exists. Skipping.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding keyword suggestion '{suggestion.suggested_keyword}': {e}", exc_info=True)
        finally:
            session.close()

    def get_keyword_suggestions_for_seed(self, seed_keyword: str) -> List[KeywordSuggestion]:
        """Retrieves keyword suggestions for a specific seed keyword."""
        session = self._get_session()
        try:
            orm_suggestions = session.query(KeywordSuggestionORM).filter_by(seed_keyword=seed_keyword).all()
            return [self._to_dataclass(sug) for sug in orm_suggestions]
        except Exception as e:
            logger.error(f"Error retrieving keyword suggestions for seed '{seed_keyword}': {e}", exc_info=True)
            return []
        finally:
            session.close()

    def get_source_domains_for_target_domains(self, target_domains: List[str]) -> Dict[str, Set[str]]:
        """
        Retrieves all unique source domains linking to each of the specified target domains.
        Returns a dictionary where keys are target domains and values are sets of unique source domains.
        """
        session = self._get_session()
        try:
            # Query for backlinks where target_domain_name is in the list of target_domains
            # Select source_domain_name and target_domain_name
            results = session.query(
                BacklinkORM.source_domain_name,
                BacklinkORM.target_domain_name
            ).filter(
                BacklinkORM.target_domain_name.in_(target_domains)
            ).all()

            linking_domains_map: Dict[str, Set[str]] = {domain: set() for domain in target_domains}
            for source_domain, target_domain in results:
                linking_domains_map[target_domain].add(source_domain)
            
            logger.info(f"Retrieved linking domains for {len(target_domains)} target domains.")
            return linking_domains_map
        except Exception as e:
            logger.error(f"Error retrieving source domains for target domains {target_domains}: {e}", exc_info=True)
            return {domain: set() for domain in target_domains} # Return empty sets on error
        finally:
            session.close()

    def get_keywords_ranked_for_domains(self, domains: List[str]) -> Dict[str, Set[str]]:
        """
        Retrieves all unique keywords that each of the specified domains rank for (from SERP results).
        Returns a dictionary where keys are domains and values are sets of unique keywords.
        """
        session = self._get_session()
        try:
            # Get all SERP results for URLs belonging to the target domains
            # Optimised query to directly filter by domain from URL
            results = session.query(
                SERPResultORM.result_url,
                SERPResultORM.keyword
            ).all() # Fetch all and filter in Python for simplicity, or use more complex SQLAlchemy for large datasets

            ranked_keywords_map: Dict[str, Set[str]] = {domain: set() for domain in domains}
            
            for result_url, keyword in results:
                try:
                    parsed_url = urlparse(result_url)
                    result_domain = parsed_url.netloc.lower()
                    if result_domain in domains:
                        ranked_keywords_map[result_domain].add(keyword)
                except Exception as e:
                    logger.warning(f"Could not parse domain from SERP result URL '{result_url}': {e}")
                    continue
            
            logger.info(f"Retrieved ranked keywords for {len(domains)} domains.")
            return ranked_keywords_map
        except Exception as e:
            logger.error(f"Error retrieving ranked keywords for domains {domains}: {e}", exc_info=True)
            return {domain: set() for domain in domains} # Return empty sets on error
        finally:
            session.close()

    def get_count_of_competitive_keyword_analyses(self) -> int:
        """
        Retrieves the count of competitive keyword analysis jobs that have been completed.
        This is a placeholder and assumes 'competitive_keyword_analysis' is a job_type.
        """
        session = self._get_session()
        try:
            count = session.query(CrawlJobORM).filter_by(job_type='competitive_keyword_analysis', status='completed').count()
            return count
        except Exception as e:
            logger.error(f"Error getting count of competitive keyword analyses: {e}", exc_info=True)
            return 0
        finally:
            session.close()

    # New: Alert Rule methods
    def save_alert_rule(self, rule: AlertRule) -> None:
        """Saves or updates an alert rule."""
        session = self._get_session()
        try:
            orm_rule = session.query(AlertRuleORM).filter_by(id=rule.id).first()
            if orm_rule:
                # Update existing
                updated_data = self._to_orm(rule)
                for column in inspect(AlertRuleORM).columns:
                    if hasattr(updated_data, column.key):
                        setattr(orm_rule, column.key, getattr(updated_data, column.key))
                logger.debug(f"Updated alert rule: {rule.name}")
            else:
                # Add new
                orm_rule = self._to_orm(rule)
                session.add(orm_rule)
                logger.debug(f"Added alert rule: {rule.name}")
            session.commit()
        except IntegrityError:
            session.rollback()
            logger.warning(f"Alert rule with name '{rule.name}' already exists. Skipping add.")
            raise ValueError(f"Alert rule with name '{rule.name}' already exists.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving alert rule {rule.name}: {e}", exc_info=True)
            raise
        finally:
            session.close()

    def get_alert_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Retrieves an alert rule by its ID."""
        session = self._get_session()
        try:
            orm_rule = session.query(AlertRuleORM).filter_by(id=rule_id).first()
            return self._to_dataclass(orm_rule)
        except Exception as e:
            logger.error(f"Error retrieving alert rule {rule_id}: {e}", exc_info=True)
            return None
        finally:
            session.close()

    def get_all_alert_rules(self, active_only: bool = False) -> List[AlertRule]:
        """Retrieves all alert rules, optionally filtering for active ones."""
        session = self._get_session()
        try:
            query = session.query(AlertRuleORM)
            if active_only:
                query = query.filter_by(is_active=True)
            orm_rules = query.all()
            return [self._to_dataclass(rule) for rule in orm_rules]
        except Exception as e:
            logger.error(f"Error retrieving all alert rules: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def delete_alert_rule(self, rule_id: str) -> bool:
        """Deletes an alert rule by its ID."""
        session = self._get_session()
        try:
            orm_rule = session.query(AlertRuleORM).filter_by(id=rule_id).first()
            if orm_rule:
                session.delete(orm_rule)
                session.commit()
                logger.info(f"Deleted alert rule {rule_id}.")
                return True
            else:
                logger.warning(f"Alert rule {rule_id} not found for deletion.")
                return False
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting alert rule {rule_id}: {e}", exc_info=True)
            raise
        finally:
            session.close()

    # New: User methods for Authentication
    def create_user(self, user: User) -> User:
        """Creates a new user in the database."""
        session = self._get_session()
        try:
            orm_user = self._to_orm(user)
            session.add(orm_user)
            session.commit()
            session.refresh(orm_user) # Refresh to get any auto-generated fields like ID
            logger.info(f"Created new user: {user.username}")
            return self._to_dataclass(orm_user)
        except IntegrityError:
            session.rollback()
            logger.warning(f"User with username '{user.username}' or email '{user.email}' already exists.")
            raise ValueError(f"User with username '{user.username}' or email '{user.email}' already exists.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating user {user.username}: {e}", exc_info=True)
            raise
        finally:
            session.close()

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Retrieves a user by their username."""
        session = self._get_session()
        try:
            orm_user = session.query(UserORM).filter_by(username=username).first()
            return self._to_dataclass(orm_user)
        except Exception as e:
            logger.error(f"Error retrieving user by username '{username}': {e}", exc_info=True)
            return None
        finally:
            session.close()

    # New: Content Gap Analysis methods
    def save_content_gap_analysis_result(self, result: ContentGapAnalysisResult) -> None:
        """Saves or updates a content gap analysis result."""
        session = self._get_session()
        try:
            orm_result = self._to_orm(result)
            session.add(orm_result)
            session.commit()
            logger.debug(f"Saved content gap analysis result for {result.target_url}.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving content gap analysis result for {result.target_url}: {e}", exc_info=True)
            raise
        finally:
            session.close()

    def get_content_gap_analysis_result(self, target_url: str) -> Optional[ContentGapAnalysisResult]:
        """Retrieves a content gap analysis result by target URL."""
        session = self._get_session()
        try:
            orm_result = session.query(ContentGapAnalysisResultORM).filter_by(target_url=target_url).first()
            return self._to_dataclass(orm_result)
        except Exception as e:
            logger.error(f"Error retrieving content gap analysis result for {target_url}: {e}", exc_info=True)
            return None
        finally:
            session.close()

    def get_backlink_counts_over_time(self, target_domain: str, time_unit: str = "month", num_units: int = 6) -> Dict[str, int]:
        """
        Retrieves the count of backlinks discovered over specified time units for a target domain.

        Args:
            target_domain: The domain for which to track backlink counts.
            time_unit: The unit of time ('day', 'week', 'month', 'quarter', 'year').
            num_units: The number of past units to retrieve data for.

        Returns:
            A dictionary where keys are time period strings (e.g., "YYYY-MM" for months)
            and values are the count of backlinks discovered in that period.
        """
        session = self._get_session()
        try:
            results = {}
            current_date = datetime.now()

            for i in range(num_units):
                if time_unit == "month":
                    start_of_unit = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30*i) # Approximate start of month
                    # Adjust to actual start of month
                    start_of_unit = start_of_unit.replace(day=1)
                    end_of_unit = (start_of_unit + timedelta(days=32)).replace(day=1) - timedelta(days=1) # End of current month
                    period_label = start_of_unit.strftime("%Y-%m")
                elif time_unit == "quarter":
                    current_quarter_month = (current_date.month - 1) // 3 * 3 + 1
                    start_of_unit = current_date.replace(month=current_quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=90*i)
                    # Adjust to actual start of quarter
                    start_of_unit = start_of_unit.replace(month=((start_of_unit.month - 1) // 3 * 3 + 1), day=1)
                    end_of_unit = (start_of_unit + timedelta(days=92)).replace(month=((start_of_unit.month - 1) // 3 * 3 + 1 + 3), day=1) - timedelta(days=1)
                    period_label = f"{start_of_unit.year}-Q{(start_of_unit.month-1)//3 + 1}"
                elif time_unit == "year":
                    start_of_unit = current_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=365*i)
                    end_of_unit = start_of_unit.replace(year=start_of_unit.year + 1) - timedelta(days=1)
                    period_label = str(start_of_unit.year)
                elif time_unit == "week":
                    start_of_unit = current_date - timedelta(weeks=i)
                    start_of_unit = start_of_unit - timedelta(days=start_of_unit.weekday()) # Monday of the week
                    start_of_unit = start_of_unit.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_of_unit = start_of_unit + timedelta(days=6, hours=23, minutes=59, seconds=59)
                    period_label = f"{start_of_unit.isocalendar().year}-W{start_of_unit.isocalendar().week:02d}"
                elif time_unit == "day":
                    start_of_unit = current_date - timedelta(days=i)
                    start_of_unit = start_of_unit.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_of_unit = start_of_unit.replace(hour=23, minute=59, second=59, microsecond=999999)
                    period_label = start_of_unit.strftime("%Y-%m-%d")
                else:
                    raise ValueError("Invalid time_unit. Must be 'day', 'week', 'month', 'quarter', or 'year'.")

                count = session.query(BacklinkORM).filter(
                    BacklinkORM.target_domain_name == target_domain,
                    BacklinkORM.discovered_date >= start_of_unit,
                    BacklinkORM.discovered_date <= end_of_unit
                ).count()
                results[period_label] = count
            
            logger.info(f"Retrieved backlink counts for {target_domain} over {num_units} {time_unit}s.")
            return results
        except Exception as e:
            logger.error(f"Error retrieving backlink counts for {target_domain}: {e}", exc_info=True)
            return {}
        finally:
            session.close()

    def save_domain_history(self, domain_history: DomainHistory) -> None:
        """Saves a historical snapshot of domain metrics."""
        session = self._get_session()
        try:
            orm_history = self._to_orm(domain_history)
            session.add(orm_history)
            session.commit()
            logger.debug(f"Saved domain history for {domain_history.domain_name} on {domain_history.snapshot_date.strftime('%Y-%m-%d')}.")
        except IntegrityError:
            session.rollback()
            logger.debug(f"Domain history for {domain_history.domain_name} on {domain_history.snapshot_date.strftime('%Y-%m-%d')} already exists. Skipping.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving domain history for {domain_history.domain_name}: {e}", exc_info=True)
            raise
        finally:
            session.close()

    def get_domain_history(self, domain_name: str, num_snapshots: int = 12) -> List[DomainHistory]:
        """
        Retrieves historical snapshots of a domain's metrics.

        Args:
            domain_name: The domain for which to retrieve history.
            num_snapshots: The maximum number of recent historical snapshots to retrieve.

        Returns:
            A list of DomainHistory objects, sorted by snapshot_date (most recent first).
        """
        session = self._get_session()
        try:
            orm_history_records = session.query(DomainHistoryORM).filter_by(domain_name=domain_name).order_by(DomainHistoryORM.snapshot_date.desc()).limit(num_snapshots).all()
            return [self._to_dataclass(rec) for rec in orm_history_records]
        except Exception as e:
            logger.error(f"Error retrieving domain history for {domain_name}: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def get_crawl_performance_trends(self, time_unit: str = "month", num_units: int = 6) -> List[Dict[str, Any]]:
        """
        Retrieves aggregated crawl performance trends over specified time units.

        Args:
            time_unit: The unit of time ('day', 'week', 'month', 'quarter', 'year').
            num_units: The number of past units to retrieve data for.

        Returns:
            A list of dictionaries, each representing a time period with aggregated metrics.
        """
        session = self._get_session()
        try:
            trends = []
            current_date = datetime.now()

            for i in range(num_units):
                if time_unit == "month":
                    start_of_unit = current_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30*i)
                    start_of_unit = start_of_unit.replace(day=1)
                    end_of_unit = (start_of_unit + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                    period_label = start_of_unit.strftime("%Y-%m")
                elif time_unit == "quarter":
                    current_quarter_month = (current_date.month - 1) // 3 * 3 + 1
                    start_of_unit = current_date.replace(month=current_quarter_month, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=90*i)
                    start_of_unit = start_of_unit.replace(month=((start_of_unit.month - 1) // 3 * 3 + 1), day=1)
                    end_of_unit = (start_of_unit + timedelta(days=92)).replace(month=((start_of_unit.month - 1) // 3 * 3 + 1 + 3), day=1) - timedelta(days=1)
                    period_label = f"{start_of_unit.year}-Q{(start_of_unit.month-1)//3 + 1}"
                elif time_unit == "year":
                    start_of_unit = current_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=365*i)
                    end_of_unit = start_of_unit.replace(year=start_of_unit.year + 1) - timedelta(days=1)
                    period_label = str(start_of_unit.year)
                elif time_unit == "week":
                    start_of_unit = current_date - timedelta(weeks=i)
                    start_of_unit = start_of_unit - timedelta(days=start_of_unit.weekday())
                    start_of_unit = start_of_unit.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_of_unit = start_of_unit + timedelta(days=6, hours=23, minutes=59, seconds=59)
                    period_label = f"{start_of_unit.isocalendar().year}-W{start_of_unit.isocalendar().week:02d}"
                elif time_unit == "day":
                    start_of_unit = current_date - timedelta(days=i)
                    start_of_unit = start_of_unit.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_of_unit = start_of_unit.replace(hour=23, minute=59, second=59, microsecond=999999)
                    period_label = start_of_unit.strftime("%Y-%m-%d")
                else:
                    raise ValueError("Invalid time_unit. Must be 'day', 'week', 'month', 'quarter', or 'year'.")

                # Query for jobs completed within the current time unit
                jobs_in_period = session.query(CrawlJobORM).filter(
                    CrawlJobORM.completed_date >= start_of_unit,
                    CrawlJobORM.completed_date <= end_of_unit
                ).all()

                total_jobs = len(jobs_in_period)
                successful_jobs = len([j for j in jobs_in_period if j.status == CrawlStatusEnum.COMPLETED])
                failed_jobs = total_jobs - successful_jobs
                
                total_duration = sum(j.duration_seconds for j in jobs_in_period if j.duration_seconds is not None)
                avg_duration = total_duration / total_jobs if total_jobs > 0 else 0.0
                
                success_rate = (successful_jobs / total_jobs) * 100 if total_jobs > 0 else 0.0
                
                total_errors = sum(j.errors_count for j in jobs_in_period)
                
                trends.append({
                    "period": period_label,
                    "total_jobs": total_jobs,
                    "successful_jobs": successful_jobs,
                    "failed_jobs": failed_jobs,
                    "avg_duration_seconds": round(avg_duration, 2),
                    "success_rate_percent": round(success_rate, 1),
                    "total_errors": total_errors
                })
            
            # Sort trends by period (oldest first)
            trends.sort(key=lambda x: x['period'])
            
            logger.info(f"Retrieved crawl performance trends for {num_units} {time_unit}s.")
            return trends
        except Exception as e:
            logger.error(f"Error retrieving crawl performance trends: {e}", exc_info=True)
            return []
        finally:
            session.close()

    # New: Domain Intelligence methods
    def save_domain_intelligence(self, intelligence: DomainIntelligence) -> None:
        """Saves or updates domain intelligence data."""
        session = self._get_session()
        try:
            orm_intelligence = session.query(DomainIntelligenceORM).filter_by(domain_name=intelligence.domain_name).first()
            if orm_intelligence:
                # Update existing
                updated_data = self._to_orm(intelligence)
                for column in inspect(DomainIntelligenceORM).columns:
                    if hasattr(updated_data, column.key):
                        setattr(orm_intelligence, column.key, getattr(updated_data, column.key))
                logger.debug(f"Updated domain intelligence for {intelligence.domain_name}.")
            else:
                # Add new
                orm_intelligence = self._to_orm(intelligence)
                session.add(orm_intelligence)
                logger.debug(f"Added domain intelligence for {intelligence.domain_name}.")
            session.commit()
        except IntegrityError:
            session.rollback()
            logger.warning(f"Domain intelligence for '{intelligence.domain_name}' already exists. Skipping add.")
            raise ValueError(f"Domain intelligence for '{intelligence.domain_name}' already exists.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving domain intelligence for {intelligence.domain_name}: {e}", exc_info=True)
            raise
        finally:
            session.close()

    def get_domain_intelligence(self, domain_name: str) -> Optional[DomainIntelligence]:
        """Retrieves domain intelligence data by domain name."""
        session = self._get_session()
        try:
            orm_intelligence = session.query(DomainIntelligenceORM).filter_by(domain_name=domain_name).first()
            return self._to_dataclass(orm_intelligence)
        except Exception as e:
            logger.error(f"Error retrieving domain intelligence for {domain_name}: {e}", exc_info=True)
            return None
        finally:
            session.close()

    # New: Social Mention methods
    def add_social_mention(self, mention: SocialMention) -> None:
        """Adds a single social media mention to the database."""
        session = self._get_session()
        try:
            orm_mention = self._to_orm(mention)
            session.add(orm_mention)
            session.commit()
            logger.debug(f"Added social mention: '{mention.query}' on '{mention.platform}'.")
        except IntegrityError:
            session.rollback()
            logger.debug(f"Social mention with URL '{mention.mention_url}' already exists. Skipping.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding social mention '{mention.id}': {e}", exc_info=True)
        finally:
            session.close()

    def add_social_mentions(self, mentions: List[SocialMention]) -> None:
        """Adds multiple social media mentions to the database in a single transaction."""
        if not mentions:
            return

        session = self._get_session()
        try:
            orm_mentions = []
            for mention in mentions:
                try:
                    orm_mentions.append(self._to_orm(mention))
                except Exception as e:
                    logger.error(f"Error converting social mention {mention.id} to ORM: {e}", exc_info=True)
            
            session.add_all(orm_mentions)
            session.commit()
            logger.info(f"Added {len(orm_mentions)} social mentions to the database.")
        except IntegrityError:
            session.rollback()
            logger.warning(f"Some social mentions already exist. Attempting individual adds for {len(mentions)} mentions.")
            for mention in mentions:
                self.add_social_mention(mention) # This will log duplicates as debug
        except Exception as e:
            session.rollback()
            logger.error(f"Error adding multiple social mentions: {e}", exc_info=True)
        finally:
            session.close()

    def get_social_mentions_for_query(self, query: str, platform: Optional[str] = None, limit: int = 100) -> List[SocialMention]:
        """Retrieves social media mentions for a specific query, optionally filtered by platform."""
        session = self._get_session()
        try:
            q = session.query(SocialMentionORM).filter_by(query=query)
            if platform:
                q = q.filter_by(platform=platform)
            orm_mentions = q.order_by(SocialMentionORM.published_date.desc()).limit(limit).all()
            return [self._to_dataclass(m) for m in orm_mentions]
        except Exception as e:
            logger.error(f"Error retrieving social mentions for query '{query}': {e}", exc_info=True)
            return []
        finally:
            session.close()

    # New: Link Prospect methods
    def save_link_prospect(self, prospect: LinkProspect) -> None:
        """Saves or updates a link prospect."""
        session = self._get_session()
        try:
            orm_prospect = session.query(LinkProspectORM).filter_by(url=prospect.url).first()
            if orm_prospect:
                # Update existing
                updated_data = self._to_orm(prospect)
                for column in inspect(LinkProspectORM).columns:
                    if hasattr(updated_data, column.key):
                        setattr(orm_prospect, column.key, getattr(updated_data, column.key))
                logger.debug(f"Updated link prospect: {prospect.url}")
            else:
                # Add new
                orm_prospect = self._to_orm(prospect)
                session.add(orm_prospect)
                logger.debug(f"Added link prospect: {prospect.url}")
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving link prospect {prospect.url}: {e}", exc_info=True)
            raise
        finally:
            session.close()

    def get_link_prospect(self, url: str) -> Optional[LinkProspect]:
        """Retrieves a link prospect by its URL."""
        session = self._get_session()
        try:
            orm_prospect = session.query(LinkProspectORM).filter_by(url=url).first()
            return self._to_dataclass(orm_prospect)
        except Exception as e:
            logger.error(f"Error retrieving link prospect {url}: {e}", exc_info=True)
            return None
        finally:
            session.close()

    def get_all_link_prospects(self, status_filter: Optional[str] = None) -> List[LinkProspect]:
        """Retrieves all link prospects, optionally filtered by status."""
        session = self._get_session()
        try:
            query = session.query(LinkProspectORM)
            if status_filter:
                query = query.filter_by(status=status_filter)
            orm_prospects = query.all()
            return [self._to_dataclass(p) for p in orm_prospects]
        except Exception as e:
            logger.error(f"Error retrieving all link prospects: {e}", exc_info=True)
            return []
        finally:
            session.close()

    # New: Outreach Campaign methods
    def save_outreach_campaign(self, campaign: OutreachCampaign) -> None:
        """Saves or updates an outreach campaign."""
        session = self._get_session()
        try:
            orm_campaign = session.query(OutreachCampaignORM).filter_by(id=campaign.id).first()
            if orm_campaign:
                # Update existing
                updated_data = self._to_orm(campaign)
                for column in inspect(OutreachCampaignORM).columns:
                    if hasattr(updated_data, column.key):
                        setattr(orm_campaign, column.key, getattr(updated_data, column.key))
                logger.debug(f"Updated outreach campaign: {campaign.name}")
            else:
                # Add new
                orm_campaign = self._to_orm(campaign)
                session.add(orm_campaign)
                logger.debug(f"Added outreach campaign: {campaign.name}")
            session.commit()
        except IntegrityError:
            session.rollback()
            logger.warning(f"Outreach campaign with name '{campaign.name}' already exists.")
            raise ValueError(f"Outreach campaign with name '{campaign.name}' already exists.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving outreach campaign {campaign.name}: {e}", exc_info=True)
            raise
        finally:
            session.close()

    def get_outreach_campaign(self, campaign_id: str) -> Optional[OutreachCampaign]:
        """Retrieves an outreach campaign by its ID."""
        session = self._get_session()
        try:
            orm_campaign = session.query(OutreachCampaignORM).filter_by(id=campaign_id).first()
            return self._to_dataclass(orm_campaign)
        except Exception as e:
            logger.error(f"Error retrieving outreach campaign {campaign_id}: {e}", exc_info=True)
            return None
        finally:
            session.close()

    def get_all_outreach_campaigns(self, status_filter: Optional[str] = None) -> List[OutreachCampaign]:
        """Retrieves all outreach campaigns, optionally filtered by status."""
        session = self._get_session()
        try:
            query = session.query(OutreachCampaignORM)
            if status_filter:
                query = query.filter_by(status=status_filter)
            orm_campaigns = query.all()
            return [self._to_dataclass(c) for c in orm_campaigns]
        except Exception as e:
            logger.error(f"Error retrieving all outreach campaigns: {e}", exc_info=True)
            return []
        finally:
            session.close()

    # New: Outreach Event methods
    def save_outreach_event(self, event: OutreachEvent) -> None:
        """Saves a new outreach event."""
        session = self._get_session()
        try:
            orm_event = self._to_orm(event)
            session.add(orm_event)
            session.commit()
            logger.debug(f"Saved outreach event {event.event_type} for prospect {event.prospect_url}.")
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving outreach event {event.id}: {e}", exc_info=True)
            raise
        finally:
            session.close()

    def get_outreach_events_for_prospect(self, prospect_url: str) -> List[OutreachEvent]:
        """Retrieves all outreach events for a specific prospect URL."""
        session = self._get_session()
        try:
            orm_events = session.query(OutreachEventORM).filter_by(prospect_url=prospect_url).order_by(OutreachEventORM.event_date.asc()).all()
            return [self._to_dataclass(e) for e in orm_events]
        except Exception as e:
            logger.error(f"Error retrieving outreach events for prospect {prospect_url}: {e}", exc_info=True)
            return []
        finally:
            session.close()

    # New: Report Job methods
    def save_report_job(self, job: ReportJob) -> None:
        """Saves or updates a report job."""
        session = self._get_session()
        try:
            orm_job = session.query(ReportJobORM).filter_by(id=job.id).first()
            if orm_job:
                # Update existing
                updated_data = self._to_orm(job)
                for column in inspect(ReportJobORM).columns:
                    if hasattr(updated_data, column.key):
                        setattr(orm_job, column.key, getattr(updated_data, column.key))
                logger.debug(f"Updated report job {job.id}.")
            else:
                # Add new
                orm_job = self._to_orm(job)
                session.add(orm_job)
                logger.debug(f"Added report job {job.id}.")
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Error saving report job {job.id}: {e}", exc_info=True)
            raise
        finally:
            session.close()

    def get_report_job(self, job_id: str) -> Optional[ReportJob]:
        """Retrieves a report job by its ID."""
        session = self._get_session()
        try:
            orm_job = session.query(ReportJobORM).filter_by(id=job_id).first()
            return self._to_dataclass(orm_job)
        except Exception as e:
            logger.error(f"Error retrieving report job {job_id}: {e}", exc_info=True)
            return None
        finally:
            session.close()

    def get_all_report_jobs(self) -> List[ReportJob]:
        """Retrieves all report jobs."""
        session = self._get_session()
        try:
            orm_jobs = session.query(ReportJobORM).all()
            return [self._to_dataclass(j) for j in orm_jobs]
        except Exception as e:
            logger.error(f"Error retrieving all report jobs: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def ping(self):
        """Pings the database to check connectivity."""
        session = self._get_session()
        try:
            session.execute(func.now())
            logger.debug("Database ping successful.")
            return True
        except Exception as e:
            logger.error(f"Database ping failed: {e}", exc_info=True)
            raise
        finally:
            session.close()
