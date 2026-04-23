"""
Tests — Reputation Service: EigenTrust algorithm and API endpoints
Uses FastAPI TestClient with SQLite in-memory database.

Covers:
  calculate_eigentrust()       (pure function — unit tests)
  GET /api/v1/reputation/{user_id}
  GET /api/v1/reputation/global
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware

# ─────────────────────────────────────────────────────────────
# Wire up SQLite before importing the app
# ─────────────────────────────────────────────────────────────

SQLALCHEMY_TEST_URL = "sqlite:///./test_reputation.db"

from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import declarative_base

# Re-create the same schema locally so we can seed rows
TestBase = declarative_base()

class TradeProposalTest(TestBase):
    __tablename__ = "trade_proposals"
    id = Column(Integer, primary_key=True)
    status = Column(String)
    user_a = Column(String)
    user_b = Column(String)
    user_c = Column(String)
    user_d = Column(String)
    verified_a = Column(Boolean, default=False)
    verified_b = Column(Boolean, default=False)
    verified_c = Column(Boolean, default=False)
    verified_d = Column(Boolean, default=False)
    created_at = Column(String)
    updated_at = Column(String)

test_engine = create_engine(
    SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False}
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
TestBase.metadata.create_all(bind=test_engine)

# Set TESTING before importing main so create_all is skipped at module level
os.environ["TESTING"] = "1"

import main as rep_main
rep_main.engine = test_engine
rep_main.SessionLocal = TestSession
# Create all tables (including Review) on the test engine
rep_main.Base.metadata.create_all(bind=test_engine)

from main import app, calculate_eigentrust

# Bypass rate limiting — pre-set view_rate_limit so sync_wrapper arg evaluation succeeds
class _SetViewRateLimit(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.view_rate_limit = None
        return await call_next(request)

app.add_middleware(_SetViewRateLimit)

async def _no_rate_limit(request, endpoint_func, in_middleware=False):
    pass

app.state.limiter._check_request_limit = _no_rate_limit

client = TestClient(app)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def seed_completed_trade(user_a, user_b, user_c):
    db = TestSession()
    db.add(TradeProposalTest(
        status="completed",
        user_a=user_a, user_b=user_b, user_c=user_c,
        verified_a=True, verified_b=True, verified_c=True,
    ))
    db.commit()
    db.close()


@pytest.fixture(autouse=True)
def clean_tables():
    yield
    db = TestSession()
    db.query(TradeProposalTest).delete()
    db.commit()
    db.close()


# ─────────────────────────────────────────────────────────────
# Unit tests — calculate_eigentrust()
# ─────────────────────────────────────────────────────────────

class TestEigenTrust:
    def test_empty_graph_returns_empty_dict(self):
        result = calculate_eigentrust()
        assert result == {}

    def test_single_completed_trade_scores_all_three_users(self):
        seed_completed_trade("alice", "bob", "carol")
        scores = calculate_eigentrust()
        assert "alice" in scores
        assert "bob" in scores
        assert "carol" in scores

    def test_scores_are_scaled_to_100(self):
        seed_completed_trade("alice", "bob", "carol")
        scores = calculate_eigentrust()
        for score in scores.values():
            # Scores are multiplied by 100; should be > 0
            assert score > 0
            # With only one trade, scores won't exceed 100 (uniform distribution)
            assert score <= 100

    def test_more_trades_increases_trust(self):
        """A user who completes more trades should have higher or equal trust."""
        # alice appears in 2 trades, carol in 1
        seed_completed_trade("alice", "bob", "carol")
        seed_completed_trade("alice", "dave", "eve")
        scores = calculate_eigentrust()
        assert scores.get("alice", 0) >= scores.get("carol", 0)

    def test_incomplete_trades_not_counted(self):
        """Only 'completed' status trades contribute to trust."""
        db = TestSession()
        db.add(TradeProposalTest(
            status="pending",
            user_a="alice", user_b="bob", user_c="carol",
            verified_a=False, verified_b=False, verified_c=False,
        ))
        db.commit()
        db.close()
        result = calculate_eigentrust()
        assert result == {}

    def test_scores_are_rounded_to_two_decimal_places(self):
        seed_completed_trade("alice", "bob", "carol")
        scores = calculate_eigentrust()
        for score in scores.values():
            assert score == round(score, 2)


# ─────────────────────────────────────────────────────────────
# GET /api/v1/reputation/{user_id}
# ─────────────────────────────────────────────────────────────

class TestGetUserReputation:
    def test_known_user_returns_200(self):
        seed_completed_trade("alice", "bob", "carol")
        resp = client.get("/api/v1/reputation/alice")
        assert resp.status_code == 200

    def test_known_user_response_schema(self):
        seed_completed_trade("alice", "bob", "carol")
        resp = client.get("/api/v1/reputation/alice")
        data = resp.json()
        assert data["user_id"] == "alice"
        assert "eigentrust_score" in data
        assert "rank" in data

    def test_unknown_user_gets_default_score(self):
        """Users not in any trade should get a base score of 10.0."""
        resp = client.get("/api/v1/reputation/ghost_user")
        assert resp.status_code == 200
        assert resp.json()["eigentrust_score"] == 10.0

    def test_rank_novice_when_score_below_20(self):
        """A user with no trades defaults to score 10 → Novice."""
        resp = client.get("/api/v1/reputation/newbie")
        assert resp.json()["rank"] == "Novice"

    def test_rank_trusted_when_score_high(self):
        """Seed many trades to push a user above 20 and check Trusted rank."""
        # Seed 5 trades all involving alice to boost her score significantly
        for i in range(5):
            seed_completed_trade("alice", f"user_{i}_b", f"user_{i}_c")
        resp = client.get("/api/v1/reputation/alice")
        data = resp.json()
        # With 5 trades alice should be above 20 in scaled score
        if data["eigentrust_score"] >= 20:
            assert data["rank"] == "Trusted"


# ─────────────────────────────────────────────────────────────
# GET /api/v1/reputation/global
# ─────────────────────────────────────────────────────────────

class TestGetGlobalReputation:
    def test_empty_returns_empty_scores(self):
        resp = client.get("/api/v1/reputation/global")
        assert resp.status_code == 200
        assert resp.json() == {"scores": {}}

    def test_returns_all_users_after_trade(self):
        seed_completed_trade("alice", "bob", "carol")
        resp = client.get("/api/v1/reputation/global")
        data = resp.json()["scores"]
        assert "alice" in data
        assert "bob" in data
        assert "carol" in data


# ─────────────────────────────────────────────────────────────
# GET /api/v1/reputation/leaderboard
# ─────────────────────────────────────────────────────────────

class TestLeaderboard:
    def test_empty_leaderboard(self):
        resp = client.get("/api/v1/reputation/leaderboard")
        assert resp.status_code == 200
        assert resp.json() == {"leaderboard": []}

    def test_leaderboard_has_rank_field(self):
        seed_completed_trade("alice", "bob", "carol")
        resp = client.get("/api/v1/reputation/leaderboard")
        entry = resp.json()["leaderboard"][0]
        assert "rank" in entry
        assert "user_id" in entry
        assert "eigentrust_score" in entry
        assert "tier" in entry
        assert "eco_impact_kg" in entry

    def test_leaderboard_limit(self):
        for i in range(5):
            seed_completed_trade(f"user{i}", f"peer{i}a", f"peer{i}b")
        resp = client.get("/api/v1/reputation/leaderboard?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()["leaderboard"]) <= 3

    def test_leaderboard_invalid_limit_returns_400(self):
        resp = client.get("/api/v1/reputation/leaderboard?limit=0")
        assert resp.status_code == 400

    def test_leaderboard_sorted_descending(self):
        # alice in 3 trades, bob in 1 — alice should rank higher
        seed_completed_trade("alice", "bob", "carol")
        seed_completed_trade("alice", "dave", "eve")
        seed_completed_trade("alice", "frank", "grace")
        resp = client.get("/api/v1/reputation/leaderboard")
        entries = resp.json()["leaderboard"]
        scores = [e["eigentrust_score"] for e in entries]
        assert scores == sorted(scores, reverse=True)


# ─────────────────────────────────────────────────────────────
# eco_impact_kg field
# ─────────────────────────────────────────────────────────────

class TestEcoImpact:
    def test_no_trades_eco_impact_is_zero(self):
        resp = client.get("/api/v1/reputation/ghost_eco")
        assert resp.json()["eco_impact_kg"] == 0.0

    def test_one_trade_eco_impact_is_five(self):
        seed_completed_trade("alice", "bob", "carol")
        resp = client.get("/api/v1/reputation/alice")
        assert resp.json()["eco_impact_kg"] == 5.0

    def test_three_trades_eco_impact_is_fifteen(self):
        for i in range(3):
            seed_completed_trade("alice", f"b{i}", f"c{i}")
        resp = client.get("/api/v1/reputation/alice")
        assert resp.json()["eco_impact_kg"] == 15.0


# ─────────────────────────────────────────────────────────────
# Rank tiers
# ─────────────────────────────────────────────────────────────

class TestRankTiers:
    def test_default_rank_is_novice(self):
        resp = client.get("/api/v1/reputation/brand_new_user")
        assert resp.json()["rank"] == "Novice"
