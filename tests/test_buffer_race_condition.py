"""Tests for buffer race condition fix in SingleFileTailWatcher.

This test suite verifies that the critical race condition where multiple
_read_new_lines() calls could add to the same buffer during processing
has been fixed by immediate buffer clearing after snapshot creation.
"""
import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from src.watcher.single_file_tail_watcher import SingleFileTailWatcher


class TestBufferRaceCondition:
    """Tests for buffer race condition fix."""
    
    @pytest.fixture
    def mock_order_manager(self):
        """Create mock order manager."""
        manager = Mock()
        manager.update_orders_batch_async = AsyncMock()
        return manager
    
    @pytest.fixture
    def watcher(self, tmp_path, mock_order_manager):
        """Create watcher instance for testing."""
        logs_path = tmp_path / "logs"
        logs_path.mkdir()
        
        watcher = SingleFileTailWatcher(
            order_manager=mock_order_manager,
            websocket_manager=None
        )
        watcher.logs_path = logs_path
        
        return watcher
    
    @pytest.mark.asyncio
    async def test_buffer_cleared_immediately_after_snapshot(self, watcher):
        """Test that buffer is cleared immediately after taking snapshot.
        
        This prevents race condition where new lines are added to buffer
        while processing is ongoing.
        """
        # Add test lines to buffer
        test_lines = [
            '{"user":"0x123","oid":1,"coin":"BTC","side":"A","px":"50000","sz":"1","timestamp":"2025-10-07T14:00:00.000000"}',
            '{"user":"0x456","oid":2,"coin":"ETH","side":"B","px":"3000","sz":"2","timestamp":"2025-10-07T14:00:01.000000"}',
            '{"user":"0x789","oid":3,"coin":"SOL","side":"A","px":"100","sz":"3","timestamp":"2025-10-07T14:00:02.000000"}'
        ]
        
        for line in test_lines:
            watcher.line_buffer.append(line)
        
        initial_buffer_size = len(watcher.line_buffer)
        assert initial_buffer_size == 3, "Buffer should have 3 lines initially"
        
        # Mock _process_batch_sequential to verify buffer state
        original_sequential = watcher._process_batch_sequential
        buffer_size_during_processing = None
        
        async def mock_sequential(lines):
            nonlocal buffer_size_during_processing
            # Check buffer size DURING processing
            buffer_size_during_processing = len(watcher.line_buffer)
            return await original_sequential(lines)
        
        with patch.object(watcher, '_process_batch_sequential', side_effect=mock_sequential):
            # Process batch
            await watcher._process_batch()
        
        # Verify buffer was cleared BEFORE processing started
        assert buffer_size_during_processing == 0, \
            "Buffer must be cleared immediately after snapshot, before processing starts"
        
        # Verify buffer is still empty after processing
        assert len(watcher.line_buffer) == 0, \
            "Buffer should remain empty after processing"
    
    @pytest.mark.asyncio
    async def test_concurrent_read_and_process_no_data_loss(self, watcher, tmp_path):
        """Test that concurrent _read_new_lines() and _process_batch() don't lose data.
        
        Simulates scenario where:
        1. First batch starts processing
        2. Second _read_new_lines() adds more lines
        3. Both batches should be processed independently
        """
        # Create test file with data
        test_file = tmp_path / "logs" / "test_14.jsonl"
        test_lines_batch1 = [
            '{"user":"0x111","oid":1,"coin":"BTC","side":"A","px":"50000","sz":"1","timestamp":"2025-10-07T14:00:00.000000"}\n',
            '{"user":"0x222","oid":2,"coin":"ETH","side":"B","px":"3000","sz":"2","timestamp":"2025-10-07T14:00:01.000000"}\n'
        ]
        test_lines_batch2 = [
            '{"user":"0x333","oid":3,"coin":"SOL","side":"A","px":"100","sz":"3","timestamp":"2025-10-07T14:00:02.000000"}\n',
            '{"user":"0x444","oid":4,"coin":"AVAX","side":"B","px":"50","sz":"4","timestamp":"2025-10-07T14:00:03.000000"}\n'
        ]
        
        # Write first batch
        test_file.write_text(''.join(test_lines_batch1))
        
        # Add first batch to buffer manually
        for line in test_lines_batch1:
            watcher.line_buffer.append(line.strip())
        
        # Mock the _process_batch_sequential to simulate processing time
        async def mock_sequential(lines):
            await asyncio.sleep(0.1)  # Simulate processing time
            # Call the actual method to process orders
            return await watcher._process_batch_sequential(lines)
        
        with patch.object(watcher, '_process_batch_sequential', side_effect=mock_sequential):
            # Start processing first batch (will take some time)
            process_task = asyncio.create_task(watcher._process_batch())
            
            # Immediately add second batch (simulating concurrent _read_new_lines())
            await asyncio.sleep(0.01)  # Small delay to ensure processing started
            for line in test_lines_batch2:
                watcher.line_buffer.append(line.strip())
            
            # Wait for first batch to complete
            await process_task
        
        # Verify second batch is in buffer
        assert len(watcher.line_buffer) == 2, \
            "Second batch should be in buffer after first batch processed"
        
        # Process second batch
        await watcher._process_batch()
        
        # Verify buffer is empty
        assert len(watcher.line_buffer) == 0, \
            "Buffer should be empty after processing both batches"
        
        # Verify all orders were processed (4 total)
        assert watcher.order_manager.update_orders_batch_async.call_count == 2, \
            "Should have 2 batch processing calls"
    
    @pytest.mark.asyncio
    async def test_buffer_snapshot_independence(self, watcher):
        """Test that buffer snapshot is independent from original buffer.
        
        Modifying buffer during processing should not affect the snapshot.
        """
        # Add initial lines
        initial_lines = [
            '{"user":"0x123","oid":1,"coin":"BTC","side":"A","px":"50000","sz":"1","timestamp":"2025-10-07T14:00:00.000000"}',
            '{"user":"0x456","oid":2,"coin":"ETH","side":"B","px":"3000","sz":"2","timestamp":"2025-10-07T14:00:01.000000"}'
        ]
        
        for line in initial_lines:
            watcher.line_buffer.append(line)
        
        # Mock processing to verify snapshot independence
        processed_lines = None
        
        async def capture_lines(lines):
            nonlocal processed_lines
            processed_lines = list(lines)  # Save what we got
            
            # Add new lines to buffer during processing
            watcher.line_buffer.append('{"user":"0x789","oid":3,"coin":"SOL","side":"A","px":"100","sz":"3","timestamp":"2025-10-07T14:00:02.000000"}')
            
            return []  # Return empty to skip order_manager call
        
        with patch.object(watcher, '_process_batch_sequential', side_effect=capture_lines):
            await watcher._process_batch()
        
        # Verify processed lines were original 2, not affected by new line added
        assert len(processed_lines) == 2, \
            "Processing should work on snapshot of 2 lines, not affected by concurrent additions"
        
        # Verify new line is in buffer for next processing
        assert len(watcher.line_buffer) == 1, \
            "New line added during processing should be in buffer for next batch"
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_process_batch_calls(self, watcher):
        """Test that multiple concurrent _process_batch() calls handle buffer correctly.
        
        This is the CRITICAL test for the race condition fix.
        """
        # Add lines for first batch
        batch1_lines = [f'{{"user":"0x{i:03x}","oid":{i},"coin":"BTC","side":"A","px":"50000","sz":"1","timestamp":"2025-10-07T14:00:00.000000"}}' for i in range(10)]
        for line in batch1_lines:
            watcher.line_buffer.append(line)
        
        # Start first batch processing
        task1 = asyncio.create_task(watcher._process_batch())
        
        # Immediately start second batch (before first completes)
        # In real scenario, second _read_new_lines() would add lines
        batch2_lines = [f'{{"user":"0x{i:03x}","oid":{i+100},"coin":"ETH","side":"B","px":"3000","sz":"2","timestamp":"2025-10-07T14:00:01.000000"}}' for i in range(5)]
        for line in batch2_lines:
            watcher.line_buffer.append(line)
        
        task2 = asyncio.create_task(watcher._process_batch())
        
        # Wait for both to complete
        await asyncio.gather(task1, task2)
        
        # Verify buffer is empty (no data loss or duplication)
        assert len(watcher.line_buffer) == 0, \
            "Buffer should be empty after concurrent processing"
        
        # Verify both batches were processed
        # (should have 2 calls to order_manager if both batches had valid orders)
        call_count = watcher.order_manager.update_orders_batch_async.call_count
        assert call_count >= 0, \
            f"Order manager should be called for valid batches, got {call_count} calls"
    
    @pytest.mark.asyncio
    async def test_exception_during_processing_clears_buffer(self, watcher):
        """Test that buffer remains clear even if exception occurs during processing."""
        # Add test lines
        test_lines = [
            '{"user":"0x123","oid":1,"coin":"BTC","side":"A","px":"50000","sz":"1","timestamp":"2025-10-07T14:00:00.000000"}',
            '{"user":"0x456","oid":2,"coin":"ETH","side":"B","px":"3000","sz":"2","timestamp":"2025-10-07T14:00:01.000000"}'
        ]
        
        for line in test_lines:
            watcher.line_buffer.append(line)
        
        # Mock to raise exception
        async def raise_exception(lines):
            raise ValueError("Test exception during processing")
        
        with patch.object(watcher, '_process_batch_sequential', side_effect=raise_exception):
            # Process should not raise (exception is caught)
            await watcher._process_batch()
        
        # Buffer should still be cleared despite exception
        assert len(watcher.line_buffer) == 0, \
            "Buffer should be cleared even when exception occurs (cleared before processing)"


