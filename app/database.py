from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger("uvicorn.error")

engine = None
db_url = settings.DATABASE_URL

if db_url.startswith("sqlite"):
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
else:
    # Check if PostgreSQL is reachable via socket first to prevent psycopg2 from hanging
    postgres_available = False
    try:
        parsed = urlparse(db_url)
        host = parsed.hostname or "127.0.0.1"
        if host == "localhost":
            host = "127.0.0.1"
        port = parsed.port or 5432
        # Quick socket check with 1 second timeout
        with socket.create_connection((host, port), timeout=1.0):
            postgres_available = True
    except Exception as e:
        logger.warning(f"PostgreSQL socket check failed on {host}:{port}: {e}")

    if postgres_available:
        try:
            # Test PostgreSQL connection
            engine = create_engine(db_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
            with engine.connect() as conn:
                pass
            logger.info("Successfully connected to PostgreSQL database.")
        except Exception as e:
            logger.warning(f"PostgreSQL connection test failed: {e}. Falling back to SQLite.")
            postgres_available = False
    
    if not postgres_available:
        logger.warning("Falling back to SQLite (sqlite:///./local_dev.db)")
        engine = create_engine("sqlite:///./local_dev.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """
    Dependency generator to yield database sessions to route handlers,
    ensuring they are properly closed after request execution.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
