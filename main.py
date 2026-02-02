from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
import os

app = FastAPI(title="НМЦК Поиск Система", description="Система поиска НМЦК для госзакупок")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def read_root():
    """Serve the main index.html file"""
    return FileResponse("app/static/index.html")

@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify connection"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "nmck-search-system",
            "version": "1.0.0",
            "endpoints": {
                "static_files": "/static",
                "main_page": "/",
                "health_check": "/api/health"
            }
        }
    )

@app.get("/api/search")
async def get_search_history():
    """Mock endpoint for search history"""
    return JSONResponse(
        status_code=200,
        content={
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
            ]
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)