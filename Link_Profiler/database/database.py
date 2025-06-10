"""
Database - Handles database operations using SQLAlchemy with PostgreSQL.
File: Link_Profiler/database/database.py
"""

import logging
import os
from typing import List, Optional, Any, Dict, Set, Callable
from datetime import datetime, timedelta # Import timedelta
from sqlalchemy import create_engine, text, inspect, func, Float # Import func and Float
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
try:
    from alembic import command
    from alembic.config import Config
    ALEMBIC_AVAILABLE = True
except ImportError:
    ALEMBIC_AVAILABLE = False
    command = None
    Config = None
import json # Import json for serializing/deserializing JSONB fields
from urllib.parse import urlparse # For parsing domains from URLs

# ClickHouse specific imports
from sqlalchemy_clickhouse import ClickHouse
from sqlalchemy_clickhouse.exc import ClickHouseError

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.database.models import (
    Base, DomainORM, URLORM, BacklinkORM, LinkProfileORM, CrawlJobORM,
    SEOMetricsORM, SERPResultORM, KeywordSuggestionORM, AlertRuleORM,
    UserORM, ContentGapAnalysisResultORM, DomainHistoryORM, LinkProspectORM,
    OutreachCampaignORM, OutreachEventORM, ReportJobORM, DomainIntelligenceORM,
    SocialMentionORM, SatellitePerformanceLogORM, TrackedDomainORM, TrackedKeywordORM, # New: Import TrackedDomainORM, TrackedKeywordORM
    LinkTypeEnum, ContentTypeEnum, CrawlStatusEnum, SpamLevelEnum, AlertSeverityEnum, AlertChannelEnum # Import ORM Enums
)
from Link_Profiler.database.clickhouse_models import ( # New: Import ClickHouse ORM models
    BacklinkAnalyticalORM, SEOAnalyticalORM, SERPAnalyticalORM,
    KeywordSuggestionAnalyticalORM, GSCBacklinkAnalyticalORM, KeywordTrendAnalyticalORM
)
from Link_Profiler.core.models import (
    Domain, URL, Backlink, LinkProfile, CrawlJob, SEOMetrics, SERPResult,
    KeywordSuggestion, AlertRule, User, ContentGapAnalysisResult, DomainHistory,
    LinkProspect, OutreachCampaign, OutreachEvent, ReportJob, DomainIntelligence,
    SocialMention, CrawlError, SatellitePerformanceLog, TrackedDomain, TrackedKeyword, # New: Import TrackedDomain, TrackedKeyword
    LinkType, ContentType, CrawlStatus, SpamLevel, AlertSeverity, AlertChannel # Import Dataclass Enums
)
from Link_Profiler.monitoring.prometheus_metrics import (
    DB_OPERATIONS_TOTAL, DB_QUERY_DURATION_SECONDS
)

logger = logging.getLogger(__name__)

