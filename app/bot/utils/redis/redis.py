import json

from redis.asyncio import Redis

from .models import UserData


class RedisStorage:
    """Class for managing user data storage using Redis."""

    NAME = "users"
    TOPICS_NAME = "user_topics"  # хранилище юзер_id -> topic_id
    NEW_TOPICS_SET = "new_topics_set"  # 🔥 SET для O(1) доступа к новым топикам вместо O(n)

    def __init__(self, redis: Redis) -> None:
        """
        Initializes the RedisStorage instance.

        :param redis: The Redis instance to be used for data storage.
        """
        self.redis = redis

    async def _get(self, name: str, key: str | int) -> bytes | None:
        """
        Retrieves data from Redis.

        :param name: The name of the Redis hash.
        :param key: The key to be retrieved.
        :return: The retrieved data or None if not found.
        """
        async with self.redis.client() as client:
            return await client.hget(name, key)

    async def _set(self, name: str, key: str | int, value: any) -> None:
        """
        Sets data in Redis.

        :param name: The name of the Redis hash.
        :param key: The key to be set.
        :param value: The value to be set.
        """
        async with self.redis.client() as client:
            await client.hset(name, key, value)

    async def _delete(self, name: str, key: str | int) -> None:
        """
        Deletes data from Redis.

        :param name: The name of the Redis hash.
        :param key: The key to be deleted.
        """
        async with self.redis.client() as client:
            await client.hdel(name, key)

    async def _update_index(self, message_thread_id: int, user_id: int) -> None:
        """
        Updates the user index in Redis.

        :param message_thread_id: The ID of the message thread.
        :param user_id: The ID of the user to be updated in the index.
        """
        index_key = f"{self.NAME}_index_{message_thread_id}"
        await self._set(index_key, user_id, "1")

    async def get_by_message_thread_id(self, message_thread_id: int) -> UserData | None:
        """
        Retrieves user data based on message thread ID.

        :param message_thread_id: The ID of the message thread.
        :return: The user data or None if not found.
        """
        user_id = await self._get_user_id_by_message_thread_id(message_thread_id)
        return None if user_id is None else await self.get_user(user_id)

    async def _get_user_id_by_message_thread_id(self, message_thread_id: int) -> int | None:
        """
        Retrieves user ID based on message thread ID.

        :param message_thread_id: The ID of the message thread.
        :return: The user ID or None if not found.
        """
        index_key = f"{self.NAME}_index_{message_thread_id}"
        async with self.redis.client() as client:
            user_ids = await client.hkeys(index_key)
            return int(user_ids[0]) if user_ids else None

    async def get_user(self, id_: int) -> UserData | None:
        """
        Retrieves user data based on user ID.

        :param id_: The ID of the user.
        :return: The user data or None if not found.
        """
        data = await self._get(self.NAME, id_)
        if data is not None:
            decoded_data = json.loads(data)
            return UserData(**decoded_data)
        return None

    async def update_user(self, id_: int, data: UserData) -> None:
        """
        Updates user data in Redis.

        :param id_: The ID of the user to be updated.
        :param data: The updated user data.
        """
        json_data = json.dumps(data.to_dict())
        await self._set(self.NAME, id_, json_data)
        await self._update_index(data.message_thread_id, id_)

    async def get_all_users_ids(self) -> list[int]:
        """
        Retrieves all user IDs stored in the Redis hash.

        :return: A list of all user IDs.
        """
        async with self.redis.client() as client:
            user_ids = await client.hkeys(self.NAME)
            return [int(user_id) for user_id in user_ids]

    # ===== НОВЫЕ МЕТОДЫ ДЛЯ ДЕДУПЛИКАЦИИ ТОПИКОВ =====

    async def get_user_topic_id(self, user_id: int) -> int | None:
        """
        Получает ID топика для пользователя (дедупликация).
        Возвращает ID существующего топика, если он есть.

        :param user_id: ID пользователя
        :return: ID топика или None, если топика нет
        """
        topic_id = await self._get(self.TOPICS_NAME, user_id)
        return int(topic_id) if topic_id else None

    async def set_user_topic_id(self, user_id: int, topic_id: int) -> None:
        """
        Сохраняет связь между пользователем и его топиком.

        :param user_id: ID пользователя
        :param topic_id: ID топика
        """
        await self._set(self.TOPICS_NAME, user_id, str(topic_id))

    async def delete_user_topic_id(self, user_id: int) -> None:
        """
        Удаляет связь между пользователем и топиком (при закрытии).

        :param user_id: ID пользователя
        """
        await self._delete(self.TOPICS_NAME, user_id)

    async def topic_exists_for_user(self, user_id: int) -> bool:
        """
        Проверяет, есть ли уже открытый топик для пользователя.

        :param user_id: ID пользователя
        :return: True, если топик существует, иначе False
        """
        return await self.get_user_topic_id(user_id) is not None

    # ===== 🔥 НОВЫЕ МЕТОДЫ ДЛЯ SET-BASED TRACKING НОВЫХ ТОПИКОВ (O(1) вместо O(n)) =====

    async def add_to_new_topics_set(self, user_id: int, thread_id: int) -> None:
        """
        Добавляет топик в SET новых топиков.
        Используется вместо сканирования всех пользователей.

        🔥 Сложность: O(1) вместо O(n)

        :param user_id: ID пользователя
        :param thread_id: ID топика (thread_id)
        """
        async with self.redis.client() as client:
            await client.sadd(self.NEW_TOPICS_SET, f"{user_id}:{thread_id}")

    async def remove_from_new_topics_set(self, user_id: int, thread_id: int) -> None:
        """
        Удаляет топик из SET новых топиков (при закрытии).

        :param user_id: ID пользователя
        :param thread_id: ID топика
        """
        async with self.redis.client() as client:
            await client.srem(self.NEW_TOPICS_SET, f"{user_id}:{thread_id}")

    async def get_new_topics_set(self) -> set[str]:
        """
        Получает ВСЕ новые топики из SET.
        
        🔥 Сложность: O(1) + O(N) где N = кол-во новых топиков (обычно < 50)
        Вместо: O(n) где n = кол-во ВСЕХ пользователей (может быть 10k+)

        :return: Множество строк вида "user_id:thread_id"
        """
        async with self.redis.client() as client:
            return await client.smembers(self.NEW_TOPICS_SET)

    async def get_new_topics_count(self) -> int:
        """
        Быстро узнает кол-во новых топиков.
        Полезно для логирования и мониторинга.

        🔥 Сложность: O(1)

        :return: Количество новых топиков
        """
        async with self.redis.client() as client:
            return await client.scard(self.NEW_TOPICS_SET)

    async def clear_new_topics_set(self) -> None:
        """
        Очищает SET новых топиков.
        Используется после отправки сводки.

        :return: Количество удаленных элементов
        """
        async with self.redis.client() as client:
            await client.delete(self.NEW_TOPICS_SET)
