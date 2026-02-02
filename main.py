from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

app = FastAPI(title="НМЦК Поиск API", description="API для поиска НМЦК в ЕИС Госзакупки")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def root():
    return {"message": "НМЦК Поиск API работает. Перейдите на /static/index.html для доступа к интерфейсу."}

@app.get("/api/health")
async def health_check():
    """Проверка состояния API"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "nmck-search-api",
            "version": "1.0.0",
            "timestamp": "2026-02-02T11:47:00Z"
        }
    )

@app.get("/api/info")
async def api_info():
    """Информация о API"""
    return {
        "name": "НМЦК Поиск API",
        "description": "API для поиска нормативных максимальных цен контрактов",
        "endpoints": [
            {"path": "/", "method": "GET", "description": "Корневой эндпоинт"},
            {"path": "/api/health", "method": "GET", "description": "Проверка состояния сервиса"},
            {"path": "/api/info", "method": "GET", "description": "Информация о API"},
            {"path": "/static/{path:path}", "method": "GET", "description": "Статические файлы фронтенда"}
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)