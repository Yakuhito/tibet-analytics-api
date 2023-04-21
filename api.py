from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
import models, database
import os

app = APIRouter()

# Dependency for getting DB session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/router")
async def get_router(db: Session = Depends(get_db)):
    router = db.query(models.Router).first()
    if not router:
        router = models.Router(
            launcher_id=os.environ.get("TIBET_LAUNCHER_ID"),
            current_coin_id=os.environ.get("TIBET_CURRENT_COIN_ID"),
            current_height=int(os.environ.get("TIBET_CURRENT_HEIGHT")),
            network=os.environ.get("TIBET_NETWORK"),
        )
        db.add(router)
        db.commit()
        db.refresh(router)
    return router

@app.get("/pairs")
async def get_pairs(db: Session = Depends(get_db)):
    pairs = db.query(models.Pair).all()
    return pairs

@app.get("/transactions")
async def get_transactions(pair_launcher_id: str, limit: int = 10, offset: int = 0, db: Session = Depends(get_db)):
    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.pair_launcher_id == pair_launcher_id)
        .order_by(desc(models.Transaction.height))
        .limit(limit)
        .offset(offset)
        .all()
    )
    return transactions
