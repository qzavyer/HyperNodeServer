#!/usr/bin/env python3
"""Debug script to test FileWatcher functionality."""

import asyncio
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.watcher.file_watcher import FileWatcher
from src.storage.order_manager import OrderManager
from src.storage.file_storage import FileStorage
from src.storage.config_manager import ConfigManager
from src.notifications.order_notifier import OrderNotifier
from src.websocket.websocket_manager import WebSocketManager
from config.settings import settings

async def debug_filewatcher():
    """Debug FileWatcher step by step."""
    print(f"🔍 Debugging FileWatcher")
    print(f"📁 Logs path: {settings.NODE_LOGS_PATH}")
    
    # Check if logs directory exists
    logs_path = Path(settings.NODE_LOGS_PATH).expanduser()
    print(f"📁 Expanded logs path: {logs_path}")
    print(f"📁 Directory exists: {logs_path.exists()}")
    
    if logs_path.exists():
        print(f"📁 Directory contents: {list(logs_path.iterdir())}")
        
        # Check hourly subdirectory
        hourly_path = logs_path / "node_order_statuses" / "hourly"
        print(f"📁 Hourly path: {hourly_path}")
        print(f"📁 Hourly exists: {hourly_path.exists()}")
        
        if hourly_path.exists():
            json_files = list(hourly_path.rglob("*.json"))
            print(f"📄 JSON files found: {len(json_files)}")
            for f in json_files[:5]:  # Show first 5
                print(f"  - {f} (size: {f.stat().st_size} bytes)")
    
    # Initialize components
    file_storage = FileStorage()
    config_manager = ConfigManager()
    websocket_manager = WebSocketManager()
    order_notifier = OrderNotifier(websocket_manager, config_manager)
    order_manager = OrderManager(file_storage, config_manager, order_notifier)
    
    print(f"✅ Components initialized")
    
    # Create FileWatcher
    file_watcher = FileWatcher(order_manager)
    print(f"✅ FileWatcher created")
    
    try:
        # Test start
        print(f"🚀 Starting FileWatcher...")
        await file_watcher.start_async()
        print(f"✅ FileWatcher started")
        
        # Wait and check status
        print(f"⏳ Waiting 10 seconds...")
        await asyncio.sleep(10)
        
        status = file_watcher.get_processing_status()
        print(f"📊 Processing status: {status}")
        
        # Check if background processor is working
        print(f"⏳ Waiting 30 more seconds for background processing...")
        await asyncio.sleep(30)
        
        status = file_watcher.get_processing_status()
        print(f"📊 Final processing status: {status}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        try:
            await file_watcher.stop_async()
            print(f"✅ FileWatcher stopped")
        except Exception as e:
            print(f"❌ Error stopping: {e}")

if __name__ == "__main__":
    asyncio.run(debug_filewatcher())
