from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_SQLITE_DB = f"sqlite+aiosqlite:///{BASE_DIR / 'fitflow.db'}"

selected_database_url = settings.DATABASE_URL
if settings.DEBUG and "supabase.com" in selected_database_url:
    selected_database_url = LOCAL_SQLITE_DB

# Create async engine
engine = create_async_engine(
    selected_database_url,
    echo=settings.DEBUG,  # Shows SQL queries in terminal when DEBUG=True
    future=True
)

# Create async session factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for all models
Base = declarative_base()


# Dependency to get database session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()