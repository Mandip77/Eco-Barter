from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class GeoLocation(BaseModel):
    type: str = "Point"
    coordinates: List[float] = Field(..., example=[-71.0589, 42.3601], description="[longitude, latitude]")

class WantList(BaseModel):
    preferences: Dict[str, Any] = Field(default_factory=dict)

class ProductBase(BaseModel):
    title: str = Field(..., max_length=150)
    description: Optional[str] = None
    category: str
    condition: str = "Good"
    emoji: str = Field(default="📦", max_length=10)
    wants: WantList = Field(default_factory=WantList)
    tags: List[str] = Field(default_factory=list)
    location: GeoLocation

class ProductCreate(ProductBase):
    pass

class Product(ProductBase):
    id: str = Field(alias="_id")
    owner_id: str
    created_at: datetime
    updated_at: datetime
    image_data: Optional[str] = None  # base64-encoded image, populated by image upload endpoint
    view_count: int = 0
    expires_at: Optional[datetime] = None

    class Config:
        populate_by_name = True
