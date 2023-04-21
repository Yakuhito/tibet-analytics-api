from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
import api, database, models, sync
import asyncio

app = FastAPI(title="TibetSwap Analytics API", description="Analytics for TibetSwap v1", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
database.init_db()

# Include the API router
app.include_router(api.app)

# sync task
async def router_and_pairs_sync_task(db: Session = Depends(api.get_db)):
    while True:
        current_router = await api.get_router(db)
        new_router, new_pairs = await sync.sync_router(current_router)
        if new_router is not None:
            pass
            # todo: save new router, insert new pairs

        all_current_pairs = await api.get_pairs(db)
        for current_pair in all_current_pairs:
            new_pair, new_transactions = await sync.sync_pair(current_pair)
            if new_pair is not None:
                pass
                # todo: save new pair, insert new transactions

        await asyncio.sleep(60)  # Wait for 60 seconds

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(router_and_pairs_sync_task())
