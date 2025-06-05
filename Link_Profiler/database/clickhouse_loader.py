"""
ClickHouse Loader - Handles data loading into ClickHouse for analytics.
File: Link_Profiler/database/clickhouse_loader.py
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
import json

from clickhouse_driver import Client # Corrected import for clickhouse_driver
from Link_Profiler.config.config_loader import config_loader
from Link_Profiler.monitoring.prometheus_metrics import DB_OPERATIONS_TOTAL, DB_QUERY_DURATION_SECONDS

logger = logging.getLogger(__name__)

class ClickHouseLoader:
    """
    Handles data loading into ClickHouse for analytical purposes.
    Uses the clickhouse_driver library for interaction.
    """
    def __init__(self, host: str, port: int, user: str = 'default', password: str = ''):
        self.logger = logging.getLogger(__name__ + ".ClickHouseLoader")
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = config_loader.get("clickhouse.database", "default")
        self.client: Optional[Client] = None

        self.enabled = config_loader.get("clickhouse.enabled", False)
        if not self.enabled:
            self.logger.info("ClickHouse integration is disabled by configuration.")
            return

        self.logger.info(f"ClickHouseLoader initialized for {self.host}:{self.port}/{self.database}")

    async def __aenter__(self):
        """Establishes a connection to ClickHouse."""
        if self.enabled:
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
                self.logger.error(f"Failed to connect to ClickHouse: {e}. ClickHouse features will be disabled.", exc_info=True)
                self.client = None # Ensure client is None if connection fails
                self.enabled = False # Disable if connection fails
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Closes the ClickHouse connection."""
        if self.client:
            self.client.disconnect()
            self.logger.info("Disconnected from ClickHouse.")

    async def _execute_query(self, query: str, data: Optional[List[List[Any]]] = None, types_check: bool = False) -> Any:
        """Internal method to execute queries against ClickHouse."""
        if not self.enabled or not self.client:
            self.logger.debug("ClickHouse is disabled or client not initialized. Skipping query.")
            return None

        start_time = datetime.now()
        try:
            if data:
                result = self.client.execute(query, data, types_check=types_check)
            else:
                result = self.client.execute(query)
            DB_OPERATIONS_TOTAL.labels(operation_type='query', table_name='clickhouse', status='success').inc()
            return result
        except Exception as e:
            self.logger.error(f"Error executing ClickHouse query: {e}", exc_info=True)
            DB_OPERATIONS_TOTAL.labels(operation_type='query', table_name='clickhouse', status='error').inc()
            raise
        finally:
            duration = (datetime.now() - start_time).total_seconds()
            DB_QUERY_DURATION_SECONDS.labels(query_type='query', table_name='clickhouse').observe(duration)

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
            first_seen DateTime,
            last_seen DateTime,
            authority_passed Float32,
            is_active UInt8,
            spam_level LowCardinality(String),
            http_status Nullable(UInt16),
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
            http_status Nullable(UInt16),
            response_time_ms Nullable(Float32),
            page_size_bytes Nullable(UInt32),
            title_length Nullable(UInt16),
            meta_description_length Nullable(UInt16),
            h1_count Nullable(UInt8),
            h2_count Nullable(UInt8),
            internal_links Nullable(UInt32),
            external_links Nullable(UInt32),
            images_count Nullable(UInt32),
            images_without_alt Nullable(UInt32),
            has_canonical Nullable(UInt8),
            has_robots_meta Nullable(UInt8),
            has_schema_markup Nullable(UInt8),
            broken_links Array(String),
            performance_score Nullable(Float32),
            mobile_friendly Nullable(UInt8),
            accessibility_score Nullable(Float32),
            audit_timestamp DateTime,
            seo_score Nullable(Float32),
            issues Array(String),
            structured_data_types Array(String),
            og_title Nullable(String),
            og_description Nullable(String),
            twitter_title Nullable(String),
            twitter_description Nullable(String),
            validation_issues Array(String),
            ocr_text Nullable(String),
            nlp_entities Array(String),
            nlp_sentiment Nullable(String),
            nlp_topics Array(String),
            video_transcription Nullable(String),
            video_topics Array(String),
            ai_content_classification Nullable(String),
            ai_content_score Nullable(Float32),
            ai_suggestions Array(String),
            ai_semantic_keywords Array(String),
            ai_readability_score Nullable(Float32)
        ) ENGINE = ReplacingMergeTree(audit_timestamp)
        ORDER BY (url, audit_timestamp);
        """

        # Table for SERP Results
        serp_results_table_schema = """
        CREATE TABLE IF NOT EXISTS serp_results_analytical (
            id String,
            keyword String,
            rank UInt16,
            url String,
            title String,
            snippet String,
            domain String,
            position_type Nullable(String),
            timestamp DateTime
        ) ENGINE = ReplacingMergeTree(timestamp)
        ORDER BY (keyword, url, timestamp);
        """

        # Table for Keyword Suggestions
        keyword_suggestions_table_schema = """
        CREATE TABLE IF NOT EXISTS keyword_suggestions_analytical (
            id String,
            keyword String,
            search_volume Nullable(UInt32),
            cpc Nullable(Float32),
            competition Nullable(Float32),
            difficulty Nullable(UInt16),
            relevance Nullable(Float32),
            source Nullable(String)
        ) ENGINE = ReplacingMergeTree(id)
        ORDER BY (keyword, source);
        """

        try:
            await self._execute_query(backlinks_table_schema)
            await self._execute_query(seo_metrics_table_schema)
            await self._execute_query(serp_results_table_schema)
            await self._execute_query(keyword_suggestions_table_schema)
            self.logger.info("ClickHouse tables created or already exist.")
        except Exception as e:
            self.logger.error(f"Failed to create ClickHouse tables: {e}", exc_info=True)
            raise

    def _prepare_backlink_data(self, backlinks: List[Any]) -> List[List[Any]]:
        """Converts a list of Backlink dataclasses to a list of lists for ClickHouse insertion."""
        rows = []
        for bl in backlinks:
            # Ensure all fields are present and correctly typed for ClickHouse
            # Handle Optional fields and Enum conversions
            rows.append([
                bl.id,
                bl.source_url,
                bl.target_url,
                bl.source_domain,
                bl.target_domain,
                bl.anchor_text,
                bl.link_type.value if bl.link_type else None,
                bl.rel_attributes,
                bl.context_text,
                bl.position_on_page if hasattr(bl, 'position_on_page') else 0, # Default if not present
                int(bl.is_image_link) if hasattr(bl, 'is_image_link') and bl.is_image_link is not None else 0,
                bl.alt_text,
                bl.first_seen,
                bl.last_seen,
                bl.authority_passed if bl.authority_passed is not None else 0.0,
                int(bl.is_active) if hasattr(bl, 'is_active') and bl.is_active is not None else 1, # Default to active
                bl.spam_level.value if bl.spam_level else None,
                bl.http_status,
                bl.crawl_timestamp,
                json.dumps(bl.source_domain_metrics) if bl.source_domain_metrics else "{}" # Serialize dict to JSON string
            ])
        return rows

    def _prepare_seo_metrics_data(self, seo_metrics_list: List[Any]) -> List[List[Any]]:
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
                int(sm.has_canonical) if sm.has_canonical is not None else None,
                int(sm.has_robots_meta) if sm.has_robots_meta is not None else None,
                int(sm.has_schema_markup) if sm.has_schema_markup is not None else None,
                sm.broken_links,
                sm.performance_score,
                int(sm.mobile_friendly) if sm.mobile_friendly is not None else None,
                sm.accessibility_score,
                sm.audit_timestamp,
                sm.seo_score,
                sm.issues,
                sm.structured_data_types,
                sm.og_title,
                sm.og_description,
                sm.twitter_title,
                sm.twitter_description,
                sm.validation_issues,
                sm.ocr_text,
                sm.nlp_entities,
                sm.nlp_sentiment,
                sm.nlp_topics,
                sm.video_transcription,
                sm.video_topics,
                sm.ai_content_classification,
                sm.ai_content_score,
                sm.ai_suggestions,
                sm.ai_semantic_keywords,
                sm.ai_readability_score
            ])
        return rows

    def _prepare_serp_results_data(self, serp_results: List[Any]) -> List[List[Any]]:
        """Converts a list of SERPResult dataclasses to a list of lists for ClickHouse insertion."""
        rows = []
        for sr in serp_results:
            rows.append([
                sr.id,
                sr.keyword,
                sr.rank, # Changed from position
                sr.url, # Changed from result_url
                sr.title, # Changed from title_text
                sr.snippet, # Changed from snippet_text
                sr.domain, # New field
                sr.position_type, # New field
                sr.timestamp
            ])
        return rows

    def _prepare_keyword_suggestions_data(self, suggestions: List[Any]) -> List[List[Any]]:
        """Converts a list of KeywordSuggestion dataclasses to a list of lists for ClickHouse insertion."""
        rows = []
        for ks in suggestions:
            rows.append([
                ks.id,
                ks.keyword, # Changed from suggested_keyword
                ks.search_volume, # Changed from search_volume_monthly
                ks.cpc, # Changed from cpc_estimate
                ks.competition, # Changed from competition_level
                ks.difficulty, # New field
                ks.relevance, # New field
                ks.source # New field
            ])
        return rows

    async def bulk_insert_backlinks(self, backlinks: List[Any]):
        """Bulk inserts Backlink data into ClickHouse."""
        if not self.enabled or not self.client:
            self.logger.error("ClickHouse client not initialized or disabled. Cannot insert backlinks.")
            return
        if not backlinks:
            return

        data_to_insert = self._prepare_backlink_data(backlinks)
        try:
            await self._execute_query(
                'INSERT INTO backlinks_analytical VALUES',
                data=data_to_insert,
                types_check=True # Enable type checking for safer inserts
            )
            self.logger.info(f"Successfully bulk inserted {len(backlinks)} backlinks into ClickHouse.")
        except Exception as e:
            self.logger.error(f"Failed to bulk insert backlinks into ClickHouse: {e}", exc_info=True)
            raise

    async def bulk_insert_seo_metrics(self, seo_metrics_list: List[Any]):
        """Bulk inserts SEOMetrics data into ClickHouse."""
        if not self.enabled or not self.client:
            self.logger.error("ClickHouse client not initialized or disabled. Cannot insert SEO metrics.")
            return
        if not seo_metrics_list:
            return

        data_to_insert = self._prepare_seo_metrics_data(seo_metrics_list)
        try:
            await self._execute_query(
                'INSERT INTO seo_metrics_analytical VALUES',
                data=data_to_insert,
                types_check=True
            )
            self.logger.info(f"Successfully bulk inserted {len(seo_metrics_list)} SEO metrics into ClickHouse.")
        except Exception as e:
            self.logger.error(f"Failed to bulk insert SEO metrics into ClickHouse: {e}", exc_info=True)
            raise

    async def bulk_insert_serp_results(self, serp_results: List[Any]):
        """Bulk inserts SERP results data into ClickHouse."""
        if not self.enabled or not self.client:
            self.logger.error("ClickHouse client not initialized or disabled. Cannot insert SERP results.")
            return
        if not serp_results:
            return

        data_to_insert = self._prepare_serp_results_data(serp_results)
        try:
            await self._execute_query(
                'INSERT INTO serp_results_analytical VALUES',
                data=data_to_insert,
                types_check=True
            )
            self.logger.info(f"Successfully bulk inserted {len(serp_results)} SERP results into ClickHouse.")
        except Exception as e:
            self.logger.error(f"Failed to bulk insert SERP results into ClickHouse: {e}", exc_info=True)
            raise

    async def bulk_insert_keyword_suggestions(self, suggestions: List[Any]):
        """Bulk inserts keyword suggestions data into ClickHouse."""
        if not self.enabled or not self.client:
            self.logger.error("ClickHouse client not initialized or disabled. Cannot insert keyword suggestions.")
            return
        if not suggestions:
            return

        data_to_insert = self._prepare_keyword_suggestions_data(suggestions)
        try:
            await self._execute_query(
                'INSERT INTO keyword_suggestions_analytical VALUES',
                data=data_to_insert,
                types_check=True
            )
            self.logger.info(f"Successfully bulk inserted {len(suggestions)} keyword suggestions into ClickHouse.")
        except Exception as e:
            self.logger.error(f"Failed to bulk insert keyword suggestions into ClickHouse: {e}", exc_info=True)
            raise

    async def select_data(self, query: str) -> List[Dict[str, Any]]:
        """
        Executes a SELECT query and returns data as a list of dictionaries.
        Assumes JSONEachRow format for output.
        """
        if not self.enabled or not self.client:
            self.logger.error("ClickHouse client not initialized or disabled. Cannot select data.")
            return []
        self.logger.debug(f"Executing ClickHouse SELECT query: {query}")
        try:
            # clickhouse_driver client.execute returns data directly
            result = await self._execute_query(query)
            # Assuming the query returns rows that can be converted to dicts
            # This might need more sophisticated parsing depending on query output
            if result:
                # If result is a list of tuples, convert to list of dicts if column names are known
                # For simplicity, if the query is "SELECT * FROM table FORMAT JSONEachRow",
                # the execute method might return a string that needs parsing.
                # However, clickhouse_driver's execute method usually returns a list of tuples.
                # For JSONEachRow, we'd typically use a separate HTTP client or a specific driver feature.
                # Let's assume for now that simple SELECTs return list of lists/tuples.
                # If you need JSONEachRow, you'd specify it in the query and parse the string result.
                # For now, we'll return the raw result from execute.
                return result
            return []
        except Exception as e:
            self.logger.error(f"Failed to select data from ClickHouse: {e}")
            raise

    async def ping(self) -> bool:
        """Pings the ClickHouse server to check connectivity."""
        if not self.enabled or not self.client:
            return False
        try:
            await self._execute_query("SELECT 1")
            self.logger.debug("ClickHouse ping successful.")
            return True
        except Exception:
            self.logger.error("ClickHouse ping failed.")
            return False

# Example usage (for testing purposes)
async def main():
    # Ensure ClickHouse is running and accessible
    # Example config:
    # clickhouse:
    #   enabled: true
    #   host: "localhost"
    #   port: 8123
    #   user: "default"
    #   password: ""
    #   database: "test_db"

    # Mock config_loader for testing
    class MockConfigLoader:
        def get(self, key, default=None):
            if key == "clickhouse.enabled": return True
            if key == "clickhouse.host": return "localhost"
            if key == "clickhouse.port": return 9000 # Default TCP port for clickhouse-driver
            if key == "clickhouse.user": return "default"
            if key == "clickhouse.password": return ""
            if key == "clickhouse.database": return "test_db"
            return default
    
    global config_loader
    config_loader = MockConfigLoader()

    loader = ClickHouseLoader(
        host=config_loader.get("clickhouse.host"),
        port=config_loader.get("clickhouse.port"),
        user=config_loader.get("clickhouse.user"),
        password=config_loader.get("clickhouse.password"),
    )

    async with loader:
        if await loader.ping():
            print("ClickHouse is reachable.")
            
            table_name = "test_metrics"
            # Note: ClickHouse schema uses different types than Python.
            # JSON is typically stored as String or JSONB (if using newer versions/drivers)
            # For clickhouse_driver, JSONB is not directly supported, use String and serialize/deserialize.
            schema = "id String, timestamp DateTime, metric_name String, value Float64, labels String"
            
            await loader.create_table(table_name, schema)
            
            data_to_insert = [
                {"id": str(uuid.uuid4()), "timestamp": datetime.now(), "metric_name": "cpu_usage", "value": 45.5, "labels": json.dumps({"host": "server1"})},
                {"id": str(uuid.uuid4()), "timestamp": datetime.now(), "metric_name": "mem_usage", "value": 60.2, "labels": json.dumps({"host": "server1", "app": "web"})},
                {"id": str(uuid.uuid4()), "timestamp": datetime.now(), "metric_name": "cpu_usage", "value": 50.1, "labels": json.dumps({"host": "server2"})},
            ]
            # Convert list of dicts to list of lists for clickhouse_driver insert
            insert_rows = [[row['id'], row['timestamp'], row['metric_name'], row['value'], row['labels']] for row in data_to_insert]

            await loader._execute_query(f'INSERT INTO {table_name} VALUES', data=insert_rows, types_check=True)
            print(f"Successfully inserted {len(insert_rows)} rows into {table_name}.")

            results = await loader.select_data(f"SELECT * FROM {table_name} WHERE metric_name = 'cpu_usage'")
            print("\nSelected Data:")
            for row in results:
                print(row)
        else:
            print("ClickHouse is not reachable. Skipping tests.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import uuid # Import uuid for example
    asyncio.run(main())
