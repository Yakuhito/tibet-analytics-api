from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import desc, func, BigInteger
from sqlalchemy.orm import Session
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
    return router

@app.get("/pairs")
async def get_pairs(db: Session = Depends(get_db)):
    pairs = db.query(models.Pair).all()
    return pairs

@app.get("/transactions")
async def get_transactions(pair_launcher_id: str, limit: int = 42, offset: int = 0, db: Session = Depends(get_db)):
    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.pair_launcher_id == pair_launcher_id)
        .order_by(desc(models.Transaction.height))
        .limit(limit)
        .offset(offset)
        .all()
    )
    return transactions

@app.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    # Number of transactions
    transaction_count = db.query(func.count(models.Transaction.coin_id)).scalar()

    # Total value locked (two times the sum of all Pairs' xch_reserve)
    total_value_locked = (
        db.query(func.sum(models.Pair.xch_reserve)).scalar() or 0
    ) * 2

    # Total trade volume (sum of all Pairs' trade_volume, converted from string to int)
    total_trade_volume = (
        db.query(func.sum(func.cast(models.Pair.trade_volume, BigInteger))).scalar() or 0
    )

    return {
        "transaction_count": transaction_count,
        "total_value_locked": total_value_locked,
        "total_trade_volume": total_trade_volume,
    }

@app.get("/")
async def root():
    return {"message": "TibetSwap Analytics API is running"}