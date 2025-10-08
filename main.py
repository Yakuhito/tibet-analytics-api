from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from dotenv import load_dotenv

import api, database, models, sync, usd_price_sync
import asyncio
import time
import os

if os.environ.get("COINSET_URL") is None:
    load_dotenv()

app = FastAPI(title="TibetSwap Analytics API", description="Analytics for TibetSwap v2 & v2r", version="2.0.0")
stop_event = asyncio.Event()

# Create database tables
database.init_db()

# Include the API router
app.include_router(api.app)

shared_sess: Session = database.SessionLocal()
def check_if_height_exists(height: int) -> bool:
    return shared_sess.query(models.HeightToTimestamp).filter(models.HeightToTimestamp.height == height).first() is not None

last_price_sync_time = 0

# sync task
async def router_and_pairs_sync_task():
    sync.ensure_client()

    db: Session = database.SessionLocal()
    while True:
        for rcat in [False, True]:
            current_router = await api.get_router(rcat, db)
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
                    # Add all new heights first (they have primary key constraints)
                    # Track which heights we've added in this batch to avoid duplicates
                    added_heights = set()
                    for new_height in new_heights:
                        if new_height.height not in added_heights and not check_if_height_exists(new_height.height):
                            db.add(new_height)
                            added_heights.add(new_height.height)
                    
                    # Add all transactions
                    for new_tx in new_transactions:
                        db.add(new_tx)
                    
                    # Update USD volumes for all transactions
                    for new_tx in new_transactions:
                        # Update USD volume if price is available
                        while True:
                            try:
                                usd_price_sync.update_transaction_usd_volume(db, new_tx)
                                break
                            except Exception as e:
                                print(f"Error updating USD volume for transaction: {e}")

                            time.sleep(30)
                    
                    # Commit everything together: pair updates, transactions, heights, and USD volumes
                    db.commit()
                    db.refresh(new_pair)
        
        global last_price_sync_time
        current_time = int(time.time())
        
        # Sync if: never synced before OR enough time has passed to sync a new hour
        max_synced = usd_price_sync.get_max_synced_timestamp(db)
        next_sync_time = max_synced + 3600 + 900  # Next hour + 15 min buffer
        
        if current_time >= next_sync_time and current_time - last_price_sync_time >= 300:
            print(f"{current_time} Starting USD price sync...")
            try:
                new_max_synced = usd_price_sync.sync_prices(db)
                if new_max_synced > 0:
                    last_price_sync_time = current_time
                    print(f"USD price sync completed; synced up to {new_max_synced}")
                else:
                    print("USD price sync failed, will retry in next cycle")
            except Exception as e:
                print(f"Error syncing USD prices: {e}")

        await asyncio.sleep(60)

async def router_and_pairs_sync_task_retry():
    while not stop_event.is_set():
        try:
            await router_and_pairs_sync_task()
        except Exception as e:
            print(e)
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
