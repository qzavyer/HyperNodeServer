"""Tests for dry-run functionality."""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, Mock

from src.cleanup.directory_cleaner import DirectoryCleaner


class TestDryRun:
    """Test cases for dry-run functionality."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cleaner = DirectoryCleaner(self.temp_dir)
        
    def teardown_method(self):
        """Cleanup test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_log_dry_run_operation(self):
        """Test dry-run operation logging."""
        # Test dry-run mode
        with patch.object(self.cleaner.logger, 'info') as mock_info:
            self.cleaner._log_dry_run_operation("delete", "test_file.txt", True)
            mock_info.assert_called_with("🔍 [DRY-RUN] Would delete: test_file.txt")
        
        # Test normal mode
        with patch.object(self.cleaner.logger, 'info') as mock_info:
            self.cleaner._log_dry_run_operation("delete", "test_file.txt", False)
            mock_info.assert_called_with("🗑️ Delete: test_file.txt")
    
    def test_get_cleanup_report(self):
        """Test cleanup report generation."""
        report = self.cleaner.get_cleanup_report(True)
        
        assert report["dry_run"] is True
        assert "timestamp" in report
        assert "summary" in report
        assert "categories" in report
        assert report["summary"]["status"] == "report_generated"
    
    def test_estimate_space_to_free_file(self):
        """Test space estimation for a file."""
        # Create a test file
        test_file = Path(self.temp_dir) / "test_file.txt"
        test_file.write_text("test content")
        
        size_mb = self.cleaner.estimate_space_to_free(test_file)
        assert size_mb > 0
    
    def test_estimate_space_to_free_directory(self):
        """Test space estimation for a directory."""
        # Create test files
        test_dir = Path(self.temp_dir) / "test_dir"
        test_dir.mkdir()
        
        (test_dir / "file1.txt").write_text("content1")
        (test_dir / "file2.txt").write_text("content2")
        
        size_mb = self.cleaner.estimate_space_to_free(test_dir)
        assert size_mb > 0
    
    def test_estimate_space_to_free_nonexistent(self):
        """Test space estimation for non-existent path."""
        nonexistent = Path(self.temp_dir) / "nonexistent"
        size_mb = self.cleaner.estimate_space_to_free(nonexistent)
        assert size_mb == 0.0
    
    @pytest.mark.asyncio
    async def test_cleanup_async_dry_run_mode(self):
        """Test cleanup_async in dry-run mode."""
        # Mock all cleanup methods to return test values
        with patch.object(self.cleaner, '_cleanup_orders_async', return_value=(1, None)) as mock_orders, \
             patch.object(self.cleaner, '_cleanup_numeric_files_async', return_value=2) as mock_numeric, \
             patch.object(self.cleaner, '_cleanup_replica_cmds_async', return_value=0) as mock_replica, \
             patch.object(self.cleaner, '_cleanup_periodic_abci_async', return_value=0) as mock_periodic, \
             patch.object(self.cleaner, '_cleanup_evm_block_receipts_async', return_value=0) as mock_evm, \
             patch.object(self.cleaner, '_cleanup_validator_connections_async', return_value=0) as mock_validator, \
             patch.object(self.cleaner, '_cleanup_node_fast_block_times_async', return_value=0) as mock_node_fast, \
             patch.object(self.cleaner, '_cleanup_checkpoints_async', return_value=0) as mock_checkpoints, \
             patch.object(self.cleaner, '_cleanup_temp_dirs_async', return_value=0) as mock_temp, \
             patch.object(self.cleaner, '_cleanup_crit_msg_stats_async', return_value=0) as mock_crit, \
             patch.object(self.cleaner, '_cleanup_dhs_data_async', return_value=0) as mock_dhs, \
             patch.object(self.cleaner, '_cleanup_latency_buckets_async', return_value=0) as mock_latency, \
             patch.object(self.cleaner, '_cleanup_node_logs_async', return_value=0) as mock_node_logs, \
             patch.object(self.cleaner, '_cleanup_periodic_data_async', return_value=0) as mock_periodic_data:
            
            removed_dirs, removed_files = await self.cleaner.cleanup_async(True)
            
            # Verify dry_run parameter was passed to all methods
            mock_orders.assert_called_once_with(True)
            # mock_numeric is only called if latest_directory exists
            mock_replica.assert_called_once_with(True)
            mock_periodic.assert_called_once_with(True)
            mock_evm.assert_called_once_with(True)
            mock_validator.assert_called_once_with(True)
            mock_node_fast.assert_called_once_with(True)
            mock_checkpoints.assert_called_once_with(True)
            mock_temp.assert_called_once_with(True)
            mock_crit.assert_called_once_with(True)
            mock_dhs.assert_called_once_with(True)
            mock_latency.assert_called_once_with(True)
            mock_node_logs.assert_called_once_with(True)
            mock_periodic_data.assert_called_once_with(True)
            
            # Verify return values
            assert removed_dirs == 1
            assert removed_files == 0  # No files removed since no latest_directory
    
    @pytest.mark.asyncio
    async def test_cleanup_async_normal_mode(self):
        """Test cleanup_async in normal mode."""
        # Mock all cleanup methods to return test values
        with patch.object(self.cleaner, '_cleanup_orders_async', return_value=(1, None)) as mock_orders, \
             patch.object(self.cleaner, '_cleanup_numeric_files_async', return_value=2) as mock_numeric, \
             patch.object(self.cleaner, '_cleanup_replica_cmds_async', return_value=0) as mock_replica, \
             patch.object(self.cleaner, '_cleanup_periodic_abci_async', return_value=0) as mock_periodic, \
             patch.object(self.cleaner, '_cleanup_evm_block_receipts_async', return_value=0) as mock_evm, \
             patch.object(self.cleaner, '_cleanup_validator_connections_async', return_value=0) as mock_validator, \
             patch.object(self.cleaner, '_cleanup_node_fast_block_times_async', return_value=0) as mock_node_fast, \
             patch.object(self.cleaner, '_cleanup_checkpoints_async', return_value=0) as mock_checkpoints, \
             patch.object(self.cleaner, '_cleanup_temp_dirs_async', return_value=0) as mock_temp, \
             patch.object(self.cleaner, '_cleanup_crit_msg_stats_async', return_value=0) as mock_crit, \
             patch.object(self.cleaner, '_cleanup_dhs_data_async', return_value=0) as mock_dhs, \
             patch.object(self.cleaner, '_cleanup_latency_buckets_async', return_value=0) as mock_latency, \
             patch.object(self.cleaner, '_cleanup_node_logs_async', return_value=0) as mock_node_logs, \
             patch.object(self.cleaner, '_cleanup_periodic_data_async', return_value=0) as mock_periodic_data:
            
            removed_dirs, removed_files = await self.cleaner.cleanup_async(False)
            
            # Verify dry_run parameter was passed to all methods
            mock_orders.assert_called_once_with(False)
            mock_replica.assert_called_once_with(False)
            mock_periodic.assert_called_once_with(False)
            mock_evm.assert_called_once_with(False)
            mock_validator.assert_called_once_with(False)
            mock_node_fast.assert_called_once_with(False)
            mock_checkpoints.assert_called_once_with(False)
            mock_temp.assert_called_once_with(False)
            mock_crit.assert_called_once_with(False)
            mock_dhs.assert_called_once_with(False)
            mock_latency.assert_called_once_with(False)
            mock_node_logs.assert_called_once_with(False)
            mock_periodic_data.assert_called_once_with(False)
            
            # Verify return values
            assert removed_dirs == 1
            assert removed_files == 0  # No files removed since no latest_directory
    
    @pytest.mark.asyncio
    async def test_cleanup_async_default_mode(self):
        """Test cleanup_async with default parameters (no dry-run)."""
        # Mock all cleanup methods
        with patch.object(self.cleaner, '_cleanup_orders_async', return_value=(0, None)) as mock_orders, \
             patch.object(self.cleaner, '_cleanup_numeric_files_async', return_value=0) as mock_numeric, \
             patch.object(self.cleaner, '_cleanup_replica_cmds_async', return_value=0) as mock_replica, \
             patch.object(self.cleaner, '_cleanup_periodic_abci_async', return_value=0) as mock_periodic, \
             patch.object(self.cleaner, '_cleanup_evm_block_receipts_async', return_value=0) as mock_evm, \
             patch.object(self.cleaner, '_cleanup_validator_connections_async', return_value=0) as mock_validator, \
             patch.object(self.cleaner, '_cleanup_node_fast_block_times_async', return_value=0) as mock_node_fast, \
             patch.object(self.cleaner, '_cleanup_checkpoints_async', return_value=0) as mock_checkpoints, \
             patch.object(self.cleaner, '_cleanup_temp_dirs_async', return_value=0) as mock_temp, \
             patch.object(self.cleaner, '_cleanup_crit_msg_stats_async', return_value=0) as mock_crit, \
             patch.object(self.cleaner, '_cleanup_dhs_data_async', return_value=0) as mock_dhs, \
             patch.object(self.cleaner, '_cleanup_latency_buckets_async', return_value=0) as mock_latency, \
             patch.object(self.cleaner, '_cleanup_node_logs_async', return_value=0) as mock_node_logs, \
             patch.object(self.cleaner, '_cleanup_periodic_data_async', return_value=0) as mock_periodic_data:
            
            removed_dirs, removed_files = await self.cleaner.cleanup_async()
            
            # Verify default False was passed to all methods
            mock_orders.assert_called_once_with(False)
            mock_replica.assert_called_once_with(False)
            mock_periodic.assert_called_once_with(False)
            mock_evm.assert_called_once_with(False)
            mock_validator.assert_called_once_with(False)
            mock_node_fast.assert_called_once_with(False)
            mock_checkpoints.assert_called_once_with(False)
            mock_temp.assert_called_once_with(False)
            mock_crit.assert_called_once_with(False)
            mock_dhs.assert_called_once_with(False)
            mock_latency.assert_called_once_with(False)
            mock_node_logs.assert_called_once_with(False)
            mock_periodic_data.assert_called_once_with(False)
            
            # Verify return values
            assert removed_dirs == 0
            assert removed_files == 0
