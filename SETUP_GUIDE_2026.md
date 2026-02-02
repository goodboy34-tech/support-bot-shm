# 🚀 Комплексная инструкция по настройке (2026)

## 1. Предварительные требования

- Docker & Docker Compose
- Git
- Telegram Bot (BotFather)
- SHM panel with bot_api template
- **НОВОЕ:** Remnawave API key

## 2. Клонирование репозитория

```bash
git clone https://github.com/goodboy34-tech/support-bot-shm.git
cd support-bot-shm
git checkout dev
```

## 3. Скачивание файлов конфигурации

```bash
curl -o docker-compose.yml https://raw.githubusercontent.com/goodboy34-tech/support-bot-shm/dev/docker-compose.yml
curl -o .env https://raw.githubusercontent.com/goodboy34-tech/support-bot-shm/dev/sample.env
```

## 4. Открытие и настройка .env

```bash
nano .env
```

### Обязательные параметры

```env
# Телеграм
BOT_TOKEN=YOUR_BOT_TOKEN                    # От @BotFather
BOT_DEV_ID=1234567890                       # Ваш ID в телеграм
BOT_GROUP_ID=-100123456789                  # ID группы поддержки (forum)
BOT_USERNAME=your_bot_username              # Без @
BOT_NAME=My VPN Support Bot                 # Название бота
BOT_EMOJI_ID=                               # Опционально, custom emoji ID

# SHM
API_URL=https://admin.example.com/shm/v1/public/bot_api

# Redis
REDIS_HOST=redis                            # или IP адрес
REDIS_PORT=6379
REDIS_DB=0

# 🚀 НОВОЕ: Remnawave
REMNAWAVE_API_URL=https://remnawave.example.com/api
REMNAWAVE_API_KEY=your_remnawave_api_key    # Получите от Remnawave admin
```

## 5. Понимание Конфигурации Remnawave

### Получение API Key

1. Войдите в Remnawave admin panel
2. Найдите "Настройки" → "API"
3. Копируйте API URL и API Key

### Нтестируем соединение

```bash
curl -X GET "https://remnawave.example.com/api/users" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## 6. Настройка Telegram группы

1. Создайте группу "Поддержка" (forum)
2. Дайте боту админправа:
   - Манеджер топиков
   - Отправка сообщений
   - Удаление сообщений
3. Отправьте сообщение в группе чтобы группа стала forum
4. Найдите ID группы добавив бота:
   ```python
   @bot.message_handler(content_types=['text'])
   def get_group_id(message):
       print(message.chat.id)
   ```

## 7. Запуска бота

### с Docker Compose (ОПТИМАЛЬНО)

```bash
# Обновить образ

docker compose pull

# Запустить
docker compose up -d

# Проверить логи
docker compose logs -f app
```

### Локально (для разработки)

```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить Redis (другое окно)
redis-server

# Запустить бот
python -m app
```

## 8. Поверка работы

### Тест 1: Открыть чат с ботом
```
/start
```

Ожидаем:
- ✅ Приветствие с вашим именем
- ✅ Данные о подписке (если есть)
- ✅ Меню опций

### Тест 2: Проверка группы
Можете видеть в group chat:
```
📄 НОВОЕ ОБРАЩЕНИЕ [1234]
28.02.2026 18:45:30

👤 Пользователь:
├─ Наименование: John
├─ Username: @john_doe
└─ ID: 123456789

📊 Подписка:
├─ План: Premium VPN ✅
├─ Трафик: 850/1000 ГБ
└─ Дней осталось: 15
```

### Тест 3: Антидедупликация
Повторные `/start` должны показать:
```
👋 Привет!

💬 У вас уже есть открытое обращение в поддержку.
📌 ID вашего обращения: 1234
```

## 🚫 Отключение

```bash
docker compose down
```

## 🔓 Отключение логов

```bash
# Текущие логи
docker compose logs app

# Прослеживание логов
docker compose logs -f app

# Последние 50 строк
docker compose logs --tail 50 app
```

## 🔧 Отключение исправления

### Проблема: Ошибка подключения к Redis

```bash
# Проверить, эписан ли Redis
docker compose ps

# Перезапустить Redis
docker compose restart redis
```

### Проблема: Remnawave API ответает 401 (Unauthorized)

```bash
# Проверите API Key в .env
grep REMNAWAVE .env

# На странице админки Remnawave
```

### Проблема: Ожиданные ошибки в логах

Если видите в логах:
- `Warning: Remnawave SDK not initialized` - ОК, Remnawave настраивается
- `No data in response from API` - ОК, пользователя не регистрирован в SHM

## ❓ Частые вопросы

**В: Как делаются во множества запросов топики если несколько топиков Отнесены?**
О: Redis хранит только последний (ID 1 юзер = 1 топик). Если топик закрыт оператором, новый `/start` создаст НОВЫЙ топик.

**В: Очистить Redis?**
О:
```bash
docker exec redis redis-cli FLUSHALL
```

**В: Обновить код на плюсинг?**
О:
```bash
git pull origin dev
docker compose up -d --build
```

---

✅ **Готово! Бот работает с оплатами!** 🌟

При возникновении вопросов открыть Issue в GitHub.
