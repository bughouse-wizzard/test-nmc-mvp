from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
import os

app = FastAPI(title="Поиск НМЦК - ЕИС Госзакупки", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def read_root():
    # Serve the main HTML file
    return FileResponse("index.html")

@app.get("/api/health")
async def health_check():
    """Mock endpoint to verify connection"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "nmck-search-api",
            "version": "1.0.0",
            "timestamp": "2026-02-02T13:34:00Z"
        }
    )

@app.get("/api/search")
async def get_searches():
    """Mock endpoint for getting search history"""
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
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)