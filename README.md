# NMCK Calculation System

A system for calculating the initial maximum contract price (NMCK) by analyzing historical procurement contracts using AI and web scraping.

## Features

- **AI-Powered Contract Analysis**: Uses DeepSeek AI to extract technical specifications from contracts
- **Web Scraping**: Automatically fetches contract data from zakupki.gov.ru
- **Specification Comparison**: Compares target specifications with actual contract specifications
- **NMCK Calculation**: Calculates the initial maximum contract price based on historical data
- **Debug Logging**: Comprehensive logging of AI responses and parser HTML for debugging

## Prerequisites

- Docker and Docker Compose
- DeepSeek API key (free tier available)

## Quick Start

### 1. Set up environment variables

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Edit the `.env` file and set your DeepSeek API key:

```env
# DeepSeek AI API Configuration
DEEPSEEK_API_KEY=your-deepseek-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

### 2. Get a DeepSeek API Key

1. Go to [DeepSeek Platform](https://platform.deepseek.com/)
2. Sign up for a free account
3. Navigate to the API section
4. Generate a new API key
5. Copy the key and paste it in your `.env` file

### 3. Run the application

Start the full stack with Docker Compose:

```bash
docker-compose up -d
```

This will start:
- **Backend API** (port 8000)
- **PostgreSQL database** (port 5432)
- **Redis** (port 6379)
- **Nginx** (port 80)
- **Celery worker** for background tasks
- **Celery beat** for scheduled tasks

### 4. Access the application

- **Frontend**: http://localhost
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## Project Structure

```
├── backend/              # FastAPI backend application
│   ├── app/             # Main application code
│   │   ├── api/         # API endpoints
│   │   ├── core/        # Core configuration and utilities
│   │   ├── models/      # Database models
│   │   ├── schemas/     # Pydantic schemas
│   │   └── worker/      # Celery worker tasks
│   ├── services/        # Business logic services
│   │   ├── ai/          # AI client for DeepSeek API
│   │   └── parser/      # Web parsers for zakupki.gov.ru
│   └── tests/           # Test suite
├── frontend/            # React frontend application
├── nginx/               # Nginx configuration
├── alembic/             # Database migrations
└── docker-compose.yml   # Docker Compose configuration
```

## Configuration

### Environment Variables

Key environment variables to configure:

| Variable | Description | Default |
|----------|-------------|---------|
| `DEEPSEEK_API_KEY` | **Required**: Your DeepSeek API key | - |
| `DEBUG` | Enable debug mode | `false` |
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://postgres:postgres@db:5432/nmck_db` |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `ZAKUPKI_BASE_URL` | Base URL for procurement portal | `https://zakupki.gov.ru` |
| `CRAWL_DELAY` | Delay between requests (respects robots.txt) | `60` |
| `WORKER_CONCURRENCY` | Number of concurrent worker processes | `2` |

### Database Migrations

The application uses Alembic for database migrations. To apply migrations:

```bash
# Run inside the backend container
docker-compose exec backend alembic upgrade head
```

To create a new migration after model changes:

```bash
docker-compose exec backend alembic revision --autogenerate -m "Description of changes"
```

## Debugging and Logging

### AI Response Debugging

The system logs all AI request and response data for debugging:

1. **Raw AI responses** are stored in the `debug_data` field of `ContractResult` records
2. **Parser HTML** is stored in both `SearchRequest.debug_data` and `ContractResult.raw_data_json.debug_data`
3. **Debug data includes**:
   - AI request parameters and response metadata
   - Raw HTML from zakupki.gov.ru (first 5000 characters)
   - Processing timestamps
   - Error information

### Accessing Debug Data

Debug data can be accessed through:
- Database queries on the `debug_data` JSON field
- API responses (when debug mode is enabled)
- Application logs

### Robots.txt Compliance

The system respects zakupki.gov.ru's robots.txt requirements:
- **Crawl delay**: 60 seconds between requests (configured via `CRAWL_DELAY`)
- **Respects allowed/disallowed paths**
- **Implements exponential backoff** for rate limiting

## API Usage

### Search for Contracts

```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{
    "object_name": "Laptop",
    "ktru_code": "32.30.11.110",
    "customer_region": "СЗФО",
    "date_from": "2024-01-01",
    "date_to": "2024-12-31"
  }'
```

### Check Search Status

```bash
curl "http://localhost:8000/api/v1/search/{search_id}/status"
```

### Get Search Results

```bash
curl "http://localhost:8000/api/v1/search/{search_id}/results"
```

## Development

### Running Tests

```bash
# Run tests inside the backend container
docker-compose exec backend pytest
```

### Code Quality

```bash
# Format code with black
docker-compose exec backend black .

# Check code style with flake8
docker-compose exec backend flake8 .

# Type checking with mypy
docker-compose exec backend mypy .
```

### Local Development Without Docker

1. Install Python dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   ```bash
   export DEEPSEEK_API_KEY=your-key-here
   export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/nmck_db
   ```

3. Run the application:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

## Troubleshooting

### Common Issues

1. **AI API errors**: Verify your `DEEPSEEK_API_KEY` is valid and has sufficient credits
2. **Database connection errors**: Ensure PostgreSQL is running and accessible
3. **Parser errors**: Check network connectivity to zakupki.gov.ru
4. **Rate limiting**: The system implements retry logic with exponential backoff

### Logs

View application logs:

```bash
# Backend logs
docker-compose logs backend

# Worker logs
docker-compose logs worker

# Database logs
docker-compose logs db
```

### Database Reset

To reset the database:

```bash
# Stop containers
docker-compose down

# Remove volumes
docker-compose down -v

# Restart
docker-compose up -d
```

## License

[Add your license information here]

## Support

For issues and feature requests, please use the issue tracker or contact the development team.