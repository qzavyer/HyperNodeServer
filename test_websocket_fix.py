#!/usr/bin/env python3
"""Test script to verify WebSocket connection fix."""

import asyncio
import websockets
import json
from websockets.exceptions import ConnectionClosedError

async def test_websocket_connection():
    """Test WebSocket connections to both endpoints."""
    
    # Test URLs
    urls = [
        "ws://localhost:8000/ws/orderUpdate",
        "ws://localhost:8000/ws/orderBatch", 
        "ws://localhost:8000/ws/status"  # This should be HTTP, not WebSocket
    ]
    
    for url in urls[:2]:  # Only test WebSocket endpoints
        print(f"\n🔌 Testing connection to: {url}")
        try:
            async with websockets.connect(url) as websocket:
                print(f"✅ Successfully connected to {url}")
                
                # Send ping message
                await websocket.send("ping")
                print("📤 Sent: ping")
                
                # Wait for response
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    print(f"📥 Received: {response}")
                except asyncio.TimeoutError:
                    print("⏰ No response received within 5 seconds")
                
                # Send close message
                await websocket.close()
                print(f"🔒 Connection closed to {url}")
                
        except ConnectionClosedError as e:
            print(f"❌ Connection closed with error: {e}")
        except Exception as e:
            print(f"❌ Failed to connect to {url}: {e}")
    
    # Test HTTP status endpoint
    print(f"\n🌐 Testing HTTP endpoint: http://localhost:8000/ws/status")
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/ws/status") as response:
                data = await response.json()
                print(f"✅ HTTP Status endpoint: {response.status}")
                print(f"📊 Response: {json.dumps(data, indent=2)}")
    except Exception as e:
        print(f"❌ Failed to get status: {e}")

if __name__ == "__main__":
    print("🚀 Starting WebSocket connection test...")
    asyncio.run(test_websocket_connection())
    print("\n✨ Test completed!")
