from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
import os

app = FastAPI(title="EcoBarter Reputation Service")

DB_URL = os.getenv("DB_URL", "postgresql://ecouser:ecopassword@postgres:5432/ecobarter_db")
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TradeProposal(Base):
    __tablename__ = "trade_proposals"
    id = Column(Integer, primary_key=True, index=True)
    status = Column(String)
    user_a = Column(String)
    user_b = Column(String)
    user_c = Column(String)
    verified_a = Column(Boolean, default=False)
    verified_b = Column(Boolean, default=False)
    verified_c = Column(Boolean, default=False)

def calculate_eigentrust():
    db = SessionLocal()
    # Fetch all completed trades
    trades = db.query(TradeProposal).filter(TradeProposal.status == "completed").all()
    db.close()

    # Build local trust matrix C
    # C[i][j] = number of times i successfully traded with j
    # In k=3: A trusts B, B trusts C, C trusts A. Also everyone in the loop trusts everyone.
    # To keep it simple: within a completed trade, all 3 nodes mutualize trust +1 to each other.
    trust_graph = {}
    for t in trades:
        users = [t.user_a, t.user_b, t.user_c]
        for u in users:
            if u not in trust_graph:
                trust_graph[u] = {}
            for v in users:
                if u != v:
                    trust_graph[u][v] = trust_graph[u].get(v, 0) + 1

    # Normalize matrix C
    nodes = list(trust_graph.keys())
    if not nodes:
        return {}
        
    C = {u: {} for u in nodes}
    for u in nodes:
        total_trust = sum(trust_graph[u].values())
        if total_trust > 0:
            for v in trust_graph[u]:
                C[u][v] = trust_graph[u][v] / total_trust
        else:
            for v in nodes:
                C[u][v] = 1.0 / len(nodes) # pre-trust fallback

    # Initialize Global Trust Vector T
    # Start uniform
    T = {u: 1.0 / len(nodes) for u in nodes}

    # Iterate (Simplified Power Iteration)
    for _ in range(10):
        new_T = {u: 0.0 for u in nodes}
        for j in nodes:
            for i in nodes:
                # T[j] = sum(C[i][j] * T[i])
                new_T[j] += C[i].get(j, 0.0) * T[i]
        T = new_T

    # Scale values up for UI visibility (e.g. 0 to 100)
    for u in T:
        T[u] = round(T[u] * 100, 2)
        
    return T

@app.get("/api/v1/reputation/{user_id}")
def get_user_reputation(user_id: str):
    scores = calculate_eigentrust()
    score = scores.get(user_id, 0.0)
    # If not in graph, default to a base 10.0 score
    if score == 0.0:
        score = 10.0
    return {"user_id": user_id, "eigentrust_score": score, "rank": "Novice" if score < 20 else "Trusted"}

@app.get("/api/v1/reputation/global")
def get_global_reputation():
    return {"scores": calculate_eigentrust()}
