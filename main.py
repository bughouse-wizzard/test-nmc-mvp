from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os

app = FastAPI(title="НМЦК Поиск API", description="API для поиска НМЦК в системе госзакупок")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML page"""
    html_path = os.path.join("app/static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify connection"""
    return {
        "status": "ok",
        "service": "nmck-search-api",
        "version": "1.0.0",
        "message": "Сервис поиска НМЦК работает нормально"
    }

@app.get("/api/search")
async def get_search_history():
    """Mock endpoint for search history"""
    return {
        "searches": [
            {
                "id": 101,
                "date": "2026-01-21",
                "name": "Бумага офисная A4",
                "ktru": "17.12.14.110",
                "status": "Завершен",
                "found": 45,
                "avg": 420.50
            },
            {
                "id": 102,
                "date": "2026-01-20",
                "name": "АРМ (Компьютеры)",
                "ktru": "26.20.15.000",
                "status": "Завершен",
                "found": 15,
                "avg": 54400.00
            }
        ],
        "total": 2,
        "page": 1,
        "page_size": 10
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)