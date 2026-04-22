from fastapi import FastAPI, HTTPException, Header, Depends, Query
from contextlib import asynccontextmanager
from typing import List, Optional
from datetime import datetime, timezone
from bson import ObjectId

from database import connect_to_mongo, close_mongo_connection, db as mongodb
from messaging import connect_to_nats, close_nats_connection, publish_preference_update
from models import ProductCreate, Product

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    await connect_to_nats()
    yield
    # Shutdown
    await close_nats_connection()
    await close_mongo_connection()

app = FastAPI(title="EcoBarter Catalog Service", lifespan=lifespan)

# Helper to require user identity from Gateway
import jwt
import os

async def get_current_user_id(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    
    token = authorization.split("Bearer ")[1]
    try:
        payload = jwt.decode(token, os.getenv("JWT_SECRET", "super_secret_dev_key_do_not_use_in_prod"), algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user_id
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

@app.get("/")
async def root():
    return {"status": "ok", "service": "catalog"}

@app.post("/api/v1/catalog/products", response_model=Product, status_code=201)
async def create_product(
    product_in: ProductCreate, 
    user_id: str = Depends(get_current_user_id)
):
    now = datetime.now(timezone.utc)
    
    product_dict = product_in.model_dump()
    product_dict["owner_id"] = user_id
    product_dict["created_at"] = now
    product_dict["updated_at"] = now
    
    # Save to MongoDB
    result = await mongodb.collection.insert_one(product_dict)
    
    # Retrieve the inserted doc to return and publish
    inserted_product = await mongodb.collection.find_one({"_id": result.inserted_id})
    inserted_product["_id"] = str(inserted_product["_id"])
    
    # Publish to NATS JetStream
    try:
        await publish_preference_update(inserted_product)
    except Exception as e:
        logger.error(f"Failed to publish to NATS: {e}")
        # Note: In an event-driven system, we might want an Outbox pattern here for reliable messaging
        
    return inserted_product

@app.get("/api/v1/catalog/products", response_model=List[Product])
async def list_products(
    lat: Optional[float] = Query(None, description="Latitude for Geospatial Search"),
    lon: Optional[float] = Query(None, description="Longitude for Geospatial Search"),
    max_distance: Optional[float] = Query(50000, description="Max distance in meters (default 50km)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    query = {}
    
    # Category Filter
    if category:
        query["category"] = category
        
    # Geospatial Filter
    if lat is not None and lon is not None:
        query["location"] = {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "$maxDistance": max_distance
            }
        }

    cursor = mongodb.collection.find(query).skip(skip).limit(limit)
    
    products = []
    async for document in cursor:
        document["_id"] = str(document["_id"])
        products.append(document)
        
    return products

@app.get("/api/v1/catalog/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid Product ID")
        
    document = await mongodb.collection.find_one({"_id": ObjectId(product_id)})
    if not document:
        raise HTTPException(status_code=404, detail="Product not found")
        
    document["_id"] = str(document["_id"])
    return document

@app.put("/api/v1/catalog/products/{product_id}", response_model=Product)
async def update_product(
    product_id: str,
    product_in: ProductCreate,
    user_id: str = Depends(get_current_user_id)
):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid Product ID")
        
    existing = await mongodb.collection.find_one({"_id": ObjectId(product_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")
        
    if existing.get("owner_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to edit this product")

    update_data = product_in.model_dump()
    update_data["updated_at"] = datetime.now(timezone.utc)
    update_data["created_at"] = existing.get("created_at")
    update_data["owner_id"] = existing.get("owner_id")

    await mongodb.collection.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": update_data}
    )
    
    updated_doc = await mongodb.collection.find_one({"_id": ObjectId(product_id)})
    updated_doc["_id"] = str(updated_doc["_id"])
    
    try:
        await publish_preference_update(updated_doc)
    except Exception as e:
        logger.error(f"Failed to publish to NATS: {e}")
        
    return updated_doc

@app.delete("/api/v1/catalog/products/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    user_id: str = Depends(get_current_user_id)
):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid Product ID")
        
    existing = await mongodb.collection.find_one({"_id": ObjectId(product_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")
        
    if existing.get("owner_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this product")
        
    await mongodb.collection.delete_one({"_id": ObjectId(product_id)})
    return None
