# /app/bot/middlewares/__init__.py
from aiogram import Dispatcher
from aiogram_newsletter.middleware import AiogramNewsletterMiddleware

from .album import AlbumMiddleware
from .manager import ManagerMiddleware
from .redis import RedisMiddleware
from .throttling import ThrottlingMiddleware
from .user_cache import UserCacheMiddleware


def register_middlewares(dp: Dispatcher, **kwargs) -> None:
    redis_storage = kwargs["redis"]
    apscheduler = kwargs["apscheduler"]

    # 🔥 Внешние мидлвары (на уровень update)
    dp.update.outer_middleware.register(RedisMiddleware(redis_storage))
    dp.update.outer_middleware.register(ManagerMiddleware())

    # 🔥 Кэш пользователя — ставим на уровень message, чтобы
    # все хендлеры сообщений получали data["user_data"]
    dp.message.middleware.register(UserCacheMiddleware())

    # Альбомы и троттлинг
    dp.message.middleware.register(AlbumMiddleware())
    dp.message.middleware.register(ThrottlingMiddleware())

    # AiogramNewsletter
    dp.update.middleware.register(AiogramNewsletterMiddleware(apscheduler))


__all__ = ["register_middlewares"]