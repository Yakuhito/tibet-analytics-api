from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os, models

DATABASE_URL = "sqlite:///./database.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, pool_size=20, max_overflow=30)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

router_launcher_id = os.environ.get("TIBET_V2_ROUTER_LAUNCHER_ID")
rcat_router_launcher_id = os.environ.get("TIBET_V2R_ROUTER_LAUNCHER_ID")

def init_db():
    session = SessionLocal()

    # Create database tables
    Base.metadata.create_all(bind=engine)

    # Normal router
    router_exists = session.query(models.Router).filter(models.Router.rcat == False).first()
    if not router_exists:
        router = models.Router(
            launcher_id=router_launcher_id,
            current_coin_id=router_launcher_id,
            rcat=False
        )
        session.add(router)
        session.commit()

    # rCAT router
    rcat_router_exists = session.query(models.Router).filter(models.Router.rcat == True).first()
    if not rcat_router_exists:
        rcat_router = models.Router(
            launcher_id=rcat_router_launcher_id,
            current_coin_id=rcat_router_launcher_id,
            rcat=True
        )
        session.add(rcat_router)
        session.commit()

    session.close()
