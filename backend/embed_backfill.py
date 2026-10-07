"""Embed every cached movie into `movie_embeddings`.

Usage (from backend/, venv active, EMBEDDINGS_ENABLED=true in .env):
    python embed_backfill.py            # embed new/changed movies
    python embed_backfill.py --drop     # remove all embeddings (rollback)
"""
import asyncio
import sys

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.services import embedding_service

BATCH = 64


async def main():
    setup_logging()
    settings = get_settings()
    db = AsyncIOMotorClient(settings.MONGO_URL)[settings.DB_NAME]

    if "--drop" in sys.argv:
        await db[embedding_service.COLLECTION].drop()
        print(f"Dropped {embedding_service.COLLECTION}")
        return

    total = await db.movies.count_documents({})
    done = 0
    cursor = db.movies.find({}, {"_id": 0})
    batch = []
    async for movie in cursor:
        batch.append(movie)
        if len(batch) == BATCH:
            await embedding_service.get_movie_vectors(db, batch)
            done += len(batch)
            print(f"{done}/{total}")
            batch = []
    if batch:
        await embedding_service.get_movie_vectors(db, batch)
        done += len(batch)
    print(f"Done: {done}/{total} movies checked")


if __name__ == "__main__":
    asyncio.run(main())
