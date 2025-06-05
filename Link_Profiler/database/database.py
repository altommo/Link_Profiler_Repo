"""
Database - Handles database operations using SQLAlchemy with PostgreSQL.
File: Link_Profiler/database/database.py
"""

import logging
from typing import List, Optional, Any, Dict, Set, Callable
from datetime import datetime
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
import json # Import json for serializing/deserializing JSONB fields

from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.database.models import (
    Base, DomainORM, URLORM, BacklinkORM, LinkProfileORM, CrawlJobORM,
    SEOMetricsORM, SERPResultORM, KeywordSuggestionORM, AlertRuleORM,
    UserORM, ContentGapAnalysisResultORM, DomainHistoryORM, LinkProspectORM,
    OutreachCampaignORM, OutreachEventORM, ReportJobORM, DomainIntelligenceORM,
    SocialMentionORM,
    LinkTypeEnum, ContentTypeEnum, CrawlStatusEnum, SpamLevelEnum, AlertSeverityEnum, AlertChannelEnum # Import ORM Enums
)
from Link_Profiler.core.models import (
    Domain, URL, Backlink, LinkProfile, CrawlJob, SEOMetrics, SERPResult,
    KeywordSuggestion, AlertRule, User, ContentGapAnalysisResult, DomainHistory,
    LinkProspect, OutreachCampaign, OutreachEvent, ReportJob, DomainIntelligence,
    SocialMention, CrawlError,
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
            self.logger.error("Database URL is not configured.")
            return

        try:
            self.engine = create_engine(self.database_url, pool_size=10, max_overflow=20, pool_timeout=30, pool_recycle=1800)
            self.Session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=self.engine))
            self.logger.info("Database connection established.")
            self._create_tables_if_not_exist()
        except SQLAlchemyError as e:
            self.logger.critical(f"Failed to connect to database: {e}", exc_info=True)
            self.engine = None
            self.Session = None

    def _create_tables_if_not_exist(self):
        """Creates database tables if they do not already exist."""
        if self.engine:
            try:
                inspector = inspect(self.engine)
                # Check for at least one table to determine if schema exists
                if not inspector.has_table(DomainORM.__tablename__):
                    self.logger.info("Creating database tables...")
                    Base.metadata.create_all(self.engine)
                    self.logger.info("Database tables created successfully.")
                else:
                    self.logger.info("Database tables already exist.")
            except SQLAlchemyError as e:
                self.logger.error(f"Error checking/creating tables: {e}", exc_info=True)

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
            return DomainIntelligenceORM(**data)
        elif isinstance(dc_obj, SocialMention):
            return SocialMentionORM(**data)
        else:
            raise TypeError(f"Unsupported dataclass type: {type(dc_obj)}")

    def _from_orm(self, orm_obj: Any):
        """Converts an ORM object to its corresponding dataclass object."""
        if orm_obj is None:
            return None

        # Convert ORM object to dict, handling SQLAlchemy internal state
        data = {c.key: getattr(orm_obj, c.key) for c in inspect(orm_obj).mapper.column_attrs}

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
            return DomainIntelligence.from_dict(data)
        elif isinstance(orm_obj, SocialMentionORM):
            return SocialMention.from_dict(data)
        else:
            raise TypeError(f"Unsupported ORM type for dataclass conversion: {type(orm_obj)}")

    def _execute_operation(self, operation_type: str, table_name: str, func: Callable):
        """Helper to execute a database operation with error handling and metrics."""
        session = self.get_session()
        start_time = datetime.now()
        try:
            result = func(session)
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
            session.remove()
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

# Create a singleton instance
db = Database()
