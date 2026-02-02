import logging
from datetime import datetime
from typing import Optional, Dict, Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from app.config import Config
from app.bot.utils.api import fetch_user_data
from app.bot.utils.remnawave_client import remnawave_client

logger = logging.getLogger(__name__)


async def notify_operator_new_request(
    bot: Bot,
    config: Config,
    user_id: int,
    user_name: str,
    username: str,
    message_thread_id: int,
) -> None:
    """
    Отправляет уведомление об операторам в групповые чат
    с информацией о новом обращении пользователя.

    :param bot: Объект bot
    :param config: Конфигурация
    :param user_id: ID пользователя
    :param user_name: Имя пользователя
    :param username: Username пользователя
    :param message_thread_id: ID топика обращения
    """
    try:
        # Получаем данные из SHM
        shm_user = await fetch_user_data(user_id)
        remnawave_info = None

        if shm_user and shm_user.get("login"):
            try:
                remnawave_info = await remnawave_client.get_user_subscription_info(
                    shm_user["login"]
                )
            except Exception as e:
                logger.warning(f"Ошибка получения инфо из Remnawave: {e}")

        # Формируем сообщение для оператора
        operator_message = await _build_operator_message(
            user_id, user_name, username, message_thread_id, remnawave_info
        )

        # Отправляем в групповые чат
        await bot.send_message(
            chat_id=config.bot.GROUP_ID,
            message_thread_id=config.api.GENERAL_TOPIC_ID
            if hasattr(config.api, "GENERAL_TOPIC_ID")
            else None,  # опционально
            text=operator_message,
            parse_mode="HTML",
        )

        logger.info(f"Отправлено уведомление об обращении узера {user_id}")

    except TelegramBadRequest as e:
        logger.error(f"Ошибка отправки сообщения в Telegram: {e}")
    except Exception as e:
        logger.error(
            f"Ошибка при отправке уведомления оператору: {e}"
        )


async def _build_operator_message(
    user_id: int,
    user_name: str,
    username: str,
    message_thread_id: int,
    remnawave_info: Optional[Dict[str, Any]],
) -> str:
    """
    Формирует сообщение для оператора с информацией о пользователе.

    :param user_id: ID пользователя
    :param user_name: Имя пользователя
    :param username: Username пользователя
    :param message_thread_id: ID топика
    :param remnawave_info: Информация о подписке
    :return: Форматированный текст
    """
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

    message = (
        f"📄 <b>НОВОЕ ОБРАЩЕНИЕ</b> [<code>{message_thread_id}</code>]\n"
        f"<i>{timestamp}</i>\n\n"
    )

    # Основная информация
    message += (
        f"<b>👤 Пользователь:</b>\n"
        f"├─ Наименование: <code>{user_name}</code>\n"
        f"├─ Username: @{username}\n"
        f"└─ ID: <code>{user_id}</code>\n\n"
    )

    # Информация о подписке
    message += f"<b>📊 Подписка:</b>\n"

    if remnawave_info and remnawave_info.get("has_active_service"):
        plan = remnawave_info.get("plan_name", "VPN")
        traffic_total = remnawave_info.get("traffic_total", 0)
        traffic_remaining = remnawave_info.get("traffic_remaining", 0)
        days = remnawave_info.get("days_remaining", 0)
        status_emoji = "✅" if days > 0 else "⚠️"

        # Конвертируем трафик в ГБ
        from app.bot.utils.remnawave_client import RemnawaveClient

        traffic_total_gb = RemnawaveClient.format_traffic_gb(traffic_total)
        traffic_remaining_gb = RemnawaveClient.format_traffic_gb(traffic_remaining)

        message += (
            f"├─ План: <code>{plan}</code> {status_emoji}\n"
            f"├─ Трафик: <code>{traffic_remaining_gb}/{traffic_total_gb} ГБ</code>\n"
            f"└─ Дней осталось: <code>{days}</code>\n\n"
        )
    else:
        message += "└─ <i>Нет активной подписки</i>\n\n"

    # Попрос на действие
    message += "🆘 <b>Что вам требуется?</b> Ожидаем ответа..."

    return message


__all__ = ["notify_operator_new_request"]
