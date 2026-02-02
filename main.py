from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
import os

app = FastAPI(title="НМЦК Поиск Система", version="1.0.0")

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
    """Health check endpoint to verify API connection"""
    return JSONResponse(
        content={
            "status": "healthy",
            "service": "nmck-search-system",
            "version": "1.0.0",
            "timestamp": "2026-02-02T13:00:00Z"
        }
    )

@app.get("/api/info")
async def get_system_info():
    """Get system information"""
    return JSONResponse(
        content={
            "name": "Система поиска НМЦК",
            "description": "Автоматизированная система определения начальной максимальной цены контракта",
            "features": [
                "Поиск контрактов по КТРУ и параметрам",
                "Парсинг документов состоявшихся закупок",
                "AI-скоринг соответствия",
                "Расчёт НМЦК на основе 3 контрактов"
            ],
            "api_endpoints": [
                "/api/health - Проверка состояния системы",
                "/api/info - Информация о системе",
                "/ - Главная страница интерфейса"
            ]
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)