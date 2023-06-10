from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from dotenv import load_dotenv

import api, database, models, sync
import asyncio
import time
import os

if os.environ.get("TIBET_NETWORK") is None:
    load_dotenv()

app = FastAPI(title="TibetSwap Analytics API", description="Analytics for TibetSwap v2", version="1.0.0")
stop_event = asyncio.Event()

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

shared_sess: Session = database.SessionLocal()
def check_if_height_exists(height: int) -> bool:
    return shared_sess.query(models.HeightToTimestamp).filter(models.HeightToTimestamp.height == height).first() is not None

# sync task
async def router_and_pairs_sync_task():
    sync.ensure_client()

    db: Session = database.SessionLocal()
    while True:
        current_router = await api.get_router(db)
        new_router, new_pairs = await sync.sync_router(current_router)
        if new_router is not None:
            db.commit()
            db.refresh(new_router)
        
        for new_pair in new_pairs:
            db.add(new_pair)
            db.commit()

        all_current_pairs = await api._get_pairs(db, wrap=False)
        for current_pair in all_current_pairs:
            new_pair, new_transactions, new_heights = await sync.sync_pair(current_pair)
            if new_pair is not None:
                db.commit()
                db.refresh(new_pair)
            
            for new_tx in new_transactions:
                db.add(new_tx)
                db.commit()

            for new_height in new_heights:
                if not check_if_height_exists(new_height.height):
                    db.add(new_height)
                    db.commit()

        await asyncio.sleep(60)  # Wait for 1 minute

async def router_and_pairs_sync_task_retry():
    while not stop_event.is_set():
        try:
            await router_and_pairs_sync_task()
        except:
            for i in range(120):
                if stop_event.is_set(): 
                    break
                time.sleep(0.5)


def handle_task_result(task):
    if task.exception():
        os._exit(1)


@app.on_event("startup")
async def startup_event():
    task = asyncio.create_task(router_and_pairs_sync_task_retry())
    task.add_done_callback(handle_task_result)


@app.on_event("shutdown")
async def shutdown_event():
    stop_event.set()
