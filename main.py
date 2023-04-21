from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
import api, database, models
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
async def router_and_pairs_sync_task():
    while True:
        print("TODO: sync router & pairs here...")
        await asyncio.sleep(60)  # Wait for 60 seconds

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(router_and_pairs_sync_task())
