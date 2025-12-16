# db_session.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Use environment variable or fallback to SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///leer_mexico.db")

# Create engine
engine = create_engine(DATABASE_URL, echo=False, future=True)

# Create session factory
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)