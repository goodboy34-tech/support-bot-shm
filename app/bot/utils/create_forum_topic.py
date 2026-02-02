import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

from app.config import Config
from .exceptions import CreateForumTopicException, NotEnoughRightsException, NotAForumException
from .redis import RedisStorage
from .redis.models import UserData
from app.bot.utils.topics import TopicManager


async def get_or_create_forum_topic(
        bot: Bot,
        redis: RedisStorage,
        config: Config,
        user_data: UserData,
) -> int:
    if user_data.message_thread_id is None:
        try:
            topic_name = f"✰ {user_data.full_name}"

            # If message_thread_id is not found, create a forum topic
            message_thread_id = await create_forum_topic(
                bot, config, topic_name,
            )
            user_data.message_thread_id = message_thread_id
            #user_data.topic_status = "new"
            await redis.update_user(user_data.id, user_data)
            
            # 🆕 Отправляем уведомление оператору о новом обращении
            await _notify_operator_async(
                bot, config, user_data
            )

        except Exception as e:
            await bot.send_message(config.bot.DEV_ID, str(e))
            logging.exception(e)

    return user_data.message_thread_id


async def create_forum_topic(bot: Bot, config: Config, name: str) -> int:
    """
    Creates a forum topic in the specified chat.

    :param bot: The Aiogram Bot instance.
    :param config: The configuration object.
    :param name: The name of the forum topic.

    :return: The message thread ID of the created forum topic.
    :raises NotEnoughRightsException: If the bot doesn't have enough rights to create a forum topic.
    :raises CreateForumTopicException: If an error occurs while creating the forum topic.
    """
    try:
        # Attempt to create a forum topic
        forum_topic = await bot.create_forum_topic(
            chat_id=config.bot.GROUP_ID,
            name=name,
            icon_custom_emoji_id=config.bot.BOT_EMOJI_ID,
            request_timeout=30,
        )
        #topic_manager = TopicManager(bot, redis, config)
        #await topic_manager.new_topic(bot, user_data)
        return forum_topic.message_thread_id

    except TelegramRetryAfter as ex:
        # Handle Retry-After exception (rate limiting)
        logging.warning(ex.message)
        await asyncio.sleep(ex.retry_after)
        return await create_forum_topic(bot, config, name)

    except TelegramBadRequest as ex:
        if "not enough rights" in ex.message:
            # Raise an exception if the bot doesn't have enough rights
            raise NotEnoughRightsException

        elif "not a forum" in ex.message:
            # Raise an exception if the chat is not a forum
            raise NotAForumException

        # Raise a generic exception for other cases
        raise CreateForumTopicException

    except Exception as ex:
        # Re-raise any other exceptions
        raise ex


async def _notify_operator_async(bot: Bot, config: Config, user_data: UserData) -> None:
    """
    Асинхронно отправляет уведомление оператору о новом обращении.
    Запускается в фоне, не блокирует основной поток.

    :param bot: Объект bot
    :param config: Конфигурация
    :param user_data: Данные пользователя
    """
    try:
        # Импортируем функцию уведомления
        from app.bot.jobs.notify_operator import notify_operator_new_request
        
        # Получаем данные пользователя
        user_name = user_data.full_name or "Пользователь"
        username = user_data.username or "неизвестен"
        
        # Отправляем уведомление асинхронно в фоне
        asyncio.create_task(
            notify_operator_new_request(
                bot=bot,
                config=config,
                user_id=user_data.id,
                user_name=user_name,
                username=username,
                message_thread_id=user_data.message_thread_id,
            )
        )
        logging.info(f"Фоновое уведомление оператору отправлено для пользователя {user_data.id}")
        
    except Exception as e:
        logging.error(f"Ошибка при отправке уведомления оператору: {e}")
