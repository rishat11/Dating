# Dating Bot — телеграм-бот для знакомств с Индексом совместимости

Бот для знакомств на aiogram 3.x с механикой «Индекс совместимости» (совместимость пары 0–100%), лентой карточек, лайками и личными чатами через бота.

## Требования

- Python 3.10+
- PostgreSQL 16 (локально — через Docker, см. ниже)
- Redis (очередь и кэш; локально — через Docker)

## Установка

```bash
cd c:\Users\Ришат\Downloads\Dating
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните:

| Переменная | Обязательно | Описание |
|------------|-------------|----------|
| `BOT_TOKEN` | Да | Токен бота от @BotFather |
| `DATABASE_URL` | Нет | По умолчанию `postgresql+asyncpg://dating:dating@localhost:5432/dating` (локальный Postgres в Docker) |
| `REDIS_URL` | Нет | Очередь и кэш. Локально: `redis://localhost:6379` (поднять `docker compose up -d redis`). В Docker задаётся в compose. |
| `DEEPSEEK_API_KEY` | Нет | Для PRO-сценариев (анализ диалога и т.д.) |
| `DAILY_LIKES_LIMIT` | Нет | Лимит лайков в день (по умолчанию 10) |
| `DESTINY_INDEX_CACHE_TTL` | Нет | TTL кэша индекса в секундах |
| `DESTINY_FREEZE_HOURS` | Нет | Часы заморозки индекса при конфликте |
| `SAVE_INDEX_SILENCE_HOURS` | Нет | Часы молчания для сценария «Спасите индекс» |
| `CHAT_MESSAGES_PER_MINUTE` | Нет | Лимит сообщений в чате в минуту (по умолчанию 30) |
| `FEED_REQUESTS_PER_MINUTE` | Нет | Лимит запросов ленты в минуту (по умолчанию 20) |
| `MESSAGES_RETENTION_MONTHS` | Нет | Хранить сообщения не более N месяцев (0 = не удалять; по умолчанию 12) |

**База данных:** при первом запуске создаются таблицы; недостающие колонки (locale, геолокация) добавляются миграцией автоматически.

## Запуск

**Локальная разработка (бот на хосте, Postgres и Redis в Docker):**

```bash
# Поднять только БД и Redis
docker compose up -d postgres redis

# В .env: BOT_TOKEN, DATABASE_URL=postgresql+asyncpg://dating:dating@localhost:5432/dating, REDIS_URL=redis://localhost:6379
python -m bot.main
```

**Всё в Docker (продакшен):**

```bash
# Создайте .env из .env.example и укажите BOT_TOKEN
docker compose up -d
```

Поднимаются бот, PostgreSQL 16 и Redis. Учётные данные Postgres: пользователь/пароль/БД — `dating`. Логи бота: `docker compose logs -f bot`.

**Webhook (production):** задайте `WEBHOOK_HOST` и `WEBHOOK_PATH` в `.env` и используйте соответствующий режим в `main.py`.

## Тесты

```bash
pip install -r requirements-dev.txt
python -m pytest tests -v
# с отчётом покрытия:
python -m pytest tests -v --cov=. --cov-report=term-missing --cov-config=.coveragerc
```

## Структура проекта

- `bot/` — точка входа, мидлварь (идемпотентность по `update_id`)
- `db/` — SQLAlchemy-модели и сессии
- `handlers/` — онбординг, анкета, лента, чат, настройки
- `i18n/` — локализация (ru/en)
- `services/` — расчёт индекса совместимости, очередь, разблокировки, лента, rate limit, аудит, retention
- `fsm/` — состояния FSM
- `keyboards/` — клавиатуры

## Функционал MVP

- Регистрация: Telegram ID, имя, фото, возраст 18+, согласие с правилами
- Анкета: имя, возраст, пол, кого ищет, город, фото; опционально описание, интересы
- Лента по фильтрам, лайк/пропуск, лимит лайков в день
- Взаимный лайк → пара (чат), уведомление обоим
- Чаты: пересылка сообщений (текст, фото, голос, стикеры) без раскрытия контактов
- Индекс совместимости: расчёт по ключевым словам, длине текста, тайм-трекеру, эмодзи; прогресс-бар в чате; разблокировки 16–30% (плейлист), 31–50% (челленджи)
- Сценарии: «Спасите индекс» (молчание >6 ч), «Конфликт» (негатив/мат — заморозка 3 ч)
