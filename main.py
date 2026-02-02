from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="НМЦК Поиск API",
    description="API для поиска и анализа контрактов для расчета НМЦК",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Health check endpoint
@app.get("/api/health")
async def health_check():
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": "nmck-search-api",
            "version": "1.0.0"
        }
    )

# Root endpoint - serve the main page
@app.get("/")
async def root():
    return {"message": "НМЦК Поиск API is running. Access the frontend at /static/index.html"}

# Mock search endpoint
@app.post("/api/search")
async def create_search():
    return JSONResponse(
        status_code=200,
        content={
            "search_id": "mock-search-123",
            "status": "running",
            "message": "Search started successfully"
        }
    )

# Mock search status endpoint
@app.get("/api/search/{search_id}")
async def get_search_status(search_id: str):
    return JSONResponse(
        status_code=200,
        content={
            "search_id": search_id,
            "status": "completed",
            "found_total": 45,
            "processed_count": 30,
            "progress": 100
        }
    )

# Mock results endpoint
@app.get("/api/search/{search_id}/results")
async def get_search_results(search_id: str):
    return JSONResponse(
        status_code=200,
        content={
            "search_id": search_id,
            "contracts": [
                {
                    "id": 1001,
                    "reestr": "03732000004240001001",
                    "year": 2024,
                    "price": 420.50,
                    "match": "Идентичный",
                    "manufacturer": "SvetoCopy",
                    "manufacturer_match": True,
                    "ai_score": 95
                },
                {
                    "id": 1002,
                    "reestr": "03732000004240001002",
                    "year": 2023,
                    "price": 380.75,
                    "match": "Идентичный",
                    "manufacturer": "Xerox",
                    "manufacturer_match": False,
                    "ai_score": 88
                },
                {
                    "id": 1003,
                    "reestr": "03732000004240001003",
                    "year": 2024,
                    "price": 450.25,
                    "match": "Однородный",
                    "manufacturer": "SvetoCopy",
                    "manufacturer_match": True,
                    "ai_score": 76
                }
            ]
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)