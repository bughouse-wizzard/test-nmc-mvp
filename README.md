# НМЦК Расчет система / NMC Calculation System

Система для автоматического расчета начальной максимальной цены контракта (НМЦК) на основе анализа госзакупок.
System for automatic calculation of the initial maximum contract price (NMC) based on analysis of government procurement.

## Архитектура / Architecture

Проект состоит из следующих компонентов:
The project consists of the following components:

### Backend (FastAPI)
- **FastAPI** - современный, быстрый веб-фреймворк для Python
- **PostgreSQL** - основная база данных
- **Redis** - кэширование и очередь задач
- **Celery** - асинхронная обработка задач

### Frontend
- Статический SPA на основе HTML/CSS/JavaScript
- Интерфейс соответствует макету `frontend/index.html`

### Инфраструктура / Infrastructure
- **Docker** - контейнеризация приложений
- **Docker Compose** - оркестрация сервисов
- **Nginx** - обратный прокси и статический сервер

## Быстрый старт / Quick Start

### Предварительные требования / Prerequisites
- Docker и Docker Compose
- Git

### Установка и запуск / Installation and Launch

1. Клонируйте репозиторий / Clone the repository:
```bash
git clone <repository-url>
cd test-nmc-mvp
```

2. Настройте переменные окружения / Configure environment variables:
```bash
cp .env.example .env
# Отредактируйте .env файл, добавьте ваш DEEPSEEK_API_KEY
# Edit the .env file, add your DEEPSEEK_API_KEY
```

3. Запустите приложение с помощью Docker Compose / Launch the application using Docker Compose:
```bash
docker-compose up -d
```

4. Приложение будет доступно по адресам / The application will be available at:
   - Frontend: http://localhost
   - Backend API: http://localhost/api
   - API документация / API documentation: http://localhost/api/docs

5. Для остановки приложения / To stop the application:
```bash
docker-compose down
```

## Структура проекта / Project Structure

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
├── src/nmc_mvp/           # Database models and configuration
│   ├── config/
│   │   └── settings.py          # Application settings
│   ├── database/
│   │   └── database.py          # Database connection and session
│   └── models/
│       ├── __init__.py          # Model exports
│       ├── base.py              # Base model with common fields
│       ├── enums.py             # Enum definitions
│       ├── search_request.py    # SearchRequest model
│       ├── contract_result.py   # ContractResult model
│       └── spec_comparison_row.py # SpecComparisonRow model
├── alembic/                     # Alembic migrations
│   ├── versions/                # Migration scripts
│   ├── env.py                   # Alembic environment
│   └── script.py.mako           # Migration template
├── alembic.ini                  # Alembic configuration
├── requirements.txt             # Python dependencies (for database models)
├── test_models.py              # Model test script
└── README.md                   # This file
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

## Database Models

### Database Tables

#### 1. `search_request`
Stores search requests with the following fields:
- `id` (UUID) - Primary key
- `created_at`, `updated_at` - Timestamps
- `status` (enum: RUNNING|DONE|STOPPED|ERROR) - Search status
- `input_source` (enum: MANUAL|FILE) - Source of search input
- `object_name` - Name of procurement object
- `ktru_code` - KTRU code
- `okpd2_code` - OKPD2 code (optional)
- `customer_region` - Customer region (default: СЗФО)
- `law` - Procurement law (default: 44)
- `date_from`, `date_to` - Date range for search
- `execution_statuses` (array) - Contract execution statuses
- `limit_contracts` - Limit of contracts to process (default: 30)
- `found_total` - Total contracts found on website
- `processed_count` - Number of contracts processed
- `nmc_value` - Calculated NMC value
- `selected_contract_ids` (array) - IDs of selected contracts for NMC calculation
- `runtime_ms` - Search runtime in milliseconds
- `error_message` - Error message if search failed
- `user_id` - User ID (for future authorization)
- `search_parameters_json` - Raw search parameters as JSON

#### 2. `contract_result`
Stores contract analysis results with the following fields:
- `id` (UUID) - Primary key
- `search_id` (UUID) - Foreign key to search_request
- `reestr_number` - Contract registry number
- `contract_url` - URL to contract card
- `sign_date` - Contract signing date
- `unit_price` - Price per unit (nullable)
- `currency` - Currency (default: RUB)
- `match_type` - Match type (IDENTICAL|HOMOGENEOUS|NO_MATCH)
- `ai_score` (0-100) - AI matching score
- `manufacturer_target` - Target manufacturer
- `manufacturer_found` - Found manufacturer
- `manufacturer_match` - Manufacturer match flag
- `is_2025_plus` - Flag for contracts from 2025+
- `accepted_for_nmc` - Flag if contract accepted for NMC calculation
- `raw_data_json` - Raw parsed contract data as JSON
- `contract_price` - Total contract price
- `customer_name` - Customer name
- `supplier_name` - Supplier name

