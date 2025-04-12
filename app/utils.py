import asyncio
import json
import logging
import os
import aiohttp
import redis.asyncio as redis
from dotenv import load_dotenv

load_dotenv()

# Redis setup
redis_client = redis.Redis.from_url(os.getenv('REDIS_URL'))

logger = logging.getLogger(__name__)


# Функции для работы с данными
async def get_dollar_rate_from_cbr() -> float:
    """
    Получает текущий курс доллара к рублю с сайта ЦБ РФ и кэширует его в Redis.
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.cbr-xml-daily.ru/daily_json.js"
            ) as response:
                response.raise_for_status()  # Проверка на ошибки HTTP
                # Проверяем Content-Type (теперь допускаем javascript)
                content_type = response.headers.get('Content-Type')
                if content_type not in ('application/json; charset=utf-8', 'application/javascript; charset=utf-8'):
                    logger.error(f"Неожиданный Content-Type: {content_type}")
                    raise ValueError("Неожиданный Content-Type ответа ЦБ РФ")

                text = await response.text() # Получаем ответ как текст

                # Извлекаем JSON из JavaScript
                start_index = text.find('{')
                end_index = text.rfind('}') + 1
                if start_index != -1 and end_index != 0:
                    json_text = text[start_index:end_index]
                    try:
                        data = json.loads(json_text)  # Используем json.loads
                    except json.JSONDecodeError as e:
                        logger.error(f"Ошибка при разборе JSON из JavaScript: {e}")
                        raise ValueError("Некорректный JSON в ответе ЦБ РФ") from e
                else:
                    logger.error("JSON не найден в ответе JavaScript.")
                    raise ValueError("JSON не найден в ответе ЦБ РФ")

                # Извлекаем курс доллара
                dollar_rate = data["Valute"]["USD"]["Value"]
                await redis_client.set("dollar_rate", str(dollar_rate), ex=3600)  # Кэш на 1 час
                logger.info("Курс доллара успешно получен с ЦБ РФ.")
                return dollar_rate
    except (aiohttp.ClientError, KeyError, ValueError, json.JSONDecodeError) as e:  # Добавлено json.JSONDecodeError
        logger.error(f"Ошибка при получении курса доллара с ЦБ РФ: {e}")
        # Возвращаем старое значение из кэша или значение по умолчанию
        cached_rate = await redis_client.get("dollar_rate")
        if cached_rate:
            logger.info("Используется кэшированный курс доллара.")
            return float(cached_rate.decode())
        else:
            logger.warning("Кэш пуст. Используется значение курса доллара по умолчанию.")
            return 90.0  # Значение по умолчанию

async def calculate_delivery_cost(parcel_weight: float, content_value: float) -> float:
    """
    Вычисляет стоимость доставки посылки в рублях.
    """
    dollar_rate = await get_dollar_rate_from_cbr()
    cost = (parcel_weight * 0.5 + content_value * 0.01) * dollar_rate
    return cost