from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import get_settings
import ssl
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None

    async def connect_to_database(self):
        try:
            # Disable TLS for localhost connections
            is_local = 'localhost' in settings.MONGO_URL or '127.0.0.1' in settings.MONGO_URL
            if is_local:
                self.client = AsyncIOMotorClient(settings.MONGO_URL)
            else:
                self.client = AsyncIOMotorClient(settings.MONGO_URL, tls=True, tlsAllowInvalidCertificates=True, tlsAllowInvalidHostnames=True)
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
    # Ensure database connection is initialized
    if db.db is None:
        await db.connect_to_database()
    return db.db
