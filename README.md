# НМЦК Расчет система

Система для автоматического расчета начальной максимальной цены контракта (НМЦК) на основе анализа госзакупок.

## Архитектура

Проект состоит из следующих компонентов:

### Backend (FastAPI)
- **FastAPI** - современный, быстрый веб-фреймворк для Python
- **PostgreSQL** - основная база данных
- **Redis** - кэширование и очередь задач
- **Celery** - асинхронная обработка задач

### Frontend
- Статический SPA на основе HTML/CSS/JavaScript
- Интерфейс соответствует макету `frontend/index.html`

### Инфраструктура
- **Docker** - контейнеризация приложений
- **Docker Compose** - оркестрация сервисов
- **Nginx** - обратный прокси и статический сервер

## Быстрый старт

### Предварительные требования
- Docker и Docker Compose
- Git

### Установка и запуск

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd test-nmc-mvp
```

2. Настройте переменные окружения:
```bash
cp .env.example .env
# Отредактируйте .env файл, добавьте ваш DEEPSEEK_API_KEY
```

3. Запустите приложение с помощью Docker Compose:
```bash
docker-compose up -d
```

4. Приложение будет доступно по адресам:
   - Frontend: http://localhost
   - Backend API: http://localhost/api
   - API документация: http://localhost/api/docs

5. Для остановки приложения:
```bash
docker-compose down
```

## Структура проекта

```
├── backend/                 # Backend приложение на FastAPI
│   ├── main.py             # Основной файл приложения
│   ├── requirements.txt    # Зависимости Python
│   └── Dockerfile          # Docker конфигурация для backend
├── frontend/               # Frontend приложение
│   └── index.html          # Основной HTML файл
├── nginx/                  # Nginx конфигурация
│   └── nginx.conf
├── docker-compose.yml      # Docker Compose конфигурация
├── init-db.sql            # SQL скрипт инициализации БД
├── .env.example           # Пример переменных окружения
├── .gitignore            # Git ignore файл
└── README.md             # Документация
```

## API Endpoints

### Основные endpoints:
- `GET /` - информация о API
- `GET /health` - проверка здоровья сервиса
- `POST /api/search` - создать новый поиск контрактов
- `GET /api/search` - список поисков
- `GET /api/search/{id}` - детали поиска
- `POST /api/search/{id}/stop` - остановить поиск
- `GET /api/search/{id}/results` - результаты поиска
- `GET /api/search/{id}/events` - события поиска (SSE)
- `GET /api/search/{id}/report` - скачать отчет

## Конфигурация

### Переменные окружения

Основные переменные окружения, которые необходимо настроить:

- `DEEPSEEK_API_KEY` - API ключ для DeepSeek AI
- `DATABASE_URL` - строка подключения к PostgreSQL
- `REDIS_URL` - строка подключения к Redis
- `ENVIRONMENT` - окружение (development/staging/production)

Полный список переменных смотрите в `.env.example`.

## Разработка

### Локальная разработка без Docker

1. Установите зависимости:
```bash
cd backend
pip install -r requirements.txt
```

2. Запустите PostgreSQL и Redis (через Docker или локально):
```bash
docker run --name nmck-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:15
docker run --name nmck-redis -p 6379:6379 -d redis:7-alpine
```

3. Создайте базу данных:
```bash
psql -h localhost -U postgres -c "CREATE DATABASE nmck_db;"
psql -h localhost -U postgres -d nmck_db -f ../init-db.sql
```

4. Запустите backend:
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

5. Запустите frontend:
```bash
cd frontend
python -m http.server 3000
```

### Запуск тестов

```bash
cd backend
pytest
```

## Деплой

### Продакшен деплой

1. Обновите `.env` файл для продакшена:
   - Установите `ENVIRONMENT=production`
   - Настройте безопасные пароли для БД
   - Добавьте SSL сертификаты для Nginx

2. Соберите и запустите:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Мониторинг

### Логи
```bash
# Просмотр логов всех сервисов
docker-compose logs -f

# Просмотр логов конкретного сервиса
docker-compose logs -f backend
docker-compose logs -f postgres
```

### Статус сервисов
```bash
docker-compose ps
```

### Проверка здоровья
```bash
curl http://localhost/health
```

## Лицензия

[Указать лицензию]

## Контакты

[Контактная информация]