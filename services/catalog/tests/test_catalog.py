"""
Tests — Catalog Service: REST API endpoints
Uses FastAPI TestClient with mocked MongoDB and NATS so no live services are required.

Covers:
  POST /api/v1/catalog/products
  GET  /api/v1/catalog/products
  GET  /api/v1/catalog/products/{id}
  PUT  /api/v1/catalog/products/{id}
  DELETE /api/v1/catalog/products/{id}
  POST /api/v1/catalog/products/{id}/image
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET", "test_secret_key")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from datetime import datetime, timezone
from fastapi.testclient import TestClient
import jwt
import io

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

JWT_SECRET = "test_secret_key"
VALID_USER_ID = "user_abc123"

SAMPLE_OID = ObjectId("507f1f77bcf86cd799439011")
SAMPLE_ID = str(SAMPLE_OID)

NOW = datetime.now(timezone.utc)

SAMPLE_PRODUCT = {
    "_id": SAMPLE_OID,
    "title": "📷 Vintage Camera",
    "category": "Electronics",
    "description": "A classic film camera.",
    "emoji": "📷",
    "owner_id": VALID_USER_ID,
    "wants": {"preferences": {"query": "Books"}},
    "tags": ["Electronics"],
    "location": {"type": "Point", "coordinates": [-71.0589, 42.3601]},
    "created_at": NOW,
    "updated_at": NOW,
    "image_data": None,
}


def make_token(user_id: str = VALID_USER_ID) -> str:
    return jwt.encode(
        {"sub": user_id, "username": "testuser"},
        JWT_SECRET,
        algorithm="HS256",
    )


def serialised(doc: dict) -> dict:
    """Return a copy with ObjectId converted to str (as the API would)."""
    out = dict(doc)
    if "_id" in out and not isinstance(out["_id"], str):
        out["_id"] = str(out["_id"])
    return out


class AsyncCursor:
    """Minimal async iterator that wraps a list, supporting .skip().limit() chaining."""

    def __init__(self, items):
        self._items = list(items)

    def skip(self, n: int):
        self._items = self._items[n:]
        return self

    def limit(self, n: int):
        self._items = self._items[:n]
        return self

    def __aiter__(self):
        self._iter = iter(self._items)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


# ─────────────────────────────────────────────────────────────
# Client fixture — patches all I/O before importing main
# ─────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_col():
    """Returns a configured AsyncMock collection and an active TestClient."""
    col = AsyncMock()
    return col


@pytest.fixture()
def client(mock_col):
    with (
        patch("database.connect_to_mongo", new_callable=AsyncMock),
        patch("database.close_mongo_connection", new_callable=AsyncMock),
        patch("messaging.connect_to_nats", new_callable=AsyncMock),
        patch("messaging.close_nats_connection", new_callable=AsyncMock),
        patch("messaging.publish_preference_update", new_callable=AsyncMock),
        patch("database.db") as mock_db,
    ):
        mock_db.collection = mock_col
        from main import app
        with TestClient(app) as c:
            yield c, mock_col


# ─────────────────────────────────────────────────────────────
# POST /api/v1/catalog/products
# ─────────────────────────────────────────────────────────────

class TestCreateProduct:
    def test_create_requires_auth(self, client):
        c, _ = client
        resp = c.post("/api/v1/catalog/products", json={})
        assert resp.status_code == 401

    def test_create_returns_201(self, client):
        c, col = client
        insert_result = MagicMock()
        insert_result.inserted_id = SAMPLE_OID
        col.insert_one = AsyncMock(return_value=insert_result)
        col.find_one = AsyncMock(return_value=dict(SAMPLE_PRODUCT))

        payload = {
            "title": "Vintage Camera",
            "category": "Electronics",
            "description": "Nice",
            "emoji": "📷",
            "wants": {"preferences": {"query": "Books"}},
            "tags": ["Electronics"],
            "location": {"type": "Point", "coordinates": [-71.0, 42.0]},
        }
        resp = c.post(
            "/api/v1/catalog/products",
            json=payload,
            headers={"Authorization": f"Bearer {make_token()}"},
        )
        assert resp.status_code == 201

    def test_create_sets_owner_id(self, client):
        c, col = client
        inserted = MagicMock()
        inserted.inserted_id = SAMPLE_OID
        col.insert_one = AsyncMock(return_value=inserted)
        col.find_one = AsyncMock(return_value=dict(SAMPLE_PRODUCT))

        resp = c.post(
            "/api/v1/catalog/products",
            json={
                "title": "Camera",
                "category": "Electronics",
                "wants": {"preferences": {}},
                "tags": [],
                "location": {"type": "Point", "coordinates": [0.0, 0.0]},
            },
            headers={"Authorization": f"Bearer {make_token()}"},
        )
        call_args = col.insert_one.call_args[0][0]
        assert call_args["owner_id"] == VALID_USER_ID

    def test_create_without_body_returns_422(self, client):
        c, _ = client
        resp = c.post(
            "/api/v1/catalog/products",
            json={"title": "Only title"},
            headers={"Authorization": f"Bearer {make_token()}"},
        )
        assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────
# GET /api/v1/catalog/products
# ─────────────────────────────────────────────────────────────

class TestListProducts:
    def test_list_returns_200_no_auth(self, client):
        c, col = client
        col.find = MagicMock(return_value=AsyncCursor([]))
        resp = c.get("/api/v1/catalog/products")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_products(self, client):
        c, col = client
        col.find = MagicMock(return_value=AsyncCursor([dict(SAMPLE_PRODUCT)]))
        resp = c.get("/api/v1/catalog/products")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["title"] == SAMPLE_PRODUCT["title"]

    def test_list_respects_limit(self, client):
        c, col = client
        products = [dict(SAMPLE_PRODUCT, _id=ObjectId()) for _ in range(5)]
        col.find = MagicMock(return_value=AsyncCursor(products))
        resp = c.get("/api/v1/catalog/products?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_list_invalid_limit_returns_422(self, client):
        c, _ = client
        resp = c.get("/api/v1/catalog/products?limit=999")
        assert resp.status_code == 422


# ─────────────────────────────────────────────────────────────
# GET /api/v1/catalog/products/{id}
# ─────────────────────────────────────────────────────────────

class TestGetProduct:
    def test_get_existing_product(self, client):
        c, col = client
        col.find_one = AsyncMock(return_value=dict(SAMPLE_PRODUCT))
        resp = c.get(f"/api/v1/catalog/products/{SAMPLE_ID}")
        assert resp.status_code == 200
        assert resp.json()["title"] == SAMPLE_PRODUCT["title"]

    def test_get_nonexistent_returns_404(self, client):
        c, col = client
        col.find_one = AsyncMock(return_value=None)
        resp = c.get(f"/api/v1/catalog/products/{SAMPLE_ID}")
        assert resp.status_code == 404

    def test_get_invalid_id_returns_400(self, client):
        c, _ = client
        resp = c.get("/api/v1/catalog/products/not-a-valid-oid")
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────
# PUT /api/v1/catalog/products/{id}
# ─────────────────────────────────────────────────────────────

class TestUpdateProduct:
    def test_update_requires_auth(self, client):
        c, _ = client
        resp = c.put(f"/api/v1/catalog/products/{SAMPLE_ID}", json={})
        assert resp.status_code == 401

    def test_update_by_owner_succeeds(self, client):
        c, col = client
        updated = dict(SAMPLE_PRODUCT, title="Updated Camera")
        col.find_one = AsyncMock(side_effect=[dict(SAMPLE_PRODUCT), updated])
        col.update_one = AsyncMock()

        payload = {
            "title": "Updated Camera",
            "category": "Electronics",
            "wants": {"preferences": {}},
            "tags": [],
            "location": {"type": "Point", "coordinates": [0.0, 0.0]},
        }
        resp = c.put(
            f"/api/v1/catalog/products/{SAMPLE_ID}",
            json=payload,
            headers={"Authorization": f"Bearer {make_token()}"},
        )
        assert resp.status_code == 200

    def test_update_by_non_owner_returns_403(self, client):
        c, col = client
        product_owned_by_other = dict(SAMPLE_PRODUCT, owner_id="other_user")
        col.find_one = AsyncMock(return_value=product_owned_by_other)

        payload = {
            "title": "Hijack",
            "category": "Electronics",
            "wants": {"preferences": {}},
            "tags": [],
            "location": {"type": "Point", "coordinates": [0.0, 0.0]},
        }
        resp = c.put(
            f"/api/v1/catalog/products/{SAMPLE_ID}",
            json=payload,
            headers={"Authorization": f"Bearer {make_token()}"},
        )
        assert resp.status_code == 403

    def test_update_nonexistent_returns_404(self, client):
        c, col = client
        col.find_one = AsyncMock(return_value=None)
        payload = {
            "title": "Ghost",
            "category": "Electronics",
            "wants": {"preferences": {}},
            "tags": [],
            "location": {"type": "Point", "coordinates": [0.0, 0.0]},
        }
        resp = c.put(
            f"/api/v1/catalog/products/{SAMPLE_ID}",
            json=payload,
            headers={"Authorization": f"Bearer {make_token()}"},
        )
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────
# DELETE /api/v1/catalog/products/{id}
# ─────────────────────────────────────────────────────────────

class TestDeleteProduct:
    def test_delete_requires_auth(self, client):
        c, _ = client
        resp = c.delete(f"/api/v1/catalog/products/{SAMPLE_ID}")
        assert resp.status_code == 401

    def test_delete_by_owner_returns_204(self, client):
        c, col = client
        col.find_one = AsyncMock(return_value=dict(SAMPLE_PRODUCT))
        col.delete_one = AsyncMock()
        resp = c.delete(
            f"/api/v1/catalog/products/{SAMPLE_ID}",
            headers={"Authorization": f"Bearer {make_token()}"},
        )
        assert resp.status_code == 204

    def test_delete_by_non_owner_returns_403(self, client):
        c, col = client
        col.find_one = AsyncMock(return_value=dict(SAMPLE_PRODUCT, owner_id="other"))
        resp = c.delete(
            f"/api/v1/catalog/products/{SAMPLE_ID}",
            headers={"Authorization": f"Bearer {make_token()}"},
        )
        assert resp.status_code == 403

    def test_delete_nonexistent_returns_404(self, client):
        c, col = client
        col.find_one = AsyncMock(return_value=None)
        resp = c.delete(
            f"/api/v1/catalog/products/{SAMPLE_ID}",
            headers={"Authorization": f"Bearer {make_token()}"},
        )
        assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────
# POST /api/v1/catalog/products/{id}/image
# ─────────────────────────────────────────────────────────────

class TestImageUpload:
    def _png_bytes(self) -> bytes:
        # Minimal 1x1 white PNG
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00"
            b"\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18"
            b"\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    def test_upload_requires_auth(self, client):
        c, _ = client
        resp = c.post(
            f"/api/v1/catalog/products/{SAMPLE_ID}/image",
            files={"file": ("img.png", self._png_bytes(), "image/png")},
        )
        assert resp.status_code == 401

    def test_upload_valid_image_returns_200(self, client):
        c, col = client
        updated = dict(SAMPLE_PRODUCT, image_data="data:image/png;base64,abc123")
        col.find_one = AsyncMock(side_effect=[dict(SAMPLE_PRODUCT), updated])
        col.update_one = AsyncMock()

        resp = c.post(
            f"/api/v1/catalog/products/{SAMPLE_ID}/image",
            files={"file": ("img.png", self._png_bytes(), "image/png")},
            headers={"Authorization": f"Bearer {make_token()}"},
        )
        assert resp.status_code == 200

    def test_upload_non_owner_returns_403(self, client):
        c, col = client
        col.find_one = AsyncMock(return_value=dict(SAMPLE_PRODUCT, owner_id="other"))
        resp = c.post(
            f"/api/v1/catalog/products/{SAMPLE_ID}/image",
            files={"file": ("img.png", self._png_bytes(), "image/png")},
            headers={"Authorization": f"Bearer {make_token()}"},
        )
        assert resp.status_code == 403

    def test_upload_unsupported_type_returns_415(self, client):
        c, col = client
        col.find_one = AsyncMock(return_value=dict(SAMPLE_PRODUCT))
        resp = c.post(
            f"/api/v1/catalog/products/{SAMPLE_ID}/image",
            files={"file": ("doc.pdf", b"%PDF-1.4 ...", "application/pdf")},
            headers={"Authorization": f"Bearer {make_token()}"},
        )
        assert resp.status_code == 415

    def test_upload_oversized_image_returns_413(self, client):
        c, col = client
        col.find_one = AsyncMock(return_value=dict(SAMPLE_PRODUCT))
        big_image = b"\x00" * (1024 * 1024 + 1)  # just over 1 MB
        resp = c.post(
            f"/api/v1/catalog/products/{SAMPLE_ID}/image",
            files={"file": ("big.png", big_image, "image/png")},
            headers={"Authorization": f"Bearer {make_token()}"},
        )
        assert resp.status_code == 413


# ─────────────────────────────────────────────────────────────
# Auth edge cases
# ─────────────────────────────────────────────────────────────

class TestAuthEdgeCases:
    def test_invalid_token_returns_401(self, client):
        c, _ = client
        resp = c.post(
            "/api/v1/catalog/products",
            json={},
            headers={"Authorization": "Bearer not.a.valid.jwt"},
        )
        assert resp.status_code == 401

    def test_missing_bearer_prefix_returns_401(self, client):
        c, _ = client
        resp = c.post(
            "/api/v1/catalog/products",
            json={},
            headers={"Authorization": "justtoken"},
        )
        assert resp.status_code == 401
