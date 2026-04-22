import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
import pymongo

logger = logging.getLogger(__name__)

MONGO_URL = os.getenv("MONGO_URL", "mongodb://admin:adminpassword@localhost:27017")
DB_NAME = "ecobarter_db"
COLLECTION_NAME = "products"

class Database:
    client: AsyncIOMotorClient = None
    db = None
    collection = None

db = Database()

async def connect_to_mongo():
    logger.info("Connecting to MongoDB...")
    db.client = AsyncIOMotorClient(MONGO_URL)
    db.db = db.client[DB_NAME]
    db.collection = db.db[COLLECTION_NAME]
    
    # Ensure Geospatial Index on the location field
    try:
        await db.collection.create_index([("location", pymongo.GEOSPHERE)])
        logger.info("Created 2dsphere index on 'location' field.")
    except Exception as e:
        logger.error(f"Error creating geospatial index: {e}")
        
    logger.info("Connected to MongoDB.")

async def close_mongo_connection():
    if db.client is not None:
        logger.info("Closing MongoDB connection...")
        db.client.close()
        logger.info("MongoDB connection closed.")
