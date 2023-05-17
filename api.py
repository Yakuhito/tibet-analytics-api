from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import desc, func, BigInteger
from cachetools import cached, TTLCache
from sqlalchemy.orm import Session
from typing import List, Optional
import models, database
import os

app = APIRouter()
cache = TTLCache(maxsize=100, ttl=10)

# Dependency for getting DB session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@cached(cache)
@app.get("/router")
async def get_router(db: Session = Depends(get_db)):
    router = db.query(models.Router).first()
    return router


def pair_to_json(pair: models.Pair):
    return {
        "launcher_id": pair.launcher_id,
        "name": pair.name,
        "short_name": pair.short_name,
        "image_url": pair.image_url,
        "asset_id": pair.asset_id,
        "current_coin_id": pair.current_coin_id,
        "xch_reserve": int(pair.xch_reserve),
        "token_reserve": int(pair.token_reserve),
        "liquidity": int(pair.liquidity),
        "trade_volume": int(pair.trade_volume)
    }


@cached(cache)
@app.get("/pairs")
async def get_pairs(db: Session = Depends(get_db)):
    return await _get_pairs(db)

async def _get_pairs(db: Session, wrap=True):
    pairs = (
        db.query(models.Pair)
        .order_by(models.Pair.xch_reserve.desc())
        .all()
    )
    return [pair_to_json(pair) for pair in pairs] if wrap else pairs


@cached(cache)
@app.get("/pair/{pair_launcher_id}")
async def get_pair(pair_launcher_id: str, db: Session = Depends(get_db)):
    pair = db.query(models.Pair).filter(models.Pair.launcher_id == pair_launcher_id).first()
    if pair is None:
        raise HTTPException(status_code=404, detail="Pair not found")
    return pair_to_json(pair)


@cached(cache)
@app.get("/transactions")
async def get_transactions(
    pair_launcher_id: Optional[str] = None,
    operation: Optional[str] = None,
    before_height: Optional[int] = None,
    after_height: Optional[int] = None,
    limit: int = 42,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    if limit > 420:
        raise HTTPException(status_code=400, detail="Limit cannot exceed 420")

    # Perform an outer join between the Transaction and HeightToTimestamp tables
    query = db.query(
        models.Transaction, 
        models.HeightToTimestamp.timestamp.label('timestamp')
    ).outerjoin(
        models.HeightToTimestamp,
        models.Transaction.height == models.HeightToTimestamp.height
    )

    if pair_launcher_id:
        query = query.filter(models.Transaction.pair_launcher_id == pair_launcher_id)

    if operation:
        query = query.filter(models.Transaction.operation == operation)

    if before_height:
        query = query.filter(models.Transaction.height < before_height)

    if after_height:
        query = query.filter(models.Transaction.height > after_height)

    transactions = (
        query.order_by(desc(models.Transaction.height))
        .limit(limit)
        .offset(offset)
        .all()
    )

    # Convert the result into a list of dictionaries
    transactions = [
        {
            **t[0].__dict__, 
            'timestamp': t[1] or 0
        } 
        for t in transactions
    ]

    # # Remove the '_sa_instance_state' key which is added by SQLAlchemy
    # for transaction in transactions:
    #     transaction.pop('_sa_instance_state', None)

    return transactions


@cached(cache)
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
