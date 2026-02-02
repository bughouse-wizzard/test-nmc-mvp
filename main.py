from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

app = FastAPI(title="НМЦК Поиск", description="Система поиска начальной максимальной цены контракта")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def root():
    return {"message": "НМЦК Поиск API"}

@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify connection"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "nmck-search",
            "version": "1.0.0",
            "timestamp": "2026-02-02T19:45:00Z"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)