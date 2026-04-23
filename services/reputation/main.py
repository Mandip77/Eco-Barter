from fastapi import FastAPI, HTTPException, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timezone
import os
import jwt as pyjwt
from fastapi import Header, Depends
from pydantic import BaseModel as PydanticModel

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="EcoBarter Reputation Service")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

DB_URL = os.getenv("DB_URL", "postgresql://ecouser:ecopassword@postgres:5432/ecobarter_db")
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

ECO_KG_PER_TRADE = 5.0  # estimated kg CO₂ saved per completed trade

class TradeProposal(Base):
    __tablename__ = "trade_proposals"
    id = Column(Integer, primary_key=True, index=True)
    status = Column(String)
    user_a = Column(String)
    user_b = Column(String)
    user_c = Column(String)
    user_d = Column(String)
    verified_a = Column(Boolean, default=False)
    verified_b = Column(Boolean, default=False)
    verified_c = Column(Boolean, default=False)
    verified_d = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    trade_id = Column(Integer, index=True)
    reviewer_id = Column(String, index=True)
    reviewee_id = Column(String, index=True)
    score = Column(Integer)  # 1–5
    comment = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ReviewCreate(PydanticModel):
    trade_id: int
    reviewee_id: str
    score: int  # 1–5
    comment: str = ""


Base.metadata.create_all(bind=engine)


def _get_rank(score: float) -> str:
    if score >= 50:
        return "Eco-Champion"
    if score >= 20:
        return "Trusted"
    return "Novice"


def calculate_eigentrust():
    """
    Compute EigenTrust global trust scores from completed trades.
    Applies a time-based decay: trust halves every 90 days without a new trade.
    Returns a dict {user_id: score} with scores scaled to [0, 100].
    """
    db = SessionLocal()
    trades = db.query(TradeProposal).filter(TradeProposal.status == "completed").all()

    # Track latest trade timestamp per user for decay
    last_trade: dict[str, datetime] = {}
    trust_graph: dict[str, dict[str, float]] = {}

    for t in trades:
        users = [u for u in [t.user_a, t.user_b, t.user_c, t.user_d] if u]
        ts = t.updated_at or t.created_at
        if ts and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        for u in users:
            if u not in trust_graph:
                trust_graph[u] = {}
            if ts and (u not in last_trade or ts > last_trade[u]):
                last_trade[u] = ts
            for v in users:
                if u != v:
                    trust_graph[u][v] = trust_graph[u].get(v, 0) + 1

    db.close()
    nodes = list(trust_graph.keys())
    if not nodes:
        return {}

    # Normalize rows of trust matrix
    C: dict[str, dict[str, float]] = {u: {} for u in nodes}
    for u in nodes:
        total = sum(trust_graph[u].values())
        if total > 0:
            for v in trust_graph[u]:
                C[u][v] = trust_graph[u][v] / total
        else:
            for v in nodes:
                C[u][v] = 1.0 / len(nodes)

    # Power iteration (10 steps)
    T: dict[str, float] = {u: 1.0 / len(nodes) for u in nodes}
    for _ in range(10):
        new_T: dict[str, float] = {u: 0.0 for u in nodes}
        for j in nodes:
            for i in nodes:
                new_T[j] += C[i].get(j, 0.0) * T[i]
        T = new_T

    # Apply time-decay: trust halves every 90 days of inactivity
    now = datetime.now(timezone.utc)
    decay_half_life_days = 90.0
    for u in T:
        if u in last_trade:
            days_idle = (now - last_trade[u]).days
            if days_idle > 0:
                decay = 0.5 ** (days_idle / decay_half_life_days)
                T[u] *= decay

    # Scale to [0, 100]
    return {u: round(T[u] * 100, 2) for u in T}


def _eco_impact(user_id: str) -> float:
    """Returns estimated kg CO₂ saved based on completed trade count."""
    db = SessionLocal()
    count = db.query(TradeProposal).filter(
        TradeProposal.status == "completed",
        (
            (TradeProposal.user_a == user_id) |
            (TradeProposal.user_b == user_id) |
            (TradeProposal.user_c == user_id) |
            (TradeProposal.user_d == user_id)
        )
    ).count()
    db.close()
    return round(count * ECO_KG_PER_TRADE, 1)


def get_current_user_id(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split("Bearer ")[1]
    try:
        payload = pyjwt.decode(
            token,
            os.getenv("JWT_SECRET", "super_secret_dev_key_do_not_use_in_prod"),
            algorithms=["HS256"],
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user_id
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@app.get("/api/v1/reputation/global")
@limiter.limit("30/minute")
def get_global_reputation(request: Request):
    return {"scores": calculate_eigentrust()}


@app.get("/api/v1/reputation/leaderboard")
@limiter.limit("30/minute")
def get_leaderboard(request: Request, limit: int = 10):
    """Returns top users sorted by EigenTrust score descending."""
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    scores = calculate_eigentrust()
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    return {
        "leaderboard": [
            {
                "rank": idx + 1,
                "user_id": uid,
                "eigentrust_score": score,
                "tier": _get_rank(score),
                "eco_impact_kg": _eco_impact(uid),
            }
            for idx, (uid, score) in enumerate(ranked)
        ]
    }


@app.get("/api/v1/reputation/{user_id}")
@limiter.limit("60/minute")
def get_user_reputation(request: Request, user_id: str):
    scores = calculate_eigentrust()
    score = scores.get(user_id, 10.0)
    return {
        "user_id": user_id,
        "eigentrust_score": score,
        "rank": _get_rank(score),
        "eco_impact_kg": _eco_impact(user_id),
    }


@app.post("/api/v1/reputation/reviews", status_code=201)
@limiter.limit("10/minute")
def submit_review(
    request: Request,
    body: ReviewCreate,
    reviewer_id: str = Depends(get_current_user_id),
):
    if not 1 <= body.score <= 5:
        raise HTTPException(status_code=422, detail="Score must be between 1 and 5")
    if reviewer_id == body.reviewee_id:
        raise HTTPException(status_code=400, detail="Cannot review yourself")
    db = SessionLocal()
    review = Review(
        trade_id=body.trade_id,
        reviewer_id=reviewer_id,
        reviewee_id=body.reviewee_id,
        score=body.score,
        comment=body.comment[:500] if body.comment else "",
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    db.close()
    return {"id": review.id, "message": "Review submitted"}


@app.get("/api/v1/reputation/reviews/{user_id}")
@limiter.limit("60/minute")
def get_user_reviews(request: Request, user_id: str):
    db = SessionLocal()
    reviews = db.query(Review).filter(Review.reviewee_id == user_id).order_by(Review.created_at.desc()).limit(20).all()
    db.close()
    return {
        "reviews": [
            {
                "id": r.id,
                "trade_id": r.trade_id,
                "reviewer_id": r.reviewer_id,
                "score": r.score,
                "comment": r.comment,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ]
    }
