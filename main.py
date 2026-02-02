from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

app = FastAPI(title="НМЦК Поиск API", description="API для поиска НМЦК в системе госзакупок")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def read_root():
    """Serve the main index.html file"""
    from fastapi.responses import FileResponse
    return FileResponse("app/static/index.html")

@app.get("/api/health")
async def health_check():
    """Health check endpoint to verify connection"""
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "nmck-search-api",
            "version": "1.0.0"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)