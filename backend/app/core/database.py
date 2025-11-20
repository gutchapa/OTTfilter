from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import get_settings
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None

    async def connect_to_database(self):
        try:
            self.client = AsyncIOMotorClient(settings.MONGO_URL)
            self.db = self.client[settings.DB_NAME]
            logger.info("Connected to MongoDB")
        except Exception as e:
            logger.error(f"Could not connect to MongoDB: {e}")
            raise

    async def close_database_connection(self):
        if self.client:
            self.client.close()
            logger.info("Closed MongoDB connection")

db = Database()

async def get_database():
    return db.db
