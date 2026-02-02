import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from remnawave_api import RemnawaveSDK
from app.config import load_config
import asyncio
from functools import lru_cache

logger = logging.getLogger(__name__)
config = load_config()

# 🔒 Семафор для ограничения одновременных запросов
REQUEST_SEMAPHORE = asyncio.Semaphore(5)  # Макс 5 одновременных запросов
CACHE_TTL = 300  # Кэш на 5 минут


class CachedUserInfo:
    """Кэшированная информация о пользователе с TTL"""
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.created_at = datetime.now()
    
    def is_expired(self) -> bool:
        return datetime.now() - self.created_at > timedelta(seconds=CACHE_TTL)


class RemnawaveClient:
    """
    Оптимизированный клиент для работы с Remnawave API.
    
    Оптимизации:
    - Семафор для ограничения одновременных запросов
    - TTL кэш результатов (5 минут)
    - Обработка таймаутов
    - Асинхронное выполнение
    """

    def __init__(self):
        try:
            self.sdk = RemnawaveSDK(
                api_url=config.remnawave.API_URL,
                api_key=config.remnawave.API_KEY,
            )
            logger.info("Remnawave SDK инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации Remnawave SDK: {e}")
            self.sdk = None
        
        # 📦 Кэш пользователей в памяти
        self._cache: Dict[str, CachedUserInfo] = {}
        self._lock = asyncio.Lock()

    async def _get_from_cache(self, user_login: str) -> Optional[Dict[str, Any]]:
        """Получить из кэша если не истёк TTL"""
        if user_login in self._cache:
            cached = self._cache[user_login]
            if not cached.is_expired():
                logger.debug(f"Cache hit для {user_login}")
                return cached.data
            else:
                # Удаляем истёкший кэш
                del self._cache[user_login]
        return None

    async def _set_cache(self, user_login: str, data: Dict[str, Any]) -> None:
        """Сохранить в кэш"""
        async with self._lock:
            self._cache[user_login] = CachedUserInfo(data)
            # 🧹 Очищаем старые записи, чтобы не расти без конца
            if len(self._cache) > 1000:
                oldest_key = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k].created_at
                )
                del self._cache[oldest_key]

    async def get_user_subscription_info(
        self, user_login: str, use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о подписке пользователя из Remnawave.
        
        ✅ С оптимизациями:
        - Кэширование результатов (5 минут)
        - Семафор для ограничения нагрузки
        - Таймауты для предотвращения зависания

        :param user_login: Логин пользователя в Remnawave
        :param use_cache: Использовать кэш (по умолчанию да)
        :return: Словарь с информацией о подписке или None при ошибке
        """
        if not self.sdk:
            logger.warning("Remnawave SDK не инициализирован")
            return None

        # ✅ Проверяем кэш
        if use_cache:
            cached_data = await self._get_from_cache(user_login)
            if cached_data is not None:
                return cached_data

        try:
            # 🔒 Семафор ограничивает одновременные запросы
            async with REQUEST_SEMAPHORE:
                # ⏱️ Таймаут 10 сек для API запроса
                user_info = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.sdk.get_user,
                        user_login
                    ),
                    timeout=10.0
                )

                if not user_info:
                    logger.warning(f"Пользователь {user_login} не найден в Remnawave")
                    # 📦 Кэшируем результат "не найден" тоже
                    default_response = {
                        "login": user_login,
                        "has_active_service": False,
                        "traffic_total": 0,
                        "traffic_remaining": 0,
                        "traffic_used": 0,
                        "days_remaining": 0,
                        "plan_name": "Нет активной подписки",
                        "status": "inactive",
                    }
                    await self._set_cache(user_login, default_response)
                    return default_response

                # Получаем информацию об услугах
                services = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.sdk.get_user_services,
                        user_info.id
                    ),
                    timeout=10.0
                )

                if not services:
                    empty_response = {
                        "login": user_login,
                        "has_active_service": False,
                        "traffic_total": 0,
                        "traffic_remaining": 0,
                        "traffic_used": 0,
                        "days_remaining": 0,
                        "plan_name": "Нет активной подписки",
                        "status": "inactive",
                    }
                    await self._set_cache(user_login, empty_response)
                    return empty_response

                # Берём первую активную услугу
                active_service = services[0]  # type: ignore

                traffic_total = getattr(active_service, "traffic_total", 0)
                traffic_used = getattr(active_service, "traffic_used", 0)
                traffic_remaining = max(0, traffic_total - traffic_used)

                # Вычисляем дни до конца
                expire_date = getattr(active_service, "expire_date", None)
                days_remaining = 0
                if expire_date:
                    today = datetime.now().date()
                    if hasattr(expire_date, "date"):
                        expire = expire_date.date()
                    else:
                        expire = expire_date
                    days_remaining = (expire - today).days

                response = {
                    "login": user_login,
                    "has_active_service": True,
                    "traffic_total": traffic_total,
                    "traffic_used": traffic_used,
                    "traffic_remaining": traffic_remaining,
                    "days_remaining": max(0, days_remaining),
                    "plan_name": getattr(active_service, "name", "VPN"),
                    "status": "active" if days_remaining > 0 else "expired",
                }
                
                # 📦 Кэшируем результат
                await self._set_cache(user_login, response)
                return response

        except asyncio.TimeoutError:
            logger.error(f"Таймаут запроса к Remnawave для {user_login}")
            return None
        except Exception as e:
            logger.error(f"Ошибка получения информации о подписке для {user_login}: {e}")
            return None

    @staticmethod
    def format_traffic_gb(bytes_value: int) -> float:
        """
        Конвертирует байты в гигабайты.

        :param bytes_value: Количество байт
        :return: Количество ГБ
        """
        if bytes_value == 0:
            return 0.0
        return round(bytes_value / (1024**3), 2)

    @staticmethod
    def format_subscription_text(info: Dict[str, Any]) -> str:
        """
        Форматирует информацию о подписке в читаемый текст.

        :param info: Словарь с информацией о подписке
        :return: Форматированный текст
        """
        if not info or not info.get("has_active_service"):
            return "📊 <b>Статус:</b> Нет активной подписки ❌"

        traffic_total = RemnawaveClient.format_traffic_gb(info["traffic_total"])
        traffic_remaining = RemnawaveClient.format_traffic_gb(
            info["traffic_remaining"]
        )
        days = info["days_remaining"]
        plan = info["plan_name"]

        status_emoji = "✅" if days > 0 else "⚠️"
        days_text = f"{days} дней" if days > 1 else f"{days} день"

        return f"""
📊 <b>Ваш статус подписки</b> {status_emoji}
├─ 📦 План: <code>{plan}</code>
├─ 🚀 Трафик: <code>{traffic_remaining}/{traffic_total} ГБ</code>
└─ ⏰ До конца: <code>{days_text}</code>
""".strip()


# Глобальный экземпляр клиента с кэшем и семафором
remnawave_client = RemnawaveClient()
