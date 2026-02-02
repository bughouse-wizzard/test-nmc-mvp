# NMCK Search API - Full Stack Application

FastAPI-based application for searching and analyzing government procurement contracts to calculate NMCK (Начальная максимальная цена контракта). This is a full-stack application with a comprehensive backend and integrated frontend.

## Features

- **FastAPI** backend with async PostgreSQL support
- **PostgreSQL** database for storing search requests and contract results
- **Redis** for caching and Celery task queue
- **Celery** workers for background processing
- **Docker** and **docker-compose** for easy deployment
- **DeepSeek AI** integration for contract analysis
- **REST API** with OpenAPI documentation
- **Integrated Frontend** with HTML, CSS, and JavaScript

## Project Structure

```
.
├── app/
│   ├── api/              # API endpoints
│   ├── core/             # Core configuration and database
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   ├── static/           # Frontend static files
│   │   ├── index.html    # Main HTML page
│   │   ├── css/          # CSS styles
│   │   └── js/           # JavaScript logic
│   └── workers/          # Celery workers and tasks
├── tests/                # Test files
├── alembic/              # Database migrations
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile           # Docker image definition
├── requirements.txt     # Python dependencies
├── .env                # Environment variables
└── README.md           # This file
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.12+ (for local development)

### Using Docker Compose

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
   - Web Interface: http://localhost:8000/
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

### Local Development

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

- `GET /` - Root endpoint (serves frontend)
- `GET /health` - Health check endpoint
- `GET /api/search` - Mock search history data

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

## Development

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

## Deployment

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

## License

[Add your license here]

## Support

For issues and feature requests, please use the issue tracker.