class Database:
    """
    A class for database operations using SQLAlchemy with PostgreSQL.
    Manages connections, sessions, and CRUD operations for various data models.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Database, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".Database")
        self.database_url = config_loader.get("database.url")
        self.engine = None
        self.Session = None
        self._connect()

    def _connect(self):
        """Establishes connection to the PostgreSQL database."""
        if not self.database_url:
            self.logger.critical("Database URL is not configured.")
            return

        try:
            self.engine = create_engine(
                self.database_url,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=1800,
            )
            self.Session = scoped_session(
                sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            )
            self.logger.info("Database connection established.")

            # Check if Alembic is available and run migrations
            if ALEMBIC_AVAILABLE:
                self._run_migrations()
            else:
                self.logger.warning("Alembic not available. Attempting to create tables directly.")
                self.logger.info("Attempting to create tables via Base.metadata.create_all...")
                Base.metadata.create_all(self.engine)
                self.logger.info("Tables created successfully via Base.metadata.create_all.")

                # --- NEW: Verify table creation ---
                inspector = inspect(self.engine)
                existing_tables = inspector.get_table_names()
                self.logger.info(f"Tables found in database after create_all: {existing_tables}")
                
                required_tables = ["crawl_jobs", "domains", "backlinks", "satellite_performance_logs", "tracked_domains", "tracked_keywords"] # Add all tables needed for MVs and tracked entities
                missing_tables = [t for t in required_tables if t not in existing_tables]
                if missing_tables:
                    self.logger.error(f"CRITICAL: Following required tables are missing after create_all: {missing_tables}")
                    # This indicates a deeper issue with Base.metadata.create_all()
                # --- END NEW ---

            self._create_materialized_views() # New: Create materialized views after migrations
        except SQLAlchemyError as e:
            self.logger.critical(f"Failed to connect to database: {e}", exc_info=True)
            self.engine = None
            self.Session = None
        except Exception as e:
            self.logger.critical(f"An unexpected error occurred during database connection or setup: {e}", exc_info=True)
            self.engine = None
            self.Session = None

    def _run_migrations(self):
        """Applies Alembic migrations to ensure the database schema is up to date."""
        if not ALEMBIC_AVAILABLE:
            self.logger.warning("Alembic not available. Skipping database migrations.")
            return
            
        try:
            alembic_cfg = Config(os.path.join(os.path.dirname(__file__), '..', '..', 'alembic.ini'))
            command.upgrade(alembic_cfg, 'head')
            self.logger.info("Database migrations applied.")
        except Exception as e:
            self.logger.error(f"Failed to run migrations: {e}")

    def _create_materialized_views(self):
        """
        Creates or refreshes materialized views for dashboard performance.
        Each operation is wrapped in its own transaction to prevent cascading failures.
        """
        if not self.engine:
            self.logger.error("Cannot create materialized views: Database engine not initialized.")
            return

        views_sql = {
            "mv_daily_job_stats": {
                "sql": """
                    CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_job_stats AS
                    SELECT
                        DATE_TRUNC('day', created_at) AS day, -- Corrected from created_date
                        job_type,
                        COUNT(id) AS total_jobs,
                        COUNT(CASE WHEN status = 'completed' THEN 1 END) AS completed_jobs,
                        COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed_jobs,
                        SUM(urls_crawled) AS total_pages_crawled,
                        AVG(EXTRACT(EPOCH FROM (completed_date - started_date))) AS avg_job_duration_seconds
                    FROM crawl_jobs
                    WHERE created_at IS NOT NULL -- Corrected from created_date
                    GROUP BY 1, 2
                    ORDER BY 1 DESC, 2;
                """,
                "source_tables": ["crawl_jobs"]
            },
            "mv_daily_backlink_stats": {
                "sql": """
                    CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_backlink_stats AS
                    SELECT
                        DATE_TRUNC('day', first_seen) AS day, -- Corrected from discovered_date
                        COUNT(id) AS total_backlinks_discovered,
                        COUNT(DISTINCT source_domain_name) AS unique_domains_discovered,
                        COUNT(CASE WHEN spam_level IN ('likely_spam', 'confirmed_spam') THEN 1 END) AS potential_spam_links,
                        AVG(authority_passed) AS avg_authority_passed
                    FROM backlinks
                    WHERE first_seen IS NOT NULL -- Corrected from discovered_date
                    GROUP BY 1
                    ORDER BY 1 DESC;
                """,
                "source_tables": ["backlinks"]
            },
            "mv_daily_domain_stats": {
                "sql": """
                    CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_domain_stats AS
                    SELECT
                        DATE_TRUNC('day', last_checked) AS day,
                        COUNT(name) AS total_domains_analyzed,
                        COUNT(CASE WHEN authority_score >= 20 AND spam_score <= 0.3 THEN 1 END) AS valuable_domains_found,
                        AVG(authority_score) AS avg_domain_authority_score
                    FROM domains
                    WHERE last_checked IS NOT NULL
                    GROUP BY 1
                    ORDER BY 1 DESC;
                """,
                "source_tables": ["domains"]
            },
            "mv_daily_satellite_performance": {
                "sql": """
                    CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_satellite_performance AS
                    SELECT
                        DATE_TRUNC('day', timestamp) AS day,
                        satellite_id,
                        AVG(pages_crawled) AS avg_pages_crawled,
                        AVG(links_extracted) AS avg_links_extracted,
                        AVG(crawl_speed_pages_per_minute) AS avg_crawl_speed_ppm,
                        AVG(success_rate_percentage) AS avg_success_rate,
                        AVG(avg_response_time_ms) AS avg_avg_response_time_ms,
                        AVG(cpu_utilization_percent) AS avg_cpu_utilization,
                        AVG(memory_utilization_percent) AS avg_memory_utilization,
                        AVG(network_io_mbps) AS avg_network_io,
                        SUM(errors_logged) AS total_errors_logged
                    FROM satellite_performance_logs
                    WHERE timestamp IS NOT NULL
                    GROUP BY 1, 2
                    ORDER BY 1 DESC, 2;
                """,
                "source_tables": ["satellite_performance_logs"]
            }
        }

        inspector = inspect(self.engine)
        existing_tables = inspector.get_table_names()
        self.logger.info(f"Tables found in database before MV creation: {existing_tables}")

        for view_name, view_info in views_sql.items():
            sql = view_info["sql"]
            source_tables = view_info["source_tables"]
            
            missing_source_tables = [t for t in source_tables if t not in existing_tables]
            if missing_source_tables:
                self.logger.warning(f"Skipping materialized view '{view_name}': Missing source tables: {missing_source_tables}. Ensure these tables are created first.")
                continue # Skip to next view if source tables are missing

            with self.engine.connect() as connection: # New connection for each MV
                try:
                    self.logger.info(f"Attempting to DROP and CREATE materialized view '{view_name}'...")
                    # Drop existing view to ensure clean creation/update
                    connection.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {view_name};"))
                    connection.commit() # Commit drop
                    self.logger.info(f"Dropped existing materialized view '{view_name}' (if it existed).")

                    connection.execute(text(sql))
                    connection.commit()
                    self.logger.info(f"Materialized view '{view_name}' created successfully.")
                    
                    # Create index on the 'day' column for faster queries
                    connection.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{view_name}_day ON {view_name} (day);"))
                    connection.commit()
                    self.logger.info(f"Index on '{view_name}.day' created or already exists.")
                except SQLAlchemyError as e:
                    self.logger.error(f"Error creating materialized view '{view_name}' (SQLAlchemyError): {e}", exc_info=True)
                    connection.rollback() # Rollback this specific transaction
                except Exception as e:
                    self.logger.error(f"Unexpected error during materialized view creation for '{view_name}': {e}", exc_info=True)
                    connection.rollback() # Rollback this specific transaction

    def refresh_materialized_views(self):
        """
        Refreshes all materialized views.
        Each refresh operation is wrapped in its own transaction to prevent cascading failures.
        """
        if not self.engine:
            self.logger.error("Cannot refresh materialized views: Database engine not initialized.")
            return

        view_names = ["mv_daily_job_stats", "mv_daily_backlink_stats", "mv_daily_domain_stats", "mv_daily_satellite_performance"] # Add satellite performance view
        for view_name in view_names:
            with self.engine.connect() as connection: # New connection for each MV
                try:
                    self.logger.info(f"Refreshing materialized view: {view_name}")
                    connection.execute(text(f"REFRESH MATERIALIZED VIEW {view_name};"))
                    connection.commit()
                    self.logger.info(f"Materialized view '{view_name}' refreshed successfully.")
                except SQLAlchemyError as e:
                    self.logger.error(f"Error refreshing materialized view '{view_name}' (SQLAlchemyError): {e}", exc_info=True)
                    connection.rollback() # Rollback this specific transaction
                except Exception as e:
                    self.logger.error(f"Unexpected error during materialized view refresh for '{view_name}': {e}", exc_info=True)
                    connection.rollback() # Rollback this specific transaction

    def get_session(self):
        """Returns a SQLAlchemy session."""
        if not self.Session:
            raise RuntimeError("Database not connected or session not initialized.")
        return self.Session()

    def ping(self) -> bool:
        """Pings the database to check connectivity."""
        if not self.engine:
            return False
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            self.logger.debug("Database ping successful.")
            return True
        except OperationalError as e:
            self.logger.error(f"Database ping failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during database ping: {e}")
            return False

    def _to_orm(self, dc_obj: Any):
        """Converts a dataclass object to its corresponding ORM object."""
        if dc_obj is None:
            return None

        # Convert dataclass to dict, handling nested dataclasses and enums
        data = dc_obj.to_dict()

        # Specific conversions for ORM compatibility
        if isinstance(dc_obj, Domain):
            # Convert enum values to string for ORM
            data['spam_score'] = dc_obj.spam_score.value if isinstance(dc_obj.spam_score, SpamLevel) else dc_obj.spam_score
            return DomainORM(**data)
        elif isinstance(dc_obj, URL):
            data['content_type'] = dc_obj.content_type.value if isinstance(dc_obj.content_type, ContentType) else dc_obj.content_type
            return URLORM(**data)
        elif isinstance(dc_obj, Backlink):
            data['link_type'] = dc_obj.link_type.value if isinstance(dc_obj.link_type, LinkType) else dc_obj.link_type
            data['spam_level'] = dc_obj.spam_level.value if isinstance(dc_obj.spam_level, SpamLevel) else dc_obj.spam_level
            return BacklinkORM(**data)
        elif isinstance(dc_obj, LinkProfile):
            # backlinks are not stored directly in LinkProfileORM, they are derived
            data.pop('backlinks', None)
            return LinkProfileORM(**data)
        elif isinstance(dc_obj, CrawlJob):
            data['status'] = dc_obj.status.value if isinstance(dc_obj.status, CrawlStatus) else dc_obj.status
            # errors are list of CrawlError dataclasses, convert to dicts for JSONB
            data['errors'] = [e.to_dict() for e in dc_obj.errors]
            return CrawlJobORM(**data)
        elif isinstance(dc_obj, SEOMetrics):
            return SEOMetricsORM(**data)
        elif isinstance(dc_obj, SERPResult):
            return SERPResultORM(**data)
        elif isinstance(dc_obj, KeywordSuggestion):
            return KeywordSuggestionORM(**data)
        elif isinstance(dc_obj, AlertRule):
            data['severity'] = dc_obj.severity.value if isinstance(dc_obj.severity, AlertSeverity) else dc_obj.severity
            data['channels'] = [c.value for c in dc_obj.channels] # Convert list of enums to list of strings
            return AlertRuleORM(**data)
        elif isinstance(dc_obj, User):
            return UserORM(**data)
        elif isinstance(dc_obj, ContentGapAnalysisResult):
            return ContentGapAnalysisResultORM(**data)
        elif isinstance(dc_obj, DomainHistory):
            return DomainHistoryORM(**data)
        elif isinstance(dc_obj, LinkProspect):
            return LinkProspectORM(**data)
        elif isinstance(dc_obj, OutreachCampaign):
            return OutreachCampaignORM(**data)
        elif isinstance(dc_obj, OutreachEvent):
            return OutreachEventORM(**data)
        elif isinstance(dc_obj, ReportJob):
            return ReportJobORM(**data)
        elif isinstance(dc_obj, DomainIntelligence):
            return DomainIntelligenceORM(**data) # Changed to direct instantiation
        elif isinstance(dc_obj, SocialMention):
            return SocialMentionORM(**data)
        elif isinstance(dc_obj, SatellitePerformanceLog): # New: Handle SatellitePerformanceLog
            return SatellitePerformanceLogORM(**data)
        elif isinstance(dc_obj, TrackedDomain): # New: Handle TrackedDomain
            return TrackedDomainORM(**data)
        elif isinstance(dc_obj, TrackedKeyword): # New: Handle TrackedKeyword
            return TrackedKeywordORM(**data)
        else:
            raise TypeError(f"Unsupported dataclass type: {type(dc_obj)}")

    def _from_orm(self, orm_obj: Any):
        """Converts an ORM object to its corresponding dataclass object."""
        if orm_obj is None:
            return None

        # Convert ORM object to dict, handling SQLAlchemy internal state
        try:
            # Try to access attributes normally first
            data = {c.key: getattr(orm_obj, c.key) for c in inspect(orm_obj).mapper.column_attrs}
        except Exception as e:
            # If object is detached from session, manually extract data
            self.logger.warning(f"ORM object {type(orm_obj)} is detached from session, extracting data manually: {e}")
            data = {}
            for c in inspect(orm_obj).mapper.column_attrs:
                try:
                    # Try to get the value from the object's __dict__ directly
                    if hasattr(orm_obj, '__dict__') and c.key in orm_obj.__dict__:
                        data[c.key] = orm_obj.__dict__[c.key]
                    else:
                        # Set to None if we can't access it
                        data[c.key] = None
                        self.logger.debug(f"Could not access attribute {c.key} on detached ORM object")
                except Exception as attr_error:
                    self.logger.warning(f"Failed to access attribute {c.key}: {attr_error}")
                    data[c.key] = None

        # Specific conversions from ORM to dataclass
        if isinstance(orm_obj, DomainORM):
            # Convert enum value from string back to enum
            if 'spam_score' in data and data['spam_score'] is not None:
                data['spam_score'] = SpamLevel(data['spam_score'])
            return Domain.from_dict(data)
        elif isinstance(orm_obj, URLORM):
            if 'content_type' in data and data['content_type'] is not None:
                data['content_type'] = ContentType(data['content_type'])
            return URL.from_dict(data)
        elif isinstance(orm_obj, BacklinkORM):
            if 'link_type' in data and data['link_type'] is not None:
                data['link_type'] = LinkType(data['link_type'])
            if 'spam_level' in data and data['spam_level'] is not None:
                data['spam_level'] = SpamLevel(data['spam_level'])
            return Backlink.from_dict(data)
        elif isinstance(orm_obj, LinkProfileORM):
            # backlinks are not stored directly in LinkProfileORM, they are derived
            # so we don't need to convert them back here
            return LinkProfile.from_dict(data)
        elif isinstance(orm_obj, CrawlJobORM):
            if 'status' in data and data['status'] is not None:
                data['status'] = CrawlStatus(data['status'])
            if 'errors' in data and data['errors'] is not None:
                data['errors'] = [CrawlError.from_dict(e) for e in data['errors']]
            return CrawlJob.from_dict(data)
        elif isinstance(orm_obj, SEOMetricsORM):
            return SEOMetrics.from_dict(data)
        elif isinstance(orm_obj, SERPResultORM):
            return SERPResult.from_dict(data)
        elif isinstance(orm_obj, KeywordSuggestionORM):
            return KeywordSuggestion.from_dict(data)
        elif isinstance(orm_obj, AlertRuleORM):
            if 'severity' in data and data['severity'] is not None:
                data['severity'] = AlertSeverity(data['severity'])
            if 'channels' in data and data['channels'] is not None:
                data['channels'] = [AlertChannel(c) for c in data['channels']]
            return AlertRule.from_dict(data)
        elif isinstance(orm_obj, UserORM):
            return User.from_dict(data)
        elif isinstance(orm_obj, ContentGapAnalysisResultORM):
            return ContentGapAnalysisResult.from_dict(data)
        elif isinstance(orm_obj, DomainHistoryORM):
            return DomainHistory.from_dict(data)
        elif isinstance(orm_obj, LinkProspectORM):
            return LinkProspect.from_dict(data)
        elif isinstance(orm_obj, OutreachCampaignORM):
            return OutreachCampaign.from_dict(data)
        elif isinstance(orm_obj, OutreachEventORM):
            return OutreachEvent.from_dict(data)
        elif isinstance(orm_obj, ReportJobORM):
            return ReportJob.from_dict(data)
        elif isinstance(orm_obj, DomainIntelligenceORM):
            return DomainIntelligence.from_dict(data) # Changed to direct instantiation
        elif isinstance(orm_obj, SocialMentionORM):
            return SocialMention.from_dict(data)
        elif isinstance(orm_obj, SatellitePerformanceLogORM): # New: Handle SatellitePerformanceLog
            return SatellitePerformanceLog.from_dict(data)
        elif isinstance(orm_obj, TrackedDomainORM): # New: Handle TrackedDomain
            return TrackedDomain.from_dict(data)
        elif isinstance(orm_obj, TrackedKeywordORM): # New: Handle TrackedKeyword
            return TrackedKeyword.from_dict(data)
        else:
            raise TypeError(f"Unsupported ORM type for dataclass conversion: {type(orm_obj)}")

    def _execute_operation(self, operation_type: str, table_name: str, func: Callable):
        """Helper to execute a database operation with error handling and metrics."""
        session = self.get_session()
        start_time = datetime.now()
        try:
            result = func(session)
            # Only commit for operations that modify data
            if operation_type in ['insert', 'update', 'delete', 'upsert']:
                session.commit()
            DB_OPERATIONS_TOTAL.labels(operation_type=operation_type, table_name=table_name, status='success').inc()
            return result
        except IntegrityError as e:
            session.rollback()
            self.logger.error(f"Integrity error during {operation_type} on {table_name}: {e}", exc_info=True)
            DB_OPERATIONS_TOTAL.labels(operation_type=operation_type, table_name=table_name, status='integrity_error').inc()
            raise
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"SQLAlchemy error during {operation_type} on {table_name}: {e}", exc_info=True)
            DB_OPERATIONS_TOTAL.labels(operation_type=operation_type, table_name=table_name, status='sql_error').inc()
            raise
        except Exception as e:
            session.rollback()
            self.logger.error(f"Unexpected error during {operation_type} on {table_name}: {e}", exc_info=True)
            DB_OPERATIONS_TOTAL.labels(operation_type=operation_type, table_name=table_name, status='unexpected_error').inc()
            raise
        finally:
            session.close() # Changed session.remove() to session.close()
            duration = (datetime.now() - start_time).total_seconds()
            DB_QUERY_DURATION_SECONDS.labels(query_type=operation_type, table_name=table_name).observe(duration)

    # --- Backlink Operations ---
    def add_backlinks(self, backlinks: List[Backlink]) -> None:
        """Adds a list of backlinks to the database."""
        def _add(session):
            orm_backlinks = [self._to_orm(bl) for bl in backlinks]
            session.add_all(orm_backlinks)
        self._execute_operation('insert', 'backlinks', _add)
        self.logger.info(f"Added {len(backlinks)} backlinks.")

    def get_backlinks_for_target(self, target_url: str) -> List[Backlink]:
        """Retrieves backlinks for a specific target URL."""
        def _get(session):
            return session.query(BacklinkORM).filter_by(target_url=target_url).all()
        orm_backlinks = self._execute_operation('select', 'backlinks', _get)
        return [self._from_orm(bl) for bl in orm_backlinks]

    def get_all_backlinks(self) -> List[Backlink]:
        """Retrieves all backlinks from the database."""
        def _get(session):
            return session.query(BacklinkORM).all()
        orm_backlinks = self._execute_operation('select', 'backlinks', _get)
        return [self._from_orm(bl) for bl in orm_backlinks]

    # --- LinkProfile Operations ---
    def save_link_profile(self, profile: LinkProfile) -> None:
        """Saves or updates a link profile."""
        def _save(session):
            orm_profile = self._to_orm(profile)
            existing_profile = session.query(LinkProfileORM).filter_by(target_url=profile.target_url).first()
            if existing_profile:
                # Update existing
                for key, value in orm_profile.__dict__.items():
                    if key != '_sa_instance_state': # Skip SQLAlchemy internal state
                        setattr(existing_profile, key, value)
            else:
                session.add(orm_profile)
        self._execute_operation('upsert', 'link_profiles', _save)
        self.logger.info(f"Saved link profile for {profile.target_url}.")

    def get_link_profile(self, target_url: str) -> Optional[LinkProfile]:
        """Retrieves a link profile by target URL."""
        def _get(session):
            return session.query(LinkProfileORM).filter_by(target_url=target_url).first()
        orm_profile = self._execute_operation('select', 'link_profiles', _get)
        return self._from_orm(orm_profile) if orm_profile else None

    def get_all_link_profiles(self) -> List[LinkProfile]:
        """Retrieves all link profiles."""
        def _get(session):
            return session.query(LinkProfileORM).all()
        orm_profiles = self._execute_operation('select', 'link_profiles', _get)
        return [self._from_orm(lp) for lp in orm_profiles]

    # --- CrawlJob Operations ---
    def add_crawl_job(self, job: CrawlJob) -> None:
        """Adds a new crawl job to the database."""
        def _add(session):
            orm_job = self._to_orm(job)
            session.add(orm_job)
        self._execute_operation('insert', 'crawl_jobs', _add)
        self.logger.info(f"Added crawl job {job.id}.")

    def get_crawl_job(self, job_id: str) -> Optional[CrawlJob]:
        """Retrieves a crawl job by its ID."""
        def _get(session):
            return session.query(CrawlJobORM).filter_by(id=job_id).first()
        orm_job = self._execute_operation('select', 'crawl_jobs', _get)
        return self._from_orm(orm_job) if orm_job else None

    def get_all_crawl_jobs(self) -> List[CrawlJob]:
        """Retrieves all crawl jobs."""
        def _get(session):
            return session.query(CrawlJobORM).all()
        orm_jobs = self._execute_operation('select', 'crawl_jobs', _get)
        return [self._from_orm(job) for job in orm_jobs]

    def update_crawl_job(self, job: CrawlJob) -> None:
        """Updates an existing crawl job."""
        def _update(session):
            orm_job = session.query(CrawlJobORM).filter_by(id=job.id).first()
            if orm_job:
                # Manually update fields from dataclass to ORM object
                job_dict = self._to_orm(job).__dict__ # Get ORM-ready dict
                
                for key, value in job_dict.items():
                    if key != '_sa_instance_state': # Skip SQLAlchemy internal state
                        setattr(orm_job, key, value)
            else:
                raise ValueError(f"CrawlJob with ID {job.id} not found for update.")
        self._execute_operation('update', 'crawl_jobs', _update)
        self.logger.info(f"Updated crawl job {job.id}.")

    # --- New CrawlJob Query Methods for Dashboard ---
    def get_crawl_jobs_by_status_and_time(self, status: CrawlStatus, time_ago: timedelta) -> List[CrawlJob]:
        """Retrieves crawl jobs by status completed within a given time period."""
        def _get(session):
            cutoff_time = datetime.utcnow() - time_ago
            return session.query(CrawlJobORM).filter(
                CrawlJobORM.status == status.value,
                CrawlJobORM.completed_date >= cutoff_time
            ).all()
        orm_jobs = self._execute_operation('select', 'crawl_jobs', _get)
        return [self._from_orm(job) for job in orm_jobs]

    def get_active_jobs_count(self) -> int:
        """Returns the count of jobs currently in progress."""
        def _get(session):
            return session.query(CrawlJobORM).filter(CrawlJobORM.status == CrawlStatus.IN_PROGRESS.value).count()
        return self._execute_operation('select_count', 'crawl_jobs', _get)

    def get_queued_jobs_count(self) -> int:
        """Returns the count of jobs currently queued or pending."""
        def _get(session):
            return session.query(CrawlJobORM).filter(
                (CrawlJobORM.status == CrawlStatus.QUEUED.value) |
                (CrawlJobORM.status == CrawlStatus.PENDING.value)
            ).count()
        return self._execute_operation('select_count', 'crawl_jobs', _get)

    def get_total_pages_crawled_in_time_period(self, time_ago: timedelta) -> int:
        """Returns the total pages crawled for jobs completed within a given time period."""
        def _get(session):
            cutoff_time = datetime.utcnow() - time_ago
            result = session.query(
                func.sum(CrawlJobORM.urls_crawled)
            ).filter(
                CrawlJobORM.completed_date >= cutoff_time,
                CrawlJobORM.status == CrawlStatus.COMPLETED.value # Only count completed jobs
            ).scalar()
            return result if result is not None else 0
        return self._execute_operation('select_sum', 'crawl_jobs', _get)

    def get_recent_job_errors(self, time_ago: timedelta, limit: int = 10) -> List[CrawlError]:
        """Retrieves recent job errors within a given time period."""
        def _get(session):
            cutoff_time = datetime.utcnow() - time_ago
            # Filter jobs that have errors and whose errors occurred recently
            # This query might be inefficient for large error JSONB fields.
            # A dedicated error table would be better for complex queries.
            # For now, we'll fetch jobs with errors and filter in Python.
            jobs_with_errors = session.query(CrawlJobORM).filter(
                CrawlJobORM.errors.isnot(None),
                CrawlJobORM.errors != '[]', # Check for non-empty JSONB array
                CrawlJobORM.completed_date >= cutoff_time # Assuming errors are logged when job completes
            ).order_by(CrawlJobORM.completed_date.desc()).all()

            all_recent_errors = []
            for job_orm in jobs_with_errors:
                if job_orm.errors:
                    for error_dict in job_orm.errors:
                        # Ensure error_dict has a timestamp and convert it to datetime
                        error_timestamp_str = error_dict.get('timestamp')
                        if error_timestamp_str:
                            try:
                                error_timestamp = datetime.fromisoformat(error_timestamp_str)
                                if error_timestamp >= cutoff_time:
                                    all_recent_errors.append(CrawlError.from_dict(error_dict))
                            except ValueError:
                                self.logger.warning(f"Invalid timestamp format in job error: {error_timestamp_str}")
            # Sort by timestamp and limit
            all_recent_errors.sort(key=lambda x: x.timestamp, reverse=True)
            return all_recent_errors[:limit]

        return self._execute_operation('select', 'crawl_jobs_errors', _get)

    def get_avg_job_completion_time_in_time_period(self, time_ago: timedelta) -> float:
        """Returns the average completion time for jobs completed within a given time period."""
        def _get(session):
            cutoff_time = datetime.utcnow() - time_ago
            result = session.query(
                func.avg(
                    func.extract('epoch', CrawlJobORM.completed_date - CrawlJobORM.started_date)
                )
            ).filter(
                CrawlJobORM.completed_date >= cutoff_time,
                CrawlJobORM.status == CrawlStatus.COMPLETED.value,
                CrawlJobORM.started_date.isnot(None)
            ).scalar()
            return result if result is not None else 0.0
        return self._execute_operation('select_avg', 'crawl_jobs', _get)

    # --- Domain Operations ---
    def save_domain(self, domain: Domain) -> None:
        """Saves or updates a domain."""
        def _save(session):
            orm_domain = self._to_orm(domain)
            existing_domain = session.query(DomainORM).filter_by(name=domain.name).first()
            if existing_domain:
                for key, value in orm_domain.__dict__.items():
                    if key != '_sa_instance_state':
                        setattr(existing_domain, key, value)
            else:
                session.add(orm_domain)
        self._execute_operation('upsert', 'domains', _save)
        self.logger.info(f"Saved domain {domain.name}.")

    def get_domain(self, name: str) -> Optional[Domain]:
        """Retrieves a domain by its name."""
        def _get(session):
            return session.query(DomainORM).filter_by(name=name).first()
        orm_domain = self._execute_operation('select', 'domains', _get)
        return self._from_orm(orm_domain) if orm_domain else None

    def get_all_domains(self) -> List[Domain]:
        """Retrieves all domains."""
        def _get(session):
            return session.query(DomainORM).all()
        orm_domains = self._execute_operation('select', 'domains', _get)
        return [self._from_orm(d) for d in orm_domains]

    # --- Other Operations (placeholders for now) ---
    def get_count_of_competitive_keyword_analyses(self) -> int:
        """Retrieves the count of competitive keyword analyses."""
        # Placeholder for actual implementation
        self.logger.warning("get_count_of_competitive_keyword_analyses is a placeholder.")
        return 0

    def get_all_alert_rules(self, active_only: bool = False) -> List[AlertRule]:
        """Retrieves all alert rules, optionally filtered by active status."""
        def _get(session):
            query = session.query(AlertRuleORM)
            if active_only:
                query = query.filter_by(is_active=True)
            return query.all()
        orm_rules = self._execute_operation('select', 'alert_rules', _get)
        return [self._from_orm(rule) for rule in orm_rules]

    def get_report_job(self, job_id: str) -> Optional[ReportJob]:
        """Retrieves a report job by its ID."""
        def _get(session):
            return session.query(ReportJobORM).filter_by(id=job_id).first()
        orm_job = self._execute_operation('select', 'report_jobs', _get)
        return self._from_orm(orm_job) if orm_job else None

    # --- User Operations ---
    def create_user(self, user: User) -> User:
        """Creates a new user if the username and email are unique."""
        def _create(session):
            existing = session.query(UserORM).filter(
                (UserORM.username == user.username) | (UserORM.email == user.email)
            ).first()
            if existing:
                raise ValueError("User with this username or email already exists")
            orm_user = self._to_orm(user)
            session.add(orm_user)
            return orm_user

        orm_user = self._execute_operation('insert', 'users', _create)
        self.logger.info(f"Created user {user.username}.")
        return self._from_orm(orm_user)

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Fetches a user by username."""
        def _get(session):
            return session.query(UserORM).filter_by(username=username).first()
        orm_user = self._execute_operation('select', 'users', _get)
        return self._from_orm(orm_user) if orm_user else None

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Fetches a user by email address."""
        def _get(session):
            return session.query(UserORM).filter_by(email=email).first()
        orm_user = self._execute_operation('select', 'users', _get)
        return self._from_orm(orm_user) if orm_user else None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Fetches a user by their ID."""
        def _get(session):
            return session.query(UserORM).filter_by(id=user_id).first()
        orm_user = self._execute_operation('select', 'users', _get)
        return self._from_orm(orm_user) if orm_user else None

    def get_all_users(self) -> List[User]:
        """Retrieves all users from the database."""
        def _get(session):
            return session.query(UserORM).all()
        orm_users = self._execute_operation('select', 'users', _get)
        return [self._from_orm(user) for user in orm_users]

    def update_user(self, user: User) -> User:
        """Updates an existing user's information."""
        def _update(session):
            orm_user = session.query(UserORM).filter_by(id=user.id).first()
            if not orm_user:
                raise ValueError(f"User with ID {user.id} not found for update.")
            
            # Update fields from the dataclass to the ORM object
            orm_user.username = user.username
            orm_user.email = user.email
            orm_user.hashed_password = user.hashed_password
            orm_user.is_active = user.is_active
            orm_user.is_admin = user.is_admin
            orm_user.role = user.role # Update role
            orm_user.organization_id = user.organization_id # Update organization_id
            orm_user.last_fetched_at = datetime.utcnow() # Update last_fetched_at on update
            return orm_user

        updated_orm_user = self._execute_operation('update', 'users', _update)
        self.logger.info(f"Updated user {user.username} (ID: {user.id}).")
        return self._from_orm(updated_orm_user)

    def delete_user(self, user_id: str) -> bool:
        """Deletes a user by their ID."""
        def _delete(session):
            orm_user = session.query(UserORM).filter_by(id=user_id).first()
            if orm_user:
                session.delete(orm_user)
                return True
            return False
        
        success = self._execute_operation('delete', 'users', _delete)
        if success:
            self.logger.info(f"Deleted user ID: {user_id}.")
        else:
            self.logger.warning(f"Attempted to delete non-existent user ID: {user_id}.")
        return success

    # --- Backlink Update ---
    def update_backlink(self, backlink: Backlink) -> None:
        """Updates an existing backlink or inserts it if not present."""
        def _update(session):
            orm_backlink = session.query(BacklinkORM).filter_by(
                source_url=backlink.source_url,
                target_url=backlink.target_url
            ).first()
            new_data = self._to_orm(backlink)
            if orm_backlink:
                for key, value in new_data.__dict__.items():
                    if key != '_sa_instance_state':
                        setattr(orm_backlink, key, value)
            else:
                session.add(new_data)

        self._execute_operation('upsert', 'backlinks', _update)

    # --- SEO Metrics Operations ---
    def save_seo_metrics(self, metrics: SEOMetrics) -> None:
        """Saves or updates SEO metrics for a URL."""
        def _save(session):
            orm_metrics = self._to_orm(metrics)
            existing = session.query(SEOMetricsORM).filter_by(url=metrics.url).first()
            if existing:
                for key, value in orm_metrics.__dict__.items():
                    if key != '_sa_instance_state':
                        setattr(existing, key, value)
            else:
                session.add(orm_metrics)

        self._execute_operation('upsert', 'seo_metrics', _save)

    def get_seo_metrics(self, url: str) -> Optional[SEOMetrics]:
        """Retrieves SEO metrics for a specific URL."""
        def _get(session):
            return session.query(SEOMetricsORM).filter_by(url=url).first()
        orm_metrics = self._execute_operation('select', 'seo_metrics', _get)
        return self._from_orm(orm_metrics) if orm_metrics else None

    # --- SERP and Keyword Operations ---
    def add_serp_results(self, results: List[SERPResult]) -> None:
        """Bulk insert SERP results."""
        def _add(session):
            orm_results = [self._to_orm(r) for r in results]
            session.add_all(orm_results)

        self._execute_operation('insert', 'serp_results', _add)

    def add_keyword_suggestions(self, suggestions: List[KeywordSuggestion]) -> None:
        """Bulk insert keyword suggestions."""
        def _add(session):
            orm_suggestions = [self._to_orm(s) for s in suggestions]
            session.add_all(orm_suggestions)

        self._execute_operation('insert', 'keyword_suggestions', _add)

    # --- Content Gap Analysis ---
    def get_latest_content_gap_analysis_result(self, target_url: str) -> Optional[ContentGapAnalysisResult]:
        """Gets the most recent content gap analysis result for a target URL."""
        def _get(session):
            return (
                session.query(ContentGapAnalysisResultORM)
                .filter_by(target_url=target_url)
                .order_by(ContentGapAnalysisResultORM.analysis_date.desc())
                .first()
            )

        orm_result = self._execute_operation('select', 'content_gap_analysis_results', _get)
        return self._from_orm(orm_result) if orm_result else None

    def save_content_gap_analysis_result(self, result: ContentGapAnalysisResult) -> None:
        """Saves a content gap analysis result."""
        def _save(session):
            orm_result = self._to_orm(result)
            session.add(orm_result)

        self._execute_operation('insert', 'content_gap_analysis_results', _save)

    # --- Domain Intelligence ---
    def get_domain_intelligence(self, domain_name: str) -> Optional[DomainIntelligence]:
        """Retrieves stored domain intelligence for a domain."""
        def _get(session):
            return session.query(DomainIntelligenceORM).filter_by(domain_name=domain_name).first()

        orm_obj = self._execute_operation('select', 'domain_intelligence', _get)
        return self._from_orm(orm_obj) if orm_obj else None

    def get_source_domains_for_target_domains(self, target_domains: List[str]) -> Dict[str, Set[str]]:
        """Returns mapping of target domains to unique source domains that link to them."""
        def _get(session):
            rows = (
                session.query(BacklinkORM.target_domain_name, BacklinkORM.source_domain_name)
                .filter(BacklinkORM.target_domain_name.in_(target_domains))
                .all()
            )
            return rows

        rows = self._execute_operation('select', 'backlinks', _get)
        mapping: Dict[str, Set[str]] = {}
        for target, source in rows:
            mapping.setdefault(target, set()).add(source)
        return mapping

    # --- URL Operations ---
    def get_url(self, url: str) -> Optional[URL]:
        """Retrieves a URL by its URL string."""
        def _get(session):
            return session.query(URLORM).filter_by(url=url).first()
        orm_url = self._execute_operation('select', 'urls', _get)
        return self._from_orm(orm_url) if orm_url else None

    def save_url(self, url_obj: URL) -> None:
        """Saves or updates a URL."""
        def _save(session):
            orm_url = self._to_orm(url_obj)
            existing_url = session.query(URLORM).filter_by(url=url_obj.url).first()
            if existing_url:
                for key, value in orm_url.__dict__.items():
                    if key != '_sa_instance_state':
                        setattr(existing_url, key, value)
            else:
                session.add(orm_url)
        self._execute_operation('upsert', 'urls', _save)
        self.logger.info(f"Saved URL {url_obj.url}.")

    # --- Social Mention Operations ---
    def add_social_mentions(self, mentions: List[SocialMention]) -> None:
        """Adds a list of social mentions to the database."""
        def _add(session):
            orm_mentions = [self._to_orm(m) for m in mentions]
            session.add_all(orm_mentions)
        self._execute_operation('insert', 'social_mentions', _add)
        self.logger.info(f"Added {len(mentions)} social mentions.")

    def get_latest_social_mentions_for_query(self, query: str, limit: int = 100) -> List[SocialMention]:
        """Retrieves the latest social mentions for a specific query."""
        def _get(session):
            return session.query(SocialMentionORM).filter_by(query=query).order_by(SocialMentionORM.published_date.desc()).limit(limit).all()
        orm_mentions = self._execute_operation('select', 'social_mentions', _get)
        return [self._from_orm(m) for m in orm_mentions]

    # --- Satellite Performance Log Operations ---
    def add_satellite_performance_log(self, log: SatellitePerformanceLog) -> None:
        """Adds a new satellite performance log entry."""
        def _add(session):
            orm_log = self._to_orm(log)
            session.add(orm_log)
        self._execute_operation('insert', 'satellite_performance_logs', _add)
        self.logger.info(f"Added performance log for {log.satellite_id} at {log.timestamp}.")

    def get_latest_satellite_performance_logs(self, satellite_id: Optional[str] = None, limit: int = 100) -> List[SatellitePerformanceLog]:
        """Retrieves recent satellite performance logs, optionally filtered by satellite_id."""
        def _get(session):
            query = session.query(SatellitePerformanceLogORM)
            if satellite_id:
                query = query.filter_by(satellite_id=satellite_id)
            return query.order_by(SatellitePerformanceLogORM.timestamp.desc()).limit(limit).all()
        orm_logs = self._execute_operation('select', 'satellite_performance_logs', _get)
        return [self._from_orm(l) for l in orm_logs]

    # --- Keyword Suggestion Operations ---
    def get_latest_keyword_suggestions_for_seed(self, seed_keyword: str, limit: int = 100) -> List[KeywordSuggestion]:
        """Retrieves the latest keyword suggestions for a specific seed keyword."""
        def _get(session):
            return session.query(KeywordSuggestionORM).filter_by(seed_keyword=seed_keyword).order_by(KeywordSuggestionORM.data_timestamp.desc()).limit(limit).all()
        orm_suggestions = self._execute_operation('select', 'keyword_suggestions', _get)
        return [self._from_orm(s) for s in orm_suggestions]

    # --- Tracked Entities Operations ---
    def get_tracked_domains(self, user_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[TrackedDomain]:
        """Retrieves all active tracked domains, optionally filtered by user or organization."""
        def _get(session):
            query = session.query(TrackedDomainORM).filter_by(is_active=True)
            if user_id:
                query = query.filter_by(user_id=user_id)
            if organization_id:
                query = query.filter_by(organization_id=organization_id)
            return query.all()
        orm_domains = self._execute_operation('select', 'tracked_domains', _get)
        return [self._from_orm(d) for d in orm_domains]

    def get_tracked_keywords(self, user_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[TrackedKeyword]:
        """Retrieves all active tracked keywords, optionally filtered by user or organization."""
        def _get(session):
            query = session.query(TrackedKeywordORM).filter_by(is_active=True)
            if user_id:
                query = query.filter_by(user_id=user_id)
            if organization_id:
                query = query.filter_by(organization_id=organization_id)
            return query.all()
        orm_keywords = self._execute_operation('select', 'tracked_keywords', _get)
        return [self._from_orm(k) for k in orm_keywords]

    def update_tracked_domain(self, tracked_domain: TrackedDomain) -> None:
        """Updates an existing tracked domain."""
        def _update(session):
            orm_tracked_domain = session.query(TrackedDomainORM).filter_by(id=tracked_domain.id).first()
            if orm_tracked_domain:
                new_data = self._to_orm(tracked_domain)
                for key, value in new_data.__dict__.items():
                    if key != '_sa_instance_state':
                        setattr(orm_tracked_domain, key, value)
            else:
                raise ValueError(f"TrackedDomain with ID {tracked_domain.id} not found for update.")
        self._execute_operation('update', 'tracked_domains', _update)
        self.logger.info(f"Updated tracked domain {tracked_domain.domain_name}.")

    def update_tracked_keyword(self, tracked_keyword: TrackedKeyword) -> None:
        """Updates an existing tracked keyword."""
        def _update(session):
            orm_tracked_keyword = session.query(TrackedKeywordORM).filter_by(id=tracked_keyword.id).first()
            if orm_tracked_keyword:
                new_data = self._to_orm(tracked_keyword)
                for key, value in new_data.__dict__.items():
                    if key != '_sa_instance_state':
                        setattr(orm_tracked_keyword, key, value)
            else:
                raise ValueError(f"TrackedKeyword with ID {tracked_keyword.id} not found for update.")
        self._execute_operation('update', 'tracked_keywords', _update)
        self.logger.info(f"Updated tracked keyword {tracked_keyword.keyword}.")


class ClickHouseClient:
    """
    Client for interacting with ClickHouse database.
    Handles connections and bulk inserts for analytical data.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ClickHouseClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(__name__ + ".ClickHouseClient")
        self.clickhouse_url = config_loader.get("clickhouse.url")
        self.enabled = config_loader.get("clickhouse.enabled", False)
        self.engine = None
        self.Session = None
        if self.enabled:
            self._connect()
        else:
            self.logger.info("ClickHouse is disabled by configuration.")

    def _connect(self):
        """Establishes connection to the ClickHouse database."""
        if not self.clickhouse_url:
            self.logger.critical("ClickHouse URL is not configured.")
            self.enabled = False
            return

        try:
            self.engine = create_engine(self.clickhouse_url, pool_size=5, max_overflow=10)
            self.Session = scoped_session(sessionmaker(bind=self.engine))
            self.logger.info("ClickHouse connection established.")
            self._create_tables()
        except ClickHouseError as e:
            self.logger.critical(f"Failed to connect to ClickHouse: {e}", exc_info=True)
            self.enabled = False
            self.engine = None
            self.Session = None
        except Exception as e:
            self.logger.critical(f"An unexpected error occurred during ClickHouse connection or setup: {e}", exc_info=True)
            self.enabled = False
            self.engine = None
            self.Session = None

    def _create_tables(self):
        """Creates ClickHouse tables if they don't exist."""
        if not self.engine:
            self.logger.warning("ClickHouse engine not initialized. Cannot create tables.")
            return
        try:
            self.logger.info("Attempting to create ClickHouse tables...")
            from Link_Profiler.database.clickhouse_models import Base as ClickHouseBase
            ClickHouseBase.metadata.create_all(self.engine)
            self.logger.info("ClickHouse tables created successfully or already exist.")
        except ClickHouseError as e:
            self.logger.error(f"Error creating ClickHouse tables: {e}", exc_info=True)
        except Exception as e:
            self.logger.error(f"Unexpected error during ClickHouse table creation: {e}", exc_info=True)

    def get_session(self):
        """Returns a ClickHouse SQLAlchemy session."""
        if not self.Session:
            raise RuntimeError("ClickHouse not connected or session not initialized.")
        return self.Session()

    def ping(self) -> bool:
        """Pings the ClickHouse database to check connectivity."""
        if not self.engine:
            return False
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            self.logger.debug("ClickHouse ping successful.")
            return True
        except OperationalError as e:
            self.logger.error(f"ClickHouse ping failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during ClickHouse ping: {e}")
            return False

    def _execute_ch_operation(self, operation_type: str, table_name: str, func: Callable):
        """Helper to execute a ClickHouse database operation with error handling and metrics."""
        if not self.enabled:
            self.logger.warning(f"ClickHouse is disabled. Skipping {operation_type} on {table_name}.")
            return None

        session = self.get_session()
        start_time = datetime.now()
        try:
            result = func(session)
            session.commit()
            DB_OPERATIONS_TOTAL.labels(operation_type=operation_type, table_name=table_name, status='success').inc()
            return result
        except ClickHouseError as e:
            session.rollback()
            self.logger.error(f"ClickHouse error during {operation_type} on {table_name}: {e}", exc_info=True)
            DB_OPERATIONS_TOTAL.labels(operation_type=operation_type, table_name=table_name, status='clickhouse_error').inc()
            raise
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"SQLAlchemy error during {operation_type} on {table_name}: {e}", exc_info=True)
            DB_OPERATIONS_TOTAL.labels(operation_type=operation_type, table_name=table_name, status='sql_error').inc()
            raise
        except Exception as e:
            session.rollback()
            self.logger.error(f"Unexpected error during {operation_type} on {table_name}: {e}", exc_info=True)
            DB_OPERATIONS_TOTAL.labels(operation_type=operation_type, table_name=table_name, status='unexpected_error').inc()
            raise
        finally:
            session.close()
            duration = (datetime.now() - start_time).total_seconds()
            DB_QUERY_DURATION_SECONDS.labels(query_type=operation_type, table_name=table_name).observe(duration)

    def _prepare_backlink_data_for_ch(self, backlink: Backlink) -> Dict[str, Any]:
        """Prepares Backlink dataclass for ClickHouse insertion."""
        return {
            "id": str(backlink.id) if hasattr(backlink, 'id') else str(uuid.uuid4()), # Ensure ID exists
            "timestamp": backlink.last_seen or datetime.utcnow(),
            "source_url": backlink.source_url,
            "target_url": backlink.target_url,
            "source_url_domain": urlparse(backlink.source_url).netloc,
            "target_url_domain": urlparse(backlink.target_url).netloc,
            "anchor_text": backlink.anchor_text,
            "link_type": backlink.link_type.value,
            "nofollow": 1 if backlink.nofollow else 0,
            "ugc": 1 if backlink.ugc else 0,
            "sponsored": 1 if backlink.sponsored else 0,
            "http_status": backlink.http_status,
            "spam_level": backlink.spam_level.value if backlink.spam_level else None,
            "source_page_authority": backlink.source_page_authority,
            "source_domain_authority": backlink.source_domain_authority,
            "user_id": backlink.user_id,
            "organization_id": backlink.organization_id,
        }

    def _prepare_seo_metrics_data_for_ch(self, metrics: SEOMetrics) -> Dict[str, Any]:
        """Prepares SEOMetrics dataclass for ClickHouse insertion."""
        return {
            "id": str(uuid.uuid4()), # Generate new ID for analytical record
            "audit_timestamp": metrics.audit_timestamp or datetime.utcnow(),
            "url": metrics.url,
            "url_domain": urlparse(metrics.url).netloc if metrics.url else None,
            "domain_authority": metrics.domain_authority,
            "page_authority": metrics.page_authority,
            "trust_flow": metrics.trust_flow,
            "citation_flow": metrics.citation_flow,
            "organic_keywords": metrics.organic_keywords,
            "organic_traffic": metrics.organic_traffic,
            "referring_domains": metrics.referring_domains,
            "spam_score": metrics.spam_score,
            "http_status": metrics.http_status,
            "response_time_ms": metrics.response_time_ms,
            "page_size_bytes": metrics.page_size_bytes,
            "seo_score": metrics.seo_score,
            "user_id": metrics.user_id,
            "organization_id": metrics.organization_id,
            "issues": json.dumps(metrics.issues),
            "structured_data_types": json.dumps(metrics.structured_data_types),
        }

    def _prepare_serp_result_data_for_ch(self, serp_result: SERPResult) -> Dict[str, Any]:
        """Prepares SERPResult dataclass for ClickHouse insertion."""
        return {
            "id": str(uuid.uuid4()), # Generate new ID for analytical record
            "timestamp": serp_result.timestamp or datetime.utcnow(),
            "keyword": serp_result.keyword,
            "rank": serp_result.rank,
            "url": serp_result.url,
            "domain": serp_result.domain,
            "title": serp_result.title,
            "snippet": serp_result.snippet,
            "position_type": serp_result.position_type,
            "user_id": serp_result.user_id,
            "organization_id": serp_result.organization_id,
        }

    def _prepare_keyword_suggestion_data_for_ch(self, suggestion: KeywordSuggestion) -> Dict[str, Any]:
        """Prepares KeywordSuggestion dataclass for ClickHouse insertion."""
        return {
            "id": str(uuid.uuid4()), # Generate new ID for analytical record
            "data_timestamp": suggestion.last_fetched_at or datetime.utcnow(),
            "seed_keyword": suggestion.seed_keyword,
            "keyword": suggestion.keyword,
            "search_volume": suggestion.search_volume,
            "cpc": suggestion.cpc,
            "competition": suggestion.competition,
            "difficulty": suggestion.difficulty,
            "relevance": suggestion.relevance,
            "source": suggestion.source,
            "keyword_trend": json.dumps(suggestion.keyword_trend) if suggestion.keyword_trend else None,
            "user_id": suggestion.user_id,
            "organization_id": suggestion.organization_id,
        }

    def _prepare_gsc_backlink_data_for_ch(self, gsc_backlink: GSCBacklink) -> Dict[str, Any]:
        """Prepares GSCBacklink dataclass for ClickHouse insertion."""
        return {
            "id": str(uuid.uuid4()), # Generate new ID for analytical record
            "fetch_date": gsc_backlink.fetch_date or datetime.utcnow(),
            "domain": gsc_backlink.domain,
            "source_url": gsc_backlink.source_url,
            "target_url": gsc_backlink.target_url,
            "anchor_text": gsc_backlink.anchor_text,
            "user_id": gsc_backlink.user_id,
            "organization_id": gsc_backlink.organization_id,
        }

    def _prepare_keyword_trend_data_for_ch(self, keyword_trend: KeywordTrend) -> Dict[str, Any]:
        """Prepares KeywordTrend dataclass for ClickHouse insertion."""
        return {
            "id": str(uuid.uuid4()), # Generate new ID for analytical record
            "keyword": keyword_trend.keyword,
            "date": keyword_trend.date,
            "trend_index": keyword_trend.trend_index,
            "source": keyword_trend.source,
            "user_id": keyword_trend.user_id,
            "organization_id": keyword_trend.organization_id,
        }

    def insert_backlinks_analytical(self, backlinks: List[Backlink]) -> None:
        """Inserts backlink data into ClickHouse analytical table."""
        if not self.enabled: return
        def _insert(session):
            ch_data = [self._prepare_backlink_data_for_ch(bl) for bl in backlinks]
            session.bulk_insert_mappings(BacklinkAnalyticalORM, ch_data)
        self._execute_ch_operation('insert', 'backlinks_analytical', _insert)
        self.logger.info(f"Inserted {len(backlinks)} backlinks into ClickHouse.")

    def insert_seo_metrics_analytical(self, metrics: List[SEOMetrics]) -> None:
        """Inserts SEO metrics data into ClickHouse analytical table."""
        if not self.enabled: return
        def _insert(session):
            ch_data = [self._prepare_seo_metrics_data_for_ch(m) for m in metrics]
            session.bulk_insert_mappings(SEOAnalyticalORM, ch_data)
        self._execute_ch_operation('insert', 'seo_metrics_analytical', _insert)
        self.logger.info(f"Inserted {len(metrics)} SEO metrics into ClickHouse.")

    def insert_serp_results_analytical(self, serp_results: List[SERPResult]) -> None:
        """Inserts SERP results data into ClickHouse analytical table."""
        if not self.enabled: return
        def _insert(session):
            ch_data = [self._prepare_serp_result_data_for_ch(sr) for sr in serp_results]
            session.bulk_insert_mappings(SERPAnalyticalORM, ch_data)
        self._execute_ch_operation('insert', 'serp_results_analytical', _insert)
        self.logger.info(f"Inserted {len(serp_results)} SERP results into ClickHouse.")

    def insert_keyword_suggestions_analytical(self, suggestions: List[KeywordSuggestion]) -> None:
        """Inserts keyword suggestions data into ClickHouse analytical table."""
        if not self.enabled: return
        def _insert(session):
            ch_data = [self._prepare_keyword_suggestion_data_for_ch(s) for s in suggestions]
            session.bulk_insert_mappings(KeywordSuggestionAnalyticalORM, ch_data)
        self._execute_ch_operation('insert', 'keyword_suggestions_analytical', _insert)
        self.logger.info(f"Inserted {len(suggestions)} keyword suggestions into ClickHouse.")

    def insert_gsc_backlinks_analytical(self, gsc_backlinks: List[GSCBacklink]) -> None:
        """Inserts GSC backlink data into ClickHouse analytical table."""
        if not self.enabled: return
        def _insert(session):
            ch_data = [self._prepare_gsc_backlink_data_for_ch(bl) for bl in gsc_backlinks]
            session.bulk_insert_mappings(GSCBacklinkAnalyticalORM, ch_data)
        self._execute_ch_operation('insert', 'gsc_backlinks_analytical', _insert)
        self.logger.info(f"Inserted {len(gsc_backlinks)} GSC backlinks into ClickHouse.")

    def insert_keyword_trends_analytical(self, keyword_trends: List[KeywordTrend]) -> None:
        """Inserts keyword trend data into ClickHouse analytical table."""
        if not self.enabled: return
        def _insert(session):
            ch_data = [self._prepare_keyword_trend_data_for_ch(kt) for kt in keyword_trends]
            session.bulk_insert_mappings(KeywordTrendAnalyticalORM, ch_data)
        self._execute_ch_operation('insert', 'keyword_trends_analytical', _insert)
        self.logger.info(f"Inserted {len(keyword_trends)} keyword trends into ClickHouse.")


# Create a singleton instance
db = Database()
clickhouse_client = ClickHouseClient()
