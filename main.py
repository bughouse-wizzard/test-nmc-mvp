from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

app = FastAPI(title="НМЦК Поиск Система", description="Система поиска и расчета начальной максимальной цены контракта")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def read_root():
    """Serve the main HTML page"""
    return {"message": "НМЦК Поиск Система API. Перейдите к /static/index.html для интерфейса"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify connection"""
    return JSONResponse(
        content={
            "status": "healthy",
            "service": "nmck-search-system",
            "version": "1.0.0"
        }
    )

@app.get("/api/info")
async def get_system_info():
    """Get system information"""
    return {
        "name": "НМЦК Поиск Система",
        "description": "Система автоматического поиска контрактов и расчета НМЦК",
        "version": "1.0.0",
        "author": "OpenHands AI",
        "endpoints": [
            "/api/health - Проверка состояния системы",
            "/api/info - Информация о системе",
            "/static/ - Статический фронтенд"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)