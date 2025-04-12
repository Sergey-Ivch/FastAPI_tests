import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

load_dotenv()

# Конфигурация
DATABASE_URL = os.getenv('DATABASE_URL') 

# SQLAlchemy setup
engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


# Dependency для получения сессии БД
async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session