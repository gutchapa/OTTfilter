import asyncio
import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv('.env')

async def test():
    mongo_url = os.environ.get('MONGO_URL')
    db_name = os.environ.get('DB_NAME', 'ottfilter')
    
    print(f"Connecting to: {mongo_url.split('@')[1] if '@' in mongo_url else 'invalid URL'}")
    print(f"Database: {db_name}")
    
    try:
        client = AsyncIOMotorClient(mongo_url)
        await client.admin.command('ping')
        print("✅ MongoDB connected!")
        
        db = client[db_name]
        collections = await db.list_collection_names()
        print(f"Collections: {collections}")
        
        # Check if movies collection has data
        if 'movies' in collections:
            count = await db.movies.count_documents({})
            print(f"Movies in database: {count}")
        else:
            print("⚠️  No 'movies' collection found - database is empty")
            print("This is normal for a new deployment")
            
    except Exception as e:
        print(f"❌ Error: {e}")

asyncio.run(test())
