#!/usr/bin/env python3
"""Run script for HyperLiquid Node Parser."""

import uvicorn
from config.settings import settings

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.API_HOST,
         port=settings.API_PORT,
        reload=True
    )


