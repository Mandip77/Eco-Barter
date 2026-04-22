import base64
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional

import jwt
from bson import ObjectId
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, UploadFile, File
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from database import close_mongo_connection, connect_to_mongo
from database import db as mongodb
from messaging import close_nats_connection, connect_to_nats, publish_preference_update
from models import Product, ProductCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 1 * 1024 * 1024  # 1 MB
ALLOWED_MIME_PREFIXES = ("image/jpeg", "image/png", "image/webp", "image/gif")

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    await connect_to_nats()
    yield
    await close_nats_connection()
    await close_mongo_connection()


app = FastAPI(title="EcoBarter Catalog Service", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


async def get_current_user_id(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split("Bearer ")[1]
    try:
        payload = jwt.decode(
            token,
            os.getenv("JWT_SECRET", "super_secret_dev_key_do_not_use_in_prod"),
            algorithms=["HS256"],
        )
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
@limiter.limit("30/minute")
async def create_product(
    request: Request,
    product_in: ProductCreate,
    user_id: str = Depends(get_current_user_id),
):
    now = datetime.now(timezone.utc)
    product_dict = product_in.model_dump()
    product_dict["owner_id"] = user_id
    product_dict["created_at"] = now
    product_dict["updated_at"] = now

    result = await mongodb.collection.insert_one(product_dict)
    inserted = await mongodb.collection.find_one({"_id": result.inserted_id})
    inserted["_id"] = str(inserted["_id"])

    try:
        await publish_preference_update(inserted)
    except Exception as e:
        logger.error(f"Failed to publish to NATS: {e}")

    return inserted


@app.get("/api/v1/catalog/products", response_model=List[Product])
@limiter.limit("120/minute")
async def list_products(
    request: Request,
    lat: Optional[float] = Query(None, description="Latitude for Geospatial Search"),
    lon: Optional[float] = Query(None, description="Longitude for Geospatial Search"),
    max_distance: Optional[float] = Query(50000, description="Max distance in meters (default 50km)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    query: dict = {}
    if category:
        query["category"] = category
    if lat is not None and lon is not None:
        query["location"] = {
            "$near": {
                "$geometry": {"type": "Point", "coordinates": [lon, lat]},
                "$maxDistance": max_distance,
            }
        }

    cursor = mongodb.collection.find(query).skip(skip).limit(limit)
    products = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        products.append(doc)
    return products


@app.get("/api/v1/catalog/products/{product_id}", response_model=Product)
@limiter.limit("120/minute")
async def get_product(request: Request, product_id: str):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid Product ID")
    doc = await mongodb.collection.find_one({"_id": ObjectId(product_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    doc["_id"] = str(doc["_id"])
    return doc


@app.put("/api/v1/catalog/products/{product_id}", response_model=Product)
@limiter.limit("30/minute")
async def update_product(
    request: Request,
    product_id: str,
    product_in: ProductCreate,
    user_id: str = Depends(get_current_user_id),
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
    # Preserve existing image if present
    if existing.get("image_data"):
        update_data["image_data"] = existing["image_data"]

    await mongodb.collection.update_one({"_id": ObjectId(product_id)}, {"$set": update_data})
    updated = await mongodb.collection.find_one({"_id": ObjectId(product_id)})
    updated["_id"] = str(updated["_id"])

    try:
        await publish_preference_update(updated)
    except Exception as e:
        logger.error(f"Failed to publish to NATS: {e}")

    return updated


@app.delete("/api/v1/catalog/products/{product_id}", status_code=204)
@limiter.limit("20/minute")
async def delete_product(
    request: Request,
    product_id: str,
    user_id: str = Depends(get_current_user_id),
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


@app.post("/api/v1/catalog/products/{product_id}/image", response_model=Product)
@limiter.limit("10/minute")
async def upload_product_image(
    request: Request,
    product_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Upload a product image (JPEG/PNG/WebP/GIF, max 1 MB). Stored as base64 in MongoDB."""
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid Product ID")
    existing = await mongodb.collection.find_one({"_id": ObjectId(product_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="Product not found")
    if existing.get("owner_id") != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to upload image for this product")

    content_type = file.content_type or ""
    if not any(content_type.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(status_code=415, detail="Unsupported image type. Use JPEG, PNG, WebP, or GIF.")

    raw = await file.read()
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 1 MB limit")

    encoded = base64.b64encode(raw).decode("utf-8")
    image_data = f"data:{content_type};base64,{encoded}"

    await mongodb.collection.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": {"image_data": image_data, "updated_at": datetime.now(timezone.utc)}},
    )
    updated = await mongodb.collection.find_one({"_id": ObjectId(product_id)})
    updated["_id"] = str(updated["_id"])
    return updated


@app.get("/api/v1/catalog/products/{product_id}/image")
@limiter.limit("120/minute")
async def get_product_image(request: Request, product_id: str):
    """Returns image_data field (base64 data URI) for a product."""
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid Product ID")
    doc = await mongodb.collection.find_one({"_id": ObjectId(product_id)}, {"image_data": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")
    if not doc.get("image_data"):
        raise HTTPException(status_code=404, detail="No image uploaded for this product")
    return {"product_id": product_id, "image_data": doc["image_data"]}
