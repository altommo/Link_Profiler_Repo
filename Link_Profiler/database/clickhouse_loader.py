"""
ClickHouse Loader - Handles bulk loading of analytical data into ClickHouse.
File: Link_Profiler/database/clickhouse_loader.py
"""

import logging
from typing import List, Dict, Any, Optional
from clickhouse_driver import Client
from datetime import datetime
import json # Added import for json

from Link_Profiler.core.models import Backlink, SEOMetrics, SERPResult, KeywordSuggestion, serialize_model

logger = logging.getLogger(__name__)

class ClickHouseLoader:
    """
    Manages bulk insertion of various data types into ClickHouse.
    """
    def __init__(self, host: str = 'localhost', port: int = 9000, user: str = 'default', password: str = '', database: str = 'default'):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.client: Optional[Client] = None
        self.logger = logging.getLogger(__name__)

    async def __aenter__(self):
        """Establishes a connection to ClickHouse."""
        self.logger.info(f"Connecting to ClickHouse at {self.host}:{self.port}/{self.database}...")
        try:
            self.client = Client(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database
            )
            # Ping to verify connection
            self.client.execute('SELECT 1')
            self.logger.info("Successfully connected to ClickHouse.")
            await self._create_tables_if_not_exists()
        except Exception as e:
            self.logger.error(f"Failed to connect to ClickHouse: {e}", exc_info=True)
            self.client = None # Ensure client is None if connection fails
            raise
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes the ClickHouse connection."""
        if self.client:
            self.client.disconnect()
            self.logger.info("Disconnected from ClickHouse.")

    async def _create_tables_if_not_exists(self):
        """
        Creates necessary tables in ClickHouse if they don't already exist.
        These schemas are optimised for analytical queries.
        """
        if not self.client:
            self.logger.error("ClickHouse client not initialized. Cannot create tables.")
            return

        # Table for Backlinks
        # Using ReplacingMergeTree to handle potential duplicates on (source_url, target_url)
        # and Order By (crawl_timestamp, source_url, target_url) for efficient queries.
        backlinks_table_schema = """
        CREATE TABLE IF NOT EXISTS backlinks_analytical (
            id String,
            source_url String,
            target_url String,
            source_domain String,
            target_domain String,
            anchor_text String,
            link_type LowCardinality(String),
            rel_attributes Array(String),
            context_text String,
            position_on_page UInt8,
            is_image_link UInt8,
            alt_text Nullable(String),
            discovered_date DateTime,
            last_seen_date DateTime,
            authority_passed Float32,
            is_active UInt8,
            spam_level LowCardinality(String),
            http_status UInt16,
            crawl_timestamp DateTime,
            source_domain_metrics String -- Stored as JSON string for flexibility
        ) ENGINE = ReplacingMergeTree(crawl_timestamp)
        ORDER BY (source_url, target_url, crawl_timestamp);
        """
        # Note: source_domain_metrics is stored as String (JSON) for simplicity.
        # For complex queries, it might be parsed into a Nested type or separate columns.

        # Table for SEO Metrics (page-level audits)
        seo_metrics_table_schema = """
        CREATE TABLE IF NOT EXISTS seo_metrics_analytical (
            url String,
            http_status UInt16,
            response_time_ms UInt32,
            page_size_bytes UInt32,
            title_length UInt16,
            meta_description_length UInt16,
            h1_count UInt8,
            h2_count UInt8,
            internal_links UInt32,
            external_links UInt32,
            images_count UInt32,
            images_without_alt UInt32,
            has_canonical UInt8,
            has_robots_meta UInt8,
            has_schema_markup UInt8,
            broken_links Array(String),
            performance_score Nullable(Float32),
            mobile_friendly Nullable(UInt8),
            accessibility_score Nullable(Float32),
            audit_timestamp DateTime,
            seo_score Float32,
            issues Array(String)
        ) ENGINE = ReplacingMergeTree(audit_timestamp)
        ORDER BY (url, audit_timestamp);
        """

        # Table for SERP Results
        serp_results_table_schema = """
        CREATE TABLE IF NOT EXISTS serp_results_analytical (
            id String,
            keyword String,
            position UInt16,
            result_url String,
            title_text String,
            snippet_text String,
            rich_features Array(String),
            page_load_time Nullable(Float32),
            crawl_timestamp DateTime
        ) ENGINE = ReplacingMergeTree(crawl_timestamp)
        ORDER BY (keyword, position, crawl_timestamp);
        """

        # Table for Keyword Suggestions
        keyword_suggestions_table_schema = """
        CREATE TABLE IF NOT EXISTS keyword_suggestions_analytical (
            id String,
            seed_keyword String,
            suggested_keyword String,
            search_volume_monthly Nullable(UInt32),
            cpc_estimate Nullable(Float32),
            keyword_trend Array(Float32),
            competition_level LowCardinality(String),
            data_timestamp DateTime
        ) ENGINE = ReplacingMergeTree(data_timestamp)
        ORDER BY (seed_keyword, suggested_keyword, data_timestamp);
        """

        try:
            self.client.execute(backlinks_table_schema)
            self.client.execute(seo_metrics_table_schema)
            self.client.execute(serp_results_table_schema)
            self.client.execute(keyword_suggestions_table_schema)
            self.logger.info("ClickHouse tables created or already exist.")
        except Exception as e:
            self.logger.error(f"Failed to create ClickHouse tables: {e}", exc_info=True)
            raise

    def _prepare_backlink_data(self, backlinks: List[Backlink]) -> List[List[Any]]:
        """Converts a list of Backlink dataclasses to a list of lists for ClickHouse insertion."""
        rows = []
        for bl in backlinks:
            rows.append([
                bl.id,
                bl.source_url,
                bl.target_url,
                bl.source_domain,
                bl.target_domain,
                bl.anchor_text,
                bl.link_type.value,
                bl.rel_attributes,
                bl.context_text,
                bl.position_on_page,
                int(bl.is_image_link), # ClickHouse UInt8 for boolean
                bl.alt_text,
                bl.discovered_date,
                bl.last_seen_date,
                bl.authority_passed,
                int(bl.is_active), # ClickHouse UInt8 for boolean
                bl.spam_level.value,
                bl.http_status,
                bl.crawl_timestamp,
                json.dumps(bl.source_domain_metrics) # Serialize dict to JSON string
            ])
        return rows

    def _prepare_seo_metrics_data(self, seo_metrics_list: List[SEOMetrics]) -> List[List[Any]]:
        """Converts a list of SEOMetrics dataclasses to a list of lists for ClickHouse insertion."""
        rows = []
        for sm in seo_metrics_list:
            rows.append([
                sm.url,
                sm.http_status,
                sm.response_time_ms,
                sm.page_size_bytes,
                sm.title_length,
                sm.meta_description_length,
                sm.h1_count,
                sm.h2_count,
                sm.internal_links,
                sm.external_links,
                sm.images_count,
                sm.images_without_alt,
                int(sm.has_canonical),
                int(sm.has_robots_meta),
                int(sm.has_schema_markup),
                sm.broken_links,
                sm.performance_score,
                int(sm.mobile_friendly) if sm.mobile_friendly is not None else None,
                sm.accessibility_score,
                sm.audit_timestamp,
                sm.seo_score,
                sm.issues
            ])
        return rows

    def _prepare_serp_results_data(self, serp_results: List[SERPResult]) -> List[List[Any]]:
        """Converts a list of SERPResult dataclasses to a list of lists for ClickHouse insertion."""
        rows = []
        for sr in serp_results:
            rows.append([
                sr.id,
                sr.keyword,
                sr.position,
                sr.result_url,
                sr.title_text,
                sr.snippet_text,
                sr.rich_features,
                sr.page_load_time,
                sr.crawl_timestamp
            ])
        return rows

    def _prepare_keyword_suggestions_data(self, suggestions: List[KeywordSuggestion]) -> List[List[Any]]:
        """Converts a list of KeywordSuggestion dataclasses to a list of lists for ClickHouse insertion."""
        rows = []
        for ks in suggestions:
            rows.append([
                ks.id,
                ks.seed_keyword,
                ks.suggested_keyword,
                ks.search_volume_monthly,
                ks.cpc_estimate,
                ks.keyword_trend,
                ks.competition_level,
                ks.data_timestamp
            ])
        return rows

    async def bulk_insert_backlinks(self, backlinks: List[Backlink]):
        """Bulk inserts Backlink data into ClickHouse."""
        if not self.client:
            self.logger.error("ClickHouse client not initialized. Cannot insert backlinks.")
            return
        if not backlinks:
            return

        data_to_insert = self._prepare_backlink_data(backlinks)
        try:
            self.client.execute(
                'INSERT INTO backlinks_analytical VALUES',
                data_to_insert,
                types_check=True # Enable type checking for safer inserts
            )
            self.logger.info(f"Successfully bulk inserted {len(backlinks)} backlinks into ClickHouse.")
        except Exception as e:
            self.logger.error(f"Failed to bulk insert backlinks into ClickHouse: {e}", exc_info=True)
            raise

    async def bulk_insert_seo_metrics(self, seo_metrics_list: List[SEOMetrics]):
        """Bulk inserts SEOMetrics data into ClickHouse."""
        if not self.client:
            self.logger.error("ClickHouse client not initialized. Cannot insert SEO metrics.")
            return
        if not seo_metrics_list:
            return

        data_to_insert = self._prepare_seo_metrics_data(seo_metrics_list)
        try:
            self.client.execute(
                'INSERT INTO seo_metrics_analytical VALUES',
                data_to_insert,
                types_check=True
            )
            self.logger.info(f"Successfully bulk inserted {len(seo_metrics_list)} SEO metrics into ClickHouse.")
        except Exception as e:
            self.logger.error(f"Failed to bulk insert SEO metrics into ClickHouse: {e}", exc_info=True)
            raise

    async def bulk_insert_serp_results(self, serp_results: List[SERPResult]):
        """Bulk inserts SERP results data into ClickHouse."""
        if not self.client:
            self.logger.error("ClickHouse client not initialized. Cannot insert SERP results.")
            return
        if not serp_results:
            return

        data_to_insert = self._prepare_serp_results_data(serp_results)
        try:
            self.client.execute(
                'INSERT INTO serp_results_analytical VALUES',
                data_to_insert,
                types_check=True
            )
            self.logger.info(f"Successfully bulk inserted {len(serp_results)} SERP results into ClickHouse.")
        except Exception as e:
            self.logger.error(f"Failed to bulk insert SERP results into ClickHouse: {e}", exc_info=True)
            raise

    async def bulk_insert_keyword_suggestions(self, suggestions: List[KeywordSuggestion]):
        """Bulk inserts keyword suggestions data into ClickHouse."""
        if not self.client:
            self.logger.error("ClickHouse client not initialized. Cannot insert keyword suggestions.")
            return
        if not suggestions:
            return

        data_to_insert = self._prepare_keyword_suggestions_data(suggestions)
        try:
            self.client.execute(
                'INSERT INTO keyword_suggestions_analytical VALUES',
                data_to_insert,
                types_check=True
            )
            self.logger.info(f"Successfully bulk inserted {len(suggestions)} keyword suggestions into ClickHouse.")
        except Exception as e:
            self.logger.error(f"Failed to bulk insert keyword suggestions into ClickHouse: {e}", exc_info=True)
            raise
