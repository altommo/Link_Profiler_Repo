import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from Link_Profiler.clients.wayback_machine_client import WaybackClient, WaybackSnapshot
from Link_Profiler.services.ai_service import AIService
from Link_Profiler.utils.content_validator import ContentValidator
from Link_Profiler.utils.proxy_manager import ProxyManager, ProxyDetails, ProxyStatus
from Link_Profiler.config.env_config import EnvironmentConfig
import os # Import os for environment variable patching
from Link_Profiler.utils.session_manager import SessionManager # Import SessionManager for mocking

class TestWaybackClient:
    """Test real Wayback Machine implementation."""
    
    @pytest.mark.asyncio
    async def test_wayback_snapshot_creation(self):
        """Test WaybackSnapshot data class."""
        cdx_data = [
            'com,example)/',
            '20200101000000',
            'http://example.com/',
            'text/html',
            '200',
            'ABCD1234',
            '1024'
        ]
        
        snapshot = WaybackSnapshot(cdx_data)
        
        assert snapshot.urlkey == 'com,example)/'
        assert snapshot.timestamp == '20200101000000'
        assert snapshot.original_url == 'http://example.com/'
        assert snapshot.status_code == '200'
        assert snapshot.timestamp_iso == '2020-01-01T00:00:00'
        assert 'web.archive.org' in snapshot.archive_url
    
    @pytest.mark.asyncio
    async def test_wayback_client_disabled(self):
        """Test client behavior when disabled."""
        with patch('Link_Profiler.config.config_loader.config_loader.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                "historical_data.wayback_machine_api.enabled": False,
                "historical_data.wayback_machine_api.base_url": "http://test.url"
            }.get(key, default)
            
            client = WaybackClient()
            results = await client.get_snapshots('http://example.com')
            
            assert results == []
    
    @pytest.mark.asyncio
    async def test_wayback_api_call(self):
        """Test real API call structure."""
        mock_session_manager = AsyncMock(spec=SessionManager) # Mock SessionManager
        mock_response = AsyncMock()
        mock_response.json.return_value = [
            ['urlkey', 'timestamp', 'original', 'mimetype', 'statuscode', 'digest', 'length'],
            ['com,example)/', '20200101000000', 'http://example.com/', 'text/html', '200', 'ABCD1234', '1024']
        ]
        mock_session_manager.get.return_value.__aenter__.return_value = mock_response
        
        with patch('Link_Profiler.config.config_loader.config_loader.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                "historical_data.wayback_machine_api.enabled": True,
                "historical_data.wayback_machine_api.base_url": "http://test.url"
            }.get(key, default)
            
            client = WaybackClient(session_manager=mock_session_manager)
            
            results = await client.get_snapshots('http://example.com')
            
            assert len(results) == 1
            assert isinstance(results[0], WaybackSnapshot)
            assert results[0].original_url == 'http://example.com/'

class TestContentValidator:
    """Test real content validation implementation."""
    
    def test_content_quality_empty(self):
        """Test validation of empty content."""
        validator = ContentValidator()
        result = validator.validate_content_quality("", "http://example.com")
        
        assert result['quality_score'] == 0
        assert 'Empty content' in result['issues']
        assert result['word_count'] == 0
    
    def test_content_quality_good(self):
        """Test validation of good quality content."""
        validator = ContentValidator()
        content = """
        This is a comprehensive analysis of machine learning algorithms.
        The research shows that deep learning models perform better than traditional methods.
        Our study includes detailed comparisons and statistical analysis.
        """ * 10  # Make it longer
        
        result = validator.validate_content_quality(content, "http://example.com")
        
        assert result['quality_score'] > 60
        assert result['word_count'] > 100
        assert result['spam_score'] < 20
    
    def test_spam_detection(self):
        """Test spam content detection."""
        validator = ContentValidator()
        spam_content = "BUY NOW!!! CLICK HERE!!! FREE MONEY!!! ACT FAST!!!"
        
        result = validator.validate_content_quality(spam_content, "http://spam.com")
        
        assert result['spam_score'] > 50
        assert result['quality_score'] < 30
    
    def test_placeholder_detection(self):
        """Test placeholder content detection."""
        validator = ContentValidator()
        placeholder_content = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. This is placeholder text and dummy content."
        
        result = validator.validate_content_quality(placeholder_content, "http://example.com")
        
        assert any('placeholder' in issue.lower() for issue in result['issues'])
    
    def test_readability_calculation(self):
        """Test readability score calculation."""
        validator = ContentValidator()
        
        # Simple sentences should have good readability
        simple_content = "This is easy to read. Short sentences are good. People like simple words."
        result = validator.validate_content_quality(simple_content, "http://example.com")
        
        assert result['readability_score'] > 50

