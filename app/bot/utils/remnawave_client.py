import logging
from typing import Optional, Dict, Any
from remnawave_api import RemnawaveSDK
from app.config import load_config

logger = logging.getLogger(__name__)
config = load_config()


class RemnawaveClient:
    """
    Клиент для работы с Remnawave API через официальный SDK.
    Получает информацию о трафике и дате окончания подписки пользователя.
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

    async def get_user_subscription_info(
        self, user_login: str
    ) -> Optional[Dict[str, Any]]:
        """
        Получает информацию о подписке пользователя из Remnawave.

        :param user_login: Логин пользователя в Remnawave
        :return: Словарь с информацией о подписке или None при ошибке
        """
        if not self.sdk:
            logger.warning("Remnawave SDK не инициализирован")
            return None

        try:
            # Получаем информацию о пользователе
            user_info = await self.sdk.get_user(login=user_login)

            if not user_info:
                logger.warning(f"Пользователь {user_login} не найден в Remnawave")
                return None

            # Получаем информацию об услугах
            services = await self.sdk.get_user_services(user_id=user_info.id)

            if not services:
                return {
                    "login": user_login,
                    "has_active_service": False,
                    "traffic_total": 0,
                    "traffic_remaining": 0,
                    "traffic_used": 0,
                    "days_remaining": 0,
                    "plan_name": "Нет активной подписки",
                    "status": "inactive",
                }

            # Берём первую активную услугу
            active_service = services[0]  # type: ignore

            traffic_total = getattr(active_service, "traffic_total", 0)
            traffic_used = getattr(active_service, "traffic_used", 0)
            traffic_remaining = traffic_total - traffic_used

            # Вычисляем дни до конца
            expire_date = getattr(active_service, "expire_date", None)
            days_remaining = 0
            if expire_date:
                from datetime import datetime

                today = datetime.now().date()
                if hasattr(expire_date, "date"):
                    expire = expire_date.date()
                else:
                    expire = expire_date
                days_remaining = (expire - today).days

            return {
                "login": user_login,
                "has_active_service": True,
                "traffic_total": traffic_total,
                "traffic_used": traffic_used,
                "traffic_remaining": traffic_remaining,
                "days_remaining": max(0, days_remaining),
                "plan_name": getattr(active_service, "name", "VPN"),
                "status": "active" if days_remaining > 0 else "expired",
            }

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


# Глобальный экземпляр клиента
remnawave_client = RemnawaveClient()
