#!/usr/bin/env python3
"""WebSocket client example for testing order notifications."""

import asyncio
import websockets
import json
import sys
from datetime import datetime

async def websocket_client(uri: str, channel: str):
    """WebSocket client for testing notifications."""
    try:
        async with websockets.connect(uri) as websocket:
            print(f"🔌 Connected to {uri}")
            print(f"📡 Subscribed to channel: {channel}")
            print("=" * 60)
            
            # Отправляем приветственное сообщение
            await websocket.send("ping")
            
            # Слушаем сообщения
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    # Форматируем вывод
                    timestamp = data.get("timestamp", "N/A")
                    msg_type = data.get("type", "unknown")
                    
                    print(f"\n📨 [{timestamp}] {msg_type}")
                    
                    if msg_type == "orderUpdate":
                        order = data.get("data", {})
                        print(f"   Symbol: {order.get('symbol')}")
                        print(f"   Side: {order.get('side')}")
                        print(f"   Price: {order.get('price')}")
                        print(f"   Size: {order.get('size')}")
                        print(f"   Status: {order.get('status')}")
                        print(f"   Liquidity: {order.get('price', 0) * order.get('size', 0):.2f}")
                        
                    elif msg_type == "orderBatch":
                        orders_data = data.get("data", {})
                        count = orders_data.get("count", 0)
                        print(f"   Batch size: {count} orders")
                        
                        # Показываем первые 3 ордера
                        orders = orders_data.get("orders", [])[:3]
                        for i, order in enumerate(orders):
                            print(f"   Order {i+1}: {order.get('symbol')} {order.get('side')} @ {order.get('price')}")
                        
                        if count > 3:
                            print(f"   ... and {count - 3} more orders")
                            
                    elif msg_type == "connected":
                        print(f"   ✅ Successfully connected to {data.get('channel')} channel")
                        
                except json.JSONDecodeError:
                    print(f"📨 Raw message: {message}")
                    
    except websockets.exceptions.ConnectionClosed:
        print("❌ Connection closed")
    except Exception as e:
        print(f"❌ Error: {e}")

async def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python websocket_client.py <channel>")
        print("Channels: orderUpdate, orderBatch")
        print("Example: python websocket_client.py orderUpdate")
        sys.exit(1)
    
    channel = sys.argv[1]
    if channel not in ["orderUpdate", "orderBatch"]:
        print("❌ Invalid channel. Use 'orderUpdate' or 'orderBatch'")
        sys.exit(1)
    
    uri = f"ws://localhost:8000/ws/{channel}"
    
    print(f"🚀 Starting WebSocket client for {channel}")
    print(f"🔗 Connecting to: {uri}")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    try:
        await websocket_client(uri, channel)
    except KeyboardInterrupt:
        print("\n👋 Client stopped by user")
    except Exception as e:
        print(f"❌ Client error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
