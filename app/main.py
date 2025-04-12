import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import parcels, parcel_types
from app.database.database import engine
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Инициализация FastAPI
app = FastAPI(
    title="Parcel Service API",
    description="API для управления посылками.",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(parcels.router)
app.include_router(parcel_types.router)

# Endpoint для установки session_id в cookie
import uuid

@app.middleware("http")
async def add_session_id_to_response(request: Request, call_next):
    response = await call_next(request)
    if "session_id" not in request.cookies:
        session_id = str(uuid.uuid4())
        response.set_cookie("session_id", session_id)
    return response


@app.on_event("startup")
async def startup_event():
    """
    Выполняется при запуске приложения.  Создает таблицы в БД, если их нет.
    """
    from app.models.models import Base, ParcelType
    from sqlalchemy.future import select
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.ext.asyncio import AsyncSession

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Заполнение таблицы типов посылок, если она пуста
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)  # Create session factory
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(ParcelType))
        if not result.scalars().first():
            parcel_types = [
                ParcelType(name="одежда"),
                ParcelType(name="электроника"),
                ParcelType(name="разное"),
            ]
            db.add_all(parcel_types)
            await db.commit()
            logger.info("Типы посылок добавлены в базу данных.")


# Обработчики ошибок
@app.exception_handler(status.HTTP_400_BAD_REQUEST)
async def validation_exception_handler(request: Request, exc: Exception):
    """
    Глобальный обработчик ошибок валидации.
    """
    logger.warning(f"Validation Error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )

@app.exception_handler(status.HTTP_404_NOT_FOUND)
async def not_found_exception_handler(request: Request, exc: Exception):
    """
    Глобальный обработчик ошибок 404.
    """
    logger.warning(f"Not Found Error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


@app.exception_handler(status.HTTP_500_INTERNAL_SERVER_ERROR)
async def internal_server_error_exception_handler(request: Request, exc: Exception):
    """
    Глобальный обработчик ошибок сервера.
    """
    logger.exception(f"Internal Server Error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Внутренняя ошибка сервера"},
    )