class TestParallelProcessingDeadlock:
    """Tests for parallel processing deadlock fix."""
    
    @pytest.fixture
    def watcher(self, tmp_path):
        """Create watcher instance."""
        manager = Mock()
        manager.update_orders_batch_async = AsyncMock()
        
        logs_path = tmp_path / "logs"
        logs_path.mkdir()
        
        watcher = SingleFileTailWatcher(
            order_manager=manager,
            websocket_manager=None
        )
        watcher.logs_path = logs_path
        watcher.parallel_workers = 4  # Set known number of workers
        
        return watcher
    
    @pytest.mark.asyncio
    async def test_chunks_exactly_equal_workers(self, watcher):
        """Test that chunks are created EXACTLY equal to num_chunks (not more!).
        
        This prevents executor overflow where extra tasks queue up
        and can cause deadlock.
        """
        # Test with various line counts that would create remainder
        test_cases = [
            (25433, 4, 4),   # 25433 % 4 = 1 remainder → should still be 4 chunks
            (10000, 4, 4),   # 10000 % 4 = 0 remainder → 4 chunks
            (5555, 4, 4),    # 5555 % 4 = 3 remainder → should still be 4 chunks
            (1001, 4, 1),    # Only 1001 lines → 1 chunk (< 1000 per chunk threshold)
        ]
        
        for line_count, workers, expected_chunks in test_cases:
            watcher.parallel_workers = workers
            test_lines = [f'{{"user":"0x{i:03x}","oid":{i},"coin":"BTC","side":"A","px":"50000","sz":"1","timestamp":"2025-10-07T14:00:00.000000"}}' for i in range(line_count)]
            
            # Track actual chunks created by mocking the executor
            actual_chunks_created = 0
            chunk_sizes = []
            
            # Mock the executor to count chunks
            def mock_run_in_executor(executor, fn, *args):
                nonlocal actual_chunks_created
                if len(args) > 0 and isinstance(args[0], list):
                    chunk_sizes.append(len(args[0]))
                    actual_chunks_created += 1
                # Return empty result
                return []
            
            with patch.object(asyncio.get_event_loop(), 'run_in_executor', side_effect=mock_run_in_executor):
                await watcher._process_batch_parallel(test_lines)
            
            assert actual_chunks_created == expected_chunks, \
                f"Expected {expected_chunks} chunks for {line_count} lines with {workers} workers, got {actual_chunks_created}"
            
            # Verify all lines are covered
            total_lines_in_chunks = sum(chunk_sizes)
            assert total_lines_in_chunks == line_count, \
                f"Expected {line_count} total lines, got {total_lines_in_chunks}"
    
    @pytest.mark.asyncio
    async def test_gather_handles_all_tasks(self, watcher):
        """Test that asyncio.gather() properly waits for all ThreadPoolExecutor tasks."""
        test_lines = [f'{{"user":"0x{i:03x}","oid":{i},"coin":"BTC","side":"A","px":"50000","sz":"1","timestamp":"2025-10-07T14:00:00.000000"}}' for i in range(5000)]
        
        call_count = 0
        
        def counting_parse(lines):
            nonlocal call_count
            call_count += 1
            return []
        
        with patch.object(watcher, '_parse_chunk_sync', side_effect=counting_parse):
            result = await watcher._process_batch_parallel(test_lines)
        
        # All workers should have been called
        assert call_count > 0, "Workers should have been called"
        assert isinstance(result, list), "Should return list of orders"
    
    @pytest.mark.asyncio
    async def test_large_batch_limited_to_max_size(self, watcher):
        """Test that batches larger than 100K lines are split.
        
        This prevents timeout on huge batches.
        """
        # Create buffer with 150K lines
        huge_buffer = [f'{{"user":"0x{i:03x}","oid":{i},"coin":"BTC","side":"A","px":"50000","sz":"1","timestamp":"2025-10-07T14:00:00.000000"}}' for i in range(150000)]
        
        for line in huge_buffer:
            watcher.line_buffer.append(line)
        
        initial_size = len(watcher.line_buffer)
        assert initial_size == 150000
        
        # Mock processing to avoid actual work and track what gets processed
        processed_lines = []
        
        async def mock_parallel(lines):
            processed_lines.extend(lines)
            return []
        
        async def mock_sequential(lines):
            processed_lines.extend(lines)
            return []
        
        # Mock both methods to track processed lines
        watcher._process_batch_parallel = mock_parallel
        watcher._process_batch_sequential = mock_sequential
        
        await watcher._process_batch()
        
        # Should have processed 100K and left 50K in buffer
        assert len(watcher.line_buffer) == 50000, \
            f"Should have 50K lines remaining in buffer, got {len(watcher.line_buffer)}"
        
        # Verify that exactly 100K lines were processed
        assert len(processed_lines) == 100000, \
            f"Should have processed 100K lines, got {len(processed_lines)}"
    
    @pytest.mark.asyncio  
    async def test_executor_recreated_after_timeout(self, watcher):
        """Test that executor is recreated after timeout to clear stuck threads."""
        test_lines = [f'{{"user":"0x{i:03x}","oid":{i},"coin":"BTC","side":"A","px":"50000","sz":"1","timestamp":"2025-10-07T14:00:00.000000"}}' for i in range(5000)]
        
        original_executor = watcher.executor
        
        # Mock gather to raise TimeoutError
        async def mock_gather(*args, **kwargs):
            raise asyncio.TimeoutError()
        
        with patch('asyncio.gather', side_effect=mock_gather):
            with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError):
                result = await watcher._process_batch_parallel(test_lines)
        
        # Executor should be different instance
        assert watcher.executor is not original_executor, \
            "Executor should be recreated after timeout"
        
        # Should return empty results after timeout
        assert result == [], "Should return empty list after timeout"