#### 3. `spec_comparison_row`
Stores specification comparison details with the following fields:
- `id` (UUID) - Primary key
- `contract_result_id` (UUID) - Foreign key to contract_result
- `name` - Characteristic name
- `target_value` - Required value from TZ
- `actual_value` - Actual value from contract
- `match_status` (enum: MATCH|DIFF|UNKNOWN) - Match status
- `weight` - Importance weight (default: 1.0)
- `unit` - Unit of measurement
- `notes` - Additional notes

### Database Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure database connection:**
   - Update `DATABASE_URL` in `.env` file
   - Or set environment variable: `export DATABASE_URL=postgresql://user:pass@host:port/dbname`

3. **Run database migrations:**
   ```bash
   # Create initial migration (already done)
   alembic revision --autogenerate -m "Initial migration"
   
   # Apply migrations
   alembic upgrade head
   ```

4. **Test the models:**
   ```bash
   python test_models.py
   ```

### Usage Examples

```python
from src.nmc_mvp.database.database import SessionLocal
from src.nmc_mvp.models import SearchRequest, ContractResult, SpecComparisonRow
from src.nmc_mvp.models.enums import SearchStatus, InputSource, MatchStatus
from datetime import datetime, timezone

# Create a database session
db = SessionLocal()

# Create a search request
search = SearchRequest(
    input_source=InputSource.MANUAL,
    object_name="Бумага офисная",
    ktru_code="24.11.11.110",
    date_from=datetime(2023, 1, 1, tzinfo=timezone.utc),
    date_to=datetime(2026, 1, 1, tzinfo=timezone.utc),
    status=SearchStatus.RUNNING
)

# Create a contract result
contract = ContractResult(
    search_id=search.id,
    reestr_number="0373200004523000010",
    contract_url="https://zakupki.gov.ru/...",
    sign_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
    match_type="IDENTICAL",
    ai_score=95,
    accepted_for_nmc=True
)

# Create specification comparison
spec = SpecComparisonRow(
    contract_result_id=contract.id,
    name="Плотность",
    target_value="80 г/м²",
    actual_value="80 г/м²",
    match_status=MatchStatus.MATCH
)

# Save to database
db.add(search)
db.add(contract)
db.add(spec)
db.commit()
```

### Migration Commands

- **Create new migration:** `alembic revision --autogenerate -m "Description"`
- **Apply migrations:** `alembic upgrade head`
- **Rollback migration:** `alembic downgrade -1`
- **Show migration history:** `alembic history`
- **Show current revision:** `alembic current`

## Конфигурация / Configuration

### Переменные окружения / Environment Variables

Основные переменные окружения, которые необходимо настроить:
Main environment variables that need to be configured:

- `DEEPSEEK_API_KEY` - API ключ для DeepSeek AI
- `DATABASE_URL` - строка подключения к PostgreSQL
- `REDIS_URL` - строка подключения к Redis
- `ENVIRONMENT` - окружение (development/staging/production)

Полный список переменных смотрите в `.env.example`.
See the full list of variables in `.env.example`.

## Разработка / Development

### Локальная разработка без Docker / Local Development without Docker

1. Установите зависимости / Install dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. Запустите PostgreSQL и Redis (через Docker или локально) / Start PostgreSQL and Redis (via Docker or locally):
```bash
docker run --name nmck-postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres:15
docker run --name nmck-redis -p 6379:6379 -d redis:7-alpine
```

3. Создайте базу данных / Create database:
```bash
psql -h localhost -U postgres -c "CREATE DATABASE nmck_db;"
psql -h localhost -U postgres -d nmck_db -f ../init-db.sql
```

4. Запустите backend / Start backend:
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

5. Запустите frontend / Start frontend:
```bash
cd frontend
python -m http.server 3000
```

### Запуск тестов / Running Tests

```bash
cd backend
pytest
```

## Деплой / Deployment

### Продакшен деплой / Production Deployment

1. Обновите `.env` файл для продакшена / Update `.env` file for production:
   - Установите `ENVIRONMENT=production`
   - Настройте безопасные пароли для БД / Configure secure passwords for database
   - Добавьте SSL сертификаты для Nginx / Add SSL certificates for Nginx

2. Соберите и запустите / Build and run:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Мониторинг / Monitoring

### Логи / Logs
```bash
# Просмотр логов всех сервисов / View logs of all services
docker-compose logs -f

# Просмотр логов конкретного сервиса / View logs of specific service
docker-compose logs -f backend
docker-compose logs -f postgres
```

### Статус сервисов / Service Status
```bash
docker-compose ps
```

### Проверка здоровья / Health Check
```bash
curl http://localhost/health
```

## Лицензия / License

[Указать лицензию / Specify license]

## Контакты / Contacts

[Контактная информация / Contact information]