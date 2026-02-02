import logging
import json
import asyncio
from typing import List
from aiogram import Bot
from app.bot.utils.redis import RedisStorage, UserData
from app.bot.utils.redis_pool import get_redis_client, REQUEST_SEMAPHORE
from app.config import Config

logger = logging.getLogger(__name__)
THREAD_LINK_TEMPLATE = "https://t.me/c/{chat_id}/{thread_id}"

# Константа для безопасного размера батча
BATCH_SIZE = 100  # Обрабатываем по 100 юзеров за раз

async def send_new_topics(bot: Bot, config: Config) -> None:
    """Отправляет сводку новых топиков в указанную группу.
    
    Оптимизировано для работы с большим кол-вом пользователей:
    - Использует Redis Connection Pool
    - Использует SCAN вместо HGETALL
    - Обрабатывает данные батчами
    - Минимизирует использование памяти
    - Защищен семафором от перегрузки

    Args:
        bot: Экземпляр бота для отправки сообщений.
        config: Конфигурация бота с GROUP_ID и Redis DSN.
    """
    GROUP_CHAT_ID = config.bot.GROUP_ID
    LINK_CHAT_ID = str(GROUP_CHAT_ID)[4:]

    # 🔥 Используем семафор для контроля нагрузки
    async with REQUEST_SEMAPHORE:
        try:
            # 🔥 Берём клиент из пула вместо создания нового подключения
            redis_client = await get_redis_client()
            try:
                redis = RedisStorage(redis_client)
                new_threads: List[str] = []
                cursor = 0
                
                # ✅ SCAN вместо HGETALL - не загружает всё в памяти
                while True:
                    cursor, keys = await redis.redis.hscan(
                        redis.NAME,
                        cursor=cursor,
                        count=BATCH_SIZE  # Батчируем по 100 ключей
                    )
                    
                    if not keys:
                        if cursor == 0:
                            break
                        continue
                    
                    # Обрабатываем батч
                    for key, value in keys:
                        try:
                            user_data = UserData(**json.loads(value))
                            
                            # ✅ Проверяем только нужные статусы
                            if (
                                user_data.topic_status == "new" 
                                and user_data.message_thread_id is not None
                            ):
                                thread_link = THREAD_LINK_TEMPLATE.format(
                                    chat_id=LINK_CHAT_ID,
                                    thread_id=user_data.message_thread_id
                                )
                                new_threads.append(
                                    f'<a href="{thread_link}">{user_data.full_name}</a>'
                                )
                        except (json.JSONDecodeError, ValueError) as e:
                            logger.warning(f"Ошибка парса данных для ключа {key}: {e}")
                            continue
                    
                    # Если достаточно результатов, можем отправить раньше
                    if len(new_threads) > 500:
                        logger.info(f"Достигнут лимит результатов: {len(new_threads)}")
                        break
                    
                    if cursor == 0:
                        break
                
                if new_threads:
                    # ✅ Ограничиваем сообщение (Telegram лимит 4096 символов)
                    max_threads = min(len(new_threads), 50)  # Макс 50 ссылок
                    message = (
                        "📢 <b>Сводка новых топиков, требующих ответа</b>:\n\n"
                        "{threads}\n\n"
                        "<b>Всего новых топиков: {count}</b>"
                    ).format(
                        threads="\n".join(f"- {link}" for link in new_threads[:max_threads]),
                        count=len(new_threads)
                    )
                    
                    # Проверяем размер сообщения
                    if len(message.encode('utf-8')) > 4000:
                        logger.warning("Сообщение слишком большое, урезаем")
                        new_threads = new_threads[:30]
                        message = (
                            "📢 <b>Новые топики (первые 30)</b>:\n\n"
                            "{threads}\n\n"
                            "<i>Показаны первые 30 из {count}</i>"
                        ).format(
                            threads="\n".join(f"- {link}" for link in new_threads),
                            count=len(new_threads)
                        )
                    
                    await bot.send_message(
                        chat_id=GROUP_CHAT_ID,
                        text=message,
                        parse_mode="HTML"
                    )
                    logger.info(f"Отправлена сводка с {len(new_threads)} новыми топиками")
                else:
                    logger.info("Нет топиков для сводки")
            finally:
                # 🔥 Возвращаем клиент в пул
                await redis_client.close()
        
        except Exception as e:
            logger.error(f"Ошибка в send_new_topics: {e}", exc_info=True)
            raise
