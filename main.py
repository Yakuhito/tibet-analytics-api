from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
import api, database, models

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
