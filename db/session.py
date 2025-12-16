from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from fastapi import HTTPException
from core.config import settings

DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def check_database_connection():
    """Verify database connection is working"""
    try:
        db = SessionLocal()
        # Execute a simple query to verify the connection
        db.execute(text('SELECT 1'))
        db.close()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to the database. Please check your database configuration. Error: {str(e)}"
        )