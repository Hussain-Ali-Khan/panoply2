from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

from models import Base  # ✅ Import Base from models.py

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:Hussain30@localhost/hexa_bot")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ✅ Create tables if not already present
Base.metadata.create_all(bind=engine)
