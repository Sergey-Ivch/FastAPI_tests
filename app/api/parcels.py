import asyncio
import json
import logging
from typing import List, Optional
import re

import aiohttp
import redis.asyncio as redis
from celery import Celery
from celery.schedules import crontab
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.pool import NullPool




import logging
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.models.models import Parcel, ParcelType
from app.schemas.shemas import ParcelCreate, ParcelRead
from app.tasks import celery, calculate_delivery_costs_task

router = APIRouter()

logger = logging.getLogger(__name__)


# Dependency для получения сессии ID
async def get_session_id(request: Request) -> str:
    """
    Получает или генерирует ID сессии пользователя.
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
    return session_id


# Dependency для получения сессии ID
@router.post("/parcels", response_model=ParcelRead, status_code=status.HTTP_201_CREATED)
async def register_parcel(
    parcel: ParcelCreate,
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Регистрирует новую посылку для пользователя.
    """
    try:
        db_parcel = Parcel(
            session_id=session_id,
            name=parcel.name,
            weight=parcel.weight,
            parcel_type_id=parcel.parcel_type_id,
            content_value=parcel.content_value,
        )
        db.add(db_parcel)
        await db.commit()
        await db.refresh(db_parcel)

        # Получаем имя типа посылки для возврата в ответе
        parcel_type = await db.get(ParcelType, db_parcel.parcel_type_id)
        parcel_type_name = parcel_type.name if parcel_type else "Неизвестно"

        logger.info(f"Посылка зарегистрирована с ID: {db_parcel.id}")
        return ParcelRead(
            id=db_parcel.id,
            name=db_parcel.name,
            weight=db_parcel.weight,
            parcel_type_id=db_parcel.parcel_type_id,
            content_value=db_parcel.content_value,
            delivery_cost=db_parcel.delivery_cost,
            parcel_type=parcel_type_name,
        )
    except Exception as e:
        logger.error(f"Ошибка при регистрации посылки: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось зарегистрировать посылку",
        )


@router.get("/parcels", response_model=List[ParcelRead])
async def get_user_parcels(
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Номер страницы"),
    page_size: int = Query(10, ge=1, le=100, description="Размер страницы"),
    parcel_type_id: Optional[int] = Query(
        None, description="Фильтр по ID типа посылки"
    ),
    delivery_cost_calculated: Optional[bool] = Query(
        None, description="Фильтр по наличию рассчитанной стоимости доставки"
    ),
):
    """
    Получает список посылок пользователя с пагинацией и фильтрацией.
    """
    try:
        query = (
            select(Parcel)
            .where(Parcel.session_id == session_id)
            .order_by(Parcel.id)
        )

        if parcel_type_id is not None:
            query = query.where(Parcel.parcel_type_id == parcel_type_id)

        if delivery_cost_calculated is not None:
            if delivery_cost_calculated:
                query = query.where(Parcel.delivery_cost != None)
            else:
                query = query.where(Parcel.delivery_cost == None)

        total_count_result = await db.execute(
            select(Parcel).where(Parcel.session_id == session_id)
        )
        total_count = len(total_count_result.scalars().all())

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        parcels = result.scalars().all()

        parcel_list = []
        for parcel in parcels:
            # Получаем имя типа посылки
            parcel_type = await db.get(ParcelType, parcel.parcel_type_id)
            parcel_type_name = parcel_type.name if parcel_type else "Неизвестно"

            parcel_list.append(
                ParcelRead(
                    id=parcel.id,
                    name=parcel.name,
                    weight=parcel.weight,
                    parcel_type_id=parcel.parcel_type_id,
                    content_value=parcel.content_value,
                    delivery_cost=parcel.delivery_cost,
                    parcel_type=parcel_type_name,
                )
            )

        return parcel_list
    except Exception as e:
        logger.error(f"Ошибка при получении списка посылок: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось получить список посылок",
        )


@router.get("/parcels/{parcel_id}", response_model=ParcelRead)
async def get_parcel_by_id(
    parcel_id: int,
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Получает данные о посылке по ее ID.
    """
    try:
        parcel = await db.get(Parcel, parcel_id)
        if parcel is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Посылка не найдена"
            )

        if parcel.session_id != session_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="У вас нет прав для просмотра этой посылки",
            )

        # Получаем имя типа посылки
        parcel_type = await db.get(ParcelType, parcel.parcel_type_id)
        parcel_type_name = parcel_type.name if parcel_type else "Неизвестно"

        return ParcelRead(
            id=parcel.id,
            name=parcel.name,
            weight=parcel.weight,
            parcel_type_id=parcel.parcel_type_id,
            content_value=parcel.content_value,
            delivery_cost=parcel.delivery_cost,
            parcel_type=parcel_type_name,
        )
    except HTTPException:
        raise  # Пробрасываем HTTPException дальше
    except Exception as e:
        logger.error(f"Ошибка при получении посылки по ID: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось получить данные о посылке",
        )

    
@router.post("/calculate_delivery_costs")
async def trigger_calculate_delivery_costs():
    """
    Запускает задачу расчета стоимости доставки для всех необработанных посылок вручную.
    """
    try:
        task = celery.send_task("app.tasks.calculate_delivery_costs_task")
        return {"message": "Задача запущена", "task_id": task.id}
    except Exception as e:
        logger.error(f"Ошибка при запуске задачи: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось запустить задачу",
        )