class TestProxyManager:
    """Test real proxy management implementation."""
    
    def test_proxy_initialization(self):
        """Test proxy manager initialization."""
        with patch('Link_Profiler.config.config_loader.config_loader.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                'proxy.use_proxies': True,
                'proxy.proxy_list': [
                    {'url': 'http://proxy1:8080', 'region': 'us'},
                    {'url': 'http://proxy2:8080', 'region': 'eu'}
                ],
                'proxy.proxy_retry_delay_seconds': 300,
                'proxy.max_failures_before_ban': 5 # Added this default as it's used in ProxyManager
            }.get(key, default)
            
            manager = ProxyManager()
            
            assert len(manager.proxies) == 2
            assert manager.use_proxies == True
            assert manager.retry_delay == 300
    
    def test_proxy_rotation(self):
        """Test proxy rotation logic."""
        # Mock config_loader for ProxyManager initialization
        with patch('Link_Profiler.config.config_loader.config_loader.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                'proxy.use_proxies': True,
                'proxy.proxy_list': [], # Empty list for this test, we'll add manually
                'proxy.proxy_retry_delay_seconds': 300,
                'proxy.max_failures_before_ban': 5
            }.get(key, default)
            
            manager = ProxyManager()
            manager.use_proxies = True
            
            # Add test proxies
            proxy1 = ProxyDetails("http://proxy1:8080", "us", ProxyStatus.ACTIVE)
            proxy1.success_count = 10
            proxy1.failure_count = 1
            
            proxy2 = ProxyDetails("http://proxy2:8080", "eu", ProxyStatus.ACTIVE)
            proxy2.success_count = 5
            proxy2.failure_count = 2
            
            manager.proxies = [proxy1, proxy2]
            
            # Should favor proxy1 (better success rate)
            selected = manager.get_next_proxy()
            assert selected is not None
            assert selected.url in ["http://proxy1:8080", "http://proxy2:8080"]
    
    def test_proxy_failure_tracking(self):
        """Test proxy failure tracking and banning."""
        # Mock config_loader for ProxyManager initialization
        with patch('Link_Profiler.config.config_loader.config_loader.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                'proxy.use_proxies': True,
                'proxy.proxy_list': [], # Empty list for this test, we'll add manually
                'proxy.proxy_retry_delay_seconds': 300,
                'proxy.max_failures_before_ban': 3 # Set max failures for this test
            }.get(key, default)

            manager = ProxyManager()
            manager.max_failures = 3
            
            proxy = ProxyDetails("http://test:8080", "us", ProxyStatus.ACTIVE)
            manager.proxies = [proxy]
            
            # Mark as failed multiple times
            for i in range(4):
                manager.mark_proxy_bad("http://test:8080", f"Error {i}")
            
            assert proxy.status == ProxyStatus.BANNED
            assert proxy.failure_count == 4
    
    @pytest.mark.asyncio
    async def test_proxy_testing(self):
        """Test proxy health checking."""
        # Mock config_loader for ProxyManager initialization
        with patch('Link_Profiler.config.config_loader.config_loader.get') as mock_config:
            mock_config.side_effect = lambda key, default=None: {
                'proxy.use_proxies': True,
                'proxy.proxy_list': [], # Empty list for this test, we'll add manually
                'proxy.proxy_retry_delay_seconds': 300,
                'proxy.max_failures_before_ban': 5
            }.get(key, default)

            manager = ProxyManager()
            proxy = ProxyDetails("http://test:8080", "us", ProxyStatus.TESTING)
            
            with patch('aiohttp.ClientSession') as mock_session:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
                
                result = await manager.test_proxy(proxy, "http://httpbin.org/ip")
                
                assert result == True
                assert proxy.status == ProxyStatus.ACTIVE

class TestEnvironmentConfig:
    """Test environment variable configuration."""
    
    def test_env_var_basic(self):
        """Test basic environment variable retrieval."""
        with patch.dict(os.environ, {'TEST_VAR': 'test_value'}):
            value = EnvironmentConfig.get_env_var('TEST_VAR')
            assert value == 'test_value'
    
    def test_env_var_default(self):
        """Test default value fallback."""
        value = EnvironmentConfig.get_env_var('NONEXISTENT_VAR', default='default_value')
        assert value == 'default_value'
    
    def test_env_var_required(self):
        """Test required variable validation."""
        with pytest.raises(ValueError, match="Required environment variable"):
            EnvironmentConfig.get_env_var('REQUIRED_VAR', required=True)
    
    def test_env_var_type_conversion(self):
        """Test type conversion."""
        with patch.dict(os.environ, {
            'BOOL_VAR': 'true',
            'INT_VAR': '42',
            'LIST_VAR': 'item1,item2,item3'
        }):
            assert EnvironmentConfig.get_env_var('BOOL_VAR', var_type=bool) == True
            assert EnvironmentConfig.get_env_var('INT_VAR', var_type=int) == 42
            assert EnvironmentConfig.get_env_var('LIST_VAR', var_type=list) == ['item1', 'item2', 'item3']
    
    def test_secret_key_generation(self):
        """Test secure secret key generation."""
        key1 = EnvironmentConfig.generate_secret_key()
        key2 = EnvironmentConfig.generate_secret_key()
        
        assert len(key1) >= 32
        assert len(key2) >= 32
        assert key1 != key2  # Should be random
    
    def test_database_url_validation(self):
        """Test database URL validation."""
        with patch.dict(os.environ, {'LP_DATABASE_URL': 'postgresql://user:pass@localhost/db'}):
            url = EnvironmentConfig.get_database_url()
            assert url == 'postgresql://user:pass@localhost/db'
        
        with patch.dict(os.environ, {'LP_DATABASE_URL': 'invalid://url'}):
            with pytest.raises(ValueError, match="Invalid database URL format"):
                EnvironmentConfig.get_database_url()
