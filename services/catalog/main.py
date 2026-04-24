import base64
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import jwt
from bson import ObjectId
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, UploadFile, File, Response as FastAPIResponse
from fastapi.middleware.cors import CORSMiddleware
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

_allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


async def get_current_user_id(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split("Bearer ")[1]
    try:
        payload = jwt.decode(
            token,
            os.getenv("JWT_SECRET"),
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
    product_dict["view_count"] = 0
    product_dict["expires_at"] = now + timedelta(days=30)

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
    now_utc = datetime.now(timezone.utc)
    query["$or"] = [
        {"expires_at": {"$exists": False}},
        {"expires_at": None},
        {"expires_at": {"$gt": now_utc}},
    ]

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
    await mongodb.collection.update_one({"_id": ObjectId(product_id)}, {"$inc": {"view_count": 1}})
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


@app.post("/api/v1/catalog/products/{product_id}/bump")
@limiter.limit("10/minute")
async def bump_product(
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
        raise HTTPException(status_code=403, detail="Not authorized")
    new_expiry = datetime.now(timezone.utc) + timedelta(days=30)
    await mongodb.collection.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": {"expires_at": new_expiry, "updated_at": datetime.now(timezone.utc)}}
    )
    return {"product_id": product_id, "expires_at": new_expiry.isoformat()}


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


@app.post("/api/v1/catalog/saves/{product_id}", status_code=201)
@limiter.limit("60/minute")
async def save_product(
    request: Request,
    product_id: str,
    user_id: str = Depends(get_current_user_id),
):
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid Product ID")
    await mongodb.saves.update_one(
        {"user_id": user_id, "product_id": product_id},
        {"$setOnInsert": {"user_id": user_id, "product_id": product_id, "saved_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    return {"product_id": product_id, "saved": True}


@app.delete("/api/v1/catalog/saves/{product_id}", status_code=204)
@limiter.limit("60/minute")
async def unsave_product(
    request: Request,
    product_id: str,
    user_id: str = Depends(get_current_user_id),
):
    await mongodb.saves.delete_one({"user_id": user_id, "product_id": product_id})
    return FastAPIResponse(status_code=204)


@app.get("/api/v1/catalog/saves")
@limiter.limit("60/minute")
async def list_saves(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    cursor = mongodb.saves.find({"user_id": user_id}, {"product_id": 1, "_id": 0})
    ids = [doc["product_id"] async for doc in cursor]
    return {"saved_ids": ids}


@app.post("/api/v1/catalog/products/{product_id}/suggest")
@limiter.limit("10/minute")
async def suggest_trade(
    request: Request,
    product_id: str,
    user_id: str = Depends(get_current_user_id),
):
    import httpx
    if not ObjectId.is_valid(product_id):
        raise HTTPException(status_code=400, detail="Invalid Product ID")
    target = await mongodb.collection.find_one({"_id": ObjectId(product_id)})
    if not target:
        raise HTTPException(status_code=404, detail="Product not found")

    cursor = mongodb.collection.find({"owner_id": user_id}).limit(10)
    my_listings = [doc async for doc in cursor]

    if not my_listings:
        return {"suggestion": "Add some listings first so I can suggest the best trade match!", "tips": []}

    target_wants = target.get("wants", {}).get("preferences", {}).get("query", "open to offers")
    my_items_text = "\n".join(
        f"- {l.get('title')} ({l.get('category', '')}): {str(l.get('description', ''))[:80]}"
        for l in my_listings
    )

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"suggestion": "AI suggestions are not configured on this server yet.", "tips": []}

    prompt = (
        f"You are a helpful trade advisor for EcoBarter, a sustainable goods exchange.\n\n"
        f"Target listing: \"{target.get('title')}\" — the owner wants: {target_wants}\n\n"
        f"My available listings:\n{my_items_text}\n\n"
        f"In 2–3 sentences, tell me which of MY listings would make the strongest trade offer for this item and why. "
        f"Be specific and practical. If none match, suggest what kind of item would seal the deal."
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 250,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        if resp.status_code == 200:
            return {"suggestion": resp.json()["content"][0]["text"]}
        return {"suggestion": "Could not generate a suggestion right now. Try again shortly."}
    except Exception:
        return {"suggestion": "AI suggestion service is temporarily unavailable."}
