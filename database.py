from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os, models

DATABASE_URL = "sqlite:///./database.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def init_db():
    session = SessionLocal()

    # Create database tables
    Base.metadata.create_all(bind=engine)

    # Check if a router object exists, and if not, create one
    router_exists = session.query(models.Router).first()
    if not router_exists:
        router = models.Router(
            launcher_id=os.environ.get("TIBET_LAUNCHER_ID"),
            current_coin_id=os.environ.get("TIBET_LAUNCHER_ID"),
            network=os.environ.get("TIBET_NETWORK")
        )
        session.add(router)
        session.commit()

    session.close()
