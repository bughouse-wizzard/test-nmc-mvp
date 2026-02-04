from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

app = FastAPI(title="НМЦК Поиск Система", description="Система поиска НМЦК для госзакупок")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def root():
    """Redirect to the main application page"""
    return {"message": "НМЦК Поиск Система. Перейдите на /static/index.html"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify connection"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "nmck-search-system",
            "version": "1.0.0",
            "timestamp": "2026-02-04T11:45:00Z"
        }
    )

@app.get("/api/info")
async def system_info():
    """System information endpoint"""
    return {
        "name": "НМЦК Поиск Система",
        "description": "Система автоматического поиска и расчета НМЦК для госзакупок",
        "version": "1.0.0",
        "author": "OpenHands AI",
        "endpoints": {
            "health": "/api/health",
            "static": "/static/",
            "main_page": "/static/index.html"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)