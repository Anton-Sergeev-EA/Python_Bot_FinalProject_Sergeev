Дипломный проект: Telegram-бот для аренды вещей
Имя Фамилия — Сергеев Антон
логин на GitHub — https://github.com/Anton-Sergeev-EA/Python_Bot_FinalProject_Sergeev
e-mail — kavery@mail.ru

# RentFromAntonBot - Telegram Bot для аренды вещей.
Бот для аренды вещей с функциями размещения объявлений, поиска, модерации и уведомлений.

## Функции.
1. **Размещение объявлений** - пользователи могут размещать объявления об аренде товаров
2. **Поиск объявлений** - фильтрация по ключевым словам, местоположению и стоимости
3. **Связь с владельцем** - возможность связаться напрямую через Telegram
4. **Редактирование объявлений** - изменение и удаление своих объявлений
5. **Уведомления** - уведомления о новых подходящих объявлениях и сообщениях
6. **Модерация** - проверка объявлений перед публикацией
7. **Обратная связь** - система отзывов о товарах и боте

## Установка.
### Локальная разработка.
1. Клонировать репозиторий:
git clone <repository-url>
cd RentFromAntonBot
2. Создать виртуальное окружение:
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
3. Установить зависимости:
pip install -r requirements.txt
4. Настроить переменные окружения:
cp .env.example .env
# Отредактировать .env файл
5. Запустить базу данных:
docker-compose up -d postgres
6. Запустить бота:
python main.py

Docker.
docker-compose up --build

Конфигурация.
Создайте файл .env со следующими переменными:
BOT_TOKEN=your_bot_token_here
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/RentFromAnton
ADMIN_IDS=123456789,987654321
LOG_LEVEL=INFO

База данных.
Бот использует PostgreSQL. Схема базы данных включает:
- Пользователи.
- Объявления.
- Сообщения.
- Отзывы.
- Поисковые запросы.
- Модерация.

Безопасность.
- Токен бота хранится в переменных окружения.
- Все пароли хешируются.
- SQL-инъекции предотвращаются через параметризованные запросы.
- Валидация входных данных.
- Модерация контента перед публикацией.

Лицензия.
MIT License - см. LICENSE.md

## Шаг 3: Создание конфигурационных файлов
### .env.example
# Bot Configuration
BOT_TOKEN=your_bot_token_here
BOT_USERNAME=RentFromAntonBot
# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/RentFromAnton
# Admin Configuration (comma-separated user IDs)
ADMIN_IDS=123456789
# Redis Configuration (for caching and job queue)
REDIS_URL=redis://localhost:6379/0
# Logging
LOG_LEVEL=INFO
# Notification Settings
NOTIFICATION_CHECK_INTERVAL=10  # minutes

Структура проекта:
RentFromAntonBot/
├── .env
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── LICENSE.md
├── README.md
├── requirements.txt
├── main.py
├── config/
│   ├ __init__.py
│   └ settings.py
├── database/
│   ├ __init__.py
│   ├ models.py
│   ├ crud.py
│   └ connection.py
├── bot/
│   ├ __init__.py
│   ├ handlers/
│   │   ├ __init__.py
│   │   ├ start.py
│   │   ├ ads.py
│   │   ├ search.py
│   │   ├ moderation.py
│   │   ├ feedback.py
│   │   └ notifications.py
│   ├ keyboards/
│   │   ├ __init__.py
│   │   └ inline_keyboards.py
│   ├ states.py
│   └ utils.py
├── tests/
│   ├ __init__.py
│   ├ test_models.py
│   └ test_handlers.py
└── scheduler/
    ├ __init__.py
    └ jobs.py
