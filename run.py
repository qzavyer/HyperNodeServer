#!/usr/bin/env python3
"""Run script for HyperLiquid Node Parser."""

# import uvicorn
# from config.settings import settings

# if __name__ == "__main__":
    # uvicorn.run(
    #    "src.main:app",
    #    host=settings.API_HOST,
    #     port=settings.API_PORT,
    #    reload=True
    #)


import asyncio
import websockets
import json

# Попробуем порт 4002 (или 4001)
WS_URL = "ws://127.0.0.1:4002"

async def main():
    async with websockets.connect(WS_URL) as ws:
        print("Connected to Hyperliquid WebSocket")

        subscribe_msg = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "subscribe",
            "params": ["OrderBookEvent"]  # уточни точное событие
        }

        await ws.send(json.dumps(subscribe_msg))
        print("Subscribed to OrderBookEvent")

        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            print(data)

asyncio.run(main())
