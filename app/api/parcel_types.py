import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.database import get_db
from app.schemas.shemas import ParcelTypeRead
from app.models.models import ParcelType

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/parcel_types", response_model=List[ParcelTypeRead])
async def get_parcel_types(db: AsyncSession = Depends(get_db)):
    """
    Получает список всех типов посылок.
    """
    try:
        result = await db.execute(select(ParcelType))
        parcel_types = result.scalars().all()
        return [ParcelTypeRead.from_orm(pt) for pt in parcel_types]
    except Exception as e:
        logger.error(f"Ошибка при получении типов посылок: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось получить типы посылок",
        )