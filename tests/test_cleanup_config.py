"""Tests for cleanup configuration functionality."""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock

from src.cleanup.directory_cleaner import DirectoryCleaner


class TestCleanupConfig:
    """Test cases for cleanup configuration functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cleaner = DirectoryCleaner(self.temp_dir)
        
        # Create test configuration
        self.test_config = {
            "version": "1.0",
            "description": "Test configuration",
            "rules": {
                "temp_directories": {
                    "description": "Temporary directories",
                    "paths": [
                        {
                            "path": "/tmp/test1/",
                            "rule_type": "date_in_filename",
                            "retention_days": 2,
                            "filename_pattern": "YYYY-MM-DD_HH:MM:SS.*"
                        }
                    ]
                },
                "test_category": {
                    "description": "Test category",
                    "paths": [
                        {
                            "path": "/tmp/test2/",
                            "rule_type": "keep_last_files",
                            "keep_count": 10,
                            "filename_pattern": "\\d+\\.log"
                        }
                    ]
                }
            },
            "rule_types": {
                "date_in_filename": {
                    "description": "Cleanup by date in filename",
                    "parameters": ["retention_days", "filename_pattern"]
                },
                "keep_last_files": {
                    "description": "Keep last N files",
                    "parameters": ["keep_count", "filename_pattern"]
                }
            },
            "settings": {
                "dry_run": False,
                "max_execution_time_minutes": 30,
                "log_level": "DEBUG"
            }
        }
    
    def teardown_method(self):
        """Cleanup test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_config_success(self):
        """Test successful configuration loading."""
        # Create temporary config file
        config_file = Path(self.temp_dir) / "test_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        # Load configuration
        self.cleaner.load_config(str(config_file))
        
        # Verify configuration was loaded
        assert self.cleaner.config is not None
        assert self.cleaner.config["version"] == "1.0"
        assert self.cleaner.config_path == config_file.resolve()
    
    def test_load_config_file_not_found(self):
        """Test configuration loading when file doesn't exist."""
        non_existent_file = Path(self.temp_dir) / "non_existent.json"
        
        # Should not raise exception, just log warning
        self.cleaner.load_config(str(non_existent_file))
        
        assert self.cleaner.config is None
        assert self.cleaner.config_path == non_existent_file.resolve()
    
    def test_load_config_invalid_json(self):
        """Test configuration loading with invalid JSON."""
        config_file = Path(self.temp_dir) / "invalid_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write("invalid json content")
        
        # Should raise JSONDecodeError
        with pytest.raises(json.JSONDecodeError):
            self.cleaner.load_config(str(config_file))
    
    def test_validate_config_complete(self):
        """Test configuration validation with complete config."""
        config_file = Path(self.temp_dir) / "complete_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        self.cleaner.load_config(str(config_file))
        
        # Should not raise any exceptions during validation
        assert self.cleaner.config is not None
    
    def test_validate_config_missing_keys(self):
        """Test configuration validation with missing keys."""
        incomplete_config = {
            "version": "1.0"
            # Missing required keys
        }
        
        config_file = Path(self.temp_dir) / "incomplete_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(incomplete_config, f)
        
        # Should not raise exception, just log warnings
        self.cleaner.load_config(str(config_file))
        assert self.cleaner.config is not None
    
    def test_validate_rule_missing_fields(self):
        """Test rule validation with missing fields."""
        invalid_config = {
            "version": "1.0",
            "rules": {
                "test_category": {
                    "paths": [
                        {
                            "path": "/tmp/test/",
                            # Missing rule_type
                        }
                    ]
                }
            },
            "rule_types": {},
            "settings": {}
        }
        
        config_file = Path(self.temp_dir) / "invalid_rule_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(invalid_config, f)
        
        # Should not raise exception, just log warnings
        self.cleaner.load_config(str(config_file))
        assert self.cleaner.config is not None
    
    def test_validate_rule_unknown_type(self):
        """Test rule validation with unknown rule type."""
        invalid_config = {
            "version": "1.0",
            "rules": {
                "test_category": {
                    "paths": [
                        {
                            "path": "/tmp/test/",
                            "rule_type": "unknown_type"
                        }
                    ]
                }
            },
            "rule_types": {},
            "settings": {}
        }
        
        config_file = Path(self.temp_dir) / "unknown_rule_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(invalid_config, f)
        
        # Should not raise exception, just log warnings
        self.cleaner.load_config(str(config_file))
        assert self.cleaner.config is not None
    
    def test_get_config_summary_no_config(self):
        """Test config summary when no configuration is loaded."""
        summary = self.cleaner.get_config_summary()
        
        assert summary["status"] == "no_config_loaded"
    
    def test_get_config_summary_with_config(self):
        """Test config summary with loaded configuration."""
        config_file = Path(self.temp_dir) / "summary_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        self.cleaner.load_config(str(config_file))
        summary = self.cleaner.get_config_summary()
        
        assert summary["status"] == "loaded"
        assert summary["version"] == "1.0"
        assert summary["config_path"] == str(config_file.resolve())
        assert "temp_directories" in summary["categories"]
        assert "test_category" in summary["categories"]
        assert "date_in_filename" in summary["rule_types"]
        assert "keep_last_files" in summary["rule_types"]
        assert summary["total_rules"] == 2  # Two rules in test config
    
    @pytest.mark.asyncio
    async def test_apply_config_rules_no_config(self):
        """Test applying rules when no configuration is loaded."""
        removed_dirs, removed_files = await self.cleaner.apply_config_rules_async()
        
        assert removed_dirs == 0
        assert removed_files == 0
    
    @pytest.mark.asyncio
    async def test_apply_config_rules_with_config(self):
        """Test applying rules with loaded configuration."""
        config_file = Path(self.temp_dir) / "apply_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        self.cleaner.load_config(str(config_file))
        
        # Mock the rule application methods to return test values
        with patch.object(self.cleaner, '_apply_rule_async', return_value=(1, 2)):
            removed_dirs, removed_files = await self.cleaner.apply_config_rules_async()
        
        # Should process 2 rules (1 from temp_directories + 1 from test_category)
        assert removed_dirs == 2  # 1 * 2 rules
        assert removed_files == 4  # 2 * 2 rules
    
    @pytest.mark.asyncio
    async def test_apply_config_rules_dry_run(self):
        """Test applying rules in dry run mode."""
        config_file = Path(self.temp_dir) / "dry_run_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_config, f)
        
        self.cleaner.load_config(str(config_file))
        
        # Mock the rule application methods to return test values
        with patch.object(self.cleaner, '_apply_rule_async', return_value=(1, 2)) as mock_apply:
            removed_dirs, removed_files = await self.cleaner.apply_config_rules_async(dry_run=True)
            
            # Verify that rules were applied (2 rules in test config)
            assert mock_apply.call_count == 2
            assert removed_dirs == 2  # 1 * 2 rules
            assert removed_files == 4  # 2 * 2 rules
    
    @pytest.mark.asyncio
    async def test_apply_rule_unknown_type(self):
        """Test applying rule with unknown type."""
        rule = {
            "path": "/tmp/test/",
            "rule_type": "unknown_type"
        }
        
        removed_dirs, removed_files = await self.cleaner._apply_rule_async(rule)
        
        assert removed_dirs == 0
        assert removed_files == 0
    
    @pytest.mark.asyncio
    async def test_apply_rule_invalid_rule(self):
        """Test applying rule with invalid data."""
        rule = {
            # Missing required fields
        }
        
        removed_dirs, removed_files = await self.cleaner._apply_rule_async(rule)
        
        assert removed_dirs == 0
        assert removed_files == 0
    
    @pytest.mark.asyncio
    async def test_apply_rule_handles_exception(self):
        """Test that rule application handles exceptions gracefully."""
        rule = {
            "path": "/tmp/test/",
            "rule_type": "date_in_filename"
        }
        
        # Mock an exception in rule application
        with patch.object(self.cleaner, '_apply_date_in_filename_rule', side_effect=Exception("Test error")):
            removed_dirs, removed_files = await self.cleaner._apply_rule_async(rule)
        
        # Should return 0, 0 and not raise exception
        assert removed_dirs == 0
        assert removed_files == 0
    
    def test_config_rule_types_validation(self):
        """Test validation of rule types in configuration."""
        config_with_rule_types = {
            "version": "1.0",
            "rules": {},
            "rule_types": {
                "valid_type": {
                    "description": "Valid rule type",
                    "parameters": ["param1", "param2"]
                },
                "invalid_type": {
                    # Missing description and parameters
                }
            },
            "settings": {}
        }
        
        config_file = Path(self.temp_dir) / "rule_types_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_with_rule_types, f)
        
        # Should not raise exception, just log warnings
        self.cleaner.load_config(str(config_file))
        assert self.cleaner.config is not None
    
    def test_config_categories_validation(self):
        """Test validation of categories in configuration."""
        config_with_categories = {
            "version": "1.0",
            "rules": {
                "valid_category": {
                    "description": "Valid category",
                    "paths": [
                        {
                            "path": "/tmp/test/",
                            "rule_type": "keep_last_files",
                            "keep_count": 10
                        }
                    ]
                },
                "invalid_category": {
                    # Missing paths
                }
            },
            "rule_types": {
                "keep_last_files": {
                    "description": "Keep last files",
                    "parameters": ["keep_count"]
                }
            },
            "settings": {}
        }
        
        config_file = Path(self.temp_dir) / "categories_config.json"
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config_with_categories, f)
        
        # Should not raise exception, just log warnings
        self.cleaner.load_config(str(config_file))
        assert self.cleaner.config is not None
