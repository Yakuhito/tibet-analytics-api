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

@app.get("/")
async def root():
    return {"message": "TibetSwap Analytics API is running"}