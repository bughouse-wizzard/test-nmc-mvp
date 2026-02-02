# НМЦК Поиск Система - FastAPI Integration

This project integrates a static frontend with a FastAPI backend for the НМЦК (Начальная Максимальная Цена Контракта) поисковая система.

## Project Structure

```
.
├── main.py                 # FastAPI application entry point
├── requirements.txt        # Python dependencies
├── README.md              # This file
└── app/
    └── static/
        ├── index.html     # Main HTML frontend
        ├── css/
        │   └── styles.css # Extracted CSS styles
        └── js/
            └── app.js     # Extracted JavaScript logic
```

## Installation

1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the FastAPI server:
   ```bash
   python main.py
   ```

## Usage

### Access the Application

1. **Frontend Interface**: Open your browser and navigate to:
   ```
   http://localhost:8000/static/index.html
   ```

2. **API Endpoints**:
   - Health Check: `GET http://localhost:8000/api/health`
   - System Info: `GET http://localhost:8000/api/info`
   - Root: `GET http://localhost:8000/`

### Features

- **Static File Serving**: All frontend assets (HTML, CSS, JS) are served from `/static/` path
- **API Backend**: RESTful API endpoints for health checks and system information
- **Code Separation**: Clean separation between frontend and backend code
- **Production Ready**: FastAPI provides async support, automatic documentation, and scalability

## Development

### Adding New Static Files
Place any new static files (images, fonts, additional CSS/JS) in the `app/static/` directory.

### Adding API Endpoints
Add new endpoints to `main.py` following FastAPI conventions.

### Testing
The application includes basic health check endpoints for monitoring.

## API Documentation

Once the server is running, you can access:
- Interactive API docs: `http://localhost:8000/docs`
- Alternative API docs: `http://localhost:8000/redoc`

## Deployment

For production deployment:
1. Use a production ASGI server like `uvicorn` with workers
2. Configure reverse proxy (nginx, Apache)
3. Set up environment variables as needed
4. Consider using Docker for containerization

## Notes

- The frontend was originally a standalone HTML file (`front13.html`)
- All functionality has been preserved during the integration
- The system is ready for further backend API development
- Static files are efficiently served with proper caching headers