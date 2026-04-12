import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Load from monorepo root
load_dotenv(dotenv_path="../.env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql://diary_user:diary_password@localhost:5432/diary_db"
if DATABASE_URL and "?" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?")[0] # Strip Prisma's ?schema=public which crashes Python psycopg2

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
