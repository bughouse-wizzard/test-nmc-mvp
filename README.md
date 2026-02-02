# NMCK Search API / НМЦК Поиск Система

FastAPI-based application for searching and analyzing government procurement contracts to calculate NMCK (Начальная максимальная цена контракта).

Система для автоматизированного поиска контрактов и расчёта начальной максимальной цены контракта (НМЦК).

## Features / Особенности

- **FastAPI** backend with async PostgreSQL support
- **PostgreSQL** database for storing search requests and contract results
- **Redis** for caching and Celery task queue
- **Celery** workers for background processing
- **Docker** and **docker-compose** for easy deployment
- **DeepSeek AI** integration for contract analysis
- **REST API** with OpenAPI documentation
- **Web Interface** with HTML/CSS/JavaScript frontend
- **Search functionality** with filtering and pagination
- **Contract comparison** with modal dialogs

## Project Structure / Структура проекта

```
.
├── app/
│   ├── api/              # API endpoints
│   ├── core/             # Core configuration and database
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   ├── workers/          # Celery workers and tasks
│   └── static/           # Frontend static files
│       ├── index.html    # Main HTML page
│       ├── css/
│       │   └── styles.css # CSS styles
│       └── js/
│           └── app.js    # JavaScript logic
├── tests/                # Test files
├── alembic/              # Database migrations
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile           # Docker image definition
├── requirements.txt     # Python dependencies
├── .env                # Environment variables
├── main.py             # FastAPI application
├── test_app.py         # Structure tests
└── README.md           # This file
```

## Quick Start / Быстрый старт

### Prerequisites / Требования

- Docker and Docker Compose
- Python 3.12+ (for local development)

### Using Docker Compose / Использование Docker Compose

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd nmck-search
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env file with your settings
   ```

3. Start the services:
   ```bash
   docker-compose up -d
   ```

4. Access the application:
   - Web Interface: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

### Local Development / Локальная разработка

1. Create and activate virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env file
   ```

4. Run the application:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## API Endpoints

### Search Management

- `POST /api/v1/search` - Create a new search
- `GET /api/v1/search` - List all searches
- `GET /api/v1/search/{id}` - Get search by ID
- `POST /api/v1/search/{id}/stop` - Stop a running search
- `GET /api/v1/search/{id}/results` - Get search results

### Contract Management

- `GET /api/v1/contracts/{id}` - Get contract by ID
- `GET /api/v1/contracts/{id}/comparison` - Get contract specification comparison

### Health Check

- `GET /` - Root endpoint (web interface)
- `GET /health` - Health check endpoint
- `GET /api/info` - System information

### Static Files

- `GET /static/{path}` - Static files (CSS, JS, HTML)

## Web Interface Features / Функциональность веб-интерфейса

The interface includes:
- Contract search by KTRU and parameters
- Search history with pagination
- Results table with filtering
- Contract selection for NMCK calculation
- Modal dialogs for specification comparison
- Action notifications

Интерфейс включает:
- Поиск контрактов по КТРУ и параметрам
- История поисков с пагинацией
- Таблица результатов с фильтрацией
- Выбор контрактов для расчёта НМЦК
- Модальные окна для сравнения характеристик
- Уведомления о действиях

## Database Schema

### Search Request
- `id` - UUID primary key
- `status` - Search status (RUNNING, DONE, STOPPED, ERROR)
- `object_name` - Object name
- `ktru_code` - KTRU code
- `customer_region` - Customer region
- `found_total` - Total contracts found
- `processed_count` - Number of processed contracts
- `nmc_value` - Calculated NMCK value

### Contract Result
- `id` - UUID primary key
- `search_id` - Foreign key to search request
- `reestr_number` - Registry number
- `contract_url` - Contract URL
- `match_type` - Match type (IDENTICAL, HOMOGENEOUS, NO_MATCH)
- `ai_score` - AI score (0-100)
- `unit_price` - Unit price

### Specification Comparison
- `id` - UUID primary key
- `contract_result_id` - Foreign key to contract result
- `name` - Specification name
- `target_value` - Target value
- `actual_value` - Actual value
- `match_status` - Match status (MATCH, DIFF, UNKNOWN)

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `POSTGRES_USER` | PostgreSQL username | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `postgres` |
| `POSTGRES_DB` | PostgreSQL database name | `nmck_db` |
| `POSTGRES_SERVER` | PostgreSQL server host | `db` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `REDIS_HOST` | Redis host | `redis` |
| `REDIS_PORT` | Redis port | `6379` |
| `REDIS_DB` | Redis database | `0` |
| `DEEPSEEK_API_KEY` | DeepSeek API key | (required) |
| `DEBUG` | Debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Development / Разработка

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black app/
isort app/
```

### Type Checking

```bash
mypy app/
```

### Database Migrations

```bash
# Generate new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

## Deployment / Развёртывание

### Production Considerations

1. Update `.env` file with production values
2. Set `DEBUG=false`
3. Use proper SSL/TLS certificates
4. Configure firewall rules
5. Set up monitoring and logging
6. Configure backup strategy

### Scaling

- Increase `docker-compose` replicas for app and worker services
- Use PostgreSQL connection pooling
- Configure Redis clustering for high availability
- Implement load balancing

## Technologies / Технологии

- **Backend**: FastAPI (Python)
- **Frontend**: HTML, CSS, JavaScript
- **Styling**: Tailwind CSS, Font Awesome
- **Server**: Uvicorn (ASGI server)
- **Database**: PostgreSQL with SQLAlchemy
- **Cache/Task Queue**: Redis with Celery
- **AI Integration**: DeepSeek API
- **Containerization**: Docker, Docker Compose

## License

[Add your license here]

## Support

For issues and feature requests, please use the issue tracker.
