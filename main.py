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
            "service": "НМЦК Поиск Система",
            "version": "1.0.0",
            "timestamp": "2024-01-01T00:00:00Z"  # This would be dynamic in production
        }
    )

@app.get("/api/info")
async def get_info():
    """Get system information"""
    return JSONResponse(
        content={
            "name": "Система поиска НМЦК",
            "description": "Автоматизированная система определения начальной максимальной цены контракта",
            "features": [
                "Поиск контрактов по КТРУ",
                "Парсинг документов закупок",
                "AI-скоринг соответствия",
                "Расчёт НМЦК"
            ]
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)