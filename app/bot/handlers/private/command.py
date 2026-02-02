from aiogram import Router, F
from aiogram.filters import Command, MagicData
from aiogram.types import Message
from aiogram_newsletter.manager import ANManager

from app.bot.handlers.private.windows import Window
from app.bot.manager import Manager
from app.bot.utils.create_forum_topic import get_or_create_forum_topic
from app.bot.utils.redis import RedisStorage
from app.bot.utils.redis.models import UserData
from app.bot.utils.remnawave_client import remnawave_client, RemnawaveClient
from app.bot.utils.api import fetch_user_data

router = Router()
router.message.filter(F.chat.type == "private")


@router.message(Command("start"))
async def handler(
        message: Message,
        manager: Manager,
        redis: RedisStorage,
        user_data: UserData,
) -> None:
    """
    Обработчик команды /start.

    Реализует антидедупликацию: один юзер = один топик.
    При повторном /start показывает сообщение "У вас уже есть открытое обращение".

    :param message: Объект сообщения
    :param manager: Объект менеджера
    :param redis: Хранилище Redis
    :param user_data: Данные пользователя
    :return: None
    """
    user_id = message.from_user.id

    # Проверяем: есть ли уже топик для этого пользователя?
    existing_topic_id = await redis.get_user_topic_id(user_id)

    if existing_topic_id:
        # Топик уже существует - отправляем уведомление
        response_text = (
            "👋 <b>Привет!</b>\n\n"
            "💬 У вас уже есть открытое обращение в поддержку.\n"
            "📌 ID вашего обращения: <code>{}</code>\n\n"
            "Если у вас есть ещё вопросы, напишите в этом же топике."
        ).format(existing_topic_id)
        await manager.send_message(response_text)
        await manager.delete_message(message)
        return

    # Первое посещение или был закрыт топик - создаём новый
    if user_data.language_code:
        await Window.main_menu(manager)
    else:
        await Window.select_language(manager)

    await manager.delete_message(message)

    # Создаём топик
    forum_result = await get_or_create_forum_topic(message.bot, redis, manager.config, user_data)

    if not forum_result:
        await manager.send_message(
            "❌ <b>Ошибка при создании обращения.</b>\n"
            "Пожалуйста, попробуйте позже."
        )
        return

    # Сохраняем связь пользователь <-> топик
    await redis.set_user_topic_id(user_id, user_data.message_thread_id)

    # Получаем данные пользователя из SHM
    shm_user = await fetch_user_data(user_id)
    remnawave_info = None
    user_name = message.from_user.first_name or "Пользователь"
    username = message.from_user.username or "неизвестен"

    # Пытаемся получить информацию о подписке из Remnawave
    if shm_user and shm_user.get("login"):
        remnawave_info = await remnawave_client.get_user_subscription_info(
            shm_user["login"]
        )

    # Формируем приветственное сообщение с информацией
    welcome_text = await _build_welcome_message(
        user_name, username, remnawave_info, user_id
    )

    await manager.send_message(welcome_text)


async def _build_welcome_message(
        user_name: str, username: str, remnawave_info, user_id: int
) -> str:
    """
    Формирует приветственное сообщение с информацией о пользователе.

    :param user_name: Имя пользователя
    :param username: Username пользователя
    :param remnawave_info: Информация о подписке из Remnawave
    :param user_id: ID пользователя
    :return: Форматированный текст приветствия
    """
    greeting = f"👋 Добро пожаловать, <b>{user_name}</b>!\n\n"

    user_section = f"👤 <b>Ваш профиль:</b>\n"
    user_section += f"├─ ID: <code>{user_id}</code>\n"
    user_section += f"└─ @{username}\n\n"

    # Информация о подписке
    if remnawave_info and remnawave_info.get("has_active_service"):
        subscription_text = RemnawaveClient.format_subscription_text(remnawave_info)
        info_section = subscription_text + "\n\n"
    else:
        info_section = (
            "📊 <b>Статус подписки:</b>\n"
            "└─ Нет активной подписки ❌\n\n"
        )

    footer = (
        "🆘 <b>Как мы можем вам помочь?</b>\n"
        "Выберите действие из меню ниже или опишите вашу проблему."
    )

    return greeting + user_section + info_section + footer


@router.message(Command("time"))
async def handler(message: Message, manager: Manager, user_data: UserData) -> None:

    last_message_date = user_data.last_message_date
    text = f"Last time: {last_message_date}"

    return await manager.send_message(text)


@router.message(Command("language"))
async def handler(message: Message, manager: Manager, user_data: UserData) -> None:
    """
    Обработчик команды /language.

    Если пользователь уже выбрал язык, предлагает сменить его.
    Иначе предлагает выбрать язык.

    :param message: Объект сообщения
    :param manager: Объект менеджера
    :param user_data: Данные пользователя
    :return: None
    """
    if user_data.language_code:
        await Window.change_language(manager)
    else:
        await Window.select_language(manager)
    await manager.delete_message(message)


@router.message(
    Command("newsletter"),
    MagicData(F.event_from_user.id == F.config.bot.DEV_ID),  # type: ignore
)
async def handler(
        message: Message,
        manager: Manager,
        an_manager: ANManager,
        redis: RedisStorage,
) -> None:
    """
    Обработчик команды /newsletter (только для админа).

    :param message: Объект сообщения
    :param manager: Объект менеджера
    :param redis: Хранилище Redis
    :param an_manager: Менеджер aiogram_newsletter
    :return: None
    """
    users_ids = await redis.get_all_users_ids()
    await an_manager.newsletter_menu(users_ids, Window.main_menu)
    await manager.delete_message(message)
