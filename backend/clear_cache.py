#!/usr/bin/env python3
"""
Clear movie cache to force re-fetch with updated OTT platform logic
Run this after updating OTT provider code to refresh all cached movies
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import get_settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def clear_movie_cache():
    """Clear all movies from cache"""
    settings = get_settings()

    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.DB_NAME]

    # Count movies before deletion
    count_before = await db.movies.count_documents({})
    logger.info(f"Found {count_before} movies in cache")

    # Delete all movies
    result = await db.movies.delete_many({})
    logger.info(f"Deleted {result.deleted_count} movies")

    # Verify deletion
    count_after = await db.movies.count_documents({})
    logger.info(f"Remaining movies: {count_after}")

    client.close()
    logger.info("Cache cleared successfully! Next /discover or /search request will re-fetch with OTT data")

if __name__ == "__main__":
    asyncio.run(clear_movie_cache())
