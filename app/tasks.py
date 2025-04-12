import asyncio
import logging

from celery import Celery
from celery.schedules import crontab
from sqlalchemy import select

from app.database.database import async_session
from app.models.models import Parcel
from app.utils import calculate_delivery_cost

# Конфигурация Celery
CELERY_BROKER_URL = "redis://redis:6379/1"
CELERY_RESULT_BACKEND = "redis://redis:6379/2"

# Инициализация Celery
celery = Celery(
    "parcel_tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["app.tasks"],
)

celery.conf.update(
    {
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "timezone": "UTC",
        "enable_utc": True,
        "beat_schedule": {
            "calculate_delivery_costs": {
                "task": "app.tasks.calculate_delivery_costs_task",
                "schedule": crontab(minute="*/5"),  # Выполнять каждые 5 минут
            }
        },
    }
)

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.calculate_delivery_costs_task")
def calculate_delivery_costs_task():
    """
    Celery task для расчета стоимости доставки для всех необработанных посылок.
    """
    asyncio.run(calculate_delivery_costs_async())  # Запуск асинхронной функции


async def calculate_delivery_costs_async():
    """
    Асинхронная функция для расчета стоимости доставки для всех необработанных посылок.
    """
    logger.info("Запущена задача расчета стоимости доставки.")
    async with async_session() as db:
        try:
            result = await db.execute(
                select(Parcel).where(Parcel.delivery_cost == None)
            )
            parcels = result.scalars().all()
            for parcel in parcels:
                cost = await calculate_delivery_cost(parcel.weight, parcel.content_value)
                parcel.delivery_cost = cost
                logger.info(
                    f"Рассчитана стоимость доставки для посылки ID {parcel.id}: {cost}"
                )
            await db.commit()
            logger.info("Расчет стоимости доставки завершен.")
        except Exception as e:
            logger.error(f"Ошибка при расчете стоимости доставки: {e}")
            await db.rollback()