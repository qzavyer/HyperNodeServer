# WebSocket Broadcasting Fix

## Problem

`SingleFileTailWatcher` was parsing orders from log files but **NOT sending them to WebSocket clients**.

### Symptoms
```
✅ Chunk processed: 167 lines -> 96 orders (failed: 0)
✅ Chunk processed: 167 lines -> 126 orders (failed: 0)
❌ No WebSocket broadcasts
```

## Root Cause

`SingleFileTailWatcher` was initialized **without** `websocket_manager`:

```python
# BEFORE (broken)
single_file_tail_watcher = SingleFileTailWatcher(order_manager)
#                                                 ^^^^^^^^^^^^ No websocket_manager!
```

Compare with `ReactiveOrderWatcher`:
```python
# ReactiveOrderWatcher (working)
reactive_order_watcher = ReactiveOrderWatcher(..., websocket_manager, ...)
#                                                   ^^^^^^^^^^^^^^^^^^ Has WebSocket!
```

## Solution

### 1. Updated `SingleFileTailWatcher` Constructor

```python
def __init__(self, order_manager: OrderManager, websocket_manager=None):
    """Initialize SingleFileTailWatcher.
    
    Args:
        order_manager: OrderManager instance
        websocket_manager: WebSocketManager for broadcasting orders
    """
    self.order_manager = order_manager
    self.websocket_manager = websocket_manager  # Added!
```

### 2. Added WebSocket Broadcasting

After chunk processing:
```python
# Diagnostic: log chunk processing results
if len(lines) > 0:
    logger.info(f"Chunk processed: {len(lines)} lines -> {len(orders)} orders (failed: {failed_lines})")

# Send orders to WebSocket if available
if orders and self.websocket_manager:
    try:
        asyncio.create_task(self._send_orders_to_websocket(orders))
    except Exception as e:
        logger.error(f"Failed to send orders to WebSocket: {e}")
```

### 3. New Method for Broadcasting

```python
async def _send_orders_to_websocket(self, orders: List) -> None:
    """Send parsed orders to WebSocket subscribers.
    
    Args:
        orders: List of parsed orders
    """
    try:
        if not self.websocket_manager:
            logger.warning("WebSocket manager not available")
            return
        
        # Send each order via WebSocket
        for order in orders:
            await self.websocket_manager.broadcast_order_update(order)
        
        logger.info(f"Sent {len(orders)} orders to WebSocket subscribers")
    except Exception as e:
        logger.error(f"Error sending orders to WebSocket: {e}")
```

### 4. Updated `main.py`

```python
# AFTER (fixed)
single_file_tail_watcher = SingleFileTailWatcher(order_manager, websocket_manager)
#                                                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

## Expected Logs After Fix

```
✅ Chunk processed: 167 lines -> 96 orders (failed: 0)
✅ Sent 96 orders to WebSocket subscribers
✅ Chunk processed: 167 lines -> 126 orders (failed: 0)  
✅ Sent 126 orders to WebSocket subscribers
```

## Testing

### 1. Restart Service

```bash
docker-compose restart app
```

### 2. Connect WebSocket Client

```bash
# Use websocket_client.py from scripts/
python scripts/websocket_client.py
```

### 3. Watch Logs

```bash
docker-compose logs -f app | grep -E "(Chunk processed|Sent.*orders)"
```

You should see:
- `Chunk processed` - orders parsed from files
- `Sent X orders to WebSocket subscribers` - orders broadcasted

## Files Changed

- `src/watcher/single_file_tail_watcher.py`
  - Updated `__init__` to accept `websocket_manager`
  - Added `_send_orders_to_websocket()` method
  - Added broadcasting after chunk processing

- `src/main.py`
  - Updated `SingleFileTailWatcher` initialization to pass `websocket_manager`

## Benefits

✅ **Real-time broadcasting** - Parsed orders immediately sent to WebSocket clients  
✅ **Consistent behavior** - Same as `ReactiveOrderWatcher`  
✅ **No data loss** - All parsed orders are broadcasted  
✅ **Better monitoring** - Logs confirm WebSocket sends  

---

**Fixed**: 2025-10-07  
**Version**: 1.0.0