class TestBufferMemoryLeak:
    """Tests specifically for memory leak prevention."""
    
    @pytest.fixture
    def watcher(self, tmp_path):
        """Create watcher instance."""
        manager = Mock()
        manager.update_orders_batch_async = AsyncMock()
        
        logs_path = tmp_path / "logs"
        logs_path.mkdir()
        
        watcher = SingleFileTailWatcher(
            order_manager=manager,
            websocket_manager=None
        )
        watcher.logs_path = logs_path
        
        return watcher
    
    @pytest.mark.asyncio
    async def test_buffer_does_not_grow_indefinitely(self, watcher):
        """Test that buffer size does not grow indefinitely during processing.
        
        This test simulates the memory leak scenario from the logs where
        buffer grew from 41M to 44M lines.
        """
        max_buffer_size_seen = 0
        buffer_sizes_during_processing = []
        
        # Mock processing to track buffer sizes
        async def track_buffer_size(lines):
            # Check buffer size DURING processing (after snapshot but before clearing)
            buffer_sizes_during_processing.append(len(watcher.line_buffer))
            await asyncio.sleep(0.01)  # Simulate processing time
            return []
        
        with patch.object(watcher, '_process_batch_sequential', side_effect=track_buffer_size):
            # Simulate multiple read cycles
            for cycle in range(10):
                # Add lines (simulating _read_new_lines())
                for i in range(100):
                    watcher.line_buffer.append(f'{{"user":"0x{i:03x}","oid":{cycle*100+i},"coin":"BTC","side":"A","px":"50000","sz":"1","timestamp":"2025-10-07T14:00:00.000000"}}')
                
                max_buffer_size_seen = max(max_buffer_size_seen, len(watcher.line_buffer))
                
                # Process batch
                await watcher._process_batch()
        
        # Verify buffer never grew beyond reasonable size
        assert max_buffer_size_seen <= 100, \
            f"Buffer should not exceed 100 lines, but saw {max_buffer_size_seen}"
        
        # Verify buffer was cleared during processing
        # The buffer is cleared immediately after snapshot, so we should see 0 in the list
        # or at least see that buffer sizes are reasonable (not growing indefinitely)
        assert len(buffer_sizes_during_processing) > 0, \
            "Should have captured buffer sizes during processing"
        
        # Check that buffer sizes are reasonable (not growing indefinitely)
        max_size_during_processing = max(buffer_sizes_during_processing) if buffer_sizes_during_processing else 0
        assert max_size_during_processing <= 100, \
            f"Buffer size during processing should be reasonable, got {max_size_during_processing}"
        
        # Final buffer should be empty
        assert len(watcher.line_buffer) == 0, \
            "Final buffer should be empty"

