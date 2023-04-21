from fastapi import FastAPI
from . import api, database, models

app = FastAPI()

# Create database tables
database.Base.metadata.create_all(bind=database.engine)

# Include the API router
app.include_router(api.app)
