#!/usr/bin/env python3
"""Test WebSocket connection to HyperNodeServer."""

import asyncio
import json
import websockets
from datetime import datetime

async def test_websocket():
    """Connect to WebSocket and listen for order updates."""
    uri = "ws://localhost:8000/ws/orderUpdate"
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Connected to WebSocket!")
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for order updates...\n")
            
            order_count = 0
            
            while True:
                try:
                    message = await websocket.recv()
                    order_count += 1
                    
                    # Parse message
                    try:
                        data = json.loads(message)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Order #{order_count}:")
                        print(f"  ID: {data.get('id', 'N/A')}")
                        print(f"  Symbol: {data.get('coin', 'N/A')}")
                        print(f"  Side: {data.get('side', 'N/A')}")
                        print(f"  Price: {data.get('px', 'N/A')}")
                        print(f"  Size: {data.get('sz', 'N/A')}")
                        print(f"  Status: {data.get('status', 'N/A')}")
                        print()
                    except json.JSONDecodeError:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Received: {message[:100]}...")
                        print()
                        
                except websockets.exceptions.ConnectionClosed:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ❌ Connection closed")
                    break
                except KeyboardInterrupt:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Stopped by user")
                    break
                    
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Is HyperNodeServer running?")
        print("   docker-compose ps")
        print("2. Check if WebSocket endpoint is available:")
        print("   curl http://localhost:8000/api/v1/health")
        print("3. Check server logs:")
        print("   docker-compose logs -f app | grep WebSocket")

if __name__ == "__main__":
    print("="*60)
    print("WebSocket Client Test")
    print("="*60)
    print()
    
    try:
        asyncio.run(test_websocket())
    except KeyboardInterrupt:
        print("\n\nTest stopped by user")

