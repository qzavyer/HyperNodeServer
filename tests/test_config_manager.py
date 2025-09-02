"""Tests for ConfigManager."""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, AsyncMock

from src.storage.config_manager import ConfigManager, ConfigError
from src.storage.models import Config

class TestConfigManager:
    """Tests for ConfigManager class."""
    
    def setup_method(self):
        """Setup before each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_config.json"
        self.manager = ConfigManager(str(self.config_file))
    
    def teardown_method(self):
        """Cleanup after each test."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init_creates_directory(self):
        """Test that init creates config directory."""
        temp_dir = tempfile.mkdtemp()
        config_file = Path(temp_dir) / "nested" / "config.json"
        
        try:
            manager = ConfigManager(str(config_file))
            assert config_file.parent.exists()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_load_config_async_creates_default_when_not_exists(self):
        """Test loading config creates default when file doesn't exist."""
        with patch('src.storage.config_manager.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = "/test/path"
            mock_settings.CLEANUP_INTERVAL_HOURS = 5
            mock_settings.API_HOST = "127.0.0.1"
            mock_settings.API_PORT = 9000
            mock_settings.LOG_LEVEL = "INFO"
            mock_settings.LOG_FILE_PATH = "test.log"
            mock_settings.LOG_MAX_SIZE_MB = 50
            mock_settings.LOG_RETENTION_DAYS = 15
            mock_settings.DATA_DIR = "test_data"
            mock_settings.CONFIG_FILE_PATH = "test_config.json"
            mock_settings.MAX_ORDERS_PER_REQUEST = 500
            mock_settings.FILE_READ_RETRY_ATTEMPTS = 2
            mock_settings.FILE_READ_RETRY_DELAY = 0.5
            
            config = await self.manager.load_config_async()
            
            assert isinstance(config, Config)
            assert config.node_logs_path == "/test/path"
            assert config.cleanup_interval_hours == 5
            assert config.api_host == "127.0.0.1"
            assert config.api_port == 9000
            assert config.log_level == "INFO"
            assert config.log_file_path == "test.log"
            assert config.log_max_size_mb == 50
            assert config.log_retention_days == 15
            assert config.data_dir == "test_data"
            assert config.config_file_path == "test_config.json"
            assert config.max_orders_per_request == 500
            assert config.file_read_retry_attempts == 2
            assert config.file_read_retry_delay == 0.5
            assert config.symbols_config == []
    
    @pytest.mark.asyncio
    async def test_load_config_async_loads_existing_file(self):
        """Test loading config from existing file."""
        # Create test config file
        test_config = {
            "node_logs_path": "/custom/path",
            "cleanup_interval_hours": 10,
            "api_host": "0.0.0.0",
            "api_port": 8080,
            "log_level": "DEBUG",
            "log_file_path": "custom.log",
            "log_max_size_mb": 200,
            "log_retention_days": 60,
            "data_dir": "custom_data",
            "config_file_path": "custom_config.json",
            "max_orders_per_request": 2000,
            "file_read_retry_attempts": 5,
            "file_read_retry_delay": 2.0,
            "symbols_config": [
                {"symbol": "BTC", "min_liquidity": 1000.0, "price_deviation": 0.01},
                {"symbol": "ETH", "min_liquidity": 500.0, "price_deviation": 0.02}
            ]
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(test_config, f)
        
        config = await self.manager.load_config_async()
        
        assert isinstance(config, Config)
        assert config.node_logs_path == "/custom/path"
        assert config.cleanup_interval_hours == 10
        assert config.api_host == "0.0.0.0"
        assert config.api_port == 8080
        assert config.log_level == "DEBUG"
        assert config.log_file_path == "custom.log"
        assert config.log_max_size_mb == 200
        assert config.log_retention_days == 60
        assert config.data_dir == "custom_data"
        assert config.config_file_path == "custom_config.json"
        assert config.max_orders_per_request == 2000
        assert config.file_read_retry_attempts == 5
        assert config.file_read_retry_delay == 2.0
        assert len(config.symbols_config) == 2
        assert config.symbols_config[0].symbol == "BTC"
        assert config.symbols_config[0].min_liquidity == 1000.0
        assert config.symbols_config[1].symbol == "ETH"
        assert config.symbols_config[1].min_liquidity == 500.0
    
    @pytest.mark.asyncio
    async def test_load_config_async_handles_invalid_json(self):
        """Test loading config handles invalid JSON."""
        with open(self.config_file, 'w') as f:
            f.write("invalid json content")
        
        with pytest.raises(ConfigError, match="Configuration loading failed"):
            await self.manager.load_config_async()
    
    @pytest.mark.asyncio
    async def test_save_config_async(self):
        """Test saving configuration."""
        with patch('src.storage.config_manager.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = "/test/path"
            mock_settings.CLEANUP_INTERVAL_HOURS = 5
            mock_settings.API_HOST = "127.0.0.1"
            mock_settings.API_PORT = 9000
            mock_settings.LOG_LEVEL = "INFO"
            mock_settings.LOG_FILE_PATH = "test.log"
            mock_settings.LOG_MAX_SIZE_MB = 50
            mock_settings.LOG_RETENTION_DAYS = 15
            mock_settings.DATA_DIR = "test_data"
            mock_settings.CONFIG_FILE_PATH = "test_config.json"
            mock_settings.MAX_ORDERS_PER_REQUEST = 500
            mock_settings.FILE_READ_RETRY_ATTEMPTS = 2
            mock_settings.FILE_READ_RETRY_DELAY = 0.5
            
            config = await self.manager.load_config_async()
            
            # Modify config
            config.api_port = 9999
            config.log_level = "ERROR"
            
            await self.manager.save_config_async(config)
            
            # Verify file was saved
            assert self.config_file.exists()
            
            # Load and verify
            with open(self.config_file, 'r') as f:
                saved_data = json.load(f)
            
            assert saved_data["api_port"] == 9999
            assert saved_data["log_level"] == "ERROR"
    
    def test_get_config_raises_error_when_not_loaded(self):
        """Test get_config raises error when config not loaded."""
        with pytest.raises(ConfigError, match="Configuration not loaded"):
            self.manager.get_config()
    
    @pytest.mark.asyncio
    async def test_update_config_async(self):
        """Test updating configuration."""
        with patch('src.storage.config_manager.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = "/test/path"
            mock_settings.CLEANUP_INTERVAL_HOURS = 5
            mock_settings.API_HOST = "127.0.0.1"
            mock_settings.API_PORT = 9000
            mock_settings.LOG_LEVEL = "INFO"
            mock_settings.LOG_FILE_PATH = "test.log"
            mock_settings.LOG_MAX_SIZE_MB = 50
            mock_settings.LOG_RETENTION_DAYS = 15
            mock_settings.DATA_DIR = "test_data"
            mock_settings.CONFIG_FILE_PATH = "test_config.json"
            mock_settings.MAX_ORDERS_PER_REQUEST = 500
            mock_settings.FILE_READ_RETRY_ATTEMPTS = 2
            mock_settings.FILE_READ_RETRY_DELAY = 0.5
            
            await self.manager.load_config_async()
            
            updates = {
                "api_port": 9999,
                "log_level": "ERROR",
                "symbols_config": [
                    {"symbol": "BTC", "min_liquidity": 5000.0, "price_deviation": 0.01}
                ]
            }
            
            updated_config = await self.manager.update_config_async(updates)
            
            assert updated_config.api_port == 9999
            assert updated_config.log_level == "ERROR"
            assert len(updated_config.symbols_config) == 1
            assert updated_config.symbols_config[0].symbol == "BTC"
            assert updated_config.symbols_config[0].min_liquidity == 5000.0
            
            # Verify file was updated
            with open(self.config_file, 'r') as f:
                saved_data = json.load(f)
            
            assert saved_data["api_port"] == 9999
            assert saved_data["log_level"] == "ERROR"
            assert len(saved_data["symbols_config"]) == 1
            assert saved_data["symbols_config"][0]["symbol"] == "BTC"
            assert saved_data["symbols_config"][0]["min_liquidity"] == 5000.0
    
    @pytest.mark.asyncio
    async def test_update_config_async_handles_invalid_updates(self):
        """Test updating config handles invalid updates."""
        with patch('src.storage.config_manager.settings') as mock_settings:
            mock_settings.NODE_LOGS_PATH = "/test/path"
            mock_settings.CLEANUP_INTERVAL_HOURS = 5
            mock_settings.API_HOST = "127.0.0.1"
            mock_settings.API_PORT = 9000
            mock_settings.LOG_LEVEL = "INFO"
            mock_settings.LOG_FILE_PATH = "test.log"
            mock_settings.LOG_MAX_SIZE_MB = 50
            mock_settings.LOG_RETENTION_DAYS = 15
            mock_settings.DATA_DIR = "test_data"
            mock_settings.CONFIG_FILE_PATH = "test_config.json"
            mock_settings.MAX_ORDERS_PER_REQUEST = 500
            mock_settings.FILE_READ_RETRY_ATTEMPTS = 2
            mock_settings.FILE_READ_RETRY_DELAY = 0.5
            
            await self.manager.load_config_async()
            
            # Invalid port number
            updates = {"api_port": 99999}
            
            with pytest.raises(ConfigError, match="Configuration update failed"):
                await self.manager.update_config_async(updates)